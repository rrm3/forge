---
difficulty: intermediate
---

# AI in UX Design

## Context

The Product team includes 5 Senior UX Designers, 2 Lead UX Designers, a Director of Design, and several curators who shape the user experience of Digital Science products. As AI features become central to our products, designers face a dual challenge: using AI tools to improve their own workflows, and designing AI-powered experiences that users can understand and trust.

This guide covers both sides.

## AI for the Design Process

### Research and Synthesis

UX research generates large amounts of qualitative data. AI can help process it without losing the nuance that makes research valuable.

**Usability test analysis:**
"I ran 6 usability tests of our new Dimensions search interface. Here are my notes from each session: [paste]. For each participant, identify:
* Tasks they completed successfully vs. where they struggled
* Specific UI elements that caused confusion
* Verbatim quotes about their experience
* Comparisons they made to other tools
Then synthesize: what are the 3 most critical usability issues to fix before launch?"

**Persona development:**
"Based on these 15 user interview summaries from Overleaf users, help me define 3 user personas. For each persona include:
* Role and context (who they are, what they do)
* Goals (what they are trying to accomplish with Overleaf)
* Pain points (what frustrates them about their current workflow)
* Technology comfort level
* A direct quote that captures their perspective"

**Journey mapping:**
"Map the customer journey for a university librarian evaluating and deploying Figshare for their institution. Include stages: Discovery, Evaluation, Purchase, Implementation, Adoption, and Renewal. For each stage, document: key actions, touchpoints, emotions, and pain points."

### Ideation and Concept Exploration

AI is a useful brainstorming partner, especially for generating concepts quickly.

**Design exploration:**
"I am designing the AI assistant interface for ReadCube. Users will ask questions about their saved research papers and get AI-generated answers. Generate 5 different UX concepts for how this interaction could work. Consider:
* Chat-based vs. inline vs. side panel approaches
* How to show source citations so users can verify claims
* How to handle cases where the AI is not confident in its answer
* How to make the interaction feel helpful rather than intrusive"

**Microcopy generation:**
"Write 3 versions of empty state copy for a Dimensions AI search feature that has no results. The user searched for something very specific. Each version should: explain why there are no results, suggest what to try instead, and maintain a helpful tone. Keep each under 40 words."

**Error state design:**
"For an AI feature that summarizes research papers, design the copy for these error states:
* The AI is taking longer than expected (loading state)
* The AI could not generate a useful summary (failure state)
* The AI is uncertain about part of its summary (low confidence state)
* The user's uploaded document could not be processed (input error)
For each, write the heading and body text. Tone should be honest and helpful, not apologetic or cute."

### Visual Design Assistance

**Layout suggestions:**
"I have a dashboard that needs to display: 3 key metrics at the top, a line chart showing trends over time, a data table with filtering, and an AI-generated insight panel. Suggest 2 different layout approaches optimized for a 1440px wide screen. Describe the layout in enough detail that I can wireframe it."

**Accessibility review:**
"Review this design specification for accessibility issues. [Describe the colors, font sizes, and interaction patterns.] Check for: color contrast compliance (WCAG AA), keyboard navigation issues, screen reader compatibility, and cognitive load concerns."

## Designing AI-Powered Features

This is the more challenging and more important part: designing AI features that users can actually work with. AI introduces uncertainty, variable quality, and new mental models that traditional UX does not prepare for.

### Key Design Principles for AI Features

**Transparency over magic:**
Users need to understand what the AI is doing well enough to know when to trust it. A Dimensions feature that says "Here are the top papers on CRISPR" should show why those papers were selected (citation count, relevance score, recency). A black box that says "trust me" will fail.

**Graceful degradation:**
AI features will sometimes produce poor results. Design for this. What does the user see when the AI has low confidence? When the input is ambiguous? When the model is unavailable? The worst UX is showing confidently wrong information.

**Progressive disclosure of complexity:**
Not all users need the same level of control. A basic user wants "Summarize this paper." An advanced user wants to specify the length, focus area, and audience. Design features that are simple by default with advanced options available for those who want them.

**Human-in-the-loop by default:**
AI output should be editable, dismissable, and subject to user correction. If an AI feature generates a response, let the user modify it before it goes anywhere. If it categorizes something, let the user correct the category. This builds trust and improves the system over time through feedback.

### Common AI UX Patterns

**The side panel assistant:** A persistent AI panel alongside the main content area. Used by Gemini in Google Workspace, GitHub Copilot, and many SaaS products. Good for: ongoing conversation, reference while working. Watch out for: taking up screen space, context confusion between panel and main content.

**Inline suggestions:** AI-generated text appears directly in the content area (like autocomplete). Used by Copilot in editors and Google Smart Compose. Good for: low friction, seamless integration. Watch out for: distraction, users accepting bad suggestions without reading.

**The chat interface:** Full conversational interaction with the AI. Good for: complex queries, multi-step tasks. Watch out for: users expecting human-level understanding, difficulty recovering from misunderstandings.

**AI-enhanced search:** Traditional search with AI-generated summaries or answers at the top. Good for: augmenting existing behavior, providing quick answers. Watch out for: users trusting AI answers over search results, hallucinated summaries.

**Proactive suggestions:** AI notices something and offers a suggestion without being asked. Good for: surfacing opportunities users would miss. Watch out for: interrupting workflow, notification fatigue, wrong suggestions eroding trust.

### Designing for Trust

Trust is the central challenge of AI UX. Too much trust and users blindly accept wrong answers. Too little and they ignore the feature.

**Calibrate user expectations:**
* Use language that sets appropriate expectations: "AI-generated summary (verify key facts)" rather than "Your summary"
* Show confidence indicators where possible (but test whether users understand them)
* Include a feedback mechanism: thumbs up/down, "Was this helpful?"

**Citation and source attribution:**
For DS products built on research data, showing sources is critical:
* Link AI-generated claims to source documents
* Show which specific passages the AI used
* Let users click through to verify

**Consistency:**
Users build mental models based on repeated interactions. An AI feature that works great 90% of the time and fails badly 10% is harder to trust than one that works moderately well 100% of the time. Design for consistency, even if it means constraining the AI's range.

### Designing for Digital Science Products Specifically

**Overleaf:**
AI writing assistance needs to respect academic norms. Authors want help with grammar and clarity, not with generating ideas (which would undermine their scholarly contribution). Design the AI as an editor, not a co-author.

**Dimensions:**
Natural language search over research data needs to handle domain-specific queries ("papers citing DOI X published after 2020 in Nature journals") alongside general queries ("recent breakthroughs in CRISPR"). The UX needs to clearly show what the AI understood from the query.

**Figshare:**
AI-assisted metadata generation (suggesting keywords, categories, descriptions for uploaded datasets) should present suggestions that users can accept, modify, or reject. Pre-filling fields is helpful; auto-submitting them is not.

**Altmetric:**
AI-generated attention summaries should clearly distinguish between factual attention data (number of tweets, news mentions) and AI-generated interpretation of that data.

## Try This Today

1. Pick an AI feature in any product (DS or external) that you find well-designed
2. Spend 15 minutes using it intentionally, noting every design decision: how it handles loading, errors, uncertainty, sources, and user control
3. Document 3 design patterns you think would work for DS products
4. Pick one AI feature in DS products that you think needs UX improvement
5. Sketch (on paper or in your design tool) an alternative approach using one of the patterns you identified
6. Share your analysis and sketch in #AI-Tuesdays

For the AI Product Teardown exercise: focus specifically on how the AI communicates uncertainty and how users verify the AI's output. These are the two hardest UX challenges in AI design and the most important for DS products.
