# Readout — Account Attention Hub

Batch-derived attention hub that ranks Concourse accounts by renewal-weighted risk, human adoption, reliability, and call-note signals — so post-sales knows where to spend next week and next quarter.

**As-of 2026-06-30** (read off the newest real activity in the packet, not the wall clock)

53 canonical accounts · $108.3M ARR · 2 red, 15 amber, 36 green

The short version: the two largest things in this portfolio are not churn stories. A 92% usage collapse across five accounts on the same day is one upstream event, and six accounts reading as zero usage are an export gap, not dead logos. Together that is $23.6M of ARR that a normal dashboard would have pointed the team at in the wrong direction. Underneath it, the real pattern is coverage debt — CSM turnover, unanswered action items, and seat adoption stuck under 30% on a third of the book.

**Walk this in the room.** Open the hub: two banners sit above the list (the $12.4M cliff, the $11.2M export gap). The ranked list underneath is what remains after those two are handled — Kesler is #1. Click any row for the score factors, quotes, and stuck items. **Data trust** at the bottom is how the messy packet was handled. This document is the week/quarter judgment; the hub is the evidence.

---

## Next week (week of 2026-06-30)

Two of these are single escalations that cover $23.6M between them, and they should be settled before anyone opens an individual save play. The other four are account-level and genuinely urgent.

### 1. One escalation, not five save plays — $12.4M

Copperline Foods, Stanton Health Services, Sierra Restaurant Holdings, Summit Health Partners and Coastal Building Systems each lost ~92% of their run volume within a day of each other, around **2026-05-22**. Volume per account fell from roughly 75 runs/day to 6. The evidence says this is not five independent churn events:

- **91 of 96 users kept running afterwards.** The people did not leave — they each did about 8x less.
- **No error-rate spike** in any of the five (failure rates actually went slightly down in three).
- **All 12 agents still in use** after the drop, in all five accounts.
- It spans **four verticals and two owners**, and none of their call notes name a cause.
- **Portfolio-wide volume is flat** across the same week, so it is not a platform-wide outage either.

Five unrelated accounts do not cut usage 92% overnight on the same day. That signature — same users, same agents, no errors, one date — points upstream at a metering, export or quota change. **Ask what shipped around 2026-05-21/22 before anyone runs a churn play.** If it turns out to be real, it is still one coordinated event worth one escalation.

This is also why the hub holds these five out of the ranked list. Scored independently they land at ranks 2, 3, 9, 16 and 19, with the same event reading red for Stanton and green for Copperline — the largest of the five at $4.0M. That hands the reader two contradictory instructions off one screen. They are shown as one block with their combined $12.4M, and stay fully available in the drilldown.

### 2. One data ticket — $11.2M

Six accounts have no activity export at all: Keystone Building Products, Vanguard Foods, Pinnacle Insurance, Westgate Energy, Harborview Retail, Fairfield Foods. They score usage and reliability as **unknown, not zero**.

They are not dead. All six still have users logging in — 4.8 users per account in the last 30 days, against 5.5 for accounts that do have export files, with logins as recent as 2026-06-27. Logins come from seat provisioning, a different system than the activity export, so that is independent corroboration rather than a hedge. Four of the six have no call notes either, so notes could not have settled this; the login data could.

**Fix the export for these six account IDs.** Until then, do not let anyone read their blank usage as a churn signal.

### 3. Kesler Machine Works — $3.8M, renews 2026-09-08

Top of the ranked list at 66/100, and the only red tier outside the cliff cohort. Every factor is bad at once: **3 of 29 licensed seats active (10%)**, only 15 runs in 30 days, a **20% failure rate** on those runs, and the rollout is explicitly blocked — *"waiting on the internal security review before more users can be provisioned."* It has also had **3 different CSMs across its last 3 meetings**. Renewal is 70 days out, which means the recovery work has to start now, not in August.

### 4. Harwell Insurance Group — $390K, renews 2026-07-09 (9 days)

Smallest ARR on this list and the most time-critical. Usage is genuinely healthy — 748 runs, up 16.5%, 67% seat adoption — so this is not a product problem. It is a relationship problem: **4 different CSMs across the last 4 meetings**, the last meeting attended by *"just their admin + us"* (the economic buyer stopped showing up), a security questionnaire that has been open **361 days**, and an expansion pricing question open **283 days**. Someone senior should own the renewal conversation this week and close both stale items.

### 5. Cascade Building Products — $1.07M, renews 2026-08-01 (32 days)

**Usage down 24%** (603 runs vs 796 the prior 30 days) heading into a renewal a month out, and the account has **one call note in its entire history**, 134 days ago, against a promised weekly cadence. Thin coverage plus declining usage plus a near renewal — this one needs a real conversation before the paperwork.

### 6. Stanton Health Services — $3.9M, renews 2026-07-20 (20 days)

Held out of the ranking as part of the cliff cohort, but flagged here anyway because **the renewal happens in 20 days regardless of what caused the drop**. Last call note was 182 days ago. Book the renewal conversation now, but do not lead with the usage number until item 1 comes back — if it is a metering artifact, presenting it as a usage problem damages credibility.

---

## Next quarter (Q3 2026)

### The renewal book is small but the relationships underneath it are not

Seven accounts renew inside 90 days for **$12.27M**:

| Renewal | Account | ARR | Tier | Note |
|---|---|---|---|---|
| 2026-07-09 | Harwell Insurance Group | $390K | amber | 4 CSMs, buyer disengaged |
| 2026-07-20 | Stanton Health Services | $3.89M | red | in cliff cohort |
| 2026-08-01 | Cascade Building Products | $1.07M | amber | usage −24% |
| 2026-08-20 | Halvorsen Tool & Die | $1.41M | green | 5,369 runs — healthy, but 2 items open ~322 days |
| 2026-09-03 | Marlowe Retail Co | $835K | amber | 24% seat adoption, 3 items open 184–445 days |
| 2026-09-08 | Kesler Machine Works | $3.84M | red | see above |
| 2026-09-10 | Prairie Gold Ag | $845K | amber | seasonal, but worst relationship score in the portfolio |

Only two are red. But **five of the seven carry relationship damage** — CSM turnover, seniority drift, or action items open for the better part of a year — which is exactly the kind of risk that does not show up in usage graphs until the renewal is already lost. The following quarter holds 11 more accounts and $19.7M, so the pipeline of renewal work gets heavier, not lighter.

Prairie Gold Ag deserves a specific note: its usage is up 460% (874 runs vs 156) because the ag cycle turned, exactly as its notes predicted. Its 15/15 relationship score — 4 CSMs in 4 meetings, no contact in 160 days, three action items open 127–205 days — is the entire risk. Do not read it as a usage save.

### Seat adoption is the largest structural gap in the book

**16 accounts, $39M ARR — over a third of the portfolio — have under 30% of licensed seats active.** Portfolio median is 54%. The worst cases are large: Foxhill Steel 7 of 35 seats ($4.0M), Kesler 3 of 29 ($3.8M), Vermillion Chemical 6 of 39 ($3.8M), Delmar Restaurant Brands 16 of 76 ($3.7M), Copper Kettle Franchising 7 of 58 ($1.9M).

This is the quarter's biggest lever and it cuts both ways. These accounts are paying for seats they are not using, which is a renewal argument against us at every one of those renewals. It is also the only expansion story in the data that survives contact with the notes: the phrase "expansion pricing" is boilerplate (it appears across the book), so the hub does not tag it as interest. The real expansion is unused licenses already sold — fill those seats and the expansion conversation is a follow-on, not a hunt.

### One shared blocker gates $13.4M of that adoption

Four accounts name an internal security review as the reason more users cannot be provisioned: **Kesler ($3.8M), Foxhill ($4.0M), Redstone Chemicals ($1.7M), Vermillion ($3.8M)** — $13.35M combined. All four also sit in the low-adoption group above (10–36% of seats) with light usage. The same blocker appears as a *stuck action item* on four more accounts: Harwell (361 days), Halvorsen (322 days), Marlowe (189 days), Prairie Gold (179 days).

Eight accounts, one problem. This is a productizable fix — a standard security questionnaire response, SSO documentation package, and an owner for it — rather than eight separate CSM conversations. It is the highest-leverage quarter-scale project in the data.

### Coverage debt is portfolio-wide, not account-specific

The post-sales process doc promises every live account a weekly meeting. Against that baseline:

- **27 of 53 accounts ($46.6M)** saw 3 or more different CSMs across their last 4 meetings.
- **17 accounts ($36.2M)** have had no contact for far longer than a week — Vermillion at 365 days, Guardian Insurance at 434.
- **22 accounts ($36.3M)** have the same action item recurring across 3+ meetings, meaning nobody closed it.
- **15 accounts ($26.6M)** show attendee seniority drift, where the last meeting was attended by more junior people than earlier ones.

These are counts of a staffing and process problem, not 27 individual account problems. Whatever is causing CSM rotation is generating more risk than any single account on the week list.

### Two smaller quarter items

**Onboarding (4 accounts):** only **Titan Energy Co ($595K)** is genuinely stalled — 9 runs in 30 days, 29% of seats, and **no call notes at all**. Tidewater Freight Systems ($3.0M) has real volume (1,100 runs) but 20% seat adoption and 3 CSMs across 4 meetings, so it is an adoption case rather than a stall. Meadowbrook Ag and Gulfstream Power & Light are healthy.

**Automation vs. humans (4 accounts, $7.65M):** Delmar, Copper Kettle, Bergstrom Industrial and Emerald Manufacturing have usage dominated by service accounts. Their run counts look fine and their human adoption does not. Worth knowing before anyone cites their volume as health.

### Where not to spend attention

Three ag accounts ($7.5M) — Prairie Gold, Delta Ag Cooperative, Northwind Agriculture — have low usage explained by their slow season, which the hub down-weights. Bergstrom's ARR looks duplicated across two CRM rows and is deliberately counted once; its write-back expectations gap is flagged rather than scored as churn risk. Highland Utilities ($1.03M) has no renewal date in the CRM and is scored on usage and notes instead, flagged `missing_renewal` — worth one CRM fix, not a save play.

---

## Design process and how the app is configured

### What I chose to build, and what I refused to build

The brief asked where to spend attention, so I built an **attention triage tool**, not a metrics dashboard. The difference matters: a dashboard shows you numbers and leaves the judgment to you, and with 53 accounts and four messy data sources that just relocates the problem. Everything in the hub earns its place by changing what someone does on Monday morning.

That produced four design decisions worth defending.

**A ranked list is the product, and its scores are fully visible.** One list, sorted by an attention score out of 100, made of six additive factors: renewal urgency (≤25), usage health (≤25), reliability (≤15), seat adoption (≤15), relationship health (≤15), onboarding stage (≤5). Every account exposes its per-factor points, the observation behind each one, and a "Score drivers" column naming the top three. Nothing is a black box, which means a CSM who disagrees with a rank can see exactly which factor to argue with. Weights are one dict in `ingest.py` and are printed in the UI.

**Cross-account findings sit above the ranking.** A ranked list can only show one row at a time, and the two biggest stories in this data are only visible reading the portfolio sideways. `build_findings()` detects them on every refresh — so they update with new data rather than being written down once in a slide — and the app renders them above the table. The shared-cliff cohort is then *held out* of the ranking, because a finding that says "treat this as one thing" next to a list that says "work five accounts at five different priorities" gives the reader contradictory instructions. A checkbox re-ranks them inline for auditing. Only a **systemic** verdict earns the hold-out; a cluster with mixed signals (users gone, or errors spiking) stays in the list, because then it probably is churn.

**Unknown is not zero.** The six accounts with no activity export would rank near the top of any naive scoring, because zero usage looks like total abandonment. They score usage and reliability as unknown, are marked `no activity` in the table, carry a warning in the drilldown, and have seat adoption capped because login-only data understates real activity. Getting this wrong is worse than a missing feature — it points the team at six healthy accounts.

**Note metadata beats note keywords.** The call notes are mostly template text. One boilerplate line ("They asked about SSO rollout…") appears in 52 of 170 files, and naive keyword matching fired on 32 of 53 accounts — a signal that finds 60% of your portfolio is not a signal. Two defenses: any line appearing for more than 10% of accounts is treated as boilerplate and dropped from tags, quotes and action items; and the relationship-health factor scores note *metadata* instead of prose — cadence gap against the promised weekly meeting, distinct CSMs across the last 4 meetings, attendee seniority drift, and action items recurring across 3+ notes. Metadata is comparable across accounts and cannot be faked by a template.

### Architecture

Two stages, deliberately decoupled:

```
candidate_packet/  --[ ingest.py ]-->  data/accounts.json  --[ app.py ]-->  Streamlit UI
```

`ingest.py` does all the reading, merging, scoring and finding-detection, and writes one JSON file containing every canonical account record plus a `meta` block (as-of date, merge rules, file counts, unmatched files, score weights, findings). `app.py` is a pure reader over that JSON. Nothing is computed in the UI layer, so the ranked list, the drilldown and the data-trust panel cannot disagree with each other, and the whole pipeline is testable without a browser. Dependencies are `pandas` and `streamlit` — nothing else.

### Configuration

All judgment calls are named constants at the top of `ingest.py`, not values buried in logic:

| Knob | Value | What it controls |
|---|---|---|
| `MERGE_GROUPS` | 3 groups | Which CRM rows are the same company, and the ARR policy per group |
| `BOILERPLATE_ACCOUNT_SHARE` | 0.10 | A note line seen on >10% of accounts is template text |
| `PROMISED_CADENCE_DAYS` | 7 | The weekly meeting the post-sales doc promises, used as the cadence baseline |
| `CSM_LOOKBACK_NOTES` | 4 | How many recent meetings define "CSM turnover" |
| `STUCK_AI_MIN_NOTES` | 3 | How many repeats make an action item "stuck" |
| `CLIFF_MIN_DROP_PCT` / `CLIFF_STEP_WINDOW_DAYS` | 70% / 7d | Cliff detection: the week after must fall ≥70% against the week before **and** stay down |
| `AS_OF_MIN_DAY_SHARE` | 0.2 | A day needs ≥20% of median volume to count as the real end of the data |
| `WINDOW_DAYS` | 30 | The usage comparison window |
| score weights | 25/25/15/15/15/5 | Renewal, usage, reliability, adoption, relationship, stage |

**Identity is hardcoded; amounts never are.** The three merge groups name which account IDs are the same company, because entity resolution UI was not worth a day. But the ARR is always computed from the CRM rows: equal ARR across a merged pair means one duplicated contract (count once), unequal means split remnants (sum). Bergstrom is the documented exception — ARR is taken once from the canonical `ACC-1000` row and the account is flagged `writeback_fiction`.

**Cliff detection is a step test, not a slope test.** Comparing period averages fires early and also catches gradual decliners, which are a different problem needing a different play. Requiring a sharp step that *stays down* is what makes the five-account cluster resolve to a single date instead of five nearby ones.

**The as-of date comes from the data.** A dump loaded three days late would otherwise push every run outside the 30-day window and read as a portfolio-wide collapse. One wrinkle: the strict maximum timestamp is the wrong answer. Files named `..._2026-06-30.csv` carry 28 rows past midnight UTC — evening activity in western timezones — so the raw max reads 2026-07-01, a date the filenames disagree with. `derive_as_of()` takes the last day carrying real volume (≥20% of median daily count), lands on 2026-06-30, and reports the ignored tail in the header and under **Data trust**.

### Messy-data handling

The pipeline ingested **47 activity files across 4 schema variants** (CSV, TSV and JSONL; `email`/`user_email`, `ts`/`timestamp`/`run_timestamp`, `duration_sec`/`duration_ms`, and a status vocabulary normalized to success/fail/partial/unknown) and **170 call-note files across 48 account folders**, with zero parse failures. Files are matched to accounts by ACC-id in the filename, then slug, then name with corporate suffixes stripped, then email domain from seat provisioning. Two files matched nothing — `wexfordplastics.csv` and `ironbridgefreight.csv` — and are **kept and flagged `no_crm_match`** rather than dropped, because an activity file with no CRM row is itself a finding. Service accounts (`svc-*` or role `Service Account`) are excluded from human adoption and feed the `bot_heavy` flag instead. An active user is the **union** of `last_login ≤30d` and appearing in activity ≤30d, so neither system alone can make an account look dead. Everything above is visible in the **Data trust** panel in the app.

### Daily refresh and rebuild

The hub is not a one-time snapshot. The header takes either a nightly **packet ZIP** (`crm_export.csv`, `activity_exports/`, `seat_provisioning.json`, `call_notes/`) or a pre-built **accounts.json**; the ZIP path re-runs the full ingest in-process and replaces `data/accounts.json`. As-of defaults to the value derived from the uploaded data and can be overridden. Findings, scores and tiers all recompute, so the cliff and export-gap analyses are live checks rather than written-down conclusions.

Locally: `python ingest.py` then `streamlit run app.py`. Hosted on Streamlit Community Cloud with `app.py` as the entry point.

---

## Cut list

| Cut | Why |
|---|---|
| Separate "week" and "quarter" ranking tabs | Two rankings means two disagreeing sources of truth. One ranked list, and the week/quarter judgment lives in this readout where it can be argued with. |
| LLM note summarization | The notes are 90% template. An LLM would fluently summarize boilerplate. Metadata scoring was cheaper and more honest. |
| Full-text note search | Answers "what did we say" — the wrong question. The tool answers "who needs attention". |
| ML churn model | 53 accounts and no labeled churn outcomes. Any model would be a black box fitted to noise, and the transparent additive score is arguable, which is the point. |
| Entity-resolution UI | Three known merges, hardcoded and documented in ~10 lines. A fuzzy-match review UI would have eaten hours and resolved the same three pairs. |
| Live CRM sync / write-back | Batch-only was a stated constraint, and write-back is exactly the expectations gap flagged on Bergstrom. |
| Auth, SSO, multi-user permissions | Internal tool, synthetic data, one-day build. |
| Owner workload strip, vertical filter | Owner and stage filters cover the real filtering need. The workload question is interesting but not what the brief asked. |
| Charts and visual polish | Numbers with their derivation shown beat sparklines. Effort went into being right about the cliff and the export gap instead. |
| Diff vs. prior night's dump | The most valuable cut item. Would turn the hub from "who is at risk" into "what changed since yesterday" — the natural v2. |
