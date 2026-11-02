"""
Generate a realistic, seeded, synthetic e-commerce marketing dataset.

Why synthetic? Real marketing/funnel data is private. This dataset mimics a
real D2C brand: paid + organic acquisition, a 5-stage purchase funnel, an A/B
test on the checkout page, plus deliberately messy records (duplicates, nulls,
impossible values) so the cleaning step in the analysis is meaningful.

Run:  python src/generate_data.py
"""
from pathlib import Path
import numpy as np
import pandas as pd

SEED = 42
rng = np.random.default_rng(SEED)
DATA = Path(__file__).resolve().parents[1] / "data"
DATA.mkdir(exist_ok=True)

START, END = pd.Timestamp("2026-01-01"), pd.Timestamp("2026-06-30")
N_USERS = 60_000

# ---------------------------------------------------------------- campaigns
channels = {
    #  channel         monthly spend (INR), traffic weight, base funnel quality
    "Google Ads":   (160_000, 0.24, 1.00),
    "Meta Ads":     (230_000, 0.26, 0.82),
    "Influencer":   ( 90_000, 0.08, 0.95),
    "Affiliate":    ( 40_000, 0.07, 0.88),
    "Email":        ( 40_000, 0.10, 1.35),
    "Organic":      (      0, 0.25, 1.15),
}
camp_rows, cid = [], 1
for ch, (monthly, _, _) in channels.items():
    for m in range(1, 7):
        s = pd.Timestamp(2026, m, 1)
        e = s + pd.offsets.MonthEnd(0)
        spend = monthly * rng.uniform(0.9, 1.15) if monthly else 0.0
        camp_rows.append((cid, ch, f"{ch.replace(' ', '')}_{s:%b}_2026", s, e, round(spend, 2)))
        cid += 1
campaigns = pd.DataFrame(camp_rows, columns=[
    "campaign_id", "channel", "campaign_name", "start_date", "end_date", "spend_inr"])

# -------------------------------------------------------------------- users
ch_names = list(channels)
ch_w = np.array([channels[c][1] for c in ch_names]); ch_w /= ch_w.sum()
user_ch = rng.choice(ch_names, N_USERS, p=ch_w)

# mild upward growth in traffic over the 6 months + weekend bump
days = pd.date_range(START, END)
day_w = np.linspace(0.85, 1.25, len(days)) * np.where(days.dayofweek >= 5, 1.15, 1.0)
day_w = day_w / day_w.sum()
visit_day = rng.choice(days, N_USERS, p=day_w)

device = rng.choice(["Mobile", "Desktop", "Tablet"], N_USERS, p=[0.68, 0.27, 0.05])
city_tier = rng.choice(["Tier 1", "Tier 2", "Tier 3"], N_USERS, p=[0.42, 0.38, 0.20])
variant = rng.choice(["A", "B"], N_USERS)          # 50/50 randomised checkout test

camp_lookup = {(r.channel, r.start_date.month): r.campaign_id for r in campaigns.itertuples()}
camp_id = [camp_lookup[(c, pd.Timestamp(d).month)] for c, d in zip(user_ch, visit_day)]

users = pd.DataFrame({
    "user_id": np.arange(1, N_USERS + 1),
    "campaign_id": camp_id,
    "first_visit_date": pd.to_datetime(visit_day),
    "device": device,
    "city_tier": city_tier,
    "ab_variant": variant,
})

# --------------------------------------------------------------- the funnel
# stage 1 visit -> 2 product_view -> 3 add_to_cart -> 4 checkout -> 5 purchase
quality = np.array([channels[c][2] for c in user_ch])
dev_mult = pd.Series(device).map({"Mobile": 0.92, "Desktop": 1.15, "Tablet": 1.00}).values
tier_mult = pd.Series(city_tier).map({"Tier 1": 1.08, "Tier 2": 1.0, "Tier 3": 0.90}).values
q = quality * dev_mult * tier_mult

p_view = np.clip(0.72 * q ** 0.35, 0, 0.97)
p_cart = np.clip(0.34 * q ** 0.8, 0, 0.9)
p_chk  = np.clip(0.58 * q ** 0.5, 0, 0.95)
# The A/B test: new one-page checkout (B) improves checkout -> purchase.
# True effect is heterogeneous: strong on mobile, ~none on desktop.
base_buy = np.clip(0.50 * q ** 0.5, 0, 0.95)
lift = np.where(variant == "B",
                np.where(device == "Mobile", 1.17, np.where(device == "Desktop", 1.01, 1.08)), 1.0)
p_buy = np.clip(base_buy * lift, 0, 0.98)

u = rng.random((N_USERS, 4))
view = u[:, 0] < p_view
cart = view & (u[:, 1] < p_cart)
chk = cart & (u[:, 2] < p_chk)
buy = chk & (u[:, 3] < p_buy)

ev = []
stage_names = ["visit", "product_view", "add_to_cart", "checkout", "purchase"]
reached = [np.ones(N_USERS, bool), view, cart, chk, buy]
for i, (name, mask) in enumerate(zip(stage_names, reached), start=1):
    idx = np.where(mask)[0]
    offs = pd.to_timedelta(rng.integers(0, 3600 * (i * 2), len(idx)), unit="s")
    ts = users.loc[idx, "first_visit_date"].values + offs.values
    ev.append(pd.DataFrame({"user_id": users.loc[idx, "user_id"].values,
                            "stage": name, "stage_order": i, "event_ts": ts}))
events = pd.concat(ev, ignore_index=True)

# ------------------------------------------------------------------- orders
buyers = users.loc[buy].copy()
aov_base = {"Google Ads": 1650, "Meta Ads": 1380, "Influencer": 1900,
            "Affiliate": 1250, "Email": 1750, "Organic": 1600}
camp_to_ch = dict(zip(campaigns.campaign_id, campaigns.channel))
mu = np.log(buyers["campaign_id"].map(camp_to_ch).map(aov_base).values.astype(float))
order_value = np.round(rng.lognormal(mu, 0.45), 2)
orders = pd.DataFrame({
    "order_id": np.arange(100001, 100001 + len(buyers)),
    "user_id": buyers["user_id"].values,
    "order_date": buyers["first_visit_date"].values
                  + pd.to_timedelta(rng.integers(0, 3, len(buyers)), unit="D").values,
    "order_value_inr": order_value,
})

# ------------------------------------- inject realistic data-quality issues
dup_users = users.sample(250, random_state=1)
users_dirty = pd.concat([users, dup_users], ignore_index=True)                   # duplicate users
users_dirty.loc[users_dirty.sample(400, random_state=2).index, "device"] = None  # missing device
users_dirty.loc[users_dirty.sample(150, random_state=3).index, "city_tier"] = "unknown"

orders_dirty = pd.concat([orders, orders.sample(120, random_state=4)], ignore_index=True)  # duplicate orders
bad = orders_dirty.sample(40, random_state=5).index
orders_dirty.loc[bad, "order_value_inr"] = -orders_dirty.loc[bad, "order_value_inr"]       # negative values
out = orders_dirty.sample(15, random_state=6).index
orders_dirty.loc[out, "order_value_inr"] = orders_dirty.loc[out, "order_value_inr"] * 40   # extreme outliers

campaigns.to_csv(DATA / "campaigns.csv", index=False)
users_dirty.to_csv(DATA / "users.csv", index=False)
events.to_csv(DATA / "funnel_events.csv", index=False)
orders_dirty.to_csv(DATA / "orders.csv", index=False)

print(f"campaigns: {len(campaigns):,} | users: {len(users_dirty):,} | "
      f"events: {len(events):,} | orders: {len(orders_dirty):,}")
