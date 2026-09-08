# Account Attention Hub — 1-pager notes

As-of **2026-06-30** · 53 accounts · $108.3M ARR · 2 red / 15 amber / 36 green
Full argument: [READOUT.md](READOUT.md)

---

## Design process & architecture

Built an **attention triage tool**, not a dashboard. The brief is “where should the team spend next week and next quarter?” — a metrics dump relocates that problem. One ranked list, with week/quarter judgment in this readout.

**Four decisions**
- **Transparent score (0–100).** Six additive factors, weights in one dict and on screen: renewal 25 · usage 25 · reliability 15 · adoption 15 · relationship 15 · stage 5. Every row shows per-factor points and the observation behind them.
- **Cross-account findings sit above the list.** A ranked list can only show one row at a time. `build_findings()` detects portfolio-level events on every refresh. A systemic cliff is *held out* of the ranking so the tool does not tell the reader to treat one event as five different priorities.
- **Unknown ≠ zero.** Missing activity is not scored as abandonment.
- **Note metadata over keywords.** One boilerplate line appears in 52 of 170 files; keyword matching fired on 32/53 accounts. Lines on >10% of accounts are dropped. Relationship score uses cadence, CSM turnover, seniority drift, and stuck action items — comparable, not fakeable by a template.

**Pipeline**

```
candidate_packet/  →  ingest.py  →  data/accounts.json  →  app.py (Streamlit)
```

`ingest.py` merges, scores, and detects findings. `app.py` is a pure reader — ranked list, drilldown, and Data trust cannot disagree. pandas + streamlit only.

**Config** — named constants at the top of `ingest.py`, not buried in logic.

| Knob | Value |
|---|---|
| Score weights | 25 / 25 / 15 / 15 / 15 / 5 |
| Cliff | ≥70% drop, 7-day step that *stays down* (not a slope) |
| Boilerplate | line seen on >10% of accounts |
| Cadence / CSM / stuck AI | 7-day promised meeting · last 4 notes · item on 3+ notes |
| As-of | last day with ≥20% of median volume (not raw max timestamp) |
| Merges | 3 hardcoded ID groups; ARR computed (equal → count once; unequal → sum). Bergstrom counted once, flagged `writeback_fiction`. |

**Messy data, handled.** 47 activity files, 4 schema variants, 170 notes, 0 parse failures. Match by ACC-id → slug → name → email domain. Two orphans kept and flagged (`wexfordplastics`, `ironbridgefreight`). Service accounts excluded from human adoption. Active user = login **or** activity in 30d. Refresh: upload a packet ZIP or `accounts.json`; findings recompute.

**Cut on purpose.** No second week/quarter ranking, no LLM on template notes, no ML churn model, no entity-resolution UI, no write-back.

---

## Key findings

The two largest things in the book are **not churn**. Together they are **$23.6M** a normal dashboard would have pointed at in the wrong direction. Underneath: coverage debt and unused seats.

### Next week — settle two events, then four accounts

1. **One escalation, not five save plays — $12.4M.** Copperline, Stanton, Sierra, Summit, Coastal each lost ~92% of volume around **2026-05-22**. 91 of 96 users kept running; no error spike; all 12 agents still in use; four verticals, two owners; portfolio volume flat. Ask what shipped 2026-05-21/22 before anyone runs a churn play. Held out of the ranked list for that reason.
2. **One data ticket — $11.2M.** Six accounts have no activity export (Keystone, Vanguard, Pinnacle, Westgate, Harborview, Fairfield) but still log in (4.8 users/account vs 5.5 with exports; latest login 2026-06-27). Fix the export. Do not read blank usage as dead.
3. **Kesler Machine Works — $3.8M, 66/100, only remaining red.** 3 of 29 seats active, 15 runs, 20% failure rate, blocked on security review, 3 CSMs in 3 meetings. Renews 2026-09-08 — start recovery now.
4. **Harwell Insurance — $390K, renews in 9 days.** Usage healthy (748 runs, +16.5%, 67% seats). Relationship is not: 4 CSMs, buyer gone (“just their admin + us”), security questionnaire 361 days, expansion pricing 283 days. Senior owner this week.
5. **Cascade Building — $1.07M, renews in 32 days.** Usage −24%; one note in its history, 134 days ago.
6. **Stanton Health — $3.9M, renews in 20 days.** In the cliff cohort. Book the renewal; do not lead with the usage number until item 1 comes back.

### Next quarter — relationships and seats, not usage graphs

- **Renewal book: 7 accounts, $12.27M.** Only two are red; **five of seven** carry CSM turnover, seniority drift, or year-old action items. Next 90 days: 11 more accounts, $19.7M. Prairie Gold usage is *up 460%* (season turned); its 15/15 relationship score is the risk — do not read it as a usage save.
- **Seat adoption is the lever.** 16 accounts / **$39M** have <30% of licensed seats active (median 54%). Foxhill 7/35, Kesler 3/29, Vermillion 6/39, Delmar 16/76, Copper Kettle 7/58. Paying for unused seats is a renewal argument against us; filling them is the real expansion story (“expansion pricing” in notes is boilerplate).
- **One security blocker gates $13.4M.** Kesler, Foxhill, Redstone, Vermillion named; same questionnaire stuck on Harwell, Halvorsen, Marlowe, Prairie Gold. Eight accounts, one package — not eight CSM conversations.
- **Coverage is a staffing problem.** 27/53 accounts ($46.6M) had 3+ CSMs in their last 4 meetings. 17 ($36.2M) have gone far past weekly cadence (Vermillion 365d, Guardian 434d). 22 ($36.3M) recycle the same action item. 15 ($26.6M) show seniority drift.

**Do not spend here.** Ag seasonality ($7.5M) is down-weighted. Bergstrom ARR counted once. Highland missing a renewal date is a CRM fix, not a save play. Titan ($595K) is the only stalled onboarding; four bot-heavy accounts look healthy on volume and are not on human adoption.
