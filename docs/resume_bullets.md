# Resume & interview material

## Project title (resume)
**Marketing Funnel & A/B Test Analytics** | Python, SQL, SciPy, Matplotlib | [GitHub link]

## Bullets (pick 3)
- Analysed a 60K-visitor, 5-stage purchase funnel with SQL window functions and CTEs, identifying a 46% checkout drop-off and a 3-point conversion gap between mobile and desktop.
- Evaluated channel profitability (CAC, ROAS, AOV) and found Email returned 7.5x ROAS versus 0.80x for Meta Ads, supporting a budget reallocation recommendation.
- Designed and analysed a checkout A/B test (sample-ratio check, two-proportion z-test, bootstrap CI, Bonferroni-corrected segments); the new design lifted conversion 7.36% → 8.74% (+18.8%, p < 0.0001) with revenue per visitor up ₹25.
- Built a reproducible cleaning pipeline (SQL views) that resolved duplicates, nulls, negative values and outliers across 60K users and 5K orders.

## Likely interview questions
1. **Why a z-test for conversion but a bootstrap for revenue?** Conversion is binary, so the normal approximation to proportions is appropriate at this sample size. Revenue is heavy-tailed, so a bootstrap CI makes fewer assumptions.
2. **Why Bonferroni on the device split?** Slicing results by segment multiplies the chance of a false positive. Desktop looked significant on its own (p = 0.03) but not after correcting (p = 0.09).
3. **What is a sample ratio mismatch?** If a 50/50 split shows a significantly different ratio, randomisation or logging is broken and results can't be trusted. Here p = 0.78, so it's healthy.
4. **What is the main weakness of the ROAS numbers?** They use first-order revenue only and ignore repeat purchases and lifetime value.
5. **Would you ship it?** Yes for mobile; for desktop I would collect more data first. The power table shows how many users are needed.
