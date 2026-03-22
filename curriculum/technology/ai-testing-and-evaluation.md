---
difficulty: advanced
---

# AI Testing and Evaluation

## Why This Is Different from Traditional Testing

When you test a traditional software feature, you can write deterministic tests: given input X, expect output Y. AI features are fundamentally different. The same input can produce different outputs each time. "Correct" is often a spectrum rather than a binary. And failure modes are subtle: the output might be grammatically perfect, confidently stated, and completely wrong.

This guide covers how to test and evaluate AI features in Digital Science products, with practical frameworks the team can adopt immediately.

## The Evaluation Stack

Testing AI features happens at multiple levels:

**Level 1: Component Testing**
Test individual components of your AI pipeline in isolation.
* Does your embedding model produce consistent embeddings for similar texts?
* Does your retrieval step return relevant documents?
* Does your chunking strategy preserve important context?

**Level 2: End-to-End Testing**
Test the full pipeline from user input to final output.
* Given a user question and your knowledge base, does the system produce a correct, relevant answer?
* Does it cite the right sources?
* Does it refuse to answer when it should?

**Level 3: Production Monitoring**
Track quality in production over time.
* Are users satisfied with responses?
* How often does the model hallucinate?
* Are there patterns in failures?

## Building an Evaluation Set

An eval set is a collection of test cases with known correct answers. This is the single most important investment you can make in AI quality.

**How to build one:**
1. Collect 100+ real examples of the kinds of queries your AI feature will handle
2. For each example, write the correct answer (or a set of acceptable answers)
3. Include easy cases, hard cases, edge cases, and adversarial cases
4. Tag each example with metadata: difficulty, category, expected behavior

**For Digital Science products, good eval set sources include:**
* Actual customer support tickets (anonymized) with correct responses
* Sample research queries with verified correct results from Dimensions
* LaTeX formatting questions with known correct solutions for Overleaf
* Publication metadata extraction tasks with ground-truth metadata

**Eval set anti-patterns:**
* Do not build eval sets that are too easy. Include cases where you expect the model to struggle.
* Do not build eval sets in isolation. Have subject matter experts validate the correct answers.
* Do not treat the eval set as static. Add new examples whenever you find failures in production.

## Metrics for AI Features

### Accuracy Metrics

**For classification tasks** (e.g., ticket categorization, sentiment analysis):
* Precision: Of the items the model classified as category X, how many actually were?
* Recall: Of all the items that were actually category X, how many did the model find?
* F1 score: Harmonic mean of precision and recall

**For generation tasks** (e.g., drafting responses, summarizing papers):
* Factual accuracy: Does the generated text contain only true statements?
* Completeness: Does the response address all parts of the question?
* Relevance: Is the response on-topic and useful?
* Source fidelity: For RAG-based features, does the response accurately reflect the source documents?

**For retrieval tasks** (e.g., search, knowledge base lookup):
* Recall@K: Among the top K retrieved documents, how many of the truly relevant ones are included?
* Mean Reciprocal Rank (MRR): How high in the results does the first correct answer appear?
* Normalized Discounted Cumulative Gain (NDCG): How well are the results ordered by relevance?

### Hallucination Detection

Hallucination detection is already in progress on the Altmetric team, so coordinate with them. Here are the key approaches:

**Claim verification:** Extract factual claims from the model's output and verify each one against the source documents or a ground-truth database.

**Self-consistency checking:** Ask the model the same question multiple times. If it gives contradictory answers, the uncertain claims are likely hallucinated.

**Source attribution:** For RAG-based features, check whether each claim in the output can be traced to a specific passage in the retrieved documents. Claims without source support are potential hallucinations.

**Confidence calibration:** Ask the model to rate its confidence for each claim. Models that are well-calibrated will express lower confidence on claims they are less sure about. Poorly calibrated models are confidently wrong.

### Latency and Performance

* **Time to first token:** How long until the user sees the first character of the response?
* **Total response time:** How long until the complete response is available?
* **Retrieval latency:** For RAG features, how long does the retrieval step take?
* **Cost per request:** What does each AI call cost in API fees?

Set SLOs for each metric. For user-facing features, total response time under 3 seconds is a reasonable target for short responses.

## Guardrails

Guardrails are runtime checks that prevent the AI from producing harmful, incorrect, or off-topic output.

**Input guardrails:**
* Detect and reject prompt injection attempts (users trying to override the system prompt)
* Validate that the input is within the expected scope of the feature
* Flag potentially sensitive data in the input before it reaches the model

**Output guardrails:**
* Check output against a list of prohibited content (competitor names, legal claims, price guarantees)
* Verify that structured output matches the expected schema
* Run hallucination detection on key factual claims
* Check output length and format against expected bounds

**Implementation pattern:**
```
User input -> Input guardrails -> Model call -> Output guardrails -> Response to user
                   |                                    |
                   v                                    v
              Block/modify if unsafe            Block/modify if unsafe
```

**For DS products specifically:**
* **Overleaf:** Guard against generating content that could be plagiarism
* **Dimensions:** Guard against fabricating publication records, citations, or grant amounts
* **Altmetric:** Guard against misrepresenting attention metrics or making unfounded correlations
* **ReadCube:** Guard against generating fake paper summaries or incorrect author attributions

## A/B Testing AI Features

AI features should be A/B tested like any other feature, but with additional considerations:

* **Metric selection:** Choose metrics that capture quality, not just engagement. A chatbot that gives wrong answers might get high engagement from users trying to correct it.
* **Sample size:** AI output is variable, so you need larger sample sizes to detect meaningful differences.
* **Segmentation:** Test across different user types. An AI feature might work well for experienced researchers but poorly for students.
* **Human evaluation:** For generation tasks, include human evaluation in your A/B test. Have evaluators rate responses on a scale for accuracy, helpfulness, and tone.

## Regression Testing for Prompt Changes

Every change to a system prompt, retrieval strategy, or model version can affect output quality. Treat these changes like code changes:

1. Run the full eval set before and after the change
2. Compare scores across all metrics
3. Manually review any cases where the new version is worse
4. Do not deploy if key metrics regress, even if overall scores improve (a regression on safety-critical cases is not acceptable even if average accuracy goes up)

## Red Teaming

Red teaming is the practice of systematically trying to make the AI fail. Schedule regular red team sessions for any AI feature you ship.

**Things to test:**
* Can users extract the system prompt?
* Can users make the AI say something harmful or misleading?
* Can users bypass safety constraints?
* What happens with inputs in languages the model was not optimized for?
* What happens with extremely long or extremely short inputs?
* What happens when the knowledge base has no relevant information?

Document failures and add them to your eval set.

## Try This Today

1. Pick an AI feature you are building or planning to build
2. Write 20 test cases: 10 where you expect correct output and 10 where you expect the model to struggle
3. Run them through your current implementation (or a prototype)
4. Score each output on a 1-5 scale for accuracy and usefulness
5. Calculate your baseline scores
6. Identify the 3 worst failures and analyze why they failed
7. Share your eval set structure and baseline scores in #AI-Tuesdays

This is the start of a real evaluation practice. Add to it each week and track scores over time as you improve your prompts and retrieval strategies.
