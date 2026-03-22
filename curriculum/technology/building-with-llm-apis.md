---
difficulty: advanced
---

# Building with LLM APIs

## Context

Several Digital Science products already incorporate AI features (Writefull, ReadCube AI Assistant, Attention Digest) and more are in development. Engineers building these features need to understand how to work with LLM APIs effectively, including structured output, function calling, and the tradeoffs involved in different integration patterns.

This guide is for developers who are moving beyond using AI as a personal productivity tool and into building AI-powered features for DS products.

## Choosing a Model Provider

The main providers you will encounter at Digital Science:

**Anthropic (Claude)**
* Strong at complex reasoning, long documents, and careful instruction following
* Good structured output with tool use / function calling
* Available directly and via AWS Bedrock
* Claude on Bedrock is relevant for FedRAMP-compliant deployments

**OpenAI (GPT-4, GPT-4o)**
* Broadest ecosystem and tooling
* Function calling is mature and well-documented
* Available directly and via Azure OpenAI Service

**Google (Gemini)**
* Tight integration with Google Cloud and Vertex AI
* Model Garden on Vertex provides access to multiple models
* Good for teams already on Google Cloud infrastructure

**Local/Open-source models**
* For use cases where data cannot leave your infrastructure
* Smaller models (Llama, Mistral) for lower-latency, lower-cost tasks
* Relevant for FedRAMP and government customer deployments

**Choosing between them:** There is no single best model. Match the model to the task. Use more capable models for complex reasoning and cheaper/faster models for simple classification or extraction. Many production systems use multiple models for different steps in a pipeline.

## Structured Output

Most AI features in products need structured output, not free-form text. If you are building a feature that extracts metadata from research papers for Dimensions, or categorizes support tickets for ReadCube, you need the model to return JSON, not prose.

**Approach 1: JSON mode / response format**
Most providers support requesting JSON output directly:
```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": prompt}],
    response_format={"type": "json_object"}
)
```

**Approach 2: Function calling / tool use**
Define the schema of the output you want, and the model will return structured data matching that schema:
```python
tools = [{
    "type": "function",
    "name": "extract_paper_metadata",
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "authors": {"type": "array", "items": {"type": "string"}},
            "doi": {"type": "string"},
            "publication_year": {"type": "integer"},
            "abstract_summary": {"type": "string", "maxLength": 200}
        },
        "required": ["title", "authors"]
    }
}]
```

Function calling is generally more reliable than asking for JSON in the prompt because the model is specifically trained on this format.

**Approach 3: Pydantic / Zod schemas with validation**
Use a validation library to define your expected output schema and validate the model's response. This catches malformed output before it hits your application logic.

**Which approach to use:**
* Simple key-value extraction: JSON mode is fine
* Complex nested structures: Function calling with schema validation
* Mission-critical pipelines: Function calling plus Pydantic/Zod validation plus retry logic

## Function Calling Patterns

Function calling lets the model decide when to call external tools (APIs, databases, search) during a conversation. This is the foundation of agentic patterns.

**Example for Dimensions:** Build a natural language query interface where users ask questions like "Show me all grants from NIH in 2024 related to genomics." The model translates this into a Dimensions API call, executes it, and presents the results.

```
User: "What is the total funding for AI research from NSF in the last 3 years?"

Model decides to call: search_grants(funder="NSF", topic="artificial intelligence", year_range="2023-2026")

Model receives results and formats a response for the user.
```

**Design considerations:**
* Define functions with clear, precise descriptions. The model uses these descriptions to decide when to call which function.
* Validate all function arguments before executing. The model may generate plausible but invalid parameters.
* Handle function call failures gracefully. The model should be able to explain what went wrong and try an alternative approach.
* Log all function calls for debugging and auditing.

## System Prompts for Product Features

The system prompt is where you define the AI feature's behavior, personality, and constraints. For production features, system prompts need to be much more carefully crafted than for personal use.

**Key elements of a production system prompt:**
* **Identity:** Who is this assistant? "You are the Overleaf writing assistant. You help users improve their LaTeX documents."
* **Capabilities:** What can it do? "You can suggest improvements to writing, fix LaTeX errors, and help with formatting."
* **Limitations:** What can it NOT do? "You cannot access the internet. You cannot modify the user's document directly. You should not provide citation data that you are not certain about."
* **Safety:** What should it refuse? "Do not generate content that could be considered plagiarism. If asked to write entire papers, explain that you can help improve existing drafts but not write papers from scratch."
* **Output format:** How should responses look? "Keep responses concise. Use LaTeX formatting when showing code examples. Explain changes so the user learns."

**Testing system prompts:**
* Test with adversarial inputs: What happens when a user tries to override the system prompt?
* Test with edge cases: What happens with empty inputs, very long inputs, or non-English text?
* Test for consistency: Does the model behave the same way across 100 similar queries?

## Error Handling and Reliability

LLM APIs are inherently less predictable than traditional APIs. Your code needs to handle:

* **Rate limiting:** Implement exponential backoff and request queuing.
* **Timeout handling:** LLM calls can take 5-30+ seconds. Set appropriate timeouts and show progress indicators to users.
* **Malformed responses:** Even with structured output, models occasionally produce invalid JSON or miss required fields. Validate and retry.
* **Content filtering:** Providers may refuse certain requests. Handle refusals gracefully.
* **Model degradation:** Model quality can vary. Monitor output quality over time and alert when it drops.

**Retry strategy for production:**
```
attempt 1: standard request
attempt 2: retry with same parameters (transient failures)
attempt 3: retry with simplified prompt (complexity issues)
fallback: return graceful error to user
```

## Cost Management

LLM API calls cost money, and costs can scale quickly in production.

* **Token counting:** Know how many tokens your prompts and responses consume. Most providers charge per token.
* **Prompt optimization:** Shorter, more focused prompts cost less. Remove unnecessary context from system prompts.
* **Model routing:** Use cheaper models for simple tasks and expensive models only when needed. A classification task might use GPT-4o-mini instead of GPT-4.
* **Caching:** Cache identical or similar requests. If 100 users ask the same question about an Overleaf feature, you do not need 100 API calls.
* **Batch processing:** For offline tasks (like processing Dimensions data pipeline outputs), use batch APIs which are typically 50% cheaper.

## Evaluation and Monitoring

Building an AI feature is not done when it ships. You need ongoing evaluation.

**Metrics to track:**
* **Accuracy:** Does the model give correct answers? For structured extraction, measure precision and recall against a labeled test set.
* **Hallucination rate:** How often does the model generate false information? The Altmetric team is already working on hallucination detection, so coordinate with them.
* **Latency:** How long does each call take? Set SLOs and alert when they are breached.
* **Cost per request:** Track spending and flag anomalies.
* **User satisfaction:** If users can rate AI responses, track satisfaction over time.

**Building eval sets:**
* Create a test set of 100+ examples with known correct answers
* Run every model change or prompt update against the eval set before deploying
* Track eval scores over time to catch regressions

## Try This Today

1. Pick an internal workflow that involves extracting structured data from text (parsing customer emails, extracting metadata, categorizing tickets)
2. Define the output schema as a JSON structure
3. Write a prompt that instructs the model to extract the data
4. Test it with 10 real examples
5. Measure how many it gets right without manual correction
6. Share your accuracy numbers and prompt in #AI-Tuesdays

This exercise takes 1-2 hours and gives you hands-on experience with the core pattern of most production AI features.
