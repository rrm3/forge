# Forge Metrics Dashboard

Date: 2026-04-15
Author: Rob McGrath (brainstorm with Claude)
Status: Proposed — awaiting review

## Context

`/forge-analytics` produces weekly narrative reports (MB, project team, app issues) with a per-week `quantitative.md` side file. Deltas are week-vs-previous-week only. Three weeks of data are in flight, with Week 4 underway. There is no multi-week trend view and no visual companion to the written reports.

The MB would benefit from a visual, data-forward artifact that:

* Shows engagement, retention, departments, tools, themes, blockers, sentiment, and ideas as trends across all weeks present.
* Lives in the existing Forge app behind admin auth.
* Lets individual charts be cherry-picked for broader comms, with strict name-handling when they leave the MB audience.
* Supports PDF export for records or sharing.

## Goals

* Cumulative, week-indexed trend data — dashboard expands automatically as new weeks are added.
* Single artifact that serves the MB at full fidelity and broader comms in sanitised form.
* Differential / incremental regeneration: running the skill in Week N only re-processes Week N's inputs.
* Stable categorisation of tools, themes, and blockers across weeks so trend lines mean what they say.

## Non-goals (v1)

* Automated scheduling of the skill.
* App-embedded "regenerate" button.
* Editable taxonomy UI.
* Dark mode.
* Historical snapshot archiving inside the app.
* Per-user drill-downs.
* PostHog event correlation.

## Architecture

Two deliverables, independent:

* **`/forge-trends` skill** (Claude Code, local): consumes existing `/forge-analytics` outputs, emits cumulative `trends.json` + `taxonomy.json`, uploads both to S3.
* **Admin dashboard** in the Forge app at `/admin/reports`: backend admin endpoint fetches from S3, optionally strips names server-side, frontend renders with Chart.js.

```
/forge-analytics  →  data/analytics/reports/week<N>-*  →  /forge-trends
                                                              │
                                                              ▼
                                       s3://forge-production-data/reports/trends.json
                                       s3://forge-production-data/reports/taxonomy.json
                                                              │
                                                              ▼
                                   GET /api/admin/trends?mode=full|shareable
                                                              │
                                                              ▼
                                               /admin/reports (React + Chart.js)
```

## Skill: `/forge-trends`

Trigger: `/forge-trends`, optional `--skip-upload` (iterate locally), `--rebuild` (clean regen, bypass cache).

Prereqs: `data/analytics/reports/week*-metrics.json` and `reports/map/` populated. Skill does not re-run `/forge-analytics`.

### Stages

1. **Discover weeks** — glob `week<N>-metrics.json`, sort ascending.
2. **Load quant metrics** — stack `this_week`, `retention`, `sessions`, `ideas`, `departments` across weeks into time-indexed arrays.
3. **Load taxonomy seed** — `~/.claude/skills/forge-trends/taxonomy-seed.yaml` (tools, themes, blockers, session-activity categories). Also loads prior run's `taxonomy.json` if it exists, as additional seed (carry-forward).
4. **Normalisation pass (LLM)** — one reduce agent per dimension (tools, themes, blockers). Inputs: merged seed + all weeks' map outputs for that dimension. Outputs `taxonomy.json` with `{canonical → [aliases], week_counts[1..N], first_seen_week}`. Agent only proposes new canonicals for items with ≥3 total mentions. **Existing canonicals are immutable** (prompt invariant) to keep trend lines valid.
5. **Per-week aggregation** — deterministic tally against canonical buckets.
6. **Sentiment extraction** — parse `sentiment:` fields already emitted by wrapup batch agents; tally per week per department.
7. **Assemble `trends.json`** — schema in `Data model`.
8. **Upload** — `AWS_PROFILE=forge aws s3 cp` both files to `s3://forge-production-data/reports/` with `text/json`.

### Differential / caching

Cache file: `data/analytics/reports/.trends-cache.json`. Keyed per week by (map-output file list + sizes + mtimes). If a week's inputs are unchanged, its per-week tallies + normalised mention list are reused verbatim. Only the current week (churning between Tuesday and Thursday) is re-normalised on a typical run.

Aggregation (stage 5) merges: prior `trends.json` loaded, current week's slice replaced, any new weeks appended. Older weeks preserved byte-for-byte unless their inputs changed.

`--rebuild` clears the cache for a clean regen.

### Taxonomy evolution rules

* Canonicals never disappear.
* Canonicals never get renamed mid-series.
* New canonicals only added for emergent items with ≥3 mentions in the new week's data.
* `taxonomy.json` includes an `immutable_canonicals: []` array used as a hard invariant in the normaliser agent's prompt.

## Data model: `trends.json`

All name-bearing fields live under `_named`, which the backend strips server-side in shareable mode.

```json
{
  "generated_at": "2026-04-15T21:12:00Z",
  "weeks": [
    {"n": 1, "start": "2026-03-24", "end": "2026-03-30", "label": "Week 1"},
    ...
  ],

  "engagement": {
    "active_users":            [{"week": N, "value": ..., "pct_of_signups": ...}],
    "returning_users":         [{"week": N, "value": ..., "retention_rate": ...}],
    "new_users":               [{"week": N, "value": ...}],
    "dropped_users":           [{"week": N, "value": ...}],
    "sessions_total":          [{"week": N, "value": ...}],
    "messages_total":          [{"week": N, "value": ...}],
    "sessions_per_user_avg":   [{"week": N, "value": ...}],
    "messages_per_session_avg":[{"week": N, "value": ...}],
    "session_type_mix":        [{"week": N, "chat": ..., "wrapup": ..., "stuck": ..., "tip": ...}]
  },

  "cohorts": {
    "weekly_cohort_retention": [
      {"cohort_week": N, "sizes_by_week": [int|null, ...]}
    ]
  },

  "departments": {
    "list": ["Research", "Product", "Sales", ...],
    "active_by_week": [
      {"department": "...", "weekly": [{"week": N, "active": ..., "signups": ...}]}
    ],
    "momentum": [
      {"department": "...", "delta_last_2_weeks": +N, "trend": "accelerating|stalling|steady"}
    ]
  },

  "tools": {
    "canonical": ["Claude", "ChatGPT", ..., "Other"],
    "mentions_by_week": [
      {"tool": "...", "weekly": [int, ...], "first_seen_week": N}
    ],
    "integration_requests_by_week": [
      {"target": "...", "weekly": [int, ...]}
    ]
  },

  "themes": {
    "canonical": ["Coding", "Writing", "Research", "Analysis", "Comms", "Ops", "Other"],
    "activity_by_week": [{"theme": "...", "weekly": [int, ...]}]
  },

  "blockers": {
    "canonical": ["Licensing/access", "Workload/BAU", "Skills gap", "Process/approvals", "Unclear guidance", "Other"],
    "counts_by_week": [{"blocker": "...", "weekly": [int, ...], "status": "resolving|persistent|new"}],
    "persistent": [{"blocker": "...", "weeks_open": N, "affected_depts": [...]}]
  },

  "sentiment": {
    "levels": ["excited", "positive", "neutral", "mixed", "frustrated"],
    "mix_by_week":           [{"week": N, "excited": ..., "positive": ..., "neutral": ..., "mixed": ..., "frustrated": ...}],
    "by_department_by_week": [{"department": "...", "week": N, "avg_score": ...}]
  },

  "ideas": {
    "new_by_week":              [{"week": N, "value": ...}],
    "status_transitions_by_week":[{"week": N, "new_to_exploring": ..., "exploring_to_built": ...}],
    "top_themes_by_week":       [{"week": N, "themes": [{"theme": "...", "count": ...}]}]
  },

  "_named": {
    "top_active_users_by_week":[{"week": N, "users": [{"user_id": "...", "name": "...", "department": "...", "sessions": ...}]}],
    "team_standouts_by_week":  [{"week": N, "manager": "...", "department": "...", "active": ..., "note": "..."}],
    "attributed_quotes":       [{"week": N, "user_id": "...", "name": "...", "department": "...", "sentiment": "...", "quote": "..."}],
    "progression_stories":     [{"user_id": "...", "name": "...", "department": "...", "arc": "..."}]
  }
}
```

`weeks[]` is the x-axis source of truth. Frontend enumerates it and builds the axis dynamically.

## Backend: `GET /api/admin/trends`

* Route: `GET /api/admin/trends?mode=full|shareable`, default `full`.
* Auth: existing admin dependency (same gate as `/admin/users`).
* Fetch `s3://forge-production-data/reports/trends.json` via boto3 (`forge` profile in prod).
* If `mode=shareable`:
  * Drop `_named` entirely.
  * Roll departments with <10 org-chart members into "Other (fewer than 10 staff)" across `departments.active_by_week`, `departments.momentum`, `sentiment.by_department_by_week`.
* Return with `Cache-Control: no-store`.
* In-memory cache: 60s TTL keyed by `(etag, mode)`.
* Missing-object error: return 404 with `{error: "No trends report uploaded yet"}`.
* File: `backend/api/reports.py`, registered in the admin router.

`taxonomy.json` uploaded alongside but not exposed through any endpoint — inspection-only for Rob.

## Frontend: `/admin/reports`

Mounted in `AdminLayout.tsx`, added as a "Reports" item in the admin sidebar. Single-scroll, top-down layout.

### Page structure

```
Header
  Title + subtitle
  Mode toggle (Full names ⇄ Shareable)     — triggers refetch
  Week range slider
  Department multi-select
  Download PDF button                       — enabled only in shareable mode

Engagement        — TrendChart (active users + retention %) + SparklineRow (sessions/user, msgs/session, avg length)
Cohorts           — CohortHeatmap (triangular)
Departments       — SlopeChart across weeks + QuadrantScatter (size vs. momentum)
Tools             — StackedArea + MoversList (top 3 risers/fallers)
Themes            — 100%-normalised StackedBar per week
Blockers          — GroupedBar + BlockerStatusList (status badges)
Sentiment         — DivergingStackedBar per week
Ideas             — TrendChart (new ideas + % progressing)

Full mode only:
Top active users  — Leaderboard
Progression       — StoryCards
Quotes            — QuoteCards grouped by sentiment
```

### Data flow

* Mount: `GET /api/admin/trends?mode={mode}`. Single fetch.
* Mode toggle: refetch (names never live in the browser when in shareable mode).
* Week range + department filters: client-side filtering of the already-fetched payload.
* Dev iteration: `?fixture=1` loads from `public/trends.sample.json` so frontend work can proceed before the S3 file exists.
* Empty-state banner per section when <2 weeks present.

### PDF export

* Button click: if `mode !== 'shareable'`, prompt to switch, refetch, then `window.print()`. Else `window.print()` directly.
* `@media print` rules in `print.css`: hide header controls, expand main column, `break-inside: avoid` on chart cards, nil tooltips.
* `@page { size: landscape }` CSS hint; user can override in the browser print dialog.
* Only way to produce a PDF is via shareable-mode data that never contained names.

### Styling (Forge design system applied)

All charts route through `chartTheme.ts`. Palette, typography, spacing, radii pulled from `DESIGN.md` tokens.

* **Bars:** `#159AC9` (primary). Ramp fades older weeks to 60-80% opacity, latest week at 100%. `borderRadius: 4`.
* **Overlay line + markers:** `#D97706` (warning/amber) as the designated accent. White-fill markers with 2px amber border, enlarged on hover.
* **Gridlines:** `#E2E8F0` (border); axis text `#64748B` (text muted); axis titles `#4A5568` (text secondary).
* **Card shell:** `#FAFBFC` with `1px solid #E2E8F0`, `border-radius: 14px`, `padding: 24px`, no shadow.
* **Title / subtitle above each chart:** title `xl` / Satoshi 600; subtitle `sm` / Satoshi 400 / muted.
* **Summary tiles below time-series charts:** equal-width grid, `md` gutters, `border-radius: 10px`. Headline: `2xl` / Geist Mono 600. Secondary metric: `xs` / Satoshi 500 / muted.
* **Numeric text:** Geist Mono with tabular-nums throughout (axes, tooltips, tiles, tables).
* **Tooltip:** dark rounded pill, reveals in 100ms (Forge `micro`).
* **Chart entry animation:** 300ms ease-out (Forge `medium`). Disabled on `prefers-reduced-motion`.

**Sentiment palette (diverging):**

* frustrated `#DC2626` (error)
* mixed `#D97706` (warning)
* neutral `#94A3B8` (text placeholder)
* positive `#159AC9` (primary)
* excited `#1287B3` (primary hover)

**Heatmap ramp:** 5 steps from `#E8F4F8` (primary subtle) to `#1287B3`.

**Scatter / quadrant:** teal fill at 70% with primary-hover border; guidelines in `#E2E8F0`.

### Chart libraries

Stay Chart.js. Add plugins only where needed:

* `chart.js` (^4.x)
* `react-chartjs-2`
* `chartjs-chart-matrix` — cohort heatmap
* `chartjs-plugin-annotation` — quadrant guidelines, blocker status markers

Slope chart and streamgraph-like stacked area implemented as custom Chart.js configs (no extra deps).

Bundle impact ~60-80KB gzipped, code-split behind `React.lazy` since only admins land here.

### File layout

```
frontend/src/components/admin/reports/
  ReportsView.tsx
  chartTheme.ts
  charts/
    TrendChart.tsx
    SparklineRow.tsx
    CohortHeatmap.tsx
    SlopeChart.tsx
    QuadrantScatter.tsx
    StackedArea.tsx
    StackedBar100.tsx
    GroupedBar.tsx
    DivergingStackedBar.tsx
  panels/
    Leaderboard.tsx
    StoryCards.tsx
    QuoteCards.tsx
    MoversList.tsx
    BlockerStatusList.tsx
  hooks/
    useTrendsData.ts
    useFilters.ts
  print.css
```

## Privacy model

* Full mode: names visible in leaderboard, progression stories, attributed quotes, team standouts.
* Shareable mode: server strips `_named` block entirely before responding; small departments rolled into "Other (fewer than 10 staff)".
* PDF export only permitted from shareable-mode data (toggle enforced in UI; data enforced server-side).
* Admin auth gates both modes.

## Testing

**Skill:**

* Idempotency: run twice, `taxonomy.json` byte-identical.
* Differential: touch one new week only, confirm older weeks' slices unchanged in `trends.json` (hash compare).
* `--rebuild` produces functionally equivalent output to the incremental path (modulo LLM noise in new-canonical naming).

**Backend:**

* `?mode=shareable` transform unit test: fixture with `_named` + small-dept entries → `_named` absent, small depts rolled up.
* Auth: non-admin → 403.
* Missing object → 404 with the expected payload.

**Frontend:**

* Fixture-driven dev (`?fixture=1`) lets visual iteration run ahead of real data.
* Mode toggle round-trip: full ↔ shareable three times, assert named sections mount/unmount and PDF button enables/disables.
* Print preview checked at A4 portrait and US Letter.
* Manual screenshot pass in shareable mode to confirm no names leak.

## Rollout order

1. Skill built. Run once locally against Weeks 1-3. Inspect `trends.json`.
2. Backend endpoint + auth gate. Deploy to staging.
3. Frontend with fixture. Iterate with a design review.
4. Wire frontend to real endpoint on staging.
5. Run skill against prod data, upload to S3, verify on staging.
6. Promote to production.

No feature flag — admin-only route, invisible to non-admins.

## Open questions

None blocking. Secondary plugins for slope charts or streamgraph may swap in later; starting with pure Chart.js + matrix + annotation.

## Out of scope (v1)

Listed above under Non-goals.
