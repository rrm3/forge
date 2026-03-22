---
difficulty: advanced
---

# RAG and Search

## Why RAG Matters at Digital Science

Retrieval-Augmented Generation (RAG) is the pattern of giving an AI model access to external data before asking it to generate a response. Instead of relying on what the model "knows" from training, you retrieve relevant documents and include them in the prompt. The model then answers based on those documents.

This is directly relevant to several DS products. Dimensions contains millions of research records. Metaphacts manages knowledge graphs. Overleaf hosts millions of LaTeX documents. ReadCube manages research libraries. Any AI feature built on top of these products needs RAG to ground responses in real data rather than model hallucinations.

## The Basic RAG Pipeline

A RAG system has three steps:

1. **Index:** Convert your documents into embeddings (numerical representations) and store them in a vector database
2. **Retrieve:** When a user asks a question, convert the question into an embedding and find the most similar documents
3. **Generate:** Include the retrieved documents in the prompt and ask the model to answer based on them

```
User question -> Embed question -> Search vector DB -> Get top-K documents ->
Include documents in prompt -> LLM generates answer -> Return to user
```

## Embeddings

Embeddings are how we represent text as numbers so that similar meanings are close together in mathematical space.

**Embedding models available:**
* OpenAI `text-embedding-3-small` / `text-embedding-3-large`: Good general-purpose embeddings
* Google `text-embedding-004`: Integrated with Vertex AI
* Open-source options (e.g., BGE, E5): Can run on your own infrastructure

**Choosing an embedding model:**
* Match the embedding model to your data domain. General-purpose models work for most DS use cases, but if you are indexing highly specialized content (patent claims for IFI Claims, or chemical structures for OntoChem), test domain-specific models.
* Consider dimensionality vs. cost: Larger embeddings are more expressive but cost more to store and search.
* Once you choose an embedding model, you are committed. Changing models means re-embedding your entire corpus.

## Vector Databases

Vector databases store embeddings and enable fast similarity search. Options include:

* **LanceDB:** Embedded vector database. Good for applications that need to be self-contained without external infrastructure. We use this for the AI Tuesdays curriculum indexing.
* **Pinecone:** Managed service, easy to set up, pay-per-use.
* **Weaviate:** Open-source, supports hybrid search (vector + keyword).
* **pgvector:** PostgreSQL extension. Good if you are already using Postgres and want to add vector search without a new database.
* **ChromaDB:** Lightweight, good for prototyping.

**For DS teams:** If your product already uses Solr for search (as several do), consider hybrid approaches where Solr handles keyword/faceted search and a vector database handles semantic search. This gives you the best of both worlds.

## Chunking Strategies

Before you can embed documents, you need to split them into chunks. How you chunk determines the quality of retrieval, and this is where most RAG implementations succeed or fail.

**Common chunking approaches:**

* **Fixed-size chunks** (e.g., 500 tokens with 50-token overlap): Simple but can split ideas mid-sentence.
* **Semantic chunking:** Split at paragraph or section boundaries. Better for structured documents like research papers.
* **Document-aware chunking:** For LaTeX documents (Overleaf), chunk by section, subsection, or environment. For knowledge graph data (Metaphacts), chunk by entity or relationship cluster.

**Practical advice:**
* Chunks that are too small lose context. Chunks that are too large dilute relevance.
* For most DS use cases, 300-800 tokens per chunk works well.
* Include metadata with each chunk: document title, section heading, date, author, product area. This metadata is crucial for filtering results.
* Test your chunking by manually reviewing what gets retrieved for sample queries. If the chunks do not contain the answer you expect, your chunking strategy needs adjustment.

## Retrieval Strategies

Basic vector similarity search is just the starting point.

**Hybrid search:** Combine vector search (semantic similarity) with keyword search (exact term matching). This catches cases where the user asks for a specific term that embedding similarity might miss. Especially important for DS products where users search for specific DOIs, grant numbers, or author names.

**Metadata filtering:** Before running similarity search, filter by metadata. "Find me documents about genomics grants from 2024" should first filter to grants from 2024, then run semantic search for "genomics." This is much more efficient and accurate than searching the entire corpus.

**Re-ranking:** After initial retrieval, use a cross-encoder or more capable model to re-rank the results. The initial retrieval might return 20 candidates; re-ranking selects the 5 most relevant.

**Multi-query retrieval:** For complex questions, generate multiple search queries from the original question. "Compare NIH and Wellcome Trust funding for genomics" becomes two searches: one for NIH genomics funding and one for Wellcome Trust genomics funding. Combine the results before generation.

## Prompt Construction for RAG

How you include retrieved documents in the prompt matters significantly.

**Basic pattern:**
```
System: You are a research assistant. Answer questions based ONLY on the
provided context. If the context does not contain enough information to
answer, say so. Do not make up information.

Context:
[Retrieved Document 1]
[Retrieved Document 2]
[Retrieved Document 3]

User: [Question]
```

**Best practices:**
* Explicitly instruct the model to use ONLY the provided context. Without this, the model will fill gaps from its training data, which may be wrong.
* Include source references in each chunk so the model can cite them in its response.
* Limit the number of retrieved documents to what fits in the context window with room for the response.
* Order documents by relevance (most relevant first).

## Common RAG Pitfalls

**Problem: Retrieved documents are irrelevant.**
Cause: Poor chunking, wrong embedding model, or missing metadata filtering.
Fix: Test retrieval separately from generation. Look at what gets retrieved for sample queries.

**Problem: Model ignores retrieved context and answers from training data.**
Cause: System prompt is not forceful enough about using only the provided context.
Fix: Strengthen the instruction. Add: "If the answer is not in the provided context, respond with 'I don't have enough information to answer this question.'"

**Problem: Model includes information from Document A when answering about Document B.**
Cause: Confusion when multiple documents are in context.
Fix: Clearly label each document with its source. Use delimiters between documents.

**Problem: Answers are correct but miss important nuance.**
Cause: Chunks are too small, cutting off relevant context.
Fix: Increase chunk size or include adjacent chunks as additional context.

## RAG at Digital Science: Concrete Use Cases

* **Dimensions natural language query:** User asks "What are the most cited papers on CRISPR from 2023?" RAG retrieves relevant publication records and generates a formatted summary with citations.
* **Overleaf writing assistant:** When a user asks for help with their paper, RAG retrieves relevant sections from LaTeX documentation, style guides, and journal formatting requirements.
* **ReadCube AI research assistant:** RAG over a user's personal library to answer questions like "Which of my saved papers discuss the methodology I need for this experiment?"
* **Metaphacts knowledge graph Q&A:** RAG over entity descriptions and relationship data to answer natural language questions about interconnected research concepts.
* **Customer support:** RAG over product documentation to help support agents quickly find answers to customer questions.

## Try This Today

1. Pick a collection of documents relevant to your work (product docs, internal wiki pages, specification documents)
2. Upload them to NotebookLM and ask a question that requires synthesizing information across multiple documents
3. Note how NotebookLM cites specific sources in its answer; this is RAG in action
4. Think about what a production version of this would look like for your product
5. Write down: What data would you index? How would you chunk it? What queries would users ask?
6. Share your design sketch in #AI-Tuesdays

For engineers ready to build, the first AI Tuesday activity for Technology teams is a hands-on workshop building a simple RAG pipeline using a sample of Dimensions publication data.
