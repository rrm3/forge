#!/usr/bin/env bash
# Upload regenerated digests to S3 production bucket.
# Only uploads digests for users in the regen list.

set -euo pipefail

WEEK="${1:-3}"
INPUT="${2:-/tmp/regen-digest-users.txt}"
BUCKET="forge-production-data"
DIGEST_DIR="$(cd "$(dirname "$0")/.." && pwd)/data/analytics/digests/digest-week${WEEK}"

export AWS_PROFILE=forge

total=$(wc -l < "$INPUT" | tr -d ' ')
echo "Uploading Week $WEEK digests for $total users to s3://$BUCKET/"

uploaded=0
skipped=0
failed=0

while IFS=$'\t' read -r user_id name; do
    local_file="$DIGEST_DIR/$user_id.md"
    s3_path="s3://$BUCKET/profiles/$user_id/digest-week${WEEK}.md"

    if [ ! -f "$local_file" ]; then
        echo "SKIP (no local file): $name ($user_id)"
        skipped=$((skipped + 1))
        continue
    fi

    # Always upload, including carry-forward digests. The wrap-up agent's
    # _load_previous_digest (backend/agent/wrapup_context.py) reads exactly
    # one S3 key (digest-week<N-1>.md) with no fallback to earlier weeks.
    # If we skip carry-forwards here, returning users without new activity
    # this week start their next wrap-up with no prior-week context loaded
    # into the system prompt.

    if aws s3 cp "$local_file" "$s3_path" --quiet 2>/dev/null; then
        uploaded=$((uploaded + 1))
    else
        echo "FAIL: $name ($user_id)"
        failed=$((failed + 1))
    fi
done < "$INPUT"

echo ""
echo "Done. Uploaded: $uploaded, Skipped: $skipped, Failed: $failed (of $total)"
