---
difficulty: beginner
---

# AI Ethics and Safety

## Why This Matters

Digital Science builds products used by researchers, universities, funders, and publishers around the world. The data we handle, and the decisions we make with AI, have real consequences for real people. Getting AI safety right is not about slowing down. It is about moving fast in a way that does not harm our people, our customers, or our business.

This guide covers the practical ethics and safety considerations every Digital Science employee should understand before using AI tools in their work.

## The Two-Factor Rule

Every time you use an AI tool, you are making two decisions simultaneously:

1. **Which tool are you using?** (Is it approved? What are its data handling policies?)
2. **What data are you putting into it?** (What classification is this data? Is it safe to share externally?)

These two factors must be reviewed together. An approved tool can still be misused if you feed it the wrong data. A safe dataset can still be compromised if you put it into an unapproved tool.

When in doubt, post a question in the #AI-Tuesdays Slack channel. Others will benefit from the discussion, and it is much better to ask than to guess.

## Data Classification

Not all data is equal. Before pasting anything into an AI tool, ask yourself which category it falls into:

**Safe to use with external AI tools:**
* Publicly available information (published papers, public websites, press releases)
* Synthetic or test data you have generated for experimentation
* Your own writing drafts (as long as they do not contain confidential information)
* General business questions that do not reference specific customers, employees, or financials

**Requires caution, check with your manager or the Tooling Playbook:**
* Internal strategy documents
* Product roadmap details
* Aggregated (anonymized) customer data
* Internal process documentation

**Do not use with external AI tools:**
* Individual customer data (names, emails, usage data, contract terms)
* Employee personal information (performance reviews, salary, health data)
* Unredacted financial records
* Security credentials, API keys, or access tokens
* Legal documents under privilege or NDA
* FedRAMP-related data or government customer information

If you need to experiment with sensitive data, use synthetic or anonymized versions. Creating fake but realistic test data is a legitimate and encouraged practice during AI Tuesdays.

## Hallucinations: When AI Gets It Wrong

AI models generate text by predicting the most likely next words, not by looking up facts in a database. This means they can, and regularly do, produce confident-sounding statements that are completely false. This is called hallucination.

**Examples of hallucination risks at Digital Science:**
* Citing a paper that does not exist when summarizing research in Dimensions
* Inventing a product feature that Overleaf does not actually have
* Stating a customer contract term that was never agreed
* Generating plausible but incorrect statistics in a report

**How to guard against hallucinations:**
* Always verify factual claims against primary sources
* Ask the AI: "What are the sources for this information?" If it cannot point to a real source, treat the claim as unverified.
* Use grounded prompts: "Using ONLY the attached document, answer the following..." This forces the AI to read rather than invent.
* Cross-check in a fresh chat. Paste the AI's output into a new conversation and ask: "Critique this for factual errors."
* For customer-facing content, always have a human review before sending.

## Bias in AI Output

AI models are trained on internet data, which contains biases. These biases can surface in ways that matter for our work:

* **Hiring:** AI might favor certain phrasings or qualifications that correlate with demographics rather than competence. The People team should always review AI-generated job descriptions and screening criteria for biased language.
* **Customer communications:** AI might default to certain cultural assumptions about formality, naming conventions, or institutional structures that do not apply globally.
* **Product features:** If we build AI features into products like ReadCube or Writefull, we need to test whether they perform equally well across different languages, disciplines, and research traditions.
* **Sales and marketing:** AI-generated content might inadvertently favor certain customer segments or geographies.

**Practical steps:**
* Review AI output with a "who might this exclude?" lens
* Test AI-generated text with colleagues from different backgrounds
* If you spot bias in an AI tool's output, share it in #AI-Tuesdays so others can learn from it

## Intellectual Property and Copyright

* **AI-generated content is not automatically copyrightable.** In most jurisdictions, copyright requires human authorship. Use AI as a drafting tool, but ensure meaningful human editing and decision-making in the final output.
* **Do not paste copyrighted material into AI tools** and ask it to reproduce, paraphrase, or create derivative works without proper authorization.
* **Code generated by AI** (via Copilot, Claude Code, or Cursor) may contain patterns from open-source projects. Developers should review generated code for license compliance.
* **Customer content** (papers in Overleaf, data in Figshare, content in ReadCube) is the customer's intellectual property. Never use it to train or prompt AI tools without explicit permission.

## When NOT to Use AI

AI is powerful, but there are situations where it should not be the primary tool:

* **Legal decisions:** AI can help research legal questions, but legal advice must come from qualified legal professionals. Our Legal team should use AI as a research accelerator, not a decision-maker.
* **Personnel decisions:** Do not use AI to make hiring, promotion, or disciplinary decisions. It can help draft documents or analyze trends, but a human must own the decision.
* **Customer commitments:** Do not let AI draft binding commitments, contract terms, or SLA promises without human review and approval.
* **Safety-critical operations:** Anything related to FedRAMP compliance, security configurations, or access control should involve human verification at every step.
* **Emotional or sensitive conversations:** If a customer is upset, or an employee is struggling, lead with human empathy. AI can help you prepare, but the conversation itself should be human-to-human.

## Transparency

If you use AI to generate content that will be shared externally (blog posts, customer communications, product documentation), consider whether disclosure is appropriate. There is no blanket rule, but here are guidelines:

* AI-assisted internal documents do not typically need disclosure.
* Customer-facing content that was drafted with AI assistance but substantially edited by a human generally does not need disclosure.
* If AI is generating responses to customers in real time (e.g., chatbots or automated support), the customer should know they are interacting with AI.
* Research-related content should be especially transparent, given Digital Science's position in the scholarly communications ecosystem.

## The EU AI Act

The EU AI Act is emerging regulation that classifies AI systems by risk level. As a company with European employees and customers, we should be aware of its implications:

* **High-risk systems** (employment decisions, educational assessments) require documentation, human oversight, and transparency.
* **General-purpose AI** providers have transparency obligations about training data and model capabilities.
* Digital Science products that incorporate AI features will need to comply with relevant provisions as they come into effect.

The Legal team is tracking this. If you are building or specifying AI features for our products, consult with Legal about compliance requirements.

## Building Good Habits

The best safety practice is making verification and caution part of your everyday workflow, not a special step you remember to do sometimes.

* Before pasting data into any AI tool, take 5 seconds to ask: "What kind of data is this?"
* Before using AI output in anything customer-facing, take 30 seconds to verify the key facts
* Before sharing an AI-generated document, ask yourself: "Would I be comfortable if someone knew AI helped write this?"

## Try This Today

1. Open an AI tool (Claude, Gemini, ChatGPT)
2. Ask it a factual question about a Digital Science product you know well (e.g., "What features does Figshare offer for institutions?")
3. Compare the AI's response to what you know to be true
4. Note where it got things right, where it hallucinated, and where it was vague
5. Try the same question with grounding: paste in actual product documentation and ask again
6. Compare the two responses

This exercise takes 10 minutes and will permanently change how much you trust ungrounded AI output.
