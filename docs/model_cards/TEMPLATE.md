# Model card · <engine / model name>

Copy to `docs/model_cards/<model>.md` and fill in every section. Judges and IMD reviewers will ask these questions.

## Summary
- **Engine:** 1 / 2 / 3 / 4a / 4b
- **Task:** (e.g. P(24 h rain ≥ 115.6 mm) per 0.25° grid point, lead days 1–5)
- **Model:** (e.g. LightGBM binary + isotonic calibration)
- **Version / date / owner:**
- **Artifact:** `ml/models/...`

## Data
- **Inputs and sources:** (with product versions, e.g. GFS 0.25° via AWS, IMD 0.25° gridded)
- **Target / labels:** (definition, thresholds, known label noise)
- **Period and region:**
- **Train / validation / test split:** (years; confirm HINDCAST_YEAR excluded)
- **Latency assumptions at inference:**

## Performance (test year, with baselines)
| Metric | Lead / threshold | Model | Baseline | n events |
|--------|-----------------|-------|----------|----------|
| | | | | |

Include: reliability diagram (for probabilities) and at least one case-study map.

## Intended use
- Who uses the output and for what decision:
- Horizons and areas where it is valid:

## Limitations and failure modes
- (e.g. under-detects urban flooding; weak over orographic rain; trained on GFS v16 only)

## Ethical / safety notes
- Over-warning vs under-warning trade-off chosen and why
- Status of outputs (experimental, not an official IMD warning)

## Changelog
| Date | Change | Effect on scores |
|------|--------|------------------|
