# PRD: Post-Sales Account Attention Hub

**Concourse FDE Take-Home · 1-day build**

| | |
|---|---|
| **Product** | Account Attention Hub (internal post-sales tool) |
| **Owner** | Candidate (Caroline) |
| **Timebox** | 1 day |
| **As-of date** | 2026-06-30 (latest packet dump; not “today”) |
| **Data source** | `candidate_packet/` (synthetic nightly S3-style export) |
| **Constraint** | Batch only — no live DB / prod access |

---

## 1. Problem

Post-sales has ~50+ live logos and no shared view of who is healthy. CSMs/FDEs run off stale spreadsheets and tribal knowledge. Leadership cannot answer: *Where should the team spend attention next week and next quarter?*

Data exists (CRM, usage, seats, call notes) but is messy: inconsistent export schemas, duplicate accounts post-acquisition, service-account inflation, and mostly boilerplate notes with rare high-signal lines.

---

## 2. Goal

Ship a **hosted hub** that, on open, surfaces a defensible ranked list of accounts needing attention — with enough evidence to act — plus a short written readout.

**Success = judgment under ambiguity**, not feature completeness.

---

## 3. Non-goals (explicit cuts)

- Live sync, auth/SSO, multi-user permissions
- Writing back to CRM or ERP
- ML churn models / forecasting
- Full-text note search product or LLM summarizer (v1)
- Owner performance analytics, email digests, mobile
- Perfect entity-resolution UI (hardcode known merges)
- Polished design system / marketing chrome
- Separate week vs quarter ranking UIs / tabs (judgment lives in the readout)
- Vertical filter; owner workload strip

---

## 4. Users & jobs

| User | Job to be done |
|---|---|
| **Primary: Post-sales lead** (Marcus-type) | Open Monday → know top attention accounts for the week |
| **Secondary: CSM / FDE** | Click an account → see usage, seats, risks, open AIs before a sync |
| **Evaluator (hiring)** | See what you chose to build, how you handled mess, whether it runs |

---

## 5. Product thesis (one sentence)

An **attention triage tool** for enterprise finance accounts that merges messy batch exports into a ranked “where to spend time” view, with transparent evidence and data-quality honesty.

---

## 6. Scope — v1 (must ship)

### 6.1 Portfolio triage (home)

- Ranked table of **canonical** accounts
- Columns: Account, ARR, Stage, Owner, Renewal, Attention score, **Primary reason**, Risk tags
- Filters (P0): Owner, Stage (Live / Onboarding), At-risk only
- Portfolio summary: total ARR, ARR in top risk bucket, # onboarding, # renewing ≤90d

### 6.2 Account drilldown

- Identity: canonical name, merged IDs/names, vertical, owner, stage, contract/renewal
- Usage: runs last 30d / prior 30d, trend direction, error/fail rate
- Seats: licensed vs provisioned vs **human** active (exclude `svc-*` / Service Account roles); flag bot-heavy usage (`bot_heavy` boolean)
- Qualitative: allowlisted note signals + quotes + open action items (see note-extraction cap below)
- “Why this rank”: scored factors with weights

**Note extraction (cap):** Allowlisted patterns only — champion leaving, competitor, security/SSO stuck, write-back gap, seasonal/slow season, open action items. Cap ~3 tags and ~2 quotes per account. No full-text search, no LLM.

### 6.3 Week vs quarter framing (v1)

Single ranked list. Surface framing via risk tags (`renewal_soon`, `onboarding_stalled`, `champion_risk`, `expansion`, `seasonal_low`, etc.). Make the **next week vs next quarter** call in the written readout — not a second ranking system or separate tabs.

### 6.4 Data trust (small panel or README section)

- As-of date
- Merge rules applied
- # activity files ingested / schema variants handled
- Known gaps (e.g. missing renewal, unmatched files, orphan activity)

### 6.5 Written deliverables

1. Hosted URL
2. One-page readout (next week / next quarter / tools / why)
3. Cut list

---

## 7. Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| F1 | Ingest all activity exports without crashing | P0 |
| F2 | Map every activity file to an account_id (heuristics + fallbacks) | P0 |
| F3 | Normalize heterogeneous schemas (columns, status, timestamps, duration units, CSV/TSV/JSONL) | P0 |
| F4 | Merge known duplicate CRM entities; **do not double-count ARR** when duplicates are the same contract | P0 |
| F5 | Compute human vs service-account activity and seat utilization | P0 |
| F6 | Produce transparent attention score + primary reason | P0 |
| F7 | Ranked portfolio UI + account drilldown with evidence | P0 |
| F8 | Surface rare note signals via allowlist only (not boilerplate; no LLM) | P0 |
| F9 | Reproducible rebuild: one command from `candidate_packet/` | P0 |
| F10 | Hosted deployment accessible without local setup | P0 |
| F11 | Filter by owner / at-risk / stage | P1 |
| F12 | Owner workload strip or count of at-risk per owner | Cut |
| F13 | Vertical filter | Cut |
| F14 | LLM note summarization | Cut |
| F15 | Separate week vs quarter ranking UI | Cut |

---

## 8. Data requirements

### 8.1 Sources

| Source | Path | Use |
|---|---|---|
| CRM | `crm_export.csv` | Identity, ARR, renewal, owner, stage, seats licensed |
| Activity | `activity_exports/*` | Usage volume, errors, agents, recency |
| Seats | `seat_provisioning.json` | Provisioned users, last_login, roles |
| Notes | `call_notes/**` | Risk/opportunity tags, open AIs |
| Context | `internal_thread.txt` | Constraints + known data issues |

### 8.2 Known dirty-data rules (encode in product)

| Issue | Decision |
|---|---|
| Halvorsen Tool & Die + Halvorsen Industrial | Merge to one canonical account; ARR appears duplicated — count once |
| Meridian Chemical + Meridian Specialty | Merge; inspect both CRM rows once — if ARR looks duplicated (same-ballpark full contract), **take max**; if clearly split remnants, **sum**. Document choice in README/readout |
| Bergstrom ACC-1000 / ACC-2000 | Merge; **count ARR once**; union seats/activity; flag write-back-as-fiction (`data_flag` / note signal) |
| Highland Utilities empty renewal | Show “renewal unknown” + still score on usage/notes |
| `svc-automation@…` / role Service Account | Exclude from human adoption metrics; show separately as automation |
| Ag accounts with “slow season” notes | Down-weight low-usage churn signal |
| Activity status vocab | Map to success / fail / partial / unknown |
| Filename zoo | Resolve via ACC id, slug, fuzzy name, email domain |
| Activity with no CRM match | Keep; orphan / `no_crm_match` flag in data-trust — do not drop |

### 8.3 Canonical account record (target schema)

**Required (day-1):**

```text
account_id_canonical
account_name
merged_account_ids[]
merged_names[]
vertical, owner, stage
arr                     # post-merge, no double count
contract_start, renewal_date, days_to_renewal
licensed_seats
provisioned_seats
human_provisioned
human_active_30d        # union: last_login ≤30d OR activity ≤30d
seat_utilization        # human_active / licensed
runs_30d, runs_prior_30d, usage_delta_pct
error_rate_30d
bot_heavy               # boolean; svc-dominated usage
note_tags[]             # ≤~3; allowlisted
note_quotes[]           # ≤~2 short excerpts
open_action_items[]
attention_score
primary_reason
risk_tier               # e.g. red / amber / green
evidence_lines[]        # short human-readable factor strings
data_flags[]            # missing_renewal, merged_duplicate, no_activity_file, no_crm_match, writeback_fiction, ...
```

**Optional (compute if easy; not required to ship):**

```text
revenue_band
top_agents[]
automation_run_share    # svc runs / all runs (bot_heavy is enough for v1)
```

---

## 9. Attention score (v1 formula)

Keep weights visible in UI/readout. Tune lightly; perfection not required.

**Suggested components (0–100 total):**

| Factor | Pts | Logic |
|---|---|---|
| Renewal urgency | 0–25 | Closer renewal + higher ARR → higher |
| Usage health | 0–25 | Low human runs and/or sharp decline → higher (except seasonal tag) |
| Reliability | 0–15 | High error/fail rate → higher |
| Adoption / seats | 0–15 | Low human seat fill → higher; bot-only usage → higher |
| Qualitative risk | 0–15 | champion leaving, competitor, security stuck, stale blockers |
| Stage risk | 0–5 | Onboarding + weak usage → higher |
| **Expansion (negative risk / separate flag)** | — | Don’t bury in “trouble”; label as opportunity in readout / tags |

**Primary reason** = highest contributing factor label, e.g. `Renewal in 20d · $3.9M ARR`.

**Risk tier:** e.g. score ≥70 red, 40–69 amber, else green — tune after inspecting distribution.

---

## 10. UX requirements

- First screen must answer attention without narration
- Every score shows **why** (no black box)
- Evidence over decoration: numbers + note quotes
- Works on laptop browser; mobile optional
- Empty/missing data states explicit (“no activity file matched”)
- Visual style: internal ops tool — clear hierarchy, not marketing landing page

---

## 11. Tech requirements

| Area | Choice |
|---|---|
| Ingest | Python + pandas → `accounts.json` |
| App | Streamlit reading static JSON |
| Host | Streamlit Community Cloud (or Railway if Cloud blocked) |
| Repro | `python ingest.py` then `streamlit run app.py` |
| Repo | README with as-of, merges, how to run, link to readout |

**Hard requirement:** another engineer can regenerate and run from the packet.

---

## 12. Deliverables checklist

| # | Deliverable | Done when |
|---|---|---|
| 1 | Ingest pipeline | All activity files parse; merges applied |
| 2 | Hosted hub | URL works in private window |
| 3 | Portfolio + drilldown | Rank + evidence for all canonical accounts |
| 4 | Readout | Next week (5–8 accounts), next quarter (themes), tools explanation |
| 5 | Cut list | Written, intentional |
| 6 | README | Rebuild steps + decisions |

---

## 13. Acceptance criteria (evaluator lens)

1. **Right tool:** Clearly an attention/triage hub, not a generic metrics dump
2. **Real story:** Surfaces renewals, adoption, duplicates, bot inflation, note risks — not vanity charts
3. **All accounts:** Messy files don’t break the pipeline; gaps flagged
4. **Runnable:** Hosted + documented rebuild
5. **Judgment:** Readout makes a call on next week vs quarter

---

## 14. Out-of-scope backlog (if extra time)

- Separate week vs quarter ranking tabs/views
- Vertical filter
- Owner capacity / workload strip
- Stale AI action-item board
- Competitor watchlist page
- Diff vs prior night’s dump
- Export “Monday brief” markdown from ranked list
- `top_agents[]` / `automation_run_share` detail beyond `bot_heavy`

---

## 15. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Ingest eats the day | Cap schema handling; fail soft + flag file |
| Double-counted ARR | Unit-test merge totals vs CRM sum of canonicals |
| Boilerplate notes drown signal | Allowlist rare phrases / tag patterns only; cap tags/quotes |
| UI yak-shave | Streamlit table first; polish last |
| Wrong as-of date | Freeze 2026-06-30 in UI header |

---

## 16. Milestone plan (1 day)

| Block | Focus | Exit criteria |
|---|---|---|
| 0–0.5h | Lock merges + ARR rules in README draft | Decisions frozen |
| 0.5–3.5h | Ingest + score → `accounts.json` | All canonical accounts + flags |
| 3.5–6.5h | Streamlit ranked list + drilldown | Score + why + evidence |
| 6.5–7.5h | Host + README | Public URL |
| 7.5–9h | Readout (week/quarter judgment) + cut list | Submission-ready |

---

## 17. Locked decisions (document in README/readout)

1. **Meridian:** Inspect both CRM rows once at ingest. If ARR looks duplicated (same-ballpark full contract), **take max**; if clearly split remnants, **sum**. Document the choice.
2. **Bergstrom ACC-1000 / ACC-2000:** Merge; **count ARR once**; union seats/activity; surface write-back-as-fiction as a `data_flag` / note signal.
3. **Orphan activity:** Keep; show in data-trust / `no_crm_match` — do not drop.
4. **Active user:** **Union** of `last_login ≤30d` OR appeared in activity ≤30d.

---

## 18. One-line pitch for the readout header

> “Batch-derived attention hub that ranks Concourse accounts by renewal-weighted risk, human adoption, reliability, and call-note signals — so post-sales knows where to spend next week and next quarter.”
