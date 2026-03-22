---
difficulty: beginner
---

# AI for HR

## Context

The People team of 25 is responsible for recruiting, onboarding, payroll, HR operations, employee experience, culture initiatives, and process improvement. The team uses Bob for HR management, DocuSign for automated HR processes, and standard ATS tools for recruitment. Notably, the People team includes Ash McDonagh, the AI Capability Lead driving AI adoption across Digital Science.

This guide covers practical AI applications for the People team's daily work, with special attention to the ethical considerations that come with using AI in people-related decisions.

## Recruitment

Recruitment is one of the clearest applications of AI in HR, but it requires careful handling to avoid bias.

### Job Description Drafting

"Draft a job description for a [role title] in the [department] team at Digital Science. The role involves: [key responsibilities]. Requirements include: [must-haves].

Use inclusive language. Avoid gendered words and unnecessary jargon. Keep it under 500 words. Include a section on what Digital Science offers (research technology company, AI-native culture, AI Tuesdays learning program). Do not include 'nice-to-haves' that could discourage qualified candidates from applying."

**Bias check:**
After drafting, ask a second AI prompt: "Review this job description for biased language. Check for: gendered words, unnecessary requirements that could exclude diverse candidates, culturally specific assumptions, and ageist language. Suggest alternatives for any issues found."

This two-step process (draft then review) catches issues that a single prompt might not.

### Interview Questions

"Generate 8 behavioural interview questions for a [role title] position. Focus on:
* [Key competency 1]: e.g., collaboration in remote teams
* [Key competency 2]: e.g., problem-solving with incomplete information
* [Key competency 3]: e.g., managing stakeholder expectations

For each question, include: the competency being assessed, what a strong answer looks like, and one follow-up question to probe deeper."

**Structured interview design:**
"Create a structured interview scorecard for [role]. For each competency, define: the question, a 1-5 rating scale with specific descriptions for scores 1, 3, and 5. This ensures all interviewers evaluate candidates consistently."

### Candidate Communication

"Draft a [rejection / offer / next-steps] email for a candidate who interviewed for [role]. Key points: [include specific details]. Tone: warm, professional, respectful of their time. If this is a rejection, provide brief constructive encouragement without making promises."

## Onboarding

### Onboarding Content Generation

"Create a one-page welcome guide for a new [role] joining the [department] team. Include:
* Their first week schedule and key meetings
* People they should meet in their first month (suggest typical roles, I will fill in names)
* Tools and systems they will need access to
* Key resources and documentation to review
* What success looks like in their first 90 days
Keep it friendly and practical, not overwhelming."

**Customizing onboarding by role type:**
"Adapt this generic onboarding template for a [technical/non-technical] role joining from [internal transfer/external hire]. Highlight what is different about Digital Science's culture and ways of working, including our AI Tuesdays initiative."

### Policy and FAQ Generation

"Based on these policy documents: [paste or summarize key policies], create a new employee FAQ covering the 15 most common questions new hires ask about: leave policies, benefits, expense reporting, working hours and flexibility, equipment and tools, and professional development."

"Update this existing policy FAQ to include information about AI Tuesdays: What it is, when it happens, what is expected, and where to find resources."

## Employee Experience

### Survey Analysis

When employee surveys come back with hundreds of open-text responses, AI can help you find the signal:

"Here are 150 open-text responses from our quarterly pulse survey question: 'What one thing would most improve your work experience?' Analyze these responses:
* Group into themes with frequency counts
* For each theme, provide 2-3 representative quotes
* Identify any themes that are specific to certain departments or locations
* Flag any responses that suggest urgent action is needed
* Summarize the top 3 findings in a paragraph suitable for a leadership briefing"

**Sentiment tracking:**
"Compare these survey results to last quarter's: [paste both]. What has improved? What has declined? Are there emerging concerns that were not present last quarter?"

### Internal Communications

"Draft an all-company email announcing [policy change / new initiative / organizational update]. The key message is: [state the core message]. Important context: [add background].
Tone: transparent, direct, and human. Avoid corporate-speak. Acknowledge any concerns employees might have. Keep it under 300 words."

"Write a Slack message for the People team channel sharing this week's AI Tuesday tip. The tip is about [topic]. Keep it casual and encouraging. Under 100 words."

## HR Analytics

"Here is our attrition data by department for the past year: [paste data]. Analyze:
* Which departments have the highest and lowest attrition rates?
* Are there seasonal patterns?
* How do our rates compare to typical tech/research industry benchmarks?
* What questions should we be asking to understand the underlying causes?
Do not make causal claims without evidence. Present this as patterns worth investigating, not conclusions."

"Calculate the cost-per-hire for our last 10 hires using this data: [recruiter time, job board fees, interview hours, onboarding costs]. Compare across roles and sources. Where are we spending the most and getting the best results?"

## Process Optimization

The People team, like many HR functions, has significant manual process work that AI can help streamline.

**Identifying automation candidates:**
Follow the same Process Automation Audit approach as the Operations team:
1. List every task you do weekly
2. Score each by: time spent, repetitiveness, and rule-based vs. judgment-based
3. High-scoring tasks are your automation targets

**Common HR automations:**
* **Leave request processing:** AI can draft approval/denial responses based on policy rules and balance availability
* **Reference check compilation:** AI can summarize reference check responses into a structured format
* **Meeting preparation:** Before 1:1s with managers, AI can summarize recent team metrics, open action items, and notable events
* **Learning and development tracking:** AI can compile training completion data and identify gaps

## Ethical Considerations for AI in HR

The People team has the highest stakes when it comes to responsible AI use, because AI decisions about hiring, evaluation, and employee experience directly affect people's lives and livelihoods.

**Hard rules:**

* **Never use AI to make final hiring decisions.** AI can help you draft descriptions, generate questions, and organize data. The decision to hire, reject, or promote must be made by humans.
* **Never use AI to evaluate individual employee performance.** AI can help you draft performance documents or analyze aggregate trends. It should not rate or rank individual employees.
* **Always disclose when AI assisted in creating candidate-facing materials.** Job descriptions drafted with AI are fine as long as a human reviewed them. AI-generated interview feedback that was not verified by the interviewer is not fine.
* **Be especially careful with AI bias in recruitment.** AI models can amplify historical biases in hiring data. If an AI tool suggests screening criteria, check whether those criteria could disproportionately exclude any group.

**GDPR and employee data:**
* Do not paste individual employee names, salaries, performance data, or personal details into external AI tools
* Use anonymized or aggregated data for AI analysis
* If analyzing survey responses, remove any identifiable information before processing

## Supporting AI Adoption Across the Organization

As the team that includes the AI Capability Lead, the People team plays a crucial role in supporting the rest of the organization through AI Tuesdays.

**Change management for AI adoption:**
* Monitor how employees feel about AI adoption (tool overwhelm, role anxiety, excitement)
* Provide coaching support for managers dealing with team resistance (use the A.A.A. framework from the Manager's Guide: Acknowledge, Audit, Align)
* Celebrate and share success stories across the organization
* Connect employees who are struggling with Accountability Partners or additional support

## Try This Today

1. Take a job description your team posted recently (or is about to post)
2. Paste it into an AI tool
3. Ask for a bias review: "Check this job description for biased language, unnecessary requirements, and anything that might discourage diverse candidates."
4. Review the suggestions. How many valid issues did the AI find?
5. Rewrite the description incorporating the best suggestions
6. Share the before/after comparison in #AI-Tuesdays

This is exactly the People team's first AI Tuesday activity: the "AI-Assisted Job Description Workshop." Bring a real role and work through the full cycle of drafting, reviewing for bias, and generating interview questions.
