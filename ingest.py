#!/usr/bin/env python3
"""Batch ingest: candidate_packet/ → data/accounts.json"""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_PACKET = Path(__file__).resolve().parent / "candidate_packet"
OUT_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_AS_OF = datetime(2026, 6, 30, 23, 59, 59, tzinfo=timezone.utc)
WINDOW_DAYS = 30

# Set for the duration of a single build_accounts() call (Streamlit is single-threaded).
PACKET = DEFAULT_PACKET
AS_OF = DEFAULT_AS_OF

# Identity merges only — ARR amounts are never hardcoded.
MERGE_GROUPS: list[dict[str, Any]] = [
    {
        "ids": ["ACC-1017", "ACC-2017"],
        "canonical": "ACC-1017",
        "arr_mode": "auto",  # equal → once; unequal → sum
        "flags": ["merged_duplicate"],
    },
    {
        "ids": ["ACC-1043", "ACC-2043"],
        "canonical": "ACC-1043",
        "arr_mode": "auto",
        "flags": ["merged_duplicate"],
    },
    {
        "ids": ["ACC-1000", "ACC-2000"],
        "canonical": "ACC-1000",
        "arr_mode": "once",  # count ARR once from canonical
        "flags": ["merged_duplicate", "writeback_fiction"],
    },
]

# A note line seen for more than this share of accounts is boilerplate, not signal.
BOILERPLATE_ACCOUNT_SHARE = 0.10

# "Every live account gets a weekly meeting" — Post Sales Process doc.
PROMISED_CADENCE_DAYS = 7
CSM_LOOKBACK_NOTES = 4
STUCK_AI_MIN_NOTES = 3

# Sudden-collapse detection
CLIFF_LOOKBACK_DAYS = 90
CLIFF_MIN_SIDE_DAYS = 14
CLIFF_MIN_DROP_PCT = 70.0
CLIFF_MIN_RUNS = 200
CLIFF_STEP_WINDOW_DAYS = 7
CLIFF_CLUSTER_SPREAD_DAYS = 2
CLIFF_CLUSTER_WINDOW_DAYS = 7

# Who shows up is a seniority signal; losing the economic buyer precedes churn.
ATTENDEE_LEVELS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"full\s+team|whole\s+team", re.I), 4),
    (re.compile(r"\bCFO\b|controller|\bVP\b|head\s+of", re.I), 3),
    (re.compile(r"FP&A\s+lead|finance\s+lead|manager|director", re.I), 2),
    (re.compile(r"\badmin\b|coordinator|analyst\s+only", re.I), 1),
]


def attendee_level(attendees: str) -> int | None:
    if not attendees:
        return None
    for pat, level in ATTENDEE_LEVELS:
        if pat.search(attendees):
            return level
    return None

SUCCESS_STATUSES = {"completed", "success", "ok", "done"}
FAIL_STATUSES = {"error", "fail", "failed", "failure"}
PARTIAL_STATUSES = {"partial", "partial_success"}

NOTE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("champion_leaving", re.compile(r"champion.*(leav|left|depart|resign)|leaving.*(role|company)|new\s+cfo|champion\s+risk", re.I)),
    ("competitor", re.compile(r"competitor|switching to|evaluating\s+\w+|rip\s*and\s*replace|another\s+vendor", re.I)),
    ("security_stuck", re.compile(r"\bSSO\b|security\s+review|info\s*sec|blocked\s+on\s+security|security\s+stuck", re.I)),
    ("writeback_gap", re.compile(r"write[-\s]?back|ERP\s+write|native\s+write", re.I)),
    ("seasonal_low", re.compile(r"slow\s+season|seasonal|off[-\s]?season|harvest\s+cycle|ag\s+season", re.I)),
    ("expansion", re.compile(r"expansion|upsell|expand\s+to|more\s+seats|pricing\s+for\s+expansion", re.I)),
]


def slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def parse_ts(v: Any) -> datetime | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        try:
            return datetime.fromtimestamp(int(v), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    s = str(v).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return None
    if s.isdigit():
        try:
            return datetime.fromtimestamp(int(s), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%m/%d/%Y %I:%M:%S %p",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        ts = pd.to_datetime(s, utc=True)
        if pd.isna(ts):
            return None
        return ts.to_pydatetime()
    except Exception:
        return None


def normalize_status(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    if s in SUCCESS_STATUSES:
        return "success"
    if s in FAIL_STATUSES:
        return "fail"
    if s in PARTIAL_STATUSES:
        return "partial"
    return "unknown"


def is_service_user(email: str, role: str = "") -> bool:
    e = (email or "").lower()
    r = (role or "").lower()
    return e.startswith("svc-") or "service account" in r or e.startswith("svc_")


def load_crm() -> pd.DataFrame:
    df = pd.read_csv(PACKET / "crm_export.csv")
    df["arr"] = pd.to_numeric(df["arr"], errors="coerce").fillna(0).astype(float)
    df["licensed_seats"] = pd.to_numeric(df["licensed_seats"], errors="coerce").fillna(0).astype(int)
    df["renewal_date"] = df["renewal_date"].fillna("").astype(str).str.strip()
    df["contract_start"] = df["contract_start"].fillna("").astype(str).str.strip()
    return df


def build_id_maps(crm: pd.DataFrame) -> tuple[dict[str, str], dict[str, list[str]], dict[str, list[str]]]:
    """member_id → canonical_id, canonical → members, canonical → extra flags."""
    member_to_canon: dict[str, str] = {aid: aid for aid in crm["account_id"]}
    canon_members: dict[str, list[str]] = {aid: [aid] for aid in crm["account_id"]}
    canon_flags: dict[str, list[str]] = defaultdict(list)

    for g in MERGE_GROUPS:
        ids = [i for i in g["ids"] if i in member_to_canon or i in set(crm["account_id"])]
        if len(ids) < 2:
            # still register known ids even if one missing
            ids = list(g["ids"])
        canon = g["canonical"]
        if canon not in set(crm["account_id"]):
            # pick first present
            present = [i for i in ids if i in set(crm["account_id"])]
            canon = present[0] if present else g["canonical"]
        members = [i for i in ids if i in set(crm["account_id"])]
        if not members:
            continue
        if canon not in members:
            canon = members[0]
        for m in members:
            member_to_canon[m] = canon
        canon_members[canon] = members
        for other in list(canon_members.keys()):
            if other != canon and other in members:
                del canon_members[other]
        canon_flags[canon].extend(g.get("flags", []))
        canon_flags[canon].append(f"arr_mode:{g['arr_mode']}")

    return member_to_canon, canon_members, canon_flags


def merge_arr(rows: pd.DataFrame, mode: str) -> float:
    vals = [float(x) for x in rows["arr"].tolist()]
    if not vals:
        return 0.0
    if mode == "once":
        # Prefer canonical row already ordered first by caller
        return float(vals[0])
    # auto
    if len(vals) == 1:
        return vals[0]
    mx, mn = max(vals), min(vals)
    if mx == 0:
        return 0.0
    if abs(mx - mn) / mx <= 0.01:
        return mx  # duplicated contract
    return float(sum(vals))  # split remnants


def load_seats() -> dict[str, Any]:
    return json.loads((PACKET / "seat_provisioning.json").read_text())


def read_activity_file(path: Path) -> pd.DataFrame | None:
    try:
        text = path.read_text(errors="replace")
        if text.lstrip().startswith("{"):
            rows = [json.loads(line) for line in text.splitlines() if line.strip()]
            df = pd.DataFrame(rows)
        else:
            df = pd.read_csv(path, sep=None, engine="python")
    except Exception as e:
        return None

    # normalize columns
    colmap = {}
    for c in df.columns:
        cl = c.lower().strip()
        if cl in {"email", "user_email"}:
            colmap[c] = "user_email"
        elif cl in {"timestamp", "ts", "run_timestamp"}:
            colmap[c] = "timestamp"
        elif cl in {"run_status", "status"}:
            colmap[c] = "run_status"
        elif cl in {"agent_name", "agent"}:
            colmap[c] = "agent_name"
        elif cl in {"run_duration_sec", "duration_sec"}:
            colmap[c] = "duration_sec"
        elif cl in {"duration_ms"}:
            colmap[c] = "duration_ms"
        elif cl == "run_id":
            colmap[c] = "run_id"
    df = df.rename(columns=colmap)
    if "user_email" not in df.columns:
        df["user_email"] = ""
    if "run_status" not in df.columns:
        df["run_status"] = "unknown"
    if "agent_name" not in df.columns:
        df["agent_name"] = ""
    if "duration_sec" not in df.columns:
        if "duration_ms" in df.columns:
            df["duration_sec"] = pd.to_numeric(df["duration_ms"], errors="coerce") / 1000.0
        else:
            df["duration_sec"] = None
    return df


def match_activity_files(
    crm: pd.DataFrame, member_to_canon: dict[str, str]
) -> tuple[dict[str, list[Path]], list[dict[str, str]], list[dict[str, str]]]:
    """Returns canon→files, unmatched file metas, parse failures."""
    act_dir = PACKET / "activity_exports"
    by_id = {r.account_id: r for r in crm.itertuples()}
    name_to_ids: dict[str, list[str]] = defaultdict(list)
    for r in crm.itertuples():
        name_to_ids[slugify(r.account_name)].append(r.account_id)
        # also strip Inc/Co suffixes lightly
        bare = slugify(re.sub(r"\b(inc|llc|co|corp|corporation|company)\b", "", r.account_name, flags=re.I))
        if bare:
            name_to_ids[bare].append(r.account_id)

    domain_to_ids: dict[str, list[str]] = defaultdict(list)
    seats = load_seats()
    for aid, blob in seats.items():
        for u in blob.get("users", []):
            email = u.get("email", "")
            if "@" in email and not is_service_user(email, u.get("role", "")):
                domain = email.split("@", 1)[1].lower()
                domain_to_ids[domain].append(aid)

    matched: dict[str, list[Path]] = defaultdict(list)
    unmatched: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []

    for path in sorted(act_dir.iterdir()):
        if not path.is_file():
            continue
        name = path.name
        aid = None
        m = re.search(r"(ACC-\d+)", name, re.I)
        if m:
            aid = m.group(1).upper()
        if not aid:
            stem = path.stem
            stem = re.sub(r"^activity_", "", stem, flags=re.I)
            stem = re.sub(r"_\d{4}-\d{2}-\d{2}$", "", stem)
            stem = re.sub(r"\s*\(\d+\)$", "", stem)
            stem = slugify(stem)
            cands = name_to_ids.get(stem, [])
            if len(set(cands)) == 1:
                aid = cands[0]
            elif len(set(cands)) > 1:
                # prefer non-merged-duplicate lower id or any
                aid = sorted(set(cands))[0]

        if aid and aid in member_to_canon:
            matched[member_to_canon[aid]].append(path)
        elif aid and aid in by_id:
            matched[member_to_canon.get(aid, aid)].append(path)
        else:
            # try domain from file contents (first rows) — expensive; skip here, flag unmatched
            unmatched.append({"file": name, "reason": "no_crm_match"})

    return matched, unmatched, failures


def clean_note_line(line: str) -> str:
    return re.sub(r"^\s*[-*]?\s*(AI\s*:)?\s*", "", line, flags=re.I).strip()


def extract_notes_for_accounts(
    crm: pd.DataFrame, canon_members: dict[str, list[str]]
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Tag accounts from call notes, ignoring lines that repeat across the corpus.

    Most notes are boilerplate ("They asked about SSO rollout..."), so a line that
    shows up for many accounts carries no signal about any one of them. Only lines
    rare across accounts are allowed to set tags, quotes, or action items.
    """
    notes_root = PACKET / "call_notes"
    # map slug → account ids
    slug_to_aids: dict[str, list[str]] = defaultdict(list)
    for r in crm.itertuples():
        slug_to_aids[slugify(r.account_name)].append(r.account_id)
        bare = slugify(re.sub(r"\b(inc|llc|co|corp|corporation|company)\b", "", r.account_name, flags=re.I))
        slug_to_aids[bare].append(r.account_id)

    # invert members to canon
    member_to_canon = {}
    for canon, members in canon_members.items():
        for m in members:
            member_to_canon[m] = canon

    # Pass 1: parse each note into structured metadata + lines
    lines_by_canon: dict[str, list[str]] = defaultdict(list)
    ai_by_canon: dict[str, list[str]] = defaultdict(list)
    parsed_by_canon: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for path in sorted(notes_root.rglob("*")):
        if not path.is_file():
            continue
        aids = slug_to_aids.get(slugify(path.parent.name), [])
        if not aids:
            continue
        canon = member_to_canon.get(aids[0], aids[0])
        try:
            text = path.read_text(errors="replace")
        except Exception:
            continue

        note_date = None
        m = re.search(r"\((\d{4}-\d{2}-\d{2})\)", text)
        if m:
            try:
                note_date = datetime.strptime(m.group(1), "%Y-%m-%d").date()
            except ValueError:
                note_date = None
        csm_m = re.search(r"_CSM:\s*([A-Za-z]{1,4})_", text)
        att_m = re.search(r"##\s*Attendees\s*\n((?:\s*[-*].*\n?)+)", text)
        attendees = ""
        if att_m:
            attendees = clean_note_line(att_m.group(1).splitlines()[0])

        section = None
        note_lines: list[str] = []
        note_ais: list[str] = []
        for raw in text.splitlines():
            stripped = raw.strip()
            if stripped.startswith("#"):
                low = stripped.lower()
                if "action item" in low:
                    section = "ai"
                elif "attendee" in low:
                    section = "attendees"
                elif "note" in low:
                    section = "notes"
                else:
                    section = None
                continue
            if not stripped or stripped.startswith("_"):
                continue
            item = clean_note_line(raw)
            if not item:
                continue
            is_ai = bool(re.match(r"^\s*[-*]?\s*AI\s*:", raw, re.I)) or (
                section == "ai" and stripped.startswith("-")
            )
            if is_ai:
                note_ais.append(item[:220])
                ai_by_canon[canon].append(item[:220])
            elif section == "notes":
                note_lines.append(item[:220])
                lines_by_canon[canon].append(item[:220])

        parsed_by_canon[canon].append(
            {
                "date": note_date,
                "csm": csm_m.group(1).upper() if csm_m else None,
                "attendees": attendees,
                "action_items": note_ais,
                "lines": note_lines,
            }
        )

    # Pass 2: a line is boilerplate if it shows up for many different accounts
    n_accounts = max(len(canon_members), 1)
    max_accounts = max(2, int(n_accounts * BOILERPLATE_ACCOUNT_SHARE))

    def account_counts(source: dict[str, list[str]]) -> Counter:
        counts: Counter = Counter()
        for canon, items in source.items():
            counts.update(set(items))
        return counts

    line_counts = account_counts(lines_by_canon)
    ai_counts = account_counts(ai_by_canon)

    boilerplate_lines = {s for s, c in line_counts.items() if c > max_accounts}
    boilerplate_ais = {s for s, c in ai_counts.items() if c > max_accounts}

    out: dict[str, dict[str, Any]] = {}
    for canon in set(lines_by_canon) | set(ai_by_canon):
        distinctive = [
            s for s in dict.fromkeys(lines_by_canon.get(canon, [])) if s not in boilerplate_lines
        ]
        tags: list[str] = []
        quotes: list[str] = []
        for tag, pat in NOTE_PATTERNS:
            for line in distinctive:
                if pat.search(line):
                    if tag not in tags:
                        tags.append(tag)
                    if line not in quotes:
                        quotes.append(line)
                    break

        ais = [
            s for s in dict.fromkeys(ai_by_canon.get(canon, [])) if s not in boilerplate_ais
        ]
        out[canon] = {
            "tags": tags[:3],
            "quotes": quotes[:2],
            "open_action_items": ais[:8],
            "boilerplate_lines_ignored": len(
                [s for s in set(lines_by_canon.get(canon, [])) if s in boilerplate_lines]
            ),
        }

    # Pass 3: metadata signals — cadence, ownership, attendee seniority, stuck items.
    # These are comparable across accounts and cannot be faked by template text.
    for canon, notes in parsed_by_canon.items():
        dated = sorted([n for n in notes if n["date"]], key=lambda n: n["date"])
        bucket = out.setdefault(
            canon,
            {"tags": [], "quotes": [], "open_action_items": [], "boilerplate_lines_ignored": 0},
        )
        bucket["notes_count"] = len(notes)
        if not dated:
            continue

        last_date = dated[-1]["date"]
        gaps = [
            (dated[i + 1]["date"] - dated[i]["date"]).days for i in range(len(dated) - 1)
        ]
        bucket["last_note_date"] = last_date.isoformat()
        bucket["days_since_last_note"] = (AS_OF.date() - last_date).days
        bucket["median_gap_days"] = (
            int(statistics.median(gaps)) if gaps else None
        )
        bucket["max_gap_days"] = max(gaps) if gaps else None

        recent = dated[-CSM_LOOKBACK_NOTES:]
        csms = [n["csm"] for n in recent if n["csm"]]
        bucket["csm_recent_sequence"] = csms
        # Turnover is only meaningful with enough meetings to compare
        bucket["distinct_csms_recent"] = len(set(csms)) if len(csms) >= 3 else None
        bucket["csm_notes_considered"] = len(csms)

        levels = [(n["date"], attendee_level(n["attendees"]), n["attendees"]) for n in dated]
        levels = [lv for lv in levels if lv[1] is not None]
        if levels:
            last_level = levels[-1][1]
            earlier = [lv[1] for lv in levels[:-1]]
            best_earlier = max(earlier) if earlier else last_level
            bucket["attendee_last"] = levels[-1][2]
            bucket["attendee_level_last"] = last_level
            bucket["attendee_level_best"] = best_earlier
            bucket["seniority_drift"] = bool(
                earlier and last_level < best_earlier and last_level <= 2
            )
        else:
            bucket["seniority_drift"] = False

        # An item repeating across separate dated notes is genuinely stuck
        ai_dates: dict[str, list[Any]] = defaultdict(list)
        for n in dated:
            for item in set(n["action_items"]):
                ai_dates[item].append(n["date"])
        stuck = [
            {
                "item": item,
                "occurrences": len(ds),
                "first_seen": min(ds).isoformat(),
                "last_seen": max(ds).isoformat(),
                "span_days": (max(ds) - min(ds)).days,
            }
            for item, ds in ai_dates.items()
            if len(ds) >= STUCK_AI_MIN_NOTES
        ]
        stuck.sort(key=lambda x: (-x["occurrences"], -x["span_days"]))
        bucket["stuck_action_items"] = stuck[:5]

    note_meta = {
        "boilerplate_threshold_accounts": max_accounts,
        "boilerplate_lines": len(boilerplate_lines),
        "boilerplate_action_items": len(boilerplate_ais),
        "distinctive_lines": len(line_counts) - len(boilerplate_lines),
        "promised_cadence_days": PROMISED_CADENCE_DAYS,
        "metadata_signals": [
            "days_since_last_note",
            "distinct_csms_recent",
            "seniority_drift",
            "stuck_action_items",
        ],
    }
    return out, note_meta


def detect_usage_cliff(act: pd.DataFrame) -> dict[str, Any] | None:
    """Find a sudden, sustained collapse in human run volume.

    Returns the changepoint plus the evidence needed to tell an export/metering
    problem apart from real churn: whether the same people kept using it, and
    whether failures spiked.
    """
    if act is None or act.empty:
        return None
    human = act[~act["_svc"]].dropna(subset=["_ts"])
    if len(human) < CLIFF_MIN_RUNS:
        return None

    window = human[human["_ts"] >= AS_OF - timedelta(days=CLIFF_LOOKBACK_DAYS)]
    if window.empty:
        return None
    daily = window.set_index("_ts").resample("D").size()
    if len(daily) < CLIFF_MIN_SIDE_DAYS * 2:
        return None

    # Onset, not the deepest point: the first day volume falls and stays down.
    # Picking the steepest split instead drifts into the flat tail and reports
    # different dates for accounts that actually broke on the same day.
    # A cliff is a step, not a slope: the week after must fall sharply against
    # the week before AND stay down. Comparing whole-period averages instead
    # fires early and also catches gradual declines, which are a different story.
    span = CLIFF_STEP_WINDOW_DAYS
    keep = 1.0 - CLIFF_MIN_DROP_PCT / 100.0
    cut_idx = None
    for i in range(span, len(daily) - CLIFF_MIN_SIDE_DAYS):
        prev = float(daily.iloc[i - span : i].mean())
        nxt = float(daily.iloc[i : i + span].mean())
        rest = float(daily.iloc[i:].mean())
        if prev > 0 and nxt <= prev * keep and rest <= prev * keep:
            cut_idx = i
            break
    if cut_idx is None:
        return None

    cut = daily.index[cut_idx]
    before_rate = float(daily.iloc[:cut_idx].mean())
    after_rate = float(daily.iloc[cut_idx:].mean())
    if before_rate <= 0:
        return None
    drop = (after_rate - before_rate) / before_rate * 100.0
    b = human[human["_ts"] < cut]
    a_ = human[human["_ts"] >= cut]
    users_before = set(b["_email"].dropna())
    users_after = set(a_["_email"].dropna())
    err_before = float((b["_status"] == "fail").mean()) if len(b) else 0.0
    err_after = float((a_["_status"] == "fail").mean()) if len(a_) else 0.0

    return {
        "date": cut.date().isoformat(),
        "drop_pct": round(drop, 1),
        "runs_per_day_before": round(float(before_rate), 1),
        "runs_per_day_after": round(float(after_rate), 1),
        "users_before": len(users_before),
        "users_after": len(users_after),
        "users_retained": len(users_before & users_after),
        "error_rate_before": round(err_before, 3),
        "error_rate_after": round(err_after, 3),
        "agents_before": int(b["agent_name"].nunique()) if "agent_name" in b else None,
        "agents_after": int(a_["agent_name"].nunique()) if "agent_name" in a_ else None,
    }


def score_account(a: dict[str, Any]) -> None:
    factors: list[tuple[str, float, str]] = []
    arr = float(a.get("arr") or 0)
    arr_phrase = f"${arr:,.0f} ARR"

    # Renewal urgency 0–25
    days = a.get("days_to_renewal")
    renew_pts = 0.0
    renew_label = "Contract renewal is not urgent right now"
    if days is None:
        renew_pts = 8.0
        renew_label = "Renewal date is missing in CRM"
    else:
        if days < 0:
            base = 25
            overdue = abs(int(days))
            renew_label = f"Renewal is overdue by {overdue} day{'s' if overdue != 1 else ''} ({arr_phrase})"
        elif days <= 30:
            base = 22
            renew_label = f"Renews in {int(days)} days ({arr_phrase})"
        elif days <= 60:
            base = 18
            renew_label = f"Renews in {int(days)} days ({arr_phrase})"
        elif days <= 90:
            base = 14
            renew_label = f"Renews in {int(days)} days ({arr_phrase})"
        elif days <= 180:
            base = 8
            renew_label = f"Renews in about {int(days)} days"
        else:
            base = 2
            renew_label = f"Renewal is {int(days)} days out"
        arr_boost = 0.0 if days < 0 else min(5.0, arr / 1_000_000 * 1.5)
        renew_pts = min(25.0, base + arr_boost)
    factors.append(("renewal", renew_pts, renew_label))

    # Usage health 0–25
    runs = int(a.get("runs_30d") or 0)
    prior = int(a.get("runs_prior_30d") or 0)
    delta = a.get("usage_delta_pct")
    seasonal = "seasonal_low" in (a.get("note_tags") or [])
    has_usage_data = bool(a.get("usage_data_available"))
    usage_pts = 0.0
    if not has_usage_data:
        # No activity export matched. Absence of data is not evidence of no usage,
        # so this scores as an unknown, not as a zero.
        usage_pts = 8.0
        usage_label = "Usage unknown — no activity export matched this account"
    elif runs == 0:
        usage_pts = 22.0
        usage_label = "No real-user product usage in the last 30 days"
    elif delta is not None and delta <= -80:
        usage_pts = 25.0
        usage_label = f"Usage collapsed ({abs(delta):.0f}% vs the prior 30 days)"
    elif runs < 20:
        usage_pts = 16.0
        usage_label = f"Light usage — only {runs} runs in the last 30 days"
    elif delta is not None and delta <= -40:
        usage_pts = 18.0
        usage_label = f"Usage dropped sharply ({abs(delta):.0f}% vs the prior 30 days)"
    elif delta is not None and delta <= -20:
        usage_pts = 12.0
        usage_label = f"Usage is declining ({abs(delta):.0f}% vs the prior 30 days)"
    else:
        usage_pts = 3.0
        usage_label = f"Usage looks steady ({runs} runs in the last 30 days)"
    if seasonal and has_usage_data and usage_pts > 8:
        usage_pts *= 0.45
        usage_label += " — partly expected in slow season"
    factors.append(("usage", min(25.0, usage_pts), usage_label))

    # Reliability 0–15
    err = float(a.get("error_rate_30d") or 0)
    if not has_usage_data:
        rel_pts, rel_label = 0.0, "Run reliability unknown — no activity export"
    elif err >= 0.25:
        rel_pts, rel_label = 15.0, f"Runs are failing often ({err:.0%} error rate)"
    elif err >= 0.12:
        rel_pts, rel_label = 10.0, f"Elevated failure rate on runs ({err:.0%})"
    elif err >= 0.05:
        rel_pts, rel_label = 5.0, f"Some run failures ({err:.0%})"
    else:
        rel_pts, rel_label = 1.0, f"Runs are mostly reliable ({err:.0%} errors)"
    factors.append(("reliability", rel_pts, rel_label))

    # Adoption / seats 0–15
    util = a.get("seat_utilization")
    bot = bool(a.get("bot_heavy"))
    if util is None:
        ad_pts, ad_label = 6.0, "Seat adoption cannot be measured yet"
    elif util < 0.15:
        ad_pts, ad_label = 14.0, f"Very few licensed seats are active ({util:.0%})"
    elif util < 0.35:
        ad_pts, ad_label = 10.0, f"Low seat adoption — only {util:.0%} of licensed seats active"
    elif util < 0.55:
        ad_pts, ad_label = 5.0, f"Moderate seat adoption ({util:.0%} active)"
    else:
        ad_pts, ad_label = 1.0, f"Healthy seat adoption ({util:.0%} active)"
    if not has_usage_data and ad_pts > 6:
        # Without activity we only see last_login, which understates who is active.
        ad_pts = 6.0
        ad_label = f"Seat adoption looks low ({util:.0%} by login) but activity export is missing"
    if bot:
        ad_pts = min(15.0, ad_pts + 4)
        ad_label += "; much of the traffic looks automated"
    factors.append(("adoption", min(15.0, ad_pts), ad_label))

    # Relationship health 0–15 — driven by note metadata, which is comparable
    # across accounts and unfakeable by template text, plus rare keyword hits.
    tags = set(a.get("note_tags") or [])
    q_pts = 0.0
    q_bits = []

    days_since = a.get("days_since_last_note")
    if days_since is None:
        q_pts += 3
        q_bits.append("no dated call notes")
    elif days_since > 90:
        q_pts += 5
        q_bits.append(f"no contact in {days_since} days (weekly cadence promised)")
    elif days_since > 45:
        q_pts += 3
        q_bits.append(f"last touch {days_since} days ago")
    elif days_since > 14:
        q_pts += 1
        q_bits.append(f"cadence slipping ({days_since} days since last note)")

    distinct_csms = a.get("distinct_csms_recent") or 0
    considered = a.get("csm_notes_considered") or 0
    if distinct_csms >= 3:
        q_pts += 4
        q_bits.append(f"{distinct_csms} different CSMs across last {considered} meetings")

    if a.get("seniority_drift"):
        q_pts += 4
        q_bits.append(f"attendees dropped to \"{a.get('attendee_last', 'junior')}\"")

    stuck = a.get("stuck_action_items") or []
    if stuck:
        top = stuck[0]
        q_pts += 3 if top["occurrences"] >= 4 else 2
        q_bits.append(
            f"same action item open across {top['occurrences']} meetings ({top['span_days']} days)"
        )

    if "champion_leaving" in tags:
        q_pts += 5
        q_bits.append("champion may be leaving")
    if "competitor" in tags:
        q_pts += 5
        q_bits.append("competitor named in notes")
    if "security_stuck" in tags:
        q_pts += 3
        q_bits.append("blocked on security review")
    if "writeback_fiction" in (a.get("data_flags") or []):
        q_pts += 2
        q_bits.append("write-back expectations gap")

    q_pts = min(15.0, q_pts)
    q_label = "Relationship: " + "; ".join(q_bits) if q_bits else "Relationship looks healthy"
    factors.append(("qualitative", q_pts, q_label))

    # Stage risk 0–5
    stage = (a.get("stage") or "").lower()
    if stage == "onboarding" and has_usage_data and runs < 50:
        st_pts, st_label = 5.0, "Still onboarding and not using the product much yet"
    elif stage == "onboarding":
        st_pts, st_label = 2.0, "Account is still in onboarding"
    else:
        st_pts, st_label = 0.0, "Account is live"
    factors.append(("stage", st_pts, st_label))

    # Risk tags (short labels for scanning — derived, not from CRM)
    risk_tags = []
    if days is not None and days < 0:
        risk_tags.append("renewal_overdue")
    elif days is not None and days <= 90:
        risk_tags.append("renewal_soon")
    if not has_usage_data:
        risk_tags.append("usage_unknown")
    if stage == "onboarding" and has_usage_data and runs < 50:
        risk_tags.append("onboarding_stalled")
    if "champion_leaving" in tags:
        risk_tags.append("champion_risk")
    if "seasonal_low" in tags:
        risk_tags.append("seasonal_low")
    if "expansion" in tags:
        risk_tags.append("expansion")
    if "competitor" in tags:
        risk_tags.append("competitor")
    if "security_stuck" in tags:
        risk_tags.append("security_stuck")
    if bot:
        risk_tags.append("bot_heavy")
    if days_since is not None and days_since > 90:
        risk_tags.append("no_recent_contact")
    if distinct_csms >= 3:
        risk_tags.append("csm_churn")
    if a.get("seniority_drift"):
        risk_tags.append("seniority_drift")
    if stuck:
        risk_tags.append("stuck_action_item")

    total = sum(p for _, p, _ in factors)
    primary = max(factors, key=lambda x: x[1])
    weight_max = {
        "renewal": 25,
        "usage": 25,
        "reliability": 15,
        "adoption": 15,
        "qualitative": 15,
        "stage": 5,
    }
    factor_titles = {
        "renewal": "Renewal urgency",
        "usage": "Usage health",
        "reliability": "Reliability",
        "adoption": "Seat adoption",
        "qualitative": "Relationship health",
        "stage": "Stage risk",
    }
    a["attention_score"] = round(total, 1)
    a["primary_reason"] = primary[2]
    a["score_factors"] = {k: round(p, 1) for k, p, _ in factors}
    a["score_breakdown"] = [
        {
            "factor": factor_titles.get(k, k),
            "factor_key": k,
            "observation": lab,
            "points": round(pts, 1),
            "max_points": weight_max.get(k, 0),
        }
        for k, pts, lab in sorted(factors, key=lambda x: -x[1])
    ]
    a["evidence_lines"] = [
        f"{factor_titles.get(k, k)}: {lab} — {pts:.0f}/{weight_max.get(k, 0)} pts"
        for k, pts, lab in sorted(factors, key=lambda x: -x[1])
        if pts > 0
    ]
    a["risk_tags"] = risk_tags
    # Tuned to packet distribution (top scores ~45–66 as-of dump)
    if total >= 50:
        a["risk_tier"] = "red"
    elif total >= 35:
        a["risk_tier"] = "amber"
    else:
        a["risk_tier"] = "green"


def build_findings(accounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group per-account anomalies into portfolio-level findings.

    A drop that hits several unrelated accounts on the same day is one
    investigation, not several account saves — and the difference changes who
    should act on it.
    """
    findings: list[dict[str, Any]] = []
    rank_of = {a["account_name"]: i for i, a in enumerate(accounts, 1)}

    # 1. Simultaneous collapses across unrelated accounts
    # Cluster by date proximity, not calendar week — a real event that lands on
    # a Sunday would otherwise be split across two weeks and hidden.
    dated = sorted(
        (a for a in accounts if a.get("usage_cliff")),
        key=lambda a: a["usage_cliff"]["date"],
    )
    clusters: list[list[dict[str, Any]]] = []
    for a in dated:
        d = date.fromisoformat(a["usage_cliff"]["date"])
        if clusters and (d - date.fromisoformat(clusters[-1][0]["usage_cliff"]["date"])).days <= CLIFF_CLUSTER_WINDOW_DAYS:
            clusters[-1].append(a)
        else:
            clusters.append([a])

    for group in clusters:
        if len(group) < 2:
            continue
        retained = sum(a["usage_cliff"]["users_retained"] for a in group)
        before = sum(a["usage_cliff"]["users_before"] for a in group)
        err_up = sum(
            1
            for a in group
            if a["usage_cliff"]["error_rate_after"] > a["usage_cliff"]["error_rate_before"] + 0.02
        )
        dates = sorted(date.fromisoformat(a["usage_cliff"]["date"]) for a in group)
        spread = (dates[-1] - dates[0]).days
        # Allow a little jitter: the detector's window can land a day either
        # side of the true edge, and a 1-2 day spread is still one event.
        same_day = spread <= CLIFF_CLUSTER_SPREAD_DAYS
        onset = Counter(dates).most_common(1)[0][0].isoformat()
        when = onset if spread == 0 else f"{onset} (±{spread}d)"
        arr = sum(a["arr"] for a in group)
        verticals = sorted({str(a.get("vertical") or "unknown") for a in group})
        owners = sorted({str(a.get("owner") or "unknown") for a in group})

        # The signature that separates a pipeline change from real churn
        looks_systemic = (
            same_day and before and retained / before >= 0.75 and err_up == 0 and len(group) >= 3
        )
        findings.append(
            {
                "kind": "shared_usage_cliff",
                "severity": "high",
                "headline": (
                    f"{len(group)} accounts (${arr:,.0f} ARR) lost "
                    f"~{abs(sum(a['usage_cliff']['drop_pct'] for a in group) / len(group)):.0f}% "
                    f"of usage {'within a day of each other' if same_day else 'in the same week'}, "
                    f"around {when}"
                ),
                "verdict": (
                    "Likely upstream — one pipeline or metering change, not N churn events"
                    if looks_systemic
                    else "Mixed signals — review the accounts individually"
                ),
                "evidence": [
                    f"{retained} of {before} users kept running after the drop"
                    + (" — the people did not leave" if before and retained / before >= 0.75 else ""),
                    (
                        "No error-rate spike in any account"
                        if err_up == 0
                        else f"{err_up} of {len(group)} accounts also saw errors rise"
                    ),
                    f"Spans {len(verticals)} verticals and {len(owners)} owners: "
                    + ", ".join(verticals),
                    f"Volume per account fell from "
                    f"{sum(a['usage_cliff']['runs_per_day_before'] for a in group) / len(group):.0f} "
                    f"to {sum(a['usage_cliff']['runs_per_day_after'] for a in group) / len(group):.0f} "
                    "runs/day",
                ],
                "action": (
                    "Check what shipped on this date (metering, export, quota) before "
                    "opening churn plays. If it is real, it is a coordinated event worth "
                    "one escalation."
                    if looks_systemic
                    else "Work these accounts individually."
                ),
                "accounts": [a["account_name"] for a in group],
                # Scored as if independent — kept so the reader can see what the
                # ranking would have said, and why that would have been wrong.
                "members": sorted(
                    (
                        {
                            "account": a["account_name"],
                            "arr": a["arr"],
                            "owner": a.get("owner"),
                            "stage": a.get("stage"),
                            "renewal_date": a.get("renewal_date"),
                            "days_to_renewal": a.get("days_to_renewal"),
                            "drop_pct": a["usage_cliff"]["drop_pct"],
                            "users_retained": a["usage_cliff"]["users_retained"],
                            "users_before": a["usage_cliff"]["users_before"],
                            "date": a["usage_cliff"]["date"],
                            "would_be_rank": rank_of.get(a["account_name"]),
                            "would_be_tier": a.get("risk_tier"),
                        }
                        for a in group
                    ),
                    key=lambda m: -m["arr"],
                ),
                "date": onset,
                "arr_at_stake": arr,
                "systemic": looks_systemic,
            }
        )
        if looks_systemic:
            ranks = sorted(r for a in group if (r := rank_of.get(a["account_name"])))
            order = ["red", "amber", "green"]
            present = [t for t in order if any(a.get("risk_tier") == t for a in group)]
            spread = (
                f" — the same event reading as {present[0]} for one account and "
                f"{present[-1]} for another"
                if len(present) > 1
                else ""
            )
            findings[-1]["evidence"].append(
                "Scored as independent accounts they land at ranks "
                + ", ".join(str(r) for r in ranks)
                + spread
                + ", which is why they are handled as one item here."
            )

    # 2. Accounts missing from the export that are demonstrably still alive
    missing = [a for a in accounts if not a.get("usage_data_available")]
    if missing:
        alive = [a for a in missing if (a.get("logins_30d") or 0) > 0]
        with_data = [a for a in accounts if a.get("usage_data_available")]
        peer_logins = (
            sum(a.get("logins_30d") or 0 for a in with_data) / len(with_data) if with_data else 0
        )
        avg_missing = sum(a.get("logins_30d") or 0 for a in alive) / len(alive) if alive else 0
        recent = sorted((a.get("last_login") or "") for a in alive)
        findings.append(
            {
                "kind": "export_gap",
                "severity": "high" if alive else "medium",
                "headline": (
                    f"{len(missing)} accounts (${sum(a['arr'] for a in missing):,.0f} ARR) have no "
                    f"activity export, but {len(alive)} of them still have users logging in"
                ),
                "verdict": (
                    "Export gap, not dead accounts — do not read these as zero usage"
                    if alive and avg_missing >= peer_logins * 0.5
                    else "Genuinely quiet — no logins either"
                ),
                "evidence": [
                    f"{avg_missing:.1f} users logged in per account in the last 30 days, "
                    f"vs {peer_logins:.1f} for accounts that do have export files",
                    f"Most recent login among them: {recent[-1] if recent else 'none'}",
                    "Logins come from seat provisioning, a separate system from the "
                    "activity export — so they are independent evidence",
                ],
                "action": (
                    "Fix the export for these account IDs; until then their usage, "
                    "error rate and adoption scores are unknown, not zero."
                ),
                "accounts": [a["account_name"] for a in missing],
                "arr_at_stake": sum(a["arr"] for a in missing),
                "systemic": bool(alive),
            }
        )

    return findings


def build_accounts(
    packet_dir: Path | str | None = None,
    as_of: datetime | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    global PACKET, AS_OF
    PACKET = Path(packet_dir) if packet_dir is not None else DEFAULT_PACKET
    AS_OF = as_of if as_of is not None else DEFAULT_AS_OF
    if AS_OF.tzinfo is None:
        AS_OF = AS_OF.replace(tzinfo=timezone.utc)

    if not (PACKET / "crm_export.csv").exists():
        raise FileNotFoundError(f"Missing crm_export.csv in packet: {PACKET}")

    crm = load_crm()
    member_to_canon, canon_members, canon_flags = build_id_maps(crm)
    seats_raw = load_seats()
    matched_files, unmatched_files, _ = match_activity_files(crm, member_to_canon)
    notes, note_meta = extract_notes_for_accounts(crm, canon_members)

    w1_start = AS_OF - timedelta(days=WINDOW_DAYS)
    w0_start = AS_OF - timedelta(days=WINDOW_DAYS * 2)

    # Preload + normalize all activity once
    activity_by_canon: dict[str, pd.DataFrame] = {}
    schema_variants: set[str] = set()
    files_ingested = 0
    file_errors: list[dict[str, str]] = []

    for canon, paths in matched_files.items():
        frames = []
        for path in paths:
            df = read_activity_file(path)
            if df is None:
                file_errors.append({"file": path.name, "error": "parse_failed"})
                continue
            schema_variants.add("|".join(sorted(df.columns.astype(str))))
            df = df.copy()
            df["_ts"] = df["timestamp"].map(parse_ts)
            df["_status"] = df["run_status"].map(normalize_status)
            df["_email"] = df["user_email"].fillna("").astype(str).str.lower()
            df["_svc"] = df["_email"].map(lambda e: is_service_user(e))
            frames.append(df)
            files_ingested += 1
        if frames:
            activity_by_canon[canon] = pd.concat(frames, ignore_index=True)

    # Orphans: try to attach unmatched via email domain
    still_unmatched = []
    domain_to_canon: dict[str, str] = {}
    for aid, blob in seats_raw.items():
        canon = member_to_canon.get(aid)
        if not canon:
            continue
        for u in blob.get("users", []):
            email = u.get("email", "")
            if "@" in email:
                domain_to_canon[email.split("@", 1)[1].lower()] = canon

    act_dir = PACKET / "activity_exports"
    unmatched_names = {u["file"] for u in unmatched_files}
    for path in act_dir.iterdir():
        if path.name not in unmatched_names:
            continue
        df = read_activity_file(path)
        if df is None:
            file_errors.append({"file": path.name, "error": "parse_failed"})
            still_unmatched.append({"file": path.name, "reason": "parse_or_no_match"})
            continue
        emails = df.get("user_email", pd.Series(dtype=str)).fillna("").astype(str)
        domains = emails.str.split("@").str[-1].str.lower()
        votes: dict[str, int] = defaultdict(int)
        for d in domains:
            if d in domain_to_canon:
                votes[domain_to_canon[d]] += 1
        if votes:
            canon = max(votes, key=votes.get)
            df = df.copy()
            df["_ts"] = df["timestamp"].map(parse_ts)
            df["_status"] = df["run_status"].map(normalize_status)
            df["_email"] = df["user_email"].fillna("").astype(str).str.lower()
            df["_svc"] = df["_email"].map(lambda e: is_service_user(e))
            if canon in activity_by_canon:
                activity_by_canon[canon] = pd.concat([activity_by_canon[canon], df], ignore_index=True)
            else:
                activity_by_canon[canon] = df
            files_ingested += 1
            schema_variants.add("|".join(sorted(df.columns.astype(str))))
        else:
            still_unmatched.append({"file": path.name, "reason": "no_crm_match"})

    accounts: list[dict[str, Any]] = []
    crm_by_id = {r.account_id: r for r in crm.itertuples()}

    for canon, members in sorted(canon_members.items(), key=lambda x: x[0]):
        rows = crm[crm["account_id"].isin(members)].copy()
        if rows.empty:
            continue
        # put canonical row first
        rows["_ord"] = rows["account_id"].apply(lambda x: 0 if x == canon else 1)
        rows = rows.sort_values("_ord")
        primary = rows.iloc[0]

        arr_mode = "auto"
        flags = list(dict.fromkeys(canon_flags.get(canon, [])))
        for g in MERGE_GROUPS:
            if canon in g["ids"] or set(members) & set(g["ids"]):
                arr_mode = g["arr_mode"]
                break
        flags = [f for f in flags if not f.startswith("arr_mode:")]

        arr = merge_arr(rows, arr_mode)
        # owner/stage/vertical from canonical preferred row; if blank take first non-null
        def first_nonempty(col: str) -> str:
            for _, r in rows.iterrows():
                v = str(r.get(col) or "").strip()
                if v:
                    return v
            return ""

        renewal_raw = first_nonempty("renewal_date")
        contract_start = first_nonempty("contract_start")
        days_to_renewal = None
        if renewal_raw:
            rd = parse_ts(renewal_raw)
            if rd:
                days_to_renewal = (rd.date() - AS_OF.date()).days
        else:
            flags.append("missing_renewal")

        licensed = int(rows.loc[rows["account_id"] == canon, "licensed_seats"].iloc[0]) if canon in set(rows["account_id"]) else int(rows["licensed_seats"].max())
        # Prefer max licensed among members when merging once? Use canonical licensed for once; sum for split seats carefully — use max to avoid double
        if len(members) > 1:
            if arr_mode == "once":
                licensed = int(crm_by_id[canon].licensed_seats) if canon in crm_by_id else int(rows["licensed_seats"].iloc[0])
            else:
                # split: sum licensed if ARR summed, else max
                licensed = int(rows["licensed_seats"].sum()) if abs(arr - float(rows["arr"].iloc[0])) > 1 else int(rows["licensed_seats"].max())

        # seats union
        users = []
        provisioned = 0
        for mid in members:
            blob = seats_raw.get(mid)
            if not blob:
                continue
            provisioned += int(blob.get("provisioned_seats") or len(blob.get("users") or []))
            users.extend(blob.get("users") or [])
        # dedupe users by email
        by_email = {}
        for u in users:
            by_email[(u.get("email") or "").lower()] = u
        users = list(by_email.values())
        if len(members) > 1 and arr_mode == "once":
            # avoid double-counting provisioned across duplicate CRM orgs — unique emails already; provisioned = len
            provisioned = len(users)

        human_users = [u for u in users if not is_service_user(u.get("email", ""), u.get("role", ""))]
        human_provisioned = len(human_users)

        act = activity_by_canon.get(canon)
        active_emails_login = set()
        for u in human_users:
            lt = parse_ts(u.get("last_login"))
            if lt and w1_start <= lt <= AS_OF:
                active_emails_login.add((u.get("email") or "").lower())

        runs_30d = runs_prior = 0
        error_rate = 0.0
        bot_heavy = False
        human_run_emails: set[str] = set()
        has_activity = act is not None and len(act) > 0
        if has_activity:
            ts = act["_ts"]
            in_w1 = act[(ts >= w1_start) & (ts <= AS_OF)]
            in_w0 = act[(ts >= w0_start) & (ts < w1_start)]
            human_w1 = in_w1[~in_w1["_svc"]]
            human_w0 = in_w0[~in_w0["_svc"]]
            runs_30d = int(len(human_w1))
            runs_prior = int(len(human_w0))
            if len(in_w1):
                error_rate = float((in_w1["_status"] == "fail").sum() / len(in_w1))
            svc_share = float(in_w1["_svc"].mean()) if len(in_w1) else 0.0
            bot_heavy = svc_share >= 0.5 or (runs_30d < 5 and int(in_w1["_svc"].sum()) >= 10)
            human_run_emails = set(human_w1["_email"].tolist())
        else:
            flags.append("no_activity_file")

        cliff = detect_usage_cliff(act) if has_activity else None

        # Logins prove an account is alive even when its activity export is missing
        logins_30d = len(active_emails_login)
        logins_60d = sum(
            1
            for u in human_users
            if (lt := parse_ts(u.get("last_login"))) and lt >= AS_OF - timedelta(days=60)
        )
        last_login = max(
            (lt for u in human_users if (lt := parse_ts(u.get("last_login")))),
            default=None,
        )

        human_active = len(active_emails_login | {e for e in human_run_emails if e})
        util = (human_active / licensed) if licensed > 0 else None
        if runs_prior > 0:
            usage_delta_pct = (runs_30d - runs_prior) / runs_prior * 100.0
        elif runs_30d > 0:
            usage_delta_pct = 100.0
        else:
            usage_delta_pct = 0.0 if has_activity else None

        note = notes.get(canon, {"tags": [], "quotes": [], "open_action_items": []})
        merged_names = sorted({str(crm_by_id[m].account_name) for m in members if m in crm_by_id})

        account = {
            "account_id_canonical": canon,
            "account_name": str(crm_by_id[canon].account_name) if canon in crm_by_id else str(primary.account_name),
            "merged_account_ids": members,
            "merged_names": merged_names,
            "vertical": first_nonempty("vertical"),
            "owner": str(crm_by_id[canon].owner) if canon in crm_by_id else first_nonempty("owner"),
            "stage": str(crm_by_id[canon].stage) if canon in crm_by_id else first_nonempty("stage"),
            "arr": arr,
            "contract_start": contract_start or None,
            "renewal_date": renewal_raw or None,
            "days_to_renewal": days_to_renewal,
            "licensed_seats": licensed,
            "provisioned_seats": provisioned,
            "human_provisioned": human_provisioned,
            "human_active_30d": human_active,
            "seat_utilization": round(util, 3) if util is not None else None,
            "runs_30d": runs_30d if has_activity else None,
            "runs_prior_30d": runs_prior if has_activity else None,
            "usage_delta_pct": round(usage_delta_pct, 1) if usage_delta_pct is not None else None,
            "error_rate_30d": round(error_rate, 3) if has_activity else None,
            "bot_heavy": bot_heavy,
            "usage_data_available": has_activity,
            "data_confidence": "full" if has_activity else "partial — no activity export",
            "usage_cliff": cliff,
            "logins_30d": logins_30d,
            "logins_60d": logins_60d,
            "last_login": last_login.date().isoformat() if last_login else None,
            "note_tags": note.get("tags", []),
            "note_quotes": note.get("quotes", []),
            "open_action_items": note.get("open_action_items", []),
            "boilerplate_lines_ignored": note.get("boilerplate_lines_ignored", 0),
            "notes_count": note.get("notes_count", 0),
            "last_note_date": note.get("last_note_date"),
            "days_since_last_note": note.get("days_since_last_note"),
            "median_gap_days": note.get("median_gap_days"),
            "max_gap_days": note.get("max_gap_days"),
            "distinct_csms_recent": note.get("distinct_csms_recent"),
            "csm_notes_considered": note.get("csm_notes_considered", 0),
            "csm_recent_sequence": note.get("csm_recent_sequence", []),
            "attendee_last": note.get("attendee_last"),
            "seniority_drift": note.get("seniority_drift", False),
            "stuck_action_items": note.get("stuck_action_items", []),
            "data_flags": sorted(set(flags)),
        }
        score_account(account)
        accounts.append(account)

    accounts.sort(key=lambda a: (-a["attention_score"], -a["arr"]))
    findings = build_findings(accounts)

    # Accounts whose drop is attributed to one shared cause are handled as a
    # cohort, not as independent per-account plays. Only a systemic verdict
    # earns this — a "mixed signals" cluster stays in the ranked list.
    cohort_of = {
        n: f
        for f in findings
        if f["kind"] == "shared_usage_cliff" and f["systemic"]
        for n in f["accounts"]
    }
    for a in accounts:
        f = cohort_of.get(a["account_name"])
        if f:
            a["cliff_cohort"] = f["date"]
            a["risk_tags"] = sorted(set(a.get("risk_tags", [])) | {"cliff_cohort"})
        else:
            a["cliff_cohort"] = None

    meta = {
        "as_of": AS_OF.date().isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "crm_rows": int(len(crm)),
        "canonical_accounts": len(accounts),
        "activity_files_ingested": files_ingested,
        "schema_variants": len(schema_variants),
        "unmatched_activity_files": still_unmatched,
        "accounts_without_activity": [
            a["account_name"] for a in accounts if not a.get("usage_data_available")
        ],
        "note_signal": note_meta,
        "file_errors": file_errors,
        "merge_groups": MERGE_GROUPS,
        "arr_policy": "auto: equal→max/once, unequal→sum; Bergstrom override: once from canonical",
        "active_user_policy": "union(last_login<=30d, activity<=30d)",
        "total_arr": sum(a["arr"] for a in accounts),
        "score_weights": {
            "renewal": 25,
            "usage": 25,
            "reliability": 15,
            "adoption": 15,
            "qualitative": 15,
            "stage": 5,
        },
        "findings": findings,
    }
    return accounts, meta


def write_accounts(
    accounts: list[dict[str, Any]],
    meta: dict[str, Any],
    out_path: Path | None = None,
) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = out_path or (OUT_DIR / "accounts.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"meta": meta, "accounts": accounts}, indent=2))
    return out


def main() -> None:
    accounts, meta = build_accounts()
    out = write_accounts(accounts, meta)
    print(f"Wrote {out} ({len(accounts)} accounts)")
    print(f"Total ARR (canonical): ${meta['total_arr']:,.0f}")
    print(f"Activity files ingested: {meta['activity_files_ingested']} | unmatched: {len(meta['unmatched_activity_files'])}")
    print("Top 5:")
    for a in accounts[:5]:
        print(f"  {a['attention_score']:5.1f}  {a['account_name'][:32]:32}  {a['primary_reason'][:60]}")


if __name__ == "__main__":
    main()
