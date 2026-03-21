# TODOS

## P2 - Community tips feed
Read-only list of recent tips from across the org shown on the home screen below action buttons. Pulls from sessions tagged as `tip`. The AI would need to distill the "tip" from the full conversation into a shareable summary.
**Why:** Makes the program feel like shared learning, not a solo experience. Drives engagement.
**Effort:** S (CC: ~30 min)
**Depends on:** Session tagging (v2 scope)

## P2 - Participation streak counter
UI element on home screen: "Week 3 of 12 - 3 sessions this week." Shows program week number, sessions completed this week, and streak indicator.
**Why:** Drives engagement through visibility, gives leadership quick proxy for participation rates before formal progress tracking is built.
**Effort:** S (CC: ~20 min)
**Depends on:** Session tagging (v2 scope)

## P3 - People matching in conversations
Agent proactively uses profile search to suggest relevant colleagues during conversations. E.g., "Sarah in marketing also does WordPress updates and shared a great tip about using AI for SEO."
**Why:** Turns the tool from a solo experience into a network effect. Connects people who can help each other.
**Effort:** M human / S with CC (~30 min)
**Depends on:** Intake completion + enough tip/session data to be useful

## P2 - 12-week progress tracking
Baseline measurement from intake, weekly progress visualization, trend tracking over the program duration.
**Why:** Core program objective - prove the initiative is working, identify who needs help.
**Effort:** L human / M with CC
**Depends on:** Intake design, session tagging

## P2 - Admin dashboard
Org-wide view of participation, proficiency levels, engagement metrics by department.
**Why:** Leadership visibility into program effectiveness.
**Effort:** L human / M with CC
**Depends on:** Progress tracking, intake data

## P3 - Admin UI for department resources
Markdown editor with preview where department leads can edit their function's resources directly in Forge. Changes auto-index into LanceDB.
**Why:** Currently department leads need CLI/S3 access to update resources. This removes the friction.
**Effort:** M human / S with CC
**Depends on:** Department resources (v2 scope)

## P3 - Memory extraction
Periodic Lambda that reads session transcripts and extracts durable facts about users into per-user memory files on S3. Loaded into system prompt at runtime.
**Why:** Captures implicit knowledge from conversation patterns beyond explicit profile data.
**Effort:** M human / S with CC
**Depends on:** Session persistence (already exists)
