# 08 · Alerts and the Common Alerting Protocol

## Why CAP
CAP 1.2 (OASIS) is the XML standard that India's NDMA uses on its **SACHET** platform to push alerts to SMS,
TV, radio and apps. If Jalproloi emits valid CAP, its warnings could in principle plug straight into the national
dissemination chain. That is a strong point for IMD/MoES judges.

Generator: `backend/app/alerts/cap.py` · Endpoint: `GET /api/alerts/{id}/cap`

## Mapping

| Jalproloi | CAP field | Value |
|-----------|-----------|-------|
| colour Red / Orange / Yellow / Green | `severity` | Extreme / Severe / Moderate / Minor |
| same | `responseType` | Evacuate / Prepare / Monitor / None |
| onset − sent ≤ 1 h / ≤ 24 h / later | `urgency` | Immediate / Expected / Future |
| probability > 0.5 / ≥ 0.1 / lower | `certainty` | Likely / Possible / Unlikely |
| area polygon (lat,lon pairs, closed) | `area/polygon` | from the area geometry |
| LGD district code | `area/geocode` | `valueName=LGD_district` |
| demo / hindcast | `status` | **Exercise** (never `Actual` in a demo) |
| colour, level word, probability | `parameter` | extra machine-readable values |

Validate the XML with a public CAP validator before the demo, and show a validated alert on a slide.

## Alert logic (run after every fusion)

1. For each area (district, then locality), compute the colour for 6 h and 24 h.
2. **Raise immediately** on an upgrade (e.g. Yellow → Orange): send `msgType=Alert`, or `Update` referencing the previous one.
3. **Downgrade only after two consecutive runs agree.** This prevents flapping, which destroys trust.
4. **Cancel** (`msgType=Cancel`) when a run drops to Green and the previous alert has not expired.
5. Never re-send an identical alert. Deduplicate on `(area, colour, onset window)`.
6. Store every alert with its CAP XML in the `alerts` table (audit trail).

## Channels

| Channel | Status | Notes |
|---------|--------|-------|
| In-app banner | done | reads `/api/risk/area` headline |
| Telegram bot | `send_telegram` ready | users `/start` the bot; store `chat_id` in `saved_places.contact` |
| Web push | TODO | `pywebpush` + VAPID keys; `frontend/public/sw.js` already handles `push` |
| SMS | TODO | Indian SMS needs DLT registration of sender ID and templates (TRAI). Skip for the hackathon unless you have a provider. |
| CAP feed | done (per alert) | add an Atom/RSS index of active CAP files for aggregators |

Saved places: after each run, look up each place's `h3` in `cell_forecasts`. Notify when its colour is higher than
`last_color_sent`, then update that column.

## Message style
- Lead with the word and the place: **"PREPARE · Anil Nagar: very heavy rain likely tonight; waterlogging expected."**
- One action: "Avoid low-lying roads; keep medicines and documents ready."
- Helplines: 1070 (state), 1077 (district), 112.
- Assamese, Bengali and Hindi templates must be written or reviewed by native speakers. Machine translation of warnings is risky.

## Done when
- [ ] CAP XML validates
- [ ] Upgrade/downgrade/cancel logic unit-tested with synthetic sequences
- [ ] Telegram message received for a saved place during a hindcast replay (status Exercise)
