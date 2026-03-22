---
difficulty: intermediate
---

# AI for Product Discovery

## Context

The Product team of 57 people, including product managers, UX designers, data analysts, and curators, defines what Digital Science builds. Several team members are already working specifically on AI-powered product features: Marta Ondresik as Director of Product for Central & AI, Norman Morrison on AI Solutions, and Stuart Tucker on Writefull's AI writing tools.

AI Tuesdays is an opportunity for the entire Product team to develop fluency with AI tools, not just as features to ship, but as instruments in the product development process itself. This guide focuses on using AI to accelerate product discovery: the research, synthesis, and ideation work that precedes building.

## User Research Synthesis

Product managers and UX researchers conduct interviews, usability tests, and survey analysis. The synthesis step, turning raw qualitative data into actionable insights, is where AI creates the most leverage.

**Interview transcript analysis:**
After a batch of user interviews, you often have hours of transcripts to process. Instead of manual coding and affinity mapping:

1. Upload transcripts to NotebookLM or paste them into Claude
2. Ask: "Analyze these 8 user interview transcripts. Identify:
   * The top 5 recurring themes across all interviews
   * Direct quotes that best illustrate each theme
   * Points where users disagreed or had conflicting needs
   * Any surprising insights that appeared in fewer than 3 interviews but seem significant"
3. Review the themes against your own reading of the transcripts. AI often surfaces patterns you noticed subconsciously but had not articulated.

**Survey open-text analysis:**
For large survey responses with open-text fields:
"Here are 200 open-text responses to the question 'What would make Overleaf more useful for your research workflow?' Categorize these into themes, count the frequency of each theme, and provide 3 representative quotes per theme. Identify any themes that are unique to specific user segments (faculty vs. students, STEM vs. humanities)."

**Competitive analysis:**
"I am evaluating [competitor product] as part of product discovery for [DS product]. Based on publicly available information, analyze:
* Their core value proposition and target users
* Key features and how they compare to our current offering
* Areas where they are ahead of us
* Areas where we have advantages
* Recent product changes or announcements that signal their strategic direction"

**Important note:** AI competitive analysis uses training data that may be outdated. Always verify with current competitor websites, recent press releases, and direct product usage.

## PRD and Requirements Drafting

AI can accelerate the structured writing that product managers do weekly.

**First draft of a PRD:**
"Draft a Product Requirements Document for the following feature: [describe the feature, the problem it solves, and the target users].

Include sections for:
* Problem statement (with specific user pain points)
* Proposed solution (high-level)
* User stories (5-7 key stories in 'As a [user], I want [action], so that [benefit]' format)
* Success metrics (how we will know this feature is working)
* Out of scope (what this feature deliberately does NOT do)
* Technical considerations (what the engineering team should know)
* Risks and open questions"

Then refine: "The user stories need more specificity. The target user is a university librarian managing institutional accounts for Figshare. They need to manage user provisioning, track storage usage, and generate reports for their administration."

**Requirements review:**
After drafting, use AI as a critical reviewer:
"Review this PRD as if you are a senior engineer who will build this feature. What questions would you have? What is ambiguous? What edge cases are not addressed? What technical constraints might I be missing?"

## Data-Driven Product Decisions

Data analysts on the Product team can use AI to move faster from question to insight.

**Metric exploration:**
"Here is our product usage data for Overleaf over the past quarter: [paste or describe the data]. What does this data tell us about:
* Feature adoption trends
* User engagement patterns (daily vs. weekly users)
* Areas of the product that are underused
* Potential retention risks"

**A/B test design:**
"I am planning an A/B test for a new onboarding flow in Dimensions. The current onboarding has a 35% completion rate. My hypothesis is that a guided tour will increase this. Help me design the test:
* What should the control and variant be?
* What metrics should I track (primary and secondary)?
* How long should the test run given [approximate daily traffic]?
* What minimum detectable effect should I set?"

**Cohort analysis:**
"Write a SQL query or Python script for a cohort analysis of Overleaf users. Group by sign-up month, track monthly active usage over 12 months, and calculate retention rates by cohort. I want to understand if recent cohorts retain better or worse than older ones."

## Rapid Prototyping and Feasibility

Understanding what AI can realistically do is critical for product managers defining AI features. AI Tuesdays is the time to build this intuition.

**Understanding AI capabilities:**
Before writing requirements for an AI feature, test the core capability yourself:
1. If you are considering an AI summarization feature for ReadCube, try summarizing 10 research papers using Claude and note the quality
2. If you are considering an AI search feature for Dimensions, try asking natural language questions about research data and see how well AI translates them to structured queries
3. If you are considering an AI writing assistant for Overleaf, test how well AI handles LaTeX and academic writing conventions

This firsthand experience prevents you from specifying features that are beyond current AI capabilities or underestimating what is possible.

**Rapid prototyping tools:**
The Product team has identified several tools for quick prototyping during Phase 2:
* **Lovable:** Generates working web application prototypes from descriptions. A PM can go from "I want a dashboard that shows grant funding by institution" to a working prototype in minutes.
* **Claude Code:** Can build functional prototypes of AI features, including the prompts, data processing, and UI.
* **Google AI Studio:** Good for testing prompt-based features before engineering builds them properly.

**Prototype testing workflow:**
1. Build a quick prototype of the AI feature using one of these tools
2. Test it with 5-10 users (internal or external)
3. Document what worked, what confused users, and what the AI got wrong
4. Use findings to refine requirements before handing to engineering

## Product Teardown Exercise

The first AI Tuesday activity for the Product team is an "AI Product Teardown."

**How to run it:**
1. Each PM or designer picks an AI feature from a competitor or adjacent product (Semantic Scholar, Elicit, Scite, Research Rabbit, or non-academic tools like Notion AI, Perplexity)
2. Spend 30 minutes using it intensively. Try normal use cases and edge cases.
3. Document:
   * What works well about the AI UX?
   * What is confusing or frustrating?
   * How do they handle errors or low-confidence results?
   * What design patterns could we adopt for DS products?
4. Present findings to the team
5. Collectively build a "DS AI Feature Patterns" reference doc

## Evaluating AI Feature Quality

As PMs shipping AI features, you need frameworks for evaluating quality. This goes beyond traditional feature QA.

**Key evaluation dimensions:**
* **Accuracy:** Does the AI give correct information? What is the error rate?
* **Consistency:** Does it give similar quality output for similar inputs?
* **Latency:** How long does the user wait? What is acceptable?
* **Failure modes:** When it fails, does it fail gracefully? Does it tell the user it is uncertain?
* **Bias:** Does the AI perform equally well across languages, disciplines, and user types?
* **User trust:** Do users understand what the AI is doing? Do they trust the output appropriately (neither too much nor too little)?

**Setting quality bars:**
"For this feature, I need the AI to be correct at least [X]% of the time. Below that, users will lose trust. Above [Y]%, the feature becomes reliable enough that users start depending on it, which means failures become more costly."

## Try This Today

1. Pick a product decision you are currently making or a feature you are exploring
2. Upload your relevant research materials (interview transcripts, survey data, competitor analysis) into NotebookLM
3. Ask it to synthesize the key themes and identify the strongest evidence for different product directions
4. Compare the AI synthesis to your own analysis
5. Note where AI surfaced something you had not considered
6. Share your experience in #AI-Tuesdays

For data analysts: Pick a product question you have been meaning to investigate. Describe it in natural language to an AI tool and ask it to generate the analysis code. Run the code and validate the results.
