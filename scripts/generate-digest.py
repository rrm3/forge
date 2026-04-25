#!/usr/bin/env python3
"""Generate a weekly digest for a single user via Bedrock.

Usage: python3 scripts/generate-digest.py --week <N> <user_id> <name>

The --week argument specifies which week's sessions to summarize.
The digest is written to data/analytics/digests/digest-week<N>/<user_id>.md
and will be served to the user at the start of Week N+1.
"""

import argparse
import json
import os
import glob
import sys
from datetime import date, timedelta

import boto3

# AI Tuesdays 12-week program: first Tuesday is March 24, 2026
PROGRAM_START_DATE = date(2026, 3, 24)


def _week_date_range(week: int) -> tuple[str, str]:
    """Return (start_iso, end_iso) for the given program week."""
    start = PROGRAM_START_DATE + timedelta(weeks=week - 1)
    end = start + timedelta(days=7)
    return start.isoformat(), end.isoformat()


def _session_in_week(messages: list[dict], week_start: str, week_end: str) -> bool:
    """Check if any message timestamp falls within the week range."""
    for msg in messages:
        ts = msg.get("timestamp", "")
        if ts and week_start <= ts[:10] < week_end:
            return True
    return False


def main():
    parser = argparse.ArgumentParser(description="Generate a weekly digest for a single user.")
    parser.add_argument("--week", type=int, required=True, help="Program week number to generate digest for")
    parser.add_argument("user_id", help="User ID (UUID)")
    parser.add_argument("name", nargs="+", help="User's display name")
    args = parser.parse_args()

    week = args.week
    user_id = args.user_id
    name = " ".join(args.name)
    week_start, week_end = _week_date_range(week)

    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sessions_dir = os.path.join(base, "data", "analytics", "s3", "sessions", user_id)
    profile_dir = os.path.join(base, "data", "analytics", "s3", "profiles", user_id)
    output_dir = os.path.join(base, "data", "analytics", "digests", f"digest-week{week}")
    output_file = os.path.join(output_dir, f"{user_id}.md")

    # Gather all session transcripts
    all_transcripts = []
    session_files = sorted(glob.glob(os.path.join(sessions_dir, "*.json")))
    for sf in session_files:
        try:
            with open(sf) as f:
                messages = json.load(f)
            # Skip sessions outside the target week
            if not _session_in_week(messages, week_start, week_end):
                continue
            session_id = os.path.basename(sf).replace(".json", "")
            transcript_lines = []
            for msg in messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                if content and role in ("user", "assistant"):
                    speaker = name if role == "user" else "AI Companion"
                    transcript_lines.append(f"[{speaker}]: {content}")
            if transcript_lines:
                all_transcripts.append(f"=== Session {session_id} ===\n" + "\n".join(transcript_lines))
        except Exception as e:
            print(f"Warning: Could not read {sf}: {e}", file=sys.stderr)

    # Gather intake responses
    intake_text = ""
    intake_file = os.path.join(profile_dir, "intake-responses.json")
    if os.path.exists(intake_file):
        try:
            with open(intake_file) as f:
                intake = json.load(f)
            intake_text = f"\n\n=== Intake Responses ===\n{json.dumps(intake, indent=2)}"
        except Exception as e:
            print(f"Warning: Could not read intake: {e}", file=sys.stderr)

    if not all_transcripts:
        print(f"SKIP: No session transcripts found for {name} ({user_id})", file=sys.stderr)
        # Write a minimal digest even for empty sessions
        os.makedirs(output_dir, exist_ok=True)
        with open(output_file, "w") as f:
            f.write(f"# Week {week} Digest: {name}\n\nNo substantive session transcripts were found for Week {week}. The AI companion should start fresh with intake and discovery.\n")
        print(f"OK: Wrote minimal digest for {name} -> {output_file}")
        return

    combined = "\n\n".join(all_transcripts) + intake_text

    # Truncate if extremely long
    if len(combined) > 150000:
        combined = combined[:150000] + "\n\n[... transcript truncated for length ...]"

    next_week = week + 1
    prompt = f"""You are generating a Week {week} digest for {name} in the AI Tuesdays program. This digest will be read by the AI companion at the start of Week {next_week} to pick up where they left off.

Below are ALL of {name}'s session transcripts and intake responses from Week {week}.

{combined}

Write a 200-400 word narrative digest answering: What does the AI companion need to know to pick up where {name} left off next week?

Be specific about:
- Projects they built or explored
- Tools and AI models they used or discussed
- Key reflections, surprises, or concerns they expressed
- Concrete next steps they mentioned or that were suggested
- Features of the AI Tuesdays platform they haven't tried yet (brainstorm, tips, ideas board, etc.)
- Their role, team, and work context (from intake if available)

Write in third person. Be concrete and actionable, not vague. Reference specific things they said or did.

Output ONLY the markdown content (no code fences). Start with:
# Week {week} Digest: {name}

Then a blank line, then the narrative paragraphs."""

    client = boto3.client('bedrock-runtime', region_name='us-east-1')
    resp = client.invoke_model(
        modelId='us.anthropic.claude-sonnet-4-6',
        body=json.dumps({
            'anthropic_version': 'bedrock-2023-05-31',
            'max_tokens': 1024,
            'messages': [{'role': 'user', 'content': prompt}]
        }),
        contentType='application/json'
    )
    result = json.loads(resp['body'].read())
    digest_text = result['content'][0]['text']

    # Ensure it starts with the expected header
    if not digest_text.startswith(f"# Week {week} Digest:"):
        digest_text = f"# Week {week} Digest: {name}\n\n{digest_text}"

    os.makedirs(output_dir, exist_ok=True)
    with open(output_file, "w") as f:
        f.write(digest_text)
        if not digest_text.endswith("\n"):
            f.write("\n")

    print(f"OK: Wrote digest for {name} -> {output_file}")


if __name__ == "__main__":
    main()
