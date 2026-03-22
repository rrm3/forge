---
difficulty: beginner
---

# AI Tools Overview

## The Landscape

There are many AI tools available, and the landscape changes fast. This guide covers the tools that are most relevant to Digital Science employees, what each is best at, and how to choose the right one for a given task.

You do not need to master all of these. Start with one or two that match your role, get comfortable, and expand from there.

## Tools Available at Digital Science

### Gemini (Google)

**What it is:** Google's AI assistant, integrated directly into Google Workspace (Docs, Sheets, Gmail, Slides, Meet).

**Best for:**
* Day-to-day productivity: summarizing emails, drafting documents, generating formulas in Sheets
* Cross-app workflows: pulling data from Gmail into Docs, or from Sheets into Slides
* Quick research using Deep Research mode
* Creating custom Gems (reusable personas) for consistent output

**Who should start here:** Everyone. If you use Google Workspace daily, this is the lowest-friction entry point because you do not need to learn a new interface.

**Limitations:** Less capable than Claude or GPT-4 for complex reasoning tasks. Tends to be more verbose. Image generation is limited compared to specialized tools.

### Claude (Anthropic)

**What it is:** A general-purpose AI assistant available via web interface and API. Known for strong analytical reasoning, careful handling of nuance, and longer context windows.

**Best for:**
* Complex analysis and synthesis (comparing documents, finding patterns, evaluating arguments)
* Long-form writing that needs to sound human and professional
* Working with large documents (Claude can process very long inputs)
* Code review and generation
* Tasks that require careful reasoning and acknowledgment of uncertainty

**Who should start here:** Anyone doing analysis-heavy work, long-form writing, or document review. Product managers, data scientists, customer consultants, and strategists will find Claude especially useful.

**Specialized tools:**
* **Claude Code:** A command-line coding assistant for developers. Works with your local codebase to build, debug, and refactor code.
* **Claude Cowork:** Runs compliance reviews, analyzes information, and generates dashboards and reports. A hands-on productivity tool.

### ChatGPT (OpenAI)

**What it is:** The most widely known AI chatbot. Available via web, mobile app, and API.

**Best for:**
* General-purpose Q&A and brainstorming
* Quick explanations of technical concepts
* Image generation via DALL-E integration
* Custom GPTs (specialized assistants you can build and share)

**Who should start here:** If you have already used ChatGPT casually, build on that familiarity. Good for teams that need quick answers and do not require deep document analysis.

### GitHub Copilot

**What it is:** An AI coding assistant that integrates into your IDE (VS Code, JetBrains, etc.). It suggests code completions, generates functions, and helps with debugging.

**Best for:**
* Code completion and generation while you type
* Generating boilerplate code and tests
* Explaining unfamiliar code
* Refactoring and improving existing code

**Who should start here:** Software developers and engineers in the Technology department.

**Note:** The Prompt Engineering Learning Track includes an advanced course on GitHub Copilot prompting techniques.

### Cursor

**What it is:** An AI-native code editor built on VS Code. It goes beyond Copilot by offering deeper codebase understanding and multi-file editing capabilities.

**Best for:**
* AI-assisted development where you want the tool to understand your full codebase
* Rapid prototyping and building features with AI guidance
* Engineers who want tighter AI integration than Copilot alone provides

**Who should start here:** Developers who want to push beyond Copilot, especially those working on AI product features for Dimensions, Overleaf, or other DS products.

### NotebookLM (Google)

**What it is:** A research-focused tool where you upload documents (PDFs, web pages, notes) and ask questions. NotebookLM answers using ONLY your uploaded sources, which dramatically reduces hallucination.

**Best for:**
* Deep research across multiple documents
* Comparing contracts, reports, or specifications
* Creating study guides and summaries from large document collections
* Generating audio overviews (podcast-style summaries)

**Who should start here:** Anyone who regularly works with large documents: product managers reviewing specs, customer consultants analyzing RFPs, legal reviewing contracts, or researchers synthesizing literature.

### Google AI Studio

**What it is:** A web-based tool for experimenting with Google's AI models. It allows you to test prompts, adjust parameters (like temperature), and try more advanced techniques.

**Best for:**
* Intermediate users who want to understand how model parameters affect output
* Experimenting with different prompting strategies
* Prototyping AI workflows before building them into products

**Who should start here:** Intermediate users ready to go beyond basic prompting.

### Other Tools in the Ecosystem

* **Midjourney:** AI image generation. Useful for marketing visuals and presentation graphics.
* **Lovable:** AI tool for rapid prototyping of web applications. The Product team has identified this for Phase 2 experimentation.
* **N8N:** Workflow automation platform that connects AI tools with other business systems.
* **Perplexity:** AI-powered search engine. The Operations team is already evaluating it for research tasks.
* **Scribe:** Automatically documents processes as you perform them. Operations is evaluating this for process documentation.
* **LinkSquares:** AI-powered contract analysis. Operations is evaluating this for contract review.

## How to Choose the Right Tool

| Task | Best Tool | Why |
|---|---|---|
| Draft an email | Gemini in Gmail | Already in your inbox, fastest workflow |
| Analyze a spreadsheet | Gemini in Sheets | Direct integration, formula generation |
| Write a long report | Claude | Better at long-form, nuanced writing |
| Complex reasoning task | Claude | Strongest analytical capabilities |
| Quick factual question | ChatGPT or Gemini | Fast, general-purpose answers |
| Code something | Copilot or Cursor | IDE integration, code-aware |
| Research across documents | NotebookLM | Source-grounded, no hallucination |
| Generate images | Midjourney or Gemini | Depends on quality needs |
| Build a prototype app | Lovable or Claude Code | Rapid UI or full-stack respectively |

## Temperature and Model Settings

When you use AI tools that let you adjust settings, two parameters matter most:

**Temperature:** Controls how creative or conservative the output is.
* Low (0.0-0.2): Factual, consistent, predictable. Use for data analysis, compliance, anything where accuracy matters more than creativity.
* Medium (0.3-0.6): Balanced. Good for general writing and business tasks.
* High (0.7-1.0): Creative, varied, surprising. Use for brainstorming, content ideation, or exploring new angles.

**Model selection:** Most tools offer multiple models with speed-quality tradeoffs.
* Use faster/lighter models for quick tasks (summaries, simple drafts)
* Use more capable models for complex tasks (analysis, long documents, nuanced writing)

## AI Tools Already in Digital Science Products

Understanding what AI features exist in our own products helps everyone, whether you are selling, supporting, or building them:

* **Writefull:** AI-powered writing tools for academic authors (language editing, paraphrasing, text generation)
* **ReadCube AI Assistant:** AI features for literature management and research
* **Attention Digest:** AI-generated summaries of attention data from Altmetric
* **Dimensions:** Exploring natural language interfaces for research data queries (Charles Festel's ARPA-H/GRACE work)

If you work on any of these products, AI Tuesdays is a great time to become a power user of your own product's AI features and bring feedback to the product team.

## Try This Today

1. Pick one tool you have never used before from the list above
2. Open it and ask it the same question you recently asked your primary AI tool
3. Compare the outputs: Which was more detailed? Which was more accurate? Which was faster?
4. Write down one task where the new tool might be better than your current default
5. Share your comparison in #AI-Tuesdays on Slack

This exercise takes 15 minutes and helps you build intuition about which tool to reach for in different situations.
