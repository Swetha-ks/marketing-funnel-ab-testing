"""
End-to-end analysis: CSV -> SQLite -> SQL queries -> statistics -> charts -> report.

Run:  python src/analysis.py
"""
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
DATA, SQL, OUT, CH = ROOT / "data", ROOT / "sql", ROOT / "outputs", ROOT / "outputs" / "charts"
CH.mkdir(parents=True, exist_ok=True)
DB = DATA / "marketing.db"
plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "font.size": 10})
PAL = {"A": "#7f8c8d", "B": "#2e86de"}


# ------------------------------------------------------------------ load
def build_db() -> sqlite3.Connection:
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    for name in ["campaigns", "users", "funnel_events", "orders"]:
        pd.read_csv(DATA / f"{name}.csv").to_sql(name, con, index=False)
    con.executescript((SQL / "01_clean_views.sql").read_text())
    return con


def q(con, file):
    return pd.read_sql_query((SQL / file).read_text(), con)


# --------------------------------------------------------- data quality
def data_quality_report(con) -> pd.DataFrame:
    one = lambda s: con.execute(s).fetchone()[0]
    rows = [
        ("users", "raw rows", one("SELECT COUNT(*) FROM users")),
        ("users", "duplicate user_id rows", one("SELECT COUNT(*) - COUNT(DISTINCT user_id) FROM users")),
        ("users", "NULL device", one("SELECT COUNT(*) FROM users WHERE device IS NULL")),
        ("users", "city_tier = 'unknown'", one("SELECT COUNT(*) FROM users WHERE city_tier='unknown'")),
        ("users", "clean rows", one("SELECT COUNT(*) FROM clean_users")),
        ("orders", "raw rows", one("SELECT COUNT(*) FROM orders")),
        ("orders", "duplicate order_id rows", one("SELECT COUNT(*) - COUNT(DISTINCT order_id) FROM orders")),
        ("orders", "negative order value", one("SELECT COUNT(*) FROM orders WHERE order_value_inr <= 0")),
        ("orders", "outliers > 20,000 INR", one("SELECT COUNT(*) FROM orders WHERE order_value_inr > 20000")),
        ("orders", "clean rows", one("SELECT COUNT(*) FROM clean_orders")),
        ("funnel", "users with purchase but no checkout (logic error)",
         one("SELECT COUNT(*) FROM user_funnel WHERE purchased=1 AND checked_out=0")),
    ]
    return pd.DataFrame(rows, columns=["table", "check", "count"])


# ------------------------------------------------------------ A/B stats
def two_prop_test(x_a, n_a, x_b, n_b, alpha=0.05):
    p_a, p_b = x_a / n_a, x_b / n_b
    diff = p_b - p_a
    p_pool = (x_a + x_b) / (n_a + n_b)
    se_pool = np.sqrt(p_pool * (1 - p_pool) * (1 / n_a + 1 / n_b))
    z = diff / se_pool
    p_val = 2 * (1 - stats.norm.cdf(abs(z)))
    se_unpooled = np.sqrt(p_a * (1 - p_a) / n_a + p_b * (1 - p_b) / n_b)
    zc = stats.norm.ppf(1 - alpha / 2)
    return dict(p_a=p_a, p_b=p_b, diff=diff, rel_lift=diff / p_a, z=z, p_value=p_val,
                ci_low=diff - zc * se_unpooled, ci_high=diff + zc * se_unpooled)


def required_n_per_arm(p_base, mde_rel, alpha=0.05, power=0.80):
    p2 = p_base * (1 + mde_rel)
    za, zb = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(power)
    var = p_base * (1 - p_base) + p2 * (1 - p2)
    return int(np.ceil(((za + zb) ** 2 * var) / (p2 - p_base) ** 2))


def bootstrap_diff_ci(a, b, n_boot=4000, seed=7):
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        diffs[i] = rng.choice(b, len(b)).mean() - rng.choice(a, len(a)).mean()
    return np.percentile(diffs, [2.5, 97.5])


def run_ab_test(con):
    df = pd.read_sql_query("""
        SELECT f.user_id, f.ab_variant AS variant, f.device, f.checked_out, f.purchased,
               COALESCE(o.order_value_inr, 0) AS revenue
        FROM user_funnel f LEFT JOIN clean_orders o ON o.user_id = f.user_id""", con)
    a, b = df[df.variant == "A"], df[df.variant == "B"]
    res = {"n_a": len(a), "n_b": len(b)}

    # 1) Sample Ratio Mismatch: is the split really 50/50?
    chi2, p_srm = stats.chisquare([len(a), len(b)])
    res["srm_p"] = p_srm

    # 2) Primary metric: purchase conversion per visitor
    res["primary"] = two_prop_test(a.purchased.sum(), len(a), b.purchased.sum(), len(b))

    # 3) Step metric: checkout -> purchase (the stage the change actually touches)
    ca, cb = a[a.checked_out == 1], b[b.checked_out == 1]
    res["checkout"] = two_prop_test(ca.purchased.sum(), len(ca), cb.purchased.sum(), len(cb))
    res["n_chk_a"], res["n_chk_b"] = len(ca), len(cb)

    # 4) Guardrail: revenue per visitor (heavy-tailed -> Welch t + bootstrap CI)
    t, p_t = stats.ttest_ind(b.revenue, a.revenue, equal_var=False)
    lo, hi = bootstrap_diff_ci(a.revenue.values, b.revenue.values)
    res["rpv"] = dict(a=a.revenue.mean(), b=b.revenue.mean(), diff=b.revenue.mean() - a.revenue.mean(),
                      p_value=p_t, ci_low=lo, ci_high=hi)

    # 5) Segment check by device, Bonferroni-corrected (guards against false positives)
    seg_rows = []
    devices = [d for d in ["Mobile", "Desktop", "Tablet"] if d in df.device.unique()]
    for d in devices:
        sa, sb = a[a.device == d], b[b.device == d]
        r = two_prop_test(sa.purchased.sum(), len(sa), sb.purchased.sum(), len(sb))
        seg_rows.append(dict(device=d, n_a=len(sa), n_b=len(sb), conv_a=r["p_a"], conv_b=r["p_b"],
                             rel_lift=r["rel_lift"], p_value=r["p_value"],
                             p_bonferroni=min(1.0, r["p_value"] * len(devices)),
                             ci_low=r["ci_low"], ci_high=r["ci_high"]))
    res["segments"] = pd.DataFrame(seg_rows)

    # 6) Power: what lift could this sample reliably detect?
    base = res["primary"]["p_a"]
    res["mde_table"] = pd.DataFrame(
        [(m, required_n_per_arm(base, m)) for m in (0.05, 0.10, 0.15, 0.20)],
        columns=["relative_mde", "n_per_arm_needed"])
    return res


# --------------------------------------------------------------- charts
def chart_funnel(f):
    fig, ax = plt.subplots(figsize=(8, 4.2))
    colors = plt.cm.Blues(np.linspace(0.85, 0.35, len(f)))
    ax.barh(f.stage[::-1], f.users[::-1], color=colors[::-1])
    for i, (u, c, s) in enumerate(zip(f.users[::-1], f.cumulative_conv_pct[::-1], f.step_conv_pct[::-1])):
        label = f"{u:,}  ({c:.1f}% of visits)" + ("" if np.isnan(s) else f"  | step: {s:.1f}%")
        ax.text(u, i, " " + label, va="center", fontsize=9)
    ax.set_xlim(0, f.users.max() * 1.6)
    ax.set_title("Purchase funnel: where users drop off")
    ax.set_xlabel("Users")
    fig.tight_layout(); fig.savefig(CH / "01_funnel.png"); plt.close(fig)


def chart_channels(ch):
    d = ch[ch.spend > 0].sort_values("roas")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].barh(d.channel, d.roas, color="#2e86de")
    axes[0].axvline(1, color="red", ls="--", lw=1); axes[0].text(1.02, -0.45, "break-even", color="red", fontsize=8)
    axes[0].set_title("ROAS by paid channel (revenue / spend)")
    for i, v in enumerate(d.roas): axes[0].text(v, i, f" {v:.2f}x", va="center")
    d2 = ch[ch.spend > 0].sort_values("cac", ascending=False)
    axes[1].barh(d2.channel, d2.cac, color="#e67e22")
    axes[1].set_title("Customer acquisition cost (INR)")
    for i, v in enumerate(d2.cac): axes[1].text(v, i, f" ₹{v:,.0f}", va="center")
    fig.tight_layout(); fig.savefig(CH / "02_channel_roas_cac.png"); plt.close(fig)


def chart_trend(w):
    fig, ax = plt.subplots(figsize=(10, 4))
    x = pd.to_datetime(w.week_start)
    ax.plot(x, w.conv_pct, color="#bdc3c7", marker="o", ms=3, label="Weekly")
    ax.plot(x, w.conv_4wk_avg_pct, color="#2e86de", lw=2.4, label="4-week rolling avg")
    ax.set_title("Weekly visitor-to-purchase conversion (%)"); ax.legend(frameon=False)
    fig.tight_layout(); fig.savefig(CH / "03_weekly_conversion.png"); plt.close(fig)


def chart_device(dev):
    cols = ["view_rate_pct", "view_to_cart_pct", "cart_to_checkout_pct", "checkout_to_buy_pct"]
    labels = ["Visit→View", "View→Cart", "Cart→Checkout", "Checkout→Buy"]
    fig, ax = plt.subplots(figsize=(8, 3.2))
    im = ax.imshow(dev[cols].values, cmap="Blues", aspect="auto")
    ax.set_xticks(range(4), labels); ax.set_yticks(range(len(dev)), dev.device)
    for i in range(len(dev)):
        for j, c in enumerate(cols):
            ax.text(j, i, f"{dev[c].iloc[i]:.1f}%", ha="center", va="center",
                    color="white" if dev[c].iloc[i] > dev[cols].values.mean() else "black")
    ax.set_title("Step conversion by device"); ax.spines[:].set_visible(False)
    fig.tight_layout(); fig.savefig(CH / "04_device_funnel_heatmap.png"); plt.close(fig)


def chart_ab(res):
    seg = res["segments"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    p = res["primary"]
    ax = axes[0]
    ax.bar(["A (control)", "B (one-page checkout)"], [p["p_a"] * 100, p["p_b"] * 100],
           color=[PAL["A"], PAL["B"]])
    for i, v in enumerate([p["p_a"], p["p_b"]]): ax.text(i, v * 100, f"{v*100:.2f}%", ha="center", va="bottom")
    ax.set_title(f"Overall conversion  (lift {p['rel_lift']*100:+.1f}%, p {fmt_p(p['p_value'])})")
    ax.set_ylim(0, max(p["p_a"], p["p_b"]) * 100 * 1.25); ax.set_ylabel("%")
    ax = axes[1]
    y = np.arange(len(seg))
    ax.errorbar(seg.conv_b.sub(seg.conv_a) * 100, y,
                xerr=[(seg.conv_b - seg.conv_a - seg.ci_low) * 100, (seg.ci_high - (seg.conv_b - seg.conv_a)) * 100],
                fmt="o", color=PAL["B"], capsize=4)
    ax.axvline(0, color="black", lw=1)
    ax.set_yticks(y, seg.device); ax.set_xlabel("Conversion difference, B − A (percentage points, 95% CI)")
    ax.set_title("Effect by device")
    fig.tight_layout(); fig.savefig(CH / "05_ab_test_results.png"); plt.close(fig)


# --------------------------------------------------------------- report
def fmt_p(v):
    return "< 0.0001" if v < 0.0001 else f"= {v:.4f}"


def main():
    con = build_db()
    dq = data_quality_report(con); dq.to_csv(OUT / "data_quality_report.csv", index=False)
    funnel = q(con, "02_funnel_analysis.sql"); funnel.to_csv(OUT / "funnel.csv", index=False)
    chan = q(con, "03_channel_performance.sql"); chan.to_csv(OUT / "channel_performance.csv", index=False)
    dev = q(con, "04_segment_analysis.sql"); dev.to_csv(OUT / "device_funnel.csv", index=False)
    weekly = q(con, "05_weekly_trend.sql"); weekly.to_csv(OUT / "weekly_trend.csv", index=False)
    ab_sql = q(con, "06_ab_test_summary.sql")
    res = run_ab_test(con)
    res["segments"].to_csv(OUT / "ab_test_by_device.csv", index=False)
    res["mde_table"].to_csv(OUT / "ab_test_power.csv", index=False)

    chart_funnel(funnel); chart_channels(chan); chart_trend(weekly); chart_device(dev); chart_ab(res)

    p, c, r = res["primary"], res["checkout"], res["rpv"]
    paid = chan[chan.spend > 0]
    best, worst = paid.loc[paid.roas.idxmax()], paid.loc[paid.roas.idxmin()]
    seg = res["segments"].set_index("device")
    print("\n=== DATA QUALITY ===\n", dq.to_string(index=False))
    print("\n=== FUNNEL ===\n", funnel.to_string(index=False))
    print("\n=== CHANNELS ===\n", chan.to_string(index=False))
    print("\n=== DEVICE FUNNEL ===\n", dev.to_string(index=False))
    print("\n=== A/B SQL SUMMARY ===\n", ab_sql.to_string(index=False))
    print(f"\nSRM p-value: {res['srm_p']:.3f}  (n_A={res['n_a']:,}, n_B={res['n_b']:,})")
    print(f"PRIMARY  conv A={p['p_a']*100:.3f}% B={p['p_b']*100:.3f}%  diff={p['diff']*100:+.3f}pp "
          f"lift={p['rel_lift']*100:+.1f}% p={p['p_value']:.4f}  CI=[{p['ci_low']*100:+.3f},{p['ci_high']*100:+.3f}]pp")
    print(f"CHECKOUT->BUY A={c['p_a']*100:.2f}% B={c['p_b']*100:.2f}% lift={c['rel_lift']*100:+.1f}% p={c['p_value']:.4f}")
    print(f"RPV A=₹{r['a']:.2f} B=₹{r['b']:.2f} diff=₹{r['diff']:.2f} p={r['p_value']:.4f} "
          f"boot CI=[{r['ci_low']:.2f},{r['ci_high']:.2f}]")
    print("\n=== SEGMENTS ===\n", res["segments"].round(4).to_string(index=False))
    print("\n=== POWER ===\n", res["mde_table"].to_string(index=False))
    print(f"\nBest paid ROAS: {best.channel} {best.roas}x | Worst: {worst.channel} {worst.roas}x")

    # machine-written findings so README numbers can never drift from the data
    lines = [
        "# Auto-generated key findings", "",
        f"- Overall visit→purchase conversion: **{funnel.cumulative_conv_pct.iloc[-1]:.2f}%**",
        f"- Best paid channel by ROAS: **{best.channel} ({best.roas:.2f}x)**; weakest: **{worst.channel} ({worst.roas:.2f}x)**",
        f"- A/B test: conversion {p['p_a']*100:.2f}% → {p['p_b']*100:.2f}% "
        f"(relative lift {p['rel_lift']*100:+.1f}%, p {fmt_p(p['p_value'])}, "
        f"95% CI for difference [{p['ci_low']*100:+.2f}, {p['ci_high']*100:+.2f}] pp)",
        f"- Checkout→purchase: {c['p_a']*100:.1f}% → {c['p_b']*100:.1f}% (p {fmt_p(c['p_value'])})",
        f"- Revenue per visitor: ₹{r['a']:.1f} → ₹{r['b']:.1f} (Welch p {fmt_p(r['p_value'])})",
        f"- Sample-ratio-mismatch check p = {res['srm_p']:.3f} (healthy if > 0.01)",
    ]
    for d in seg.index:
        lines.append(f"- {d}: {seg.loc[d,'rel_lift']*100:+.1f}% lift, Bonferroni-adjusted p {fmt_p(seg.loc[d,'p_bonferroni'])}")
    (OUT / "key_findings.md").write_text("\n".join(lines) + "\n")
    con.close()
    DB.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
