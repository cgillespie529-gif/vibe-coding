# Account Attention Hub

Internal post-sales triage tool for the Concourse FDE take-home.

**As-of date:** `2026-06-30` (packet dump — not “today”)

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python ingest.py
streamlit run app.py
```

## Merge rules (identity hardcoded; amounts computed)

| Group | Canonical | ARR policy |
|---|---|---|
| Halvorsen Tool & Die + Halvorsen Industrial | Prefer Live / lower id | **auto:** equal ARR → count once (max); unequal → sum |
| Meridian Chemical + Meridian Specialty | Prefer lower id | **auto** (split remnants → sum) |
| Bergstrom ACC-1000 + ACC-2000 | `ACC-1000` | **once** from canonical row (do not sum); flag `writeback_fiction` |

## Call notes: metadata over keywords

Note prose is mostly template text — one boilerplate line ("They asked about SSO rollout…") appears in 52 of 170 files, so keyword matching fired on 32 of 53 accounts. Two defenses:

1. Any line appearing for more than 10% of accounts is treated as boilerplate and ignored for tags, quotes, and action items.
2. The **relationship health** factor scores note *metadata*, which is comparable across accounts and unfakeable by templates:
   - **Cadence gap** — days since last note vs the weekly meeting promised in the post-sales process doc
   - **CSM turnover** — distinct CSMs across the last 4 meetings (only scored with 3+ dated notes, so sparse accounts aren't penalized)
   - **Attendee seniority drift** — last meeting attended by more junior contacts than earlier ones (losing the economic buyer)
   - **Stuck action items** — the same item recurring across 3+ dated notes, scored by persistence rather than raw count

## Cross-account findings

A ranked list shows symptoms one row at a time. Two patterns in this data only appear when you read the portfolio sideways, so `build_findings()` detects them and the app shows them above the ranking. Both are computed on every refresh, so they update with new data rather than being written down once.

**One drop, five accounts.** Copperline, Stanton, Sierra, Summit and Coastal each lost ~92% of run volume within a day of each other, around 2026-05-22. The evidence says this is not five churn stories:

- 91 of 96 users kept running afterwards — the people did not leave, they each did ~8x less
- No error-rate spike in any of the five
- All 12 agents still in use after the drop
- It spans four verticals and two owners, and their notes name no cause
- Portfolio-wide volume is flat across the same week, so it is not a platform outage

Five unrelated accounts do not cut usage 92% overnight on the same day. That signature — same users, same agents, no errors, one date — points upstream, at a metering, export or quota change. Worth one escalation, not five save plays.

**So the cohort is held out of the ranked list.** Scoring them independently put them at ranks 2, 3, 9, 16 and 19, with the same event reading as red for Stanton and green for Copperline — which is the largest of the five at $3.98M. That gives the reader two contradictory instructions from one screen: the finding says treat it as one thing, the list says work five separate accounts at five different priorities. Instead the five are tagged `cliff_cohort`, shown as one block with their combined $12.4M, and the ranked list is what remains after the systemic issue is handled. A checkbox re-ranks them inline for auditing, and they stay fully available in the drilldown — out of the ranking, not out of the tool.

Only a **systemic** verdict earns the hold-out. A cluster with mixed signals — users gone, or errors spiking — stays in the ranked list, because then it probably is churn.

Detection is a step test, not a slope test (`detect_usage_cliff`): the 7 days after a candidate day must fall ≥70% against the 7 days before **and** stay down. Comparing period averages instead fires early and also catches gradual decliners, which are a different problem.

## Missing data is not bad news

Six accounts have no matching activity export. They score usage and reliability as **unknown**, not zero, are marked `no activity` in the table, and carry a warning in the drilldown. Seat adoption is capped for them because login-only data understates real activity.

These are not dead accounts, and there is evidence rather than a hedge. All six still have users logging in — 4.8 per account in the last 30 days, against 5.5 for accounts that do have export files, with logins as recent as three days before the as-of date. Logins come from seat provisioning, a different system than the activity export, so they are independent corroboration. Four of the six have no call notes at all, so notes could not settle this; the login data could.

Other policies:

- **Active user:** `last_login ≤30d` **OR** appeared in activity ≤30d (union)
- **Service accounts:** email `svc-*` or role `Service Account` excluded from human adoption; feed `bot_heavy`
- **Orphan activity:** kept with `no_crm_match` — not dropped
- **Missing renewal:** score on usage/notes; flag `missing_renewal`

## Daily refresh

In the app header, upload either:

1. **Packet ZIP** — nightly dump with `crm_export.csv`, `activity_exports/`, `seat_provisioning.json`, `call_notes/` (zip root or `candidate_packet/` folder). Set **As-of date**, then **Apply upload**. The hub re-ingests and replaces `data/accounts.json`.
2. **accounts.json** — pre-built output from `python ingest.py` (skips re-ingest).

The ranked list always reads the **latest applied upload** (or the bundled `data/accounts.json` until the first upload).

## Rebuild

`python ingest.py` reads `candidate_packet/` → writes `data/accounts.json` (+ meta).  
The Streamlit app reads that JSON by default, and replaces it when you upload.

## Deploy

Push to GitHub → Streamlit Community Cloud → main file `app.py`.
