---
difficulty: beginner
---

# Prompt Engineering Basics

## Why Prompting Matters

The quality of what you get from an AI tool is directly tied to the quality of what you put in. A vague prompt produces vague output. A specific, well-structured prompt produces output you can actually use. This is true whether you are writing an email, analyzing data, building code, or summarizing research.

Prompt engineering is not a technical skill reserved for developers. It is a practical skill that anyone at Digital Science can learn, and it will make every interaction with AI tools more productive.

## The RTCF Framework

A useful mental model for structuring prompts is RTCF: Role, Task, Context, and Format.

**Role:** Tell the AI who it should be. This sets the domain expertise and tone.
* "You are a senior product marketing manager at a research technology company."

**Task:** Tell the AI what to do. Be specific about the action and what success looks like.
* "Write a one-paragraph summary of this feature update for our institutional customers."

**Context:** Give the AI the background information it needs. Include constraints.
* "Our customers are university librarians who care about ROI and ease of deployment. Keep the tone professional but not stiff. Avoid jargon."

**Format:** Tell the AI how to structure the output.
* "Output as a single paragraph of 80-100 words, suitable for an email newsletter."

Putting it together: "You are a senior product marketing manager at a research technology company. Write a one-paragraph summary of this feature update for our institutional customers. Our customers are university librarians who care about ROI and ease of deployment. Keep the tone professional but not stiff. Avoid jargon. Output as a single paragraph of 80-100 words, suitable for an email newsletter."

## Core Techniques

### 1. Be Specific, Not Vague

Bad: "Write me something about our product."
Better: "Write a 200-word description of Dimensions that explains its value to a research funder who needs to track the impact of their grants."

The more specific you are about audience, length, tone, and purpose, the less editing you will need to do.

### 2. Provide Reference Material

AI works best when it has source material to work from rather than generating from scratch. This is called "grounding."

* Upload a document: "Using ONLY the attached document, answer the following question..."
* Paste in examples: "Here is an example of the tone I want. Match this style."
* Reference prior work: "Here is last quarter's report. Write this quarter's in the same format."

Grounding is the single most effective way to reduce hallucinations. When you give the AI a reference, it reads from that reference rather than inventing facts.

### 3. Use Personas

Assigning the AI a role focuses its output dramatically. Some useful personas for Digital Science work:

* "Act as a Senior Risk Auditor. Review this proposal for regulatory gaps."
* "Act as a customer support specialist for Overleaf. Draft a response to this ticket."
* "Act as a data analyst. Explain these trends in plain English for a non-technical audience."

### 4. Chain-of-Thought Prompting

For complex tasks, ask the AI to show its reasoning before giving a final answer. This helps you spot errors in logic early.

* "Think through this step by step before giving your final answer."
* "Show your internal logic as a brief outline, then provide the recommendation."

### 5. Ask for Multiple Versions

Never settle for the first output. Options let you be the editor, not the writer.

* "Provide three versions: one conservative, one bold, and one minimalist."
* "Give me two approaches to solving this problem, with pros and cons for each."

### 6. Use Negative Constraints

Tell the AI what NOT to do. This is surprisingly effective for getting output that sounds human and professional.

* "Do not use the words 'delve,' 'tapestry,' 'transformative,' or 'comprehensive.'"
* "Do not start with 'I hope this email finds you well.'"
* "Avoid bullet points. Write in flowing paragraphs."

### 7. Iterate and Refine

AI conversations are not one-shot. Treat them like a dialogue with a capable but literal-minded colleague.

* "That is too formal. Make it more conversational."
* "Good structure, but the second paragraph is too long. Tighten it."
* "I disagree with your third point. Give me a stronger alternative."

Pushing back on the AI forces it to dig deeper. It is designed to be agreeable, so constructive conflict produces better results.

## Verification Habits

AI is a reasoning engine, not a fact engine. Every output needs human verification.

* **Ask for sources:** "What evidence supports this claim? Provide the source."
* **Confidence check:** "On a scale of 1-10, how confident are you in this answer? Why might you be wrong?"
* **Assumption mapping:** "List every assumption you made to reach this conclusion."
* **Cross-check:** Copy the AI's output into a new chat and ask: "Critique this for factual errors and logical fallacies."

These verification steps take 30 seconds and can save you from publishing or acting on something incorrect.

## Practical Prompt Templates

Here are ready-to-use prompts adapted for common Digital Science work:

**Summarize a document:**
"Summarize the attached document in 5 bullet points. Focus on action items and decisions. Ignore background context. Target audience is a senior manager who has 2 minutes to read this."

**Draft a customer email:**
"Draft a reply to this customer support ticket for [Figshare/Overleaf/Dimensions]. The customer's issue is [X]. Use a helpful, professional tone. Keep it under 150 words. Include a clear next step."

**Prepare for a meeting:**
"I have a meeting with [institution/company]. Using the information below, prepare a one-page briefing covering: their likely priorities, how our products address those priorities, and two questions I should ask."

**Analyze data:**
"Here is a CSV of [description]. Identify the top 3 trends, any anomalies, and suggest what might be driving these patterns. Present findings as a brief narrative, not a table."

**Review your own writing:**
"Review this document as a Critical Friend. Identify the weakest argument, flag any jargon, and suggest how to make it 30% shorter without losing meaning."

## Common Mistakes to Avoid

* **Being too vague:** "Help me with my presentation" gives the AI nothing to work with.
* **Trusting without verifying:** AI will confidently state incorrect facts. Always check.
* **Using AI to replace thinking:** Use it to augment your thinking, not substitute for it. You are the decision-maker.
* **Giving up after one bad output:** Refine the prompt, add context, push back. The second or third try is usually much better.

## Try This Today

1. Pick a task you have coming up this week (an email, a report, a meeting prep)
2. Write a prompt using the RTCF framework
3. Run it through Claude or Gemini
4. Note what worked and what needed editing
5. Refine your prompt and run it again
6. Save the improved prompt somewhere you can reuse it

The goal is to build a personal library of prompts that work for your specific role. Over time, this library becomes a significant time saver.
