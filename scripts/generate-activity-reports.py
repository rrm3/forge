#!/usr/bin/env python3
"""Generate per-user activity reports for the My Team and Activity Log views.

Produces one JSON file per user in data/analytics/reports/activity/{user_id}.json.
Each file contains participation data and privacy-sanitized weekly summaries.

Uses Opus via Bedrock (AWS profile: forge) with parallel workers.

Usage:
  # Full run (all users, 10 parallel workers)
  python3 scripts/generate-activity-reports.py

  # Incremental (only users with new activity since last run)
  python3 scripts/generate-activity-reports.py --incremental

  # Single user
  python3 scripts/generate-activity-reports.py --user <user_id>

  # Dry run
  python3 scripts/generate-activity-reports.py --dry-run

  # Specific week only
  python3 scripts/generate-activity-reports.py --week 3

  # Custom parallelism
  python3 scripts/generate-activity-reports.py --workers 20

  # Upload to S3 after generation
  python3 scripts/generate-activity-reports.py --upload
"""

import argparse
import glob
import json
import os
import sys
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone

import boto3

# ── Program constants ────────────────────────────────────────────────────────

PROGRAM_START_DATE = date(2026, 3, 24)
CURRENT_WEEK_MAX = 12

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "analytics")
REPORTS_DIR = os.path.join(DATA_DIR, "reports", "activity")
META_FILE = os.path.join(REPORTS_DIR, "_generation_meta.json")

QUARANTINE_DOMAINS = {"holtzbrinck.com"}

MODEL_ID = "us.anthropic.claude-opus-4-6-v1"


def _week_date_range(week: int) -> tuple[str, str]:
    start = PROGRAM_START_DATE + timedelta(weeks=week - 1)
    end = start + timedelta(days=7)
    return start.isoformat(), end.isoformat()


def _current_program_week() -> int:
    today = date.today()
    days = (today - PROGRAM_START_DATE).days
    return max(1, min(days // 7 + 1, CURRENT_WEEK_MAX))


# ── Data loading ─────────────────────────────────────────────────────────────

def load_profiles() -> dict[str, dict]:
    profiles = {}
    profile_dir = os.path.join(DATA_DIR, "dynamodb", "profiles")
    for f in glob.glob(os.path.join(profile_dir, "*.json")):
        try:
            with open(f) as fh:
                p = json.load(fh)
            uid = p.get("user_id", "")
            email = p.get("email", "")
            domain = email.split("@")[-1] if "@" in email else ""
            if domain in QUARANTINE_DOMAINS:
                continue
            if uid:
                profiles[uid] = p
        except Exception as e:
            print(f"  Warning: bad profile {f}: {e}", file=sys.stderr)
    return profiles


def load_sessions() -> dict[str, list[dict]]:
    by_user: dict[str, list[dict]] = defaultdict(list)
    sessions_dir = os.path.join(DATA_DIR, "dynamodb", "sessions")
    for f in glob.glob(os.path.join(sessions_dir, "*.json")):
        try:
            with open(f) as fh:
                s = json.load(fh)
            uid = s.get("user_id", "")
            if uid:
                by_user[uid].append(s)
        except Exception:
            pass
    return dict(by_user)


def load_user_ideas() -> dict[str, list[dict]]:
    by_user: dict[str, list[dict]] = defaultdict(list)
    ideas_dir = os.path.join(DATA_DIR, "dynamodb", "user-ideas")
    for f in glob.glob(os.path.join(ideas_dir, "*.json")):
        try:
            with open(f) as fh:
                idea = json.load(fh)
            uid = idea.get("user_id", "")
            if uid:
                by_user[uid].append(idea)
        except Exception:
            pass
    return dict(by_user)


def load_tips() -> dict[str, list[dict]]:
    """Load all tips with full content, grouped by author user_id."""
    by_user: dict[str, list[dict]] = defaultdict(list)
    tips_dir = os.path.join(DATA_DIR, "dynamodb", "tips")
    for f in glob.glob(os.path.join(tips_dir, "*.json")):
        try:
            with open(f) as fh:
                tip = json.load(fh)
            uid = tip.get("author_id", "") or tip.get("user_id", "")
            if uid:
                by_user[uid].append(tip)
        except Exception:
            pass
    return dict(by_user)


def load_collabs() -> dict[str, list[dict]]:
    """Load all collaborations with full content, grouped by author_id."""
    by_user: dict[str, list[dict]] = defaultdict(list)
    collabs_dir = os.path.join(DATA_DIR, "dynamodb", "collabs")
    if not os.path.isdir(collabs_dir):
        return dict(by_user)
    for f in glob.glob(os.path.join(collabs_dir, "*.json")):
        try:
            with open(f) as fh:
                collab = json.load(fh)
            uid = collab.get("author_id", "")
            if uid:
                by_user[uid].append(collab)
        except Exception:
            pass
    return dict(by_user)


# ── Per-user participation extraction ────────────────────────────────────────

def extract_participation(
    user_id: str,
    sessions: list[dict],
    ideas: list[dict],
    tips: list[dict],
    collabs: list[dict],
    max_week: int,
    intake_weeks: dict | None = None,
) -> dict[int, dict]:
    """Extract per-week participation facts for a user. No LLM needed."""
    weeks: dict[int, dict] = {}
    intake_weeks = intake_weeks or {}

    for w in range(1, max_week + 1):
        week_start, week_end = _week_date_range(w)

        def _in_week(item: dict) -> bool:
            """Check if item falls in this week by date range OR program_week field."""
            ts = item.get("created_at", "")[:10]
            if ts >= week_start and ts < week_end:
                return True
            # Fallback: check program_week field (handles pre-program sessions)
            pw = item.get("program_week")
            if pw is not None and str(pw) == str(w):
                return True
            return False

        week_sessions = [s for s in sessions if _in_week(s)]
        intake_sessions = [s for s in week_sessions if s.get("type") == "intake"]
        wrapup_sessions = [s for s in week_sessions if s.get("type") == "wrapup"]
        other_sessions = [s for s in week_sessions if s.get("type") not in ("intake", "wrapup")]

        # Also check intake_weeks from profile as source of truth
        intake_from_profile = str(w) in intake_weeks

        week_ideas = [i for i in ideas if _in_week(i)]
        week_tips = [t for t in tips if _in_week(t)]
        week_collabs = [c for c in collabs if _in_week(c)]

        if not week_sessions and not intake_from_profile:
            continue

        # Build full tip descriptions for the LLM
        tip_details = []
        for t in week_tips:
            category = t.get("category", "tip")
            title = t.get("title", "")
            content = t.get("content", "")
            summary = t.get("summary", "")
            votes = t.get("vote_count", 0)
            tip_details.append({
                "title": title,
                "category": category,
                "content": content or summary,
                "votes": int(votes) if votes else 0,
            })

        # Build full collab descriptions for the LLM
        collab_details = []
        for c in week_collabs:
            collab_details.append({
                "title": c.get("title", ""),
                "problem": c.get("problem", ""),
                "needed_skills": c.get("needed_skills", []),
                "status": c.get("status", ""),
                "interested_count": int(c.get("interested_count", 0)),
            })

        weeks[w] = {
            "intake_completed": len(intake_sessions) > 0 or intake_from_profile,
            "wrapup_completed": len(wrapup_sessions) > 0,
            "session_count": len(week_sessions),
            "other_session_count": len(other_sessions),
            "message_count": sum(int(s.get("message_count", 0)) for s in week_sessions),
            "ideas_count": len(week_ideas),
            "tips_shared": len(week_tips),
            "collabs_started": len(week_collabs),
            "tip_titles": [t.get("title", "") for t in week_tips if t.get("title")],
            "idea_titles": [i.get("title", "") for i in week_ideas if i.get("title")],
            "collab_titles": [c.get("title", "") for c in week_collabs if c.get("title")],
            # Full content for LLM (not stored in final report)
            "_tip_details": tip_details,
            "_collab_details": collab_details,
        }

    return weeks


# ── LLM summary generation ──────────────────────────────────────────────────

SUMMARY_PROMPT = """You are generating a brief, factual activity summary for a manager report. This summary will be visible to the employee's direct manager and to the employee themselves.

**Privacy rules (STRICT):**
- Report ONLY what the person worked on and accomplished
- Do NOT include: mood, sentiment, emotional state, personal reflections, frustrations
- Do NOT include: AI proficiency assessments, skill evaluations, or performance judgments
- Do NOT include: coaching notes, tone observations, or personality observations
- Do NOT include: recommendations for improvement or what they should try next
- Do NOT mention features they haven't used or things they didn't do
- Frame everything as factual reporting of self-reported activity
- Use neutral, non-evaluative language throughout

**Input data:**
Name: {name}
Week: {week}

Digest (AI companion's notes from all sessions that week):
{digest}

Tips shared with colleagues this week:
{tips}

Collaborations proposed this week:
{collabs}

**Output format - respond with ONLY a JSON object, no markdown fences:**
{{
  "plan": "1-2 sentences summarizing what they planned to work on this week. Use 'No plan recorded' if unknown.",
  "accomplished": "2-3 sentences summarizing what they actually worked on and produced. Use 'No activity recorded' if unknown.",
  "insights": ["Array of brief factual notes worth flagging to a manager. Include: tips shared (with title), collaborations proposed (with title), blockers reported, tools or access needed. Empty array if nothing notable. Max 4 items."]
}}"""


def generate_summary(
    bedrock_client,
    name: str,
    week: int,
    digest_text: str,
    tip_details: list[dict],
    collab_details: list[dict],
) -> dict:
    """Use Opus via Bedrock to generate a privacy-sanitized summary."""
    digest_display = digest_text if digest_text else "(No digest available)"

    # Format tips for prompt
    if tip_details:
        tips_text = "\n".join(
            f'- [{t["category"].upper()}] "{t["title"]}": {t["content"][:200]}... ({t["votes"]} votes)'
            if len(t["content"]) > 200
            else f'- [{t["category"].upper()}] "{t["title"]}": {t["content"]} ({t["votes"]} votes)'
            for t in tip_details
        )
    else:
        tips_text = "(None this week)"

    # Format collabs for prompt
    if collab_details:
        collabs_text = "\n".join(
            f'- "{c["title"]}": {c["problem"][:200]}... (status: {c["status"]}, {c["interested_count"]} interested)'
            if len(c.get("problem", "")) > 200
            else f'- "{c["title"]}": {c.get("problem", "")} (status: {c["status"]}, {c["interested_count"]} interested)'
            for c in collab_details
        )
    else:
        collabs_text = "(None this week)"

    prompt = SUMMARY_PROMPT.format(
        name=name,
        week=week,
        digest=digest_display,
        tips=tips_text,
        collabs=collabs_text,
    )

    try:
        resp = bedrock_client.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 512,
                "messages": [{"role": "user", "content": prompt}],
            }),
            contentType="application/json",
        )
        result = json.loads(resp["body"].read())
        text = result["content"][0]["text"].strip()

        # Parse JSON from response (handle possible markdown fences)
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(text)
    except Exception as e:
        print(f"  Warning: LLM summary failed for {name} week {week}: {e}", file=sys.stderr)
        return {
            "plan": "Summary generation failed",
            "accomplished": "Summary generation failed",
            "insights": [],
        }


# ── Report assembly ──────────────────────────────────────────────────────────

def load_digest(user_id: str, week: int) -> str:
    for path in [
        os.path.join(DATA_DIR, "digests", f"digest-week{week}", f"{user_id}.md"),
        os.path.join(DATA_DIR, "s3", "profiles", user_id, f"digest-week{week}.md"),
    ]:
        if os.path.exists(path):
            with open(path) as f:
                return f.read()
    return ""


def build_user_report(
    bedrock_client,
    user_id: str,
    profile: dict,
    sessions: list[dict],
    ideas: list[dict],
    tips: list[dict],
    collabs: list[dict],
    max_week: int,
    target_week: int | None = None,
    existing_report: dict | None = None,
) -> dict | None:
    name = profile.get("name", "Unknown")

    participation = extract_participation(
        user_id, sessions, ideas, tips, collabs, max_week,
        intake_weeks=profile.get("intake_weeks"),
    )

    if not participation:
        return None

    if existing_report and existing_report.get("weeks"):
        report_weeks = existing_report["weeks"]
    else:
        report_weeks = {}

    weeks_to_process = [target_week] if target_week else sorted(participation.keys())

    for w in weeks_to_process:
        if w not in participation:
            continue

        p = participation[w]

        # Extract LLM-only fields before building the stored report
        tip_details = p.pop("_tip_details", [])
        collab_details = p.pop("_collab_details", [])

        # Load digest as primary source
        digest_text = load_digest(user_id, w)

        # Generate sanitized summary via Opus
        summary = generate_summary(
            bedrock_client, name, w, digest_text, tip_details, collab_details
        )

        report_weeks[str(w)] = {
            "intake_completed": p["intake_completed"],
            "wrapup_completed": p["wrapup_completed"],
            "session_count": p["session_count"],
            "other_session_count": p["other_session_count"],
            "message_count": p["message_count"],
            "ideas_count": p["ideas_count"],
            "tips_shared": p["tips_shared"],
            "collabs_started": p["collabs_started"],
            "tip_titles": p["tip_titles"],
            "idea_titles": p["idea_titles"],
            "collab_titles": p["collab_titles"],
            "plan": summary.get("plan", ""),
            "accomplished": summary.get("accomplished", ""),
            "insights": summary.get("insights", []),
        }

    return {
        "user_id": user_id,
        "name": name,
        "title": profile.get("title", ""),
        "department": profile.get("department", ""),
        "team": profile.get("team", ""),
        "manager": profile.get("manager", ""),
        "avatar_url": profile.get("avatar_url", ""),
        "weeks": report_weeks,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "last_activity": max(
            (s.get("updated_at", "") for s in sessions),
            default="",
        ),
    }


# ── Incremental logic ───────────────────────────────────────────────────────

def load_generation_meta() -> dict:
    if os.path.exists(META_FILE):
        with open(META_FILE) as f:
            return json.load(f)
    return {"last_run": None, "user_timestamps": {}}


def save_generation_meta(meta: dict):
    os.makedirs(os.path.dirname(META_FILE), exist_ok=True)
    with open(META_FILE, "w") as f:
        json.dump(meta, f, indent=2)


def user_needs_update(user_id: str, sessions: list[dict], meta: dict) -> bool:
    last_ts = meta.get("user_timestamps", {}).get(user_id, "")
    if not last_ts:
        return True
    latest_activity = max(
        (s.get("updated_at", "") for s in sessions),
        default="",
    )
    return latest_activity > last_ts


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate activity reports for My Team / Activity Log.")
    parser.add_argument("--incremental", action="store_true", help="Only process users with new activity")
    parser.add_argument("--user", type=str, help="Process a single user ID")
    parser.add_argument("--week", type=int, help="Process only a specific week")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed without generating")
    parser.add_argument("--upload", action="store_true", help="Upload generated reports to S3 after generation")
    parser.add_argument("--workers", type=int, default=10, help="Number of parallel workers (default: 10)")
    args = parser.parse_args()

    max_week = _current_program_week()
    print(f"Activity Report Generation (model: {MODEL_ID})")
    print(f"  Current program week: {max_week}")
    print(f"  Output: {REPORTS_DIR}")
    print()

    # Load all data
    print("Loading data...")
    profiles = load_profiles()
    all_sessions = load_sessions()
    all_ideas = load_user_ideas()
    all_tips = load_tips()
    all_collabs = load_collabs()
    tip_count = sum(len(v) for v in all_tips.values())
    collab_count = sum(len(v) for v in all_collabs.values())
    print(f"  {len(profiles)} profiles, {sum(len(v) for v in all_sessions.values())} sessions")
    print(f"  {tip_count} tips, {collab_count} collabs")

    # Determine which users to process
    meta = load_generation_meta()
    users_to_process = []

    if args.user:
        if args.user in profiles:
            users_to_process = [args.user]
        else:
            print(f"Error: User {args.user} not found in profiles", file=sys.stderr)
            sys.exit(1)
    else:
        for uid in profiles:
            sessions = all_sessions.get(uid, [])
            if not sessions:
                continue
            if args.incremental and not user_needs_update(uid, sessions, meta):
                continue
            users_to_process.append(uid)

    print(f"  {len(users_to_process)} users to process" +
          (" (incremental)" if args.incremental else ""))
    print()

    if args.dry_run:
        for uid in users_to_process[:20]:
            p = profiles[uid]
            print(f"  Would process: {p.get('name', uid)} ({p.get('department', '?')})")
        if len(users_to_process) > 20:
            print(f"  ... and {len(users_to_process) - 20} more")
        return

    # Bedrock via AWS profile forge
    boto_session = boto3.Session(profile_name="forge")

    os.makedirs(REPORTS_DIR, exist_ok=True)
    processed = 0
    skipped = 0
    errors = 0
    _lock = threading.Lock()
    _start_time = datetime.now()

    def process_user(uid: str) -> tuple[str, str, str | None]:
        """Process one user. Returns (uid, status, detail)."""
        # Each thread gets its own Bedrock client
        bedrock = boto_session.client("bedrock-runtime", region_name="us-east-1")

        profile = profiles[uid]
        name = profile.get("name", uid)
        sessions = all_sessions.get(uid, [])
        ideas = all_ideas.get(uid, [])
        tips = all_tips.get(uid, [])
        collabs = all_collabs.get(uid, [])

        # Load existing report for incremental updates
        report_file = os.path.join(REPORTS_DIR, f"{uid}.json")
        existing = None
        if args.incremental and os.path.exists(report_file):
            try:
                with open(report_file) as f:
                    existing = json.load(f)
            except Exception:
                pass

        try:
            report = build_user_report(
                bedrock, uid, profile, sessions, ideas, tips, collabs,
                max_week,
                target_week=args.week,
                existing_report=existing,
            )
            if report is None:
                return uid, "skipped", None

            with open(report_file, "w") as f:
                json.dump(report, f, indent=2)

            with _lock:
                meta.setdefault("user_timestamps", {})[uid] = report["last_activity"]

            dept = profile.get("department", "?")
            weeks_str = ",".join(sorted(report["weeks"].keys()))
            return uid, "ok", f"{name} ({dept}) - weeks [{weeks_str}]"

        except Exception as e:
            return uid, "error", f"{name}: {e}"

    workers = args.workers
    print(f"Processing with {workers} parallel workers...\n")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(process_user, uid): uid for uid in users_to_process}
        for future in as_completed(futures):
            uid, status, msg = future.result()
            if status == "ok":
                processed += 1
                print(f"  OK: {msg}")
            elif status == "skipped":
                skipped += 1
            else:
                errors += 1
                print(f"  ERROR: {msg}", file=sys.stderr)

            done = processed + skipped + errors
            if done % 50 == 0:
                elapsed = (datetime.now() - _start_time).total_seconds()
                rate = done / elapsed if elapsed > 0 else 0
                eta = (len(users_to_process) - done) / rate if rate > 0 else 0
                print(f"  ... {done}/{len(users_to_process)} ({processed} ok, {skipped} skip, {errors} err) "
                      f"[{rate:.1f}/s, ~{eta:.0f}s remaining]")

    # Save metadata
    meta["last_run"] = datetime.now(timezone.utc).isoformat()
    save_generation_meta(meta)

    elapsed = (datetime.now() - _start_time).total_seconds()
    print()
    print(f"Done in {elapsed:.0f}s: {processed} processed, {skipped} skipped, {errors} errors")
    print(f"Reports: {REPORTS_DIR}")

    # Upload to S3 if requested
    if args.upload and processed > 0:
        bucket = "forge-production-data"
        s3 = boto_session.client("s3", region_name="us-east-1")
        uploaded = 0
        print(f"\nUploading to s3://{bucket}/reports/activity/...")
        for uid in users_to_process:
            report_file = os.path.join(REPORTS_DIR, f"{uid}.json")
            if os.path.exists(report_file):
                s3_key = f"reports/activity/{uid}.json"
                s3.upload_file(report_file, bucket, s3_key, ExtraArgs={"ContentType": "application/json"})
                uploaded += 1
        print(f"  Uploaded {uploaded} reports to S3")


if __name__ == "__main__":
    main()
