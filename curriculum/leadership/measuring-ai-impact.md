---
difficulty: intermediate
---

# Measuring AI Impact

## Context

AI Tuesdays is a significant investment: 685 people dedicating 20% of their work week for 12 weeks. Leadership needs to know if this investment is working. This guide covers how to measure the impact of AI adoption at team, department, and organizational levels, and how to track progress without creating a bureaucratic reporting burden.

The Success Measures document defines three categories of success: Engagement, Productivity Impact, and Security Impact. This guide provides practical frameworks for measuring each.

## The Success Framework

### Engagement

**Goal:** 80-100% participation in weekly AI Tuesdays.

**What to measure:**
* Participation rate: percentage of employees who actively engaged with AI learning each Tuesday
* Slack activity: posts, reactions, and threads in #AI-Tuesdays
* Showcase participation: who presents, who attends, quality of presentations
* Accountability Partner interactions: are pairs meeting regularly?
* Tool usage: are AI tool login rates increasing week over week?

**How to measure without surveillance:**
Engagement should not feel like attendance tracking. Focus on positive signals rather than monitoring:
* Count contributions to #AI-Tuesdays (posts, shared learnings, questions asked)
* Track showcase sign-ups and attendance
* Ask managers for qualitative assessments in 1:1s
* Use pulse surveys (1-2 questions, monthly) to gauge sentiment

**What good looks like:**
* Week 1-2: 70%+ participation, lots of questions, some confusion
* Week 3-4: 80%+ participation, early success stories, fewer "what do I do?" questions
* Week 5-6: Sustained participation, use cases defined, cross-team collaboration emerging
* Week 7-12: Active project work, tangible outputs, natural AI usage beyond Tuesdays

### Productivity Impact

**Goal:** Each function achieves at least 20% time saving on a validated use case by Week 12.

**What to measure:**
* Time savings: measured in specific workflows (hours per week or per task)
* Output quality: did AI assistance improve the quality, not just the speed?
* Capacity reclaimed: what are people doing with the time they saved?

**How to measure time savings:**
The simplest approach is before-and-after measurement on specific tasks:

1. **Identify the task:** "Monthly financial reconciliation report"
2. **Measure the baseline:** "Currently takes 6 hours per month"
3. **Apply AI:** Build the AI-assisted workflow during AI Tuesdays
4. **Measure the new time:** "Now takes 3.5 hours per month"
5. **Calculate savings:** "2.5 hours saved per month (42% improvement)"

Do this for one or two key tasks per team, not for everything. The goal is validated examples, not comprehensive measurement.

**Validated use case template:**

```
Team: [department]
Process: [name of the workflow]
Before AI:
  * Time per occurrence: [hours]
  * Frequency: [weekly/monthly/quarterly]
  * Annual time investment: [total hours]
After AI:
  * Time per occurrence: [hours]
  * Quality impact: [same/better/tradeoff]
  * AI tool(s) used: [name(s)]
  * Human review still needed: [yes/no, describe]
Time saved: [hours per year]
Equivalent value: [hours x avg hourly cost]
```

Each functional team should submit at least one of these by Week 12.

### Capability Uplift

**Goal:** Improve the company's AI literacy baseline through individual upskilling.

**What to measure:**
* Self-assessed skill level: Basic, Intermediate, Advanced, Expert (measured at Week 1 and Week 12)
* Tool proficiency: number of AI tools people can use effectively
* Prompt sophistication: are people moving beyond simple queries to structured, multi-step prompts?
* Teaching: are people sharing knowledge with colleagues? (A sign of deep learning)

**Measuring skill progression:**
The Getting Started Guide defines four skill levels. Use the same framework for a simple pre/post assessment:

* **Week 1 survey:** "Rate your current AI skill level (Basic/Intermediate/Advanced/Expert)"
* **Week 12 survey:** Same question, plus: "Give one specific example of how you use AI differently now than you did 12 weeks ago"

**Target:** 75% of employees move up at least one proficiency level.

### Security Impact

**Goals:**
* No high-impact security incidents from AI usage
* Staff routinely choose appropriate data sources for AI tools
* Near misses are escalated and learned from quickly

**What to measure:**
* Security incidents related to AI tool usage (target: zero high-impact)
* Near-miss reports and how they were handled (more reports is better, as it means people are paying attention)
* Adherence to data classification guidelines (spot-check through surveys or audits)
* Tool approval compliance (are people using approved tools or going rogue?)

**How to measure:**
* Work with Group IT & Security to track incidents
* Include a security question in monthly pulse surveys: "In the past month, have you been uncertain about whether it was safe to use specific data with an AI tool?" (Yes/No, with follow-up)
* Review the #AI-Tuesdays Slack channel for security questions (high question volume is a good sign)

## Department-Level Metrics

Each department should track metrics specific to their context:

**Technology (219 people):**
* Code generated or assisted by AI tools (percentage of commits with AI assistance)
* Test coverage improvements from AI-generated tests
* Time saved on code review
* AI features shipped in DS products

**Customer (159 people):**
* Average time to draft customer responses (before/after)
* Ticket resolution time changes
* Customer satisfaction scores (holding steady or improving despite faster resolution)
* Data analysis time for research analytics reports

**Sales (75 people):**
* Meeting prep time (before/after)
* Proposal drafting time (before/after)
* Email personalization at scale (outreach volume with maintained quality)
* Pipeline velocity changes

**Product (57 people):**
* Time from research to insight synthesis
* PRD drafting time
* Number of AI feature prototypes tested
* User research analysis throughput

**Marketing (42 people):**
* Content production volume and quality
* Time to produce campaign assets
* Content repurposing efficiency (one piece into multiple formats)
* SEO and analytics reporting time

**Operations (39 people):**
* Process automation count (number of processes partially or fully automated)
* CRM data quality metrics
* RFP response time
* Report generation time

**People (25 people):**
* Job description creation time
* Survey analysis time
* Onboarding material production time
* Recruitment process efficiency

**Finance (24 people):**
* Reconciliation time
* Report generation time
* Month-end close process time
* Manual task hours reduced

## ROI Calculation

For leadership considering the overall return on the AI Tuesdays investment:

**Investment cost:**
```
Salary cost of AI Tuesdays = (average daily salary) x 685 people x 12 Tuesdays
Tool licensing costs = (annual cost of AI tools provided)
Program management costs = (project team time and resources)
Total investment = sum of above
```

**Return (measured at Week 12):**
```
Time savings = sum of all validated use cases across departments
Value of time savings = total hours saved x average hourly cost
Quality improvements = value of improved output (harder to quantify, estimate conservatively)
Revenue impact = any attributable pipeline or deal acceleration from Sales
Total return = sum of above
```

**Break-even analysis:**
If each employee saves just 2 hours per week through AI assistance after the program, that is:
* 685 people x 2 hours x 50 weeks = 68,500 hours per year
* At an average loaded cost of (estimate) per hour, that is significant

Even a modest productivity improvement pays for the program many times over. The goal of measurement is not to prove this mathematically but to demonstrate concrete examples that make the case undeniable.

## Reporting Cadence

**Weekly (Slack):**
* Wins and learnings shared in #AI-Tuesdays
* Quick pulse from managers: "How is your team engaging?"

**Biweekly (leadership summary):**
* Participation rates by department
* Notable success stories (2-3 highlighted)
* Blockers or concerns requiring attention

**Monthly (executive briefing):**
* Engagement metrics trend
* Validated use cases submitted
* Security incidents (or lack thereof)
* Qualitative assessment of culture shift

**Week 12 (final report):**
* Full before/after comparison
* All validated use cases compiled
* Skill level progression analysis
* Recommendations for sustaining momentum post-program

## Common Measurement Mistakes

* **Measuring too much:** If tracking becomes burdensome, people will game it or resent it. Focus on a few meaningful metrics, not comprehensive coverage.
* **Measuring too early:** Weeks 1-3 will show high activity but little measurable productivity impact. That is normal. Productivity gains emerge in Weeks 6-12.
* **Ignoring qualitative signals:** Numbers alone miss the culture shift. Pay attention to how people talk about AI, whether they are helping each other, and whether the energy is positive.
* **Comparing across departments:** Technology will move faster than Finance because of different starting points and data sensitivity constraints. Compare each department to its own baseline, not to other departments.
* **Rewarding only successes:** Teams that tried ambitious experiments and failed may have learned more than teams that picked easy wins. Measure effort and learning, not just results.

## Try This Today

1. Define one specific task in your team that you will use as the baseline measurement for AI Tuesdays
2. Measure how long it takes today (the "before" number)
3. Document this as your team's initial validated use case template (even before the "after" is known)
4. Share the use case with your functional leader so it can be included in the department's AI Tuesdays goals
5. Set a reminder to re-measure the same task at Week 6 and Week 12

Start simple. One good before-and-after measurement is worth more than a dozen vague claims about productivity improvement.
