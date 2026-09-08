#!/usr/bin/env python3
"""Account Attention Hub — Streamlit UI."""

from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from ingest import build_accounts, write_accounts

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_PATH = DATA_DIR / "accounts.json"
UPLOAD_META_PATH = DATA_DIR / "upload_meta.json"
PACKET_LIVE = DATA_DIR / "packet_live"

st.set_page_config(
    page_title="Account Attention Hub",
    layout="wide",
)

TIER_COLOR = {"red": "#B42318", "amber": "#B54708", "green": "#027A48"}


def load_upload_meta() -> dict | None:
    if not UPLOAD_META_PATH.exists():
        return None
    try:
        return json.loads(UPLOAD_META_PATH.read_text())
    except Exception:
        return None


def save_upload_meta(meta: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_META_PATH.write_text(json.dumps(meta, indent=2))


@st.cache_data
def load_data(mtime: float):
    if not DATA_PATH.exists():
        return None
    return json.loads(DATA_PATH.read_text())


def fmt_arr(v: float) -> str:
    if v >= 1_000_000:
        return f"${v/1_000_000:.2f}M"
    if v >= 1_000:
        return f"${v/1_000:.0f}K"
    return f"${v:,.0f}"


TAG_LABELS = {
    "renewal_soon": "Renewal soon",
    "renewal_overdue": "Renewal overdue",
    "onboarding_stalled": "Onboarding stalled",
    "champion_risk": "Champion risk",
    "seasonal_low": "Seasonal low",
    "expansion": "Expansion",
    "competitor": "Competitor",
    "security_stuck": "Security / SSO stuck",
    "bot_heavy": "Bot-heavy usage",
    "usage_unknown": "No activity data",
    "no_recent_contact": "No recent contact",
    "csm_churn": "CSM turnover",
    "seniority_drift": "Seniority drift",
    "stuck_action_item": "Stuck action item",
    "cliff_cohort": "Shared usage cliff",
}

NOTE_TAG_LABELS = {
    "champion_leaving": "Champion may be leaving",
    "competitor": "Competitor mentioned",
    "security_stuck": "Blocked on security / SSO",
    "writeback_gap": "Write-back gap",
    "seasonal_low": "Seasonal / slow season",
    "expansion": "Expansion interest",
}


def fmt_note_tag(tag: str) -> str:
    return NOTE_TAG_LABELS.get(tag, tag.replace("_", " ").capitalize())


def fmt_renewal(a: dict) -> str:
    if not a.get("renewal_date"):
        return "unknown"
    d = a.get("days_to_renewal")
    if d is None:
        return a["renewal_date"]
    if d < 0:
        return f"{a['renewal_date']} (overdue {abs(int(d))}d)"
    return f"{a['renewal_date']} ({int(d)}d)"


FACTOR_COLUMN_MAX = {
    "Renew pts": 25,
    "Usage pts": 25,
    "Adoption pts": 15,
    "Reliab. pts": 15,
    "Relationship pts": 15,
    "Stage pts": 5,
}
FACTOR_COLUMNS = list(FACTOR_COLUMN_MAX)

DRIVER_SHORT = {
    "Renewal urgency": "Renewal",
    "Usage health": "Usage",
    "Reliability": "Reliability",
    "Seat adoption": "Adoption",
        "Relationship health": "Relationship",
    "Stage risk": "Stage",
}


def fmt_drivers(a: dict, top_n: int = 3) -> str:
    """Top contributing factors with points, e.g. 'Renewal 19 · Usage 16 · Adoption 14'."""
    breakdown = a.get("score_breakdown") or []
    parts = [
        f"{DRIVER_SHORT.get(row['factor'], row['factor'])} {row['points']:g}"
        for row in breakdown[:top_n]
        if row.get("points")
    ]
    return " · ".join(parts)


def fmt_tags(tags: list | None) -> str:
    if not tags:
        return ""
    return ", ".join(TAG_LABELS.get(t, t.replace("_", " ")) for t in tags)


def labeled_rows(rows: list[tuple[str, object]]) -> None:
    display_rows = []
    for label, value in rows:
        if value is None or value == "" or value == []:
            display = "—"
        elif isinstance(value, list):
            display = ", ".join(str(v) for v in value)
        elif isinstance(value, bool):
            display = "yes" if value else "no"
        else:
            display = str(value)
        display_rows.append({"Field": label, "Value": display})
    st.dataframe(
        pd.DataFrame(display_rows),
        width="stretch",
        hide_index=True,
        height=min(52 + 35 * len(display_rows), 320),
    )


def find_packet_root(extracted: Path) -> Path:
    """Accept zip rooted at packet/ or with crm_export.csv at top level."""
    if (extracted / "crm_export.csv").exists():
        return extracted
    direct = extracted / "candidate_packet"
    if (direct / "crm_export.csv").exists():
        return direct
    matches = list(extracted.rglob("crm_export.csv"))
    if len(matches) == 1:
        return matches[0].parent
    if matches:
        # Prefer shallowest
        matches.sort(key=lambda p: len(p.parts))
        return matches[0].parent
    raise FileNotFoundError(
        "Zip must contain crm_export.csv (packet root or candidate_packet/)."
    )


def apply_accounts_json(upload_bytes: bytes, filename: str) -> None:
    payload = json.loads(upload_bytes.decode("utf-8"))
    if "accounts" not in payload or "meta" not in payload:
        raise ValueError("JSON must be an accounts export with `accounts` and `meta`.")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(payload, indent=2))
    save_upload_meta(
        {
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "source_filename": filename,
            "kind": "accounts_json",
            "as_of": payload.get("meta", {}).get("as_of"),
            "canonical_accounts": len(payload.get("accounts") or []),
        }
    )


def apply_packet_zip(upload_bytes: bytes, filename: str, as_of_day: date | None) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        zip_path = tmp_path / "upload.zip"
        zip_path.write_bytes(upload_bytes)
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)
        packet_root = find_packet_root(extract_dir)

        # Replace live packet on disk so rebuilds are reproducible from last upload
        if PACKET_LIVE.exists():
            shutil.rmtree(PACKET_LIVE)
        PACKET_LIVE.mkdir(parents=True, exist_ok=True)
        shutil.copytree(packet_root, PACKET_LIVE, dirs_exist_ok=True)

    # None lets the pipeline read the as-of off the data itself
    as_of = (
        datetime(
            as_of_day.year, as_of_day.month, as_of_day.day, 23, 59, 59, tzinfo=timezone.utc
        )
        if as_of_day is not None
        else None
    )
    with st.spinner("Ingesting uploaded packet…"):
        accounts, meta = build_accounts(packet_dir=PACKET_LIVE, as_of=as_of)
        write_accounts(accounts, meta, out_path=DATA_PATH)

    save_upload_meta(
        {
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "source_filename": filename,
            "kind": "packet_zip",
            "as_of": meta["as_of"],
            "as_of_source": meta.get("as_of_source"),
            "canonical_accounts": len(accounts),
            "packet_path": str(PACKET_LIVE),
        }
    )


def active_upload_meta(meta: dict) -> dict | None:
    """Upload metadata, but only when it actually describes the loaded dataset.

    Rebuilding from the bundled packet leaves the old upload record on disk,
    which otherwise keeps advertising a stale filename and as-of date.
    """
    um = load_upload_meta()
    if not um:
        return None
    packet_dir = meta.get("packet_dir") or ""
    if packet_dir and Path(packet_dir) != PACKET_LIVE:
        return None
    if um.get("as_of") and meta.get("as_of") and um["as_of"] != meta["as_of"]:
        return None
    return um


def render_upload_bar(data_as_of: date | None = None, meta: dict | None = None) -> None:
    upload_meta = active_upload_meta(meta or {})
    # Collapsed by default: it is a once-a-day action, not something the reader
    # needs open while working the list.
    with st.expander("Daily data refresh", expanded=False):
        st.caption(
            "Upload today’s nightly dump to replace the active dataset. "
            "Accepts a **packet ZIP** (`crm_export.csv`, `activity_exports/`, "
            "`seat_provisioning.json`, `call_notes/`) or a pre-built **accounts.json**."
        )
        c1, c2 = st.columns([3, 1])
        with c1:
            uploaded = st.file_uploader(
                "Upload data",
                type=["zip", "json"],
                label_visibility="collapsed",
                key="data_upload",
            )
        with c2:
            auto_as_of = st.checkbox(
                "As-of from data",
                value=True,
                help=(
                    "Reads the reporting date off the newest activity in the upload. "
                    "Uncheck to set it manually."
                ),
            )
            as_of_day = st.date_input(
                "As-of date",
                value=data_as_of or date.today(),
                disabled=auto_as_of,
                help="Only used when 'As-of from data' is unchecked.",
            )
        if auto_as_of:
            as_of_day = None

        if upload_meta:
            st.caption(
                f"Active data: **{upload_meta.get('source_filename')}** · "
                f"as-of **{data_as_of or '—'}** · "
                f"loaded {upload_meta.get('uploaded_at', '')[:19].replace('T', ' ')} UTC"
            )
        else:
            st.caption(
                f"Using the bundled packet · as-of **{data_as_of or '—'}** "
                "· upload a ZIP to replace it."
            )

        apply = st.button("Apply upload", type="primary", disabled=uploaded is None)
        if apply and uploaded is not None:
            try:
                raw = uploaded.getvalue()
                name = uploaded.name or "upload"
                if name.lower().endswith(".json"):
                    apply_accounts_json(raw, name)
                else:
                    apply_packet_zip(raw, name, as_of_day)
                load_data.clear()
                st.success(f"Applied **{name}**. Hub now reads from this upload.")
                st.rerun()
            except Exception as e:
                st.error(f"Upload failed: {e}")


def render_findings(findings: list[dict]) -> None:
    """Patterns that span accounts, shown above the ranking.

    A per-account list makes one pipeline break look like five churn risks.
    These read the portfolio sideways so the reader sees the event, not the
    symptoms.
    """
    if not findings:
        return

    systemic_n = sum(1 for f in findings if f.get("systemic"))
    title = f"What the data is telling you ({len(findings)})"
    if systemic_n:
        title += f" — {systemic_n} needing action before the list"
    with st.expander(title, expanded=True):
        render_findings_body(findings)


def render_findings_body(findings: list[dict]) -> None:
    st.caption(
        "Patterns that cut across accounts. These are detected from the data on "
        "every refresh, not hand-written, so they update with each upload."
    )

    for f in findings:
        systemic = f.get("systemic")
        members = f.get("members") or []
        with st.container(border=True):
            st.markdown(f"**{f['headline']}**")
            (st.warning if systemic else st.info)(f["verdict"])
            st.markdown("\n".join(f"- {e}" for e in f.get("evidence", [])))
            st.markdown(f"**Do this:** {f['action']}")

            if members:
                # The cohort is worked as one item, so it gets one table rather
                # than five rows scattered through a list of per-account plays.
                rows = [
                    {
                        "Account": m["account"],
                        "ARR": m["arr"],
                        "Owner": m.get("owner") or "—",
                        "Renewal": fmt_renewal(m),
                        "Usage drop": f"{abs(m['drop_pct']):.0f}%",
                        "Users kept": f"{m['users_retained']}/{m['users_before']}",
                        "Dropped on": m["date"],
                    }
                    for m in members
                ]
                st.dataframe(
                    pd.DataFrame(rows),
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "ARR": st.column_config.NumberColumn("ARR", format="$%,d")
                    },
                )
                st.caption(
                    "These are held out of the ranked list below — the list is for "
                    "per-account plays, and this is one investigation."
                )
            else:
                names = f.get("accounts", [])
                if names:
                    st.caption("Accounts: " + ", ".join(names))


def main() -> None:
    st.title("Account Attention Hub")

    # Load first so the upload bar can show the dataset's real as-of instead of
    # today's date — one as-of value on the screen, taken from the data.
    mtime = DATA_PATH.stat().st_mtime if DATA_PATH.exists() else 0.0
    data = load_data(mtime)
    meta = (data or {}).get("meta", {})
    data_as_of = None
    if meta.get("as_of"):
        try:
            data_as_of = date.fromisoformat(meta["as_of"])
        except ValueError:
            data_as_of = None

    render_upload_bar(data_as_of, meta)

    if data is None:
        st.error("No active dataset yet. Upload a packet ZIP or accounts.json above.")
        st.stop()

    accounts = data["accounts"]
    upload_meta = active_upload_meta(meta)

    caption_bits = [
        f"As-of **{meta['as_of']}**",
        f"{meta['canonical_accounts']} canonical accounts",
        "batch export only",
    ]
    if meta.get("as_of_source"):
        caption_bits.append(f"as-of from {meta['as_of_source']}")
    st.caption(" · ".join(caption_bits))

    # Portfolio summary
    total_arr = meta.get("total_arr") or sum(a["arr"] for a in accounts)
    red_arr = sum(a["arr"] for a in accounts if a.get("risk_tier") == "red")
    n_onb = sum(1 for a in accounts if (a.get("stage") or "").lower() == "onboarding")
    n_ren = sum(
        1
        for a in accounts
        if a.get("days_to_renewal") is not None and a["days_to_renewal"] <= 90
    )

    with st.expander("Portfolio summary", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Portfolio ARR", fmt_arr(total_arr))
        c2.metric("ARR in red tier", fmt_arr(red_arr))
        c3.metric("Onboarding", n_onb)
        c4.metric("Renewing ≤90d", n_ren)

    render_findings(meta.get("findings", []))

    cohort = [a for a in accounts if a.get("cliff_cohort")]
    with st.expander("Ranked attention list", expanded=True):
        filtered = render_ranked_list(accounts, cohort)

    with st.expander("Account drilldown", expanded=True):
        render_drilldown(filtered, cohort, meta)

    render_data_trust(meta, upload_meta)


def render_ranked_list(accounts: list[dict], cohort: list[dict]) -> list[dict]:
    if cohort:
        show_cohort = st.checkbox(
            f"Also rank the {len(cohort)} shared-cliff accounts here",
            value=False,
            help=(
                "Off by default: their drop has one shared cause, so they are "
                "handled as a cohort above. Turn on to audit how they would score "
                "if treated as independent accounts."
            ),
        )
    else:
        show_cohort = True

    ranked = accounts if show_cohort else [a for a in accounts if not a.get("cliff_cohort")]
    if cohort and not show_cohort:
        st.caption(
            f"{len(cohort)} accounts ({fmt_arr(sum(a['arr'] for a in cohort))}) are "
            "held out and handled in the shared-cliff block above."
        )

    owners = sorted({a.get("owner") or "—" for a in ranked})
    stages = sorted({a.get("stage") or "—" for a in ranked})

    f1, f2, f3, f4 = st.columns(4)
    owner_f = f1.multiselect("Owner", owners)
    stage_f = f2.multiselect("Stage", stages, default=[])
    table_order = f3.selectbox(
        "Table order",
        [
            "Attention score (default)",
            "ARR: high → low",
            "ARR: low → high",
            "Account: A → Z",
        ],
        help="Reorders the table only. #, Score, Tier, Primary reason, and Tags stay the same.",
    )
    at_risk = f4.checkbox("At-risk only (red + amber)", value=False)

    filtered = ranked
    if owner_f:
        filtered = [a for a in filtered if a.get("owner") in owner_f]
    if stage_f:
        filtered = [a for a in filtered if a.get("stage") in stage_f]
    if at_risk:
        filtered = [a for a in filtered if a.get("risk_tier") in {"red", "amber"}]

    # # = attention rank within the current filter (stable even if table is sorted by ARR)
    rows = []
    for rank, a in enumerate(filtered, start=1):
        f = a.get("score_factors") or {}
        rows.append(
            {
                "#": rank,
                "Account": a["account_name"],
                "ARR": a["arr"],
                "Stage": a.get("stage"),
                "Owner": a.get("owner"),
                "Renewal": fmt_renewal(a),
                "Score": a.get("attention_score"),
                "Tier": a.get("risk_tier"),
                "Renew pts": f.get("renewal"),
                "Usage pts": f.get("usage"),
                "Adoption pts": f.get("adoption"),
                "Reliab. pts": f.get("reliability"),
                "Relationship pts": f.get("qualitative"),
                "Stage pts": f.get("stage"),
                "Score drivers": fmt_drivers(a),
                "Data": "full" if a.get("usage_data_available", True) else "no activity",
                "Primary reason": a.get("primary_reason"),
                "Tags": fmt_tags(a.get("risk_tags")),
                "_id": a["account_id_canonical"],
            }
        )
    df = pd.DataFrame(rows)

    st.caption(f"**{len(df)} accounts**")
    st.caption(
        "Highest-attention accounts first by default. **Score** (max 100) is the sum of six factors: "
        "renewal urgency (≤25), usage health (≤25), reliability (≤15), seat adoption (≤15), "
        "relationship health (≤15, from note cadence / CSM turnover / attendee seniority / stuck items), "
        "onboarding stage (≤5). **Score drivers** shows the top three factors "
        "with their points, so a lower-ARR account can outrank a bigger one when adoption, "
        "reliability, or usage are worse. Sorting only changes row order — # and Score stay fixed."
    )
    if df.empty:
        st.info("No accounts match filters.")
        return filtered

    show_factor_cols = st.checkbox(
        "Show points for every factor",
        value=False,
        help="Adds one numeric column per scoring factor so you can sort and compare drivers directly.",
    )

    show = df.copy()
    if table_order == "ARR: high → low":
        show = show.sort_values("ARR", ascending=False, kind="mergesort")
    elif table_order == "ARR: low → high":
        show = show.sort_values("ARR", ascending=True, kind="mergesort")
    elif table_order == "Account: A → Z":
        show = show.sort_values("Account", ascending=True, key=lambda s: s.str.lower(), kind="mergesort")
    show = show.drop(columns=["_id"])
    if not show_factor_cols:
        show = show.drop(columns=FACTOR_COLUMNS)

    factor_config = {
        col: st.column_config.NumberColumn(
            format="%.0f",
            help=f"Points earned out of {cap} for this factor",
        )
        for col, cap in FACTOR_COLUMN_MAX.items()
    }

    # Keep ARR numeric so dataframe header sort is numeric (not lexicographic on "$1,005,000")
    st.dataframe(
        show,
        width="stretch",
        hide_index=True,
        column_config={
            "ARR": st.column_config.NumberColumn(
                format="$%,.0f",
                help="Annual recurring revenue",
            ),
            "Score": st.column_config.NumberColumn(
                format="%.1f", help="Sum of all six factors (max 100)"
            ),
            "Score drivers": st.column_config.TextColumn(
                width="medium",
                help="Top three factors contributing to the score, with points earned",
            ),
            "Data": st.column_config.TextColumn(
                help="'no activity' means no usage export matched — usage and reliability are unknown, not zero",
            ),
            "#": st.column_config.NumberColumn(
                help="Attention rank (unchanged when sorting by ARR or Account)"
            ),
            **factor_config,
        },
        height=420,
    )
    return filtered


def render_drilldown(filtered: list[dict], cohort: list[dict], meta: dict) -> None:
    # Held-out cohort accounts stay inspectable — they are out of the ranking,
    # not out of the tool.
    drill = filtered + [a for a in cohort if a not in filtered]
    if not drill:
        st.info("No accounts match the current filters.")
        return
    labels = [
        f"{a['account_name']}  ·  {a['attention_score']}  ·  {a['risk_tier']}"
        + ("  ·  shared cliff" if a.get("cliff_cohort") else "")
        for a in drill
    ]
    choice = st.selectbox("Select account", labels, index=0)
    acct = drill[labels.index(choice)]

    tier = acct.get("risk_tier", "green")
    st.markdown(
        f"### {acct['account_name']}  "
        f"<span style='color:{TIER_COLOR.get(tier, '#333')};font-size:0.85em'>"
        f"{tier.upper()} · score {acct['attention_score']}</span>",
        unsafe_allow_html=True,
    )
    st.write(f"**Primary reason:** {acct.get('primary_reason')}")

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("ARR", fmt_arr(acct["arr"]))
    has_usage = acct.get("usage_data_available", True)
    if has_usage:
        # Signed percentage so the arrow and colour follow the actual direction.
        # A "prior N" label reads as non-negative and renders green-up on a decline.
        pct = acct.get("usage_delta_pct")
        d2.metric(
            "Runs 30d",
            acct.get("runs_30d", 0),
            delta=(
                f"{pct:+.1f}% vs prior 30d ({acct.get('runs_prior_30d', 0)})"
                if pct is not None
                else None
            ),
        )
        err = acct.get("error_rate_30d")
        d4.metric("Error rate 30d", f"{err:.0%}" if err is not None else "—")
    else:
        d2.metric("Runs 30d", "no data")
        d4.metric("Error rate 30d", "no data")
    util = acct.get("seat_utilization")
    d3.metric("Human seat util", f"{util:.0%}" if util is not None else "—")

    if not has_usage:
        st.warning(
            "No activity export matched this account, so usage and reliability are **unknown, not zero**. "
            "Seat activity below is based on logins only and understates real use."
        )

    delta = acct.get("usage_delta_pct")
    delta_display = f"{delta:+.1f}%" if delta is not None else None

    left, right = st.columns(2)
    with left:
        st.markdown("**Identity**")
        labeled_rows(
            [
                ("Canonical ID", acct["account_id_canonical"]),
                ("Merged IDs", acct.get("merged_account_ids")),
                ("Merged names", acct.get("merged_names")),
                ("Vertical", acct.get("vertical")),
                ("Owner", acct.get("owner")),
                ("Stage", acct.get("stage")),
                ("Contract start", acct.get("contract_start")),
                ("Renewal", fmt_renewal(acct)),
            ]
        )
        st.markdown("**Why this rank**")
        breakdown = acct.get("score_breakdown") or []
        if breakdown:
            total = acct.get("attention_score", 0)
            st.caption(
                f"Attention score **{total}** = sum of six factors (max **100**). "
                "Each row is what we observed and how many points it contributed toward that factor’s max."
            )
            bd = pd.DataFrame(
                [
                    {
                        "Factor": row["factor"],
                        "What we saw": row["observation"],
                        "Points": f"{row['points']:g} / {row['max_points']}",
                    }
                    for row in breakdown
                ]
            )
            st.dataframe(bd, width="stretch", hide_index=True, height=260)
            st.markdown(
                """
**How points are earned**
- **Renewal:** closer or overdue renewal, especially at higher ARR → more points
- **Usage:** low or falling real-user usage → more points
- **Reliability:** higher run failure rate → more points
- **Seat adoption:** fewer licensed seats active, or bot-heavy traffic → more points
- **Relationship health:** slipping meeting cadence, CSM turnover, less senior attendees, or action items still open across several meetings → more points
- **Stage:** still onboarding with weak usage → more points
"""
            )
        else:
            for line in acct.get("evidence_lines") or []:
                st.write(f"- {line}")
            weights = meta.get("score_weights") or {}
            if weights:
                st.caption(
                    "Max weights: " + ", ".join(f"{k}≤{v}" for k, v in weights.items())
                )

    with right:
        st.markdown("**Seats & usage**")
        labeled_rows(
            [
                ("Licensed seats", acct.get("licensed_seats")),
                ("Provisioned seats", acct.get("provisioned_seats")),
                ("Human provisioned", acct.get("human_provisioned")),
                ("Human active (30d)", acct.get("human_active_30d")),
                ("Usage vs prior 30d", delta_display),
                ("Bot-heavy usage", acct.get("bot_heavy")),
            ]
        )
        st.markdown("**Relationship health** (from note metadata)")
        days_since = acct.get("days_since_last_note")
        cadence = "—"
        if days_since is not None:
            cadence = f"{days_since} days ago"
            if days_since > 14:
                cadence += " (weekly cadence promised)"
        csms = acct.get("distinct_csms_recent")
        csm_display = "—"
        if csms:
            seq = " → ".join(acct.get("csm_recent_sequence") or [])
            csm_display = f"{csms} CSMs across last {acct.get('csm_notes_considered')} meetings ({seq})"
        stuck = acct.get("stuck_action_items") or []
        labeled_rows(
            [
                ("Last note", acct.get("last_note_date")),
                ("Time since last contact", cadence),
                ("Typical gap between notes", 
                 f"{acct['median_gap_days']} days" if acct.get("median_gap_days") else None),
                ("Coverage", csm_display),
                ("Last attendees", acct.get("attendee_last")),
                ("Seniority drift", acct.get("seniority_drift")),
            ]
        )
        if stuck:
            st.markdown("**Stuck items** (same request across multiple meetings)")
            st.markdown(
                "\n".join(
                    f"- {s['item']} — open across {s['occurrences']} meetings "
                    f"({s['first_seen']} → {s['last_seen']})"
                    for s in stuck
                )
            )

        st.markdown("**Note signals**")
        tags = acct.get("note_tags") or []
        quotes = acct.get("note_quotes") or []
        ais = acct.get("open_action_items") or []
        ignored = acct.get("boilerplate_lines_ignored") or 0
        if not tags and not quotes and not ais:
            msg = "No distinctive note signals for this account."
            if ignored:
                msg += f" ({ignored} boilerplate lines ignored.)"
            st.caption(msg)
        else:
            if tags:
                st.markdown("**Flags from notes**")
                st.markdown("\n".join(f"- {fmt_note_tag(t)}" for t in tags))
            if quotes:
                st.markdown("**Excerpts**")
                st.markdown(
                    "\n".join(f"- {q.strip()}" for q in quotes if str(q).strip())
                )
            if ais:
                st.markdown("**Open action items**")
                st.markdown(
                    "\n".join(f"- {ai.strip()}" for ai in ais if str(ai).strip())
                )
            if ignored:
                st.caption(
                    f"{ignored} boilerplate lines ignored (they repeat across many accounts)."
                )
        flags = acct.get("data_flags") or []
        if flags:
            st.warning("Data flags: " + ", ".join(flags))
        if "no_activity_file" in flags:
            logins = acct.get("logins_30d") or 0
            last = acct.get("last_login")
            if logins:
                st.info(
                    f"No activity file matched for this account — but {logins} "
                    f"user(s) logged in during the last 30 days"
                    + (f", most recently {last}" if last else "")
                    + ". Logins come from seat provisioning, so this is an export "
                    "gap rather than a dead account. Usage and error rate are "
                    "unknown here, not zero."
                )
            else:
                st.info(
                    "No activity file matched, and no logins in the last 30 days "
                    "either — genuinely quiet."
                )

        cliff = acct.get("usage_cliff")
        if cliff:
            st.markdown("**Sudden usage drop**")
            kept, before = cliff["users_retained"], cliff["users_before"]
            err_moved = cliff["error_rate_after"] > cliff["error_rate_before"] + 0.02
            st.markdown(
                "\n".join(
                    [
                        f"- Volume fell {abs(cliff['drop_pct']):.0f}% on {cliff['date']} "
                        f"({cliff['runs_per_day_before']:.0f} → "
                        f"{cliff['runs_per_day_after']:.0f} runs/day)",
                        f"- {kept} of {before} users kept running afterwards"
                        + (" — the same people, doing far less" if before and kept / before >= 0.75 else ""),
                        f"- Error rate {cliff['error_rate_before']:.1%} → "
                        f"{cliff['error_rate_after']:.1%}"
                        + ("" if err_moved else " — no failure spike to explain it"),
                        f"- Agents in use {cliff['agents_before']} → {cliff['agents_after']}",
                    ]
                )
            )
            if acct.get("cliff_cohort"):
                st.warning(
                    "This account is part of the shared-cliff cohort, so it is held "
                    "out of the ranked list. Its usage score still reflects the drop "
                    "as if it were account-specific — treat that score as an upper "
                    "bound until the shared cause is ruled in or out."
                )

def render_data_trust(meta: dict, upload_meta: dict | None) -> None:
    # Its own top-level section: Streamlit cannot nest an expander inside one.
    with st.expander("Data trust", expanded=False):
        unmatched = meta.get("unmatched_activity_files") or []
        unmatched_names = (
            [u.get("file", str(u)) for u in unmatched] if unmatched else []
        )
        merges = meta.get("merge_groups") or []
        merge_summary = [
            f"{g.get('canonical')}: {', '.join(g.get('ids') or [])} ({g.get('arr_mode')})"
            for g in merges
        ]
        labeled_rows(
            [
                ("As-of", meta.get("as_of")),
                ("How as-of was set", meta.get("as_of_source")),
                (
                    "Data source",
                    (upload_meta or {}).get("source_filename")
                    or "bundled candidate_packet",
                ),
                ("Last upload", (upload_meta or {}).get("uploaded_at") or "—"),
                ("Activity files ingested", meta.get("activity_files_ingested")),
                ("Schema variants handled", meta.get("schema_variants")),
                ("Unmatched activity files", unmatched_names),
                ("Accounts with no activity export", meta.get("accounts_without_activity") or []),
                (
                    "Boilerplate note lines ignored",
                    (meta.get("note_signal") or {}).get("boilerplate_lines"),
                ),
                (
                    "Distinctive note lines kept",
                    (meta.get("note_signal") or {}).get("distinctive_lines"),
                ),
                ("Parse errors", meta.get("file_errors") or []),
                ("ARR policy", meta.get("arr_policy")),
                ("Active user policy", meta.get("active_user_policy")),
                ("Merge groups", merge_summary),
            ]
        )


if __name__ == "__main__":
    main()
