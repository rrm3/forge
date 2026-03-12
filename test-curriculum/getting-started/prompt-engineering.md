---
difficulty: beginner
---

# Prompt Engineering Basics

## What is Prompt Engineering?

Prompt engineering is the practice of crafting inputs to AI language models to get better, more reliable outputs. The term sounds more technical than it is. At its core, it is about being clear, specific, and providing the right context - the same skills that make written communication effective in general.

Most people underestimate how much prompt quality affects results. The same model given a vague prompt versus a well-structured prompt can produce outputs that look like they came from entirely different tools.

## The Core Elements of a Good Prompt

**Role or persona** - Tell the model who it should be. "You are a technical writer" or "You are helping a product manager" frames the response appropriately.

**Task** - Be explicit about what you want. "Summarise this" is weaker than "Write a three-sentence summary of the key findings for a non-technical audience."

**Context** - Provide the information the model needs. Paste in the document, describe the situation, explain the constraints.

**Format** - Specify the output format when it matters. "Return a bulleted list", "Write in plain paragraphs", "Use a table with columns X and Y."

**Constraints** - Add guardrails. "Keep it under 200 words", "Do not include jargon", "Avoid recommending specific vendors."

## Prompt Patterns

**Chain of thought**: Ask the model to think step by step. Particularly useful for analytical or reasoning tasks. "Think through this step by step before giving your final answer."

**Few-shot examples**: Show the model what good output looks like by including one or two examples. "Here is an example of the format I want: [example]. Now do the same for [new input]."

**Persona prompting**: Set a role to shape tone and approach. "You are a senior editor reviewing this for clarity and concision."

**Adversarial prompting**: Ask the model to challenge your work. "What are the three strongest objections to this proposal?" or "What am I missing?"

**Refinement loop**: Treat the first output as a draft. Follow up with "make it shorter", "make the tone more formal", or "replace the second paragraph with something more concrete."

## What Good Prompts Look Like

A weak prompt: "Write an email about the project update."

A stronger prompt: "Write a brief project update email to senior stakeholders. The project is on track, the main milestone was delivered last week, and the next milestone is in three weeks. Tone should be confident and concise. No jargon. Under 150 words."

The difference is specificity. The model cannot infer your audience, your tone requirements, or your word limit unless you tell it.

## Iterating on Prompts

Do not expect perfection on the first try. Treat prompts like drafts:

1. Write a first attempt and see what you get
2. Identify what is missing or wrong in the output
3. Add constraints, examples, or clarifications to the prompt
4. Try again

Keeping a personal library of prompts that work well is worth the effort. If you write a prompt that produces great results for a recurring task, save it.

## Forge-Specific Tips

In Forge, the system prompt already provides context about Digital Science. You do not need to explain what the organisation does in every prompt. Focus your prompt on the specific task and any context unique to your request.

Use the memory feature to store information the model should always know about you - your role, your preferences, recurring projects. This reduces the amount of context you need to include in every message.

When asking about documents, upload or paste them directly rather than describing them. The model works best with the actual content.
