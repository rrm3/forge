---
difficulty: beginner
---

# AI for Customer Support

## Context

The Customer department is 159 people, the second largest at Digital Science, supporting products across Overleaf, ReadCube, Altmetric, Figshare, Symplectic Elements, IFI Claims, and Metaphacts. The team includes technical consultants, data scientists, support specialists, program managers, implementation managers, and pre-sales specialists. Skill levels range from highly technical (data science team) to non-technical (support coordinators).

AI can make a meaningful difference in how this team handles the volume and variety of customer interactions, but the key word is "assist." AI helps you respond faster and more consistently. It does not replace the judgment, empathy, and product knowledge that makes customer support at DS effective.

## Drafting Customer Responses

The most immediate win is using AI to draft responses to customer emails and support tickets. This is not about having AI respond directly to customers. It is about reducing the time between reading a ticket and having a well-structured draft ready for your review.

**Workflow for ticket response drafting:**
1. Copy the customer's message into Claude or Gemini
2. Add context: "This is a support ticket from a university librarian using Figshare. They are asking about storage limits on their institutional account."
3. Ask: "Draft a helpful, professional response that explains the storage policy and offers to schedule a call if they need further clarification. Keep it under 150 words."
4. Review the draft. Edit for accuracy (AI may get product details wrong). Adjust tone.
5. Send.

**Making this faster over time:**
* Create a Gemini Gem called "DS Support Writer" with your standard tone, product knowledge, and formatting preferences. Reuse it for every ticket.
* Build a prompt template for each product: "You are a customer support specialist for [Overleaf/Figshare/Elements]. The customer's issue is: [paste]. Draft a response that is helpful, professional, and concise."
* Save your best prompts. Over weeks, you will build a library that covers the most common ticket types.

**What AI does well here:** Grammar, tone, structure, and speed. It can take a rough set of bullet points and turn them into a polished customer email in seconds.

**What AI does NOT do well:** Product-specific accuracy. AI does not know the current state of our products, recent changes, or specific customer configurations. Always verify technical details before sending.

## Ticket Triage and Categorization

If your team handles a high volume of tickets, AI can help with initial categorization.

**Simple triage workflow:**
1. Paste the ticket content into an AI tool
2. Ask: "Categorize this ticket as one of: billing, technical issue, feature request, account access, data migration, or general inquiry. Also rate the urgency as high, medium, or low. Explain your reasoning in one sentence."
3. Use the categorization to route the ticket appropriately

**For teams using Front:** Explore whether AI can be integrated into your triage workflow directly. The Operations team is evaluating AI capabilities within Front and other support platforms.

**Batch categorization:** If you have a backlog of tickets, paste 10-20 at a time and ask AI to categorize all of them in a table format. This is much faster than reading each one individually.

## Knowledge Base Improvement

AI is excellent at identifying gaps in your knowledge base by analyzing what customers actually ask about.

**Finding gaps:**
1. Collect the last 50 support tickets (anonymized)
2. Ask AI: "Analyze these tickets. What are the top 10 topics customers ask about? For each topic, identify whether our knowledge base likely covers it well, partially, or not at all."
3. Use the results to prioritize knowledge base updates

**Creating knowledge base articles:**
1. Take a product area where you get frequent questions
2. Ask AI: "Write a customer-facing FAQ about [Overleaf institutional account setup / Figshare data repository management / Elements CRIS integration]. Include the 5 most common questions and clear, step-by-step answers."
3. Review for accuracy. Add screenshots or links. Publish.

**Maintaining articles:**
When product features change, ask AI to review existing articles: "Here is our current knowledge base article about X. The product has changed in the following ways: [list changes]. Update the article to reflect the new behavior."

## Summarizing Customer Interactions

For consultants and program managers who manage long-running customer relationships, AI can help synthesize interactions.

**Meeting summary workflow:**
After a customer meeting, paste your notes (or the transcript if the meeting was recorded) into an AI tool and ask:
"Summarize this meeting in three sections: Key Decisions, Action Items (with owners and deadlines), and Open Questions. Format as bullet points."

**Relationship summaries:**
Before a customer review meeting, gather your recent correspondence and notes. Ask AI:
"Based on these interactions over the past quarter, summarize: the customer's main priorities, outstanding issues, recent wins, and any risks to the relationship. Keep it to one page."

This is especially useful for pre-sales specialists preparing demos. AI can analyze past interactions with an institution and suggest which product features to emphasize based on their stated priorities.

## Data Analysis for the Customer Team

The Customer department includes a significant data science team (Chris Wolcott's team) plus technical engineers and data analysts. For these team members, AI can accelerate analytical work.

**Natural language to SQL:**
If you work with Dimensions data or customer analytics databases, AI can translate natural language questions into SQL queries:
"Write a SQL query that finds all institutions with more than 100 Overleaf users whose subscription is up for renewal in the next 90 days, ordered by user count descending."

Review the SQL carefully before running it. AI sometimes makes assumptions about table structures or relationships that do not match your schema.

**Analysis acceleration:**
* "Here is a CSV of customer support tickets from the past month. Identify trends: Are ticket volumes increasing? Which product areas generate the most tickets? Are resolution times getting better or worse?"
* "Analyze this customer health data. Which accounts show signs of decreasing engagement? What patterns do you see?"

**For the research analytics team:** AI can help generate analytical reports more quickly. Provide the raw data and ask for narrative summaries, visualizations suggestions, or anomaly detection.

## Pre-Sales Demo Personalization

Pre-sales specialists and solutions consultants can use AI to tailor demos to specific customers.

**Demo prep workflow:**
1. Gather information about the prospect: institution type, size, current tools, stated needs
2. Ask AI: "I am preparing a demo of [Dimensions/Elements/Altmetric] for a [large research university / government funder / pharmaceutical company]. Based on this information about them: [paste details]. Suggest which features to highlight, what pain points to address, and what questions they are likely to ask."
3. Use the output to structure your demo and prepare for objections

## Try This Today

**For support specialists:**
1. Take the last ticket you responded to
2. Paste the customer's message into AI with this prompt: "Draft a helpful, professional response to this customer support inquiry about [product]. Keep it under 150 words and include a clear next step."
3. Compare the AI draft to what you actually sent
4. Note: Was the AI version faster to produce? Was it more or less accurate? What did it miss?

**For consultants and program managers:**
1. Take notes from your last customer meeting
2. Ask AI to generate a structured summary with Key Decisions, Action Items, and Open Questions
3. Compare to what you normally produce
4. Estimate the time savings

**For data scientists:**
1. Describe a query you recently wrote in natural language
2. Ask AI to generate the SQL
3. Compare to your actual query. Did it get the logic right? The table names?
4. Try a more complex query and see where AI starts to struggle

Share your results in #AI-Tuesdays. The Customer department's first AI Tuesday activity is a workshop on using AI to improve customer communications, so bring your findings.
