---
difficulty: intermediate
---

# Data Analysis with AI

## Context

Across the Customer department, many roles involve working with data: the data science team analyzing research metrics, technical consultants running implementation queries, program managers reviewing customer health dashboards, and the research analytics team producing reports for government and funder customers. AI tools can accelerate every part of the analysis workflow, from writing queries to interpreting results to communicating findings.

This guide is for anyone in the Customer department who works with data, regardless of technical level. If you use spreadsheets, you will find value here. If you write Python or SQL, there is more to dig into.

## Natural Language to SQL

One of the most practical AI capabilities for data work is translating plain English questions into SQL queries.

**How it works:**
Describe what you want to know, and the AI generates the SQL to answer it. This works best when you tell the AI about your database structure first.

**Example workflow:**
1. Describe your database: "I have a table called `subscriptions` with columns: institution_name, product (values: overleaf, figshare, dimensions, elements, altmetric), start_date, end_date, user_count, annual_value_usd, status (values: active, expired, pending_renewal)."
2. Ask your question: "Which institutions have active Overleaf subscriptions with more than 500 users that expire in the next 6 months?"
3. Review the generated SQL before running it
4. If the query is not quite right, refine: "Also include the annual value and sort by expiry date ascending."

**Tips for better SQL generation:**
* Always describe your schema first. The AI cannot guess your table names or column structures.
* Include sample data if possible: "Here are 3 example rows from this table: ..."
* Start with simple queries and build complexity. Get the basic SELECT right before adding JOINs and subqueries.
* Always review the WHERE clause carefully. This is where AI makes the most mistakes.

**For Dimensions data work:** If you query the Dimensions API or underlying data, describe the data model to the AI. "Dimensions publication records have fields: doi, title, authors (array), journal, year, citations_count, funder_ids, research_org_ids, concepts (array)."

## AI-Assisted Analysis in Spreadsheets

For team members who work primarily in Google Sheets or Excel, AI features built into these tools can save significant time.

**Google Sheets with Gemini:**
* Open the Gemini side panel and describe your analysis goal: "I have monthly customer support ticket counts by product in columns B through G. Calculate year-over-year growth rates and highlight any product where tickets increased by more than 20%."
* Ask for formula explanations: "What does this ARRAYFORMULA do?" Paste any formula you did not write yourself.
* Generate charts: "Create a line chart showing ticket volume trends over time, with a separate line for each product."

**Data cleaning with AI:**
Messy data is the norm in customer analytics. AI can help:
* "Standardize these institution names. Group variations like 'MIT', 'Massachusetts Institute of Technology', and 'Mass. Inst. of Tech.' under a single canonical name."
* "These dates are in mixed formats (DD/MM/YYYY, MM-DD-YYYY, YYYY.MM.DD). Standardize them all to ISO format."
* "Identify duplicate rows based on the email column, keeping the most recent entry."

## Python and R Acceleration

For the data science team and technical analysts, AI is an effective pair programmer for analytical code.

**Generating analysis scripts:**
Describe what you want to analyze and the AI can generate working Python or R code:
"Write a Python script using pandas that: loads a CSV of customer renewal data, groups by product line, calculates the renewal rate (renewed / total) for each product, creates a bar chart comparing renewal rates, and flags any product with a renewal rate below 80%."

**Debugging and optimization:**
* Paste error messages along with your code. AI is very good at explaining Python tracebacks and suggesting fixes.
* Ask for optimization: "This pandas operation takes 30 seconds on my 500K row dataset. How can I make it faster?"
* Request code reviews: "Review this analysis script for bugs, edge cases, and readability improvements."

**Statistical analysis:**
* "I have two groups of customers (high-touch and low-touch support). Here are their renewal rates. Run a chi-squared test to determine if the difference is statistically significant. Show the code and explain the result."
* "Perform a cohort analysis on this customer data, grouping by sign-up quarter and tracking retention over 12 months."

## Building Dashboards and Visualizations

AI can help you go from raw data to a presentable dashboard faster.

**Narrative generation:**
After running your analysis, paste the key numbers into an AI tool and ask: "Write a one-paragraph executive summary of these customer health metrics. Target audience is a VP who has 2 minutes to read this. Highlight the most important trend and one area of concern."

**Visualization suggestions:**
Describe your data and ask: "What is the best way to visualize this data? I need to show customer churn by product over 12 months, broken down by customer segment." AI will suggest chart types and explain why each works.

**Report generation:**
For the research analytics team producing reports for government and funder customers:
1. Run your analysis and collect the key findings
2. Ask AI to draft the narrative sections: "Based on these findings about grant funding patterns in genomics from 2020-2025, write a two-paragraph summary suitable for an ARPA-H program officer."
3. Review carefully for accuracy. Funders expect precision.

## Customer Health Scoring

AI can help analyze customer behavior patterns to predict churn or identify upsell opportunities.

**Simple health scoring:**
1. Define your signals: login frequency, support ticket volume, feature adoption, contract utilization
2. Ask AI: "Here is customer engagement data for 50 accounts. Based on these signals, identify which accounts show signs of decreasing engagement and which show signs of strong adoption. Explain your reasoning."
3. Cross-reference with your knowledge of the accounts

**Sentiment analysis:**
If you have customer feedback data (survey responses, support tickets, NPS comments):
* "Categorize these customer comments as positive, negative, or neutral. For negative comments, identify the primary concern (product quality, support responsiveness, pricing, or functionality gap)."
* "Summarize the top 3 themes in this quarter's NPS detractor comments."

## Practical Considerations

**Data sensitivity:** Before pasting customer data into an AI tool, anonymize it. Replace institution names with codes, remove individual user information, and aggregate where possible. Refer to the AI Ethics and Safety guide for detailed data classification guidance.

**Verification:** AI-generated analysis code can contain subtle bugs. Always spot-check results against manual calculations for a few rows. If AI tells you the renewal rate is 85%, verify it by hand on a sample.

**Reproducibility:** If you generate code with AI assistance, save the prompts alongside the code. This makes it easier for colleagues to understand how the code was produced and to modify it later.

## Try This Today

**For spreadsheet users:**
1. Open a Sheet you are currently working with
2. Ask Gemini to identify the top 3 trends in the data
3. Compare its analysis to your own understanding
4. Ask it to generate a chart you would normally spend 15 minutes creating manually

**For SQL users:**
1. Pick a question you recently answered with a query
2. Describe it in plain English to AI without showing your query
3. Compare the AI-generated SQL to yours
4. Try a new, harder question

**For Python/R users:**
1. Take an analysis script you wrote recently
2. Ask AI to review it for bugs, edge cases, and optimization opportunities
3. Try generating a similar analysis from scratch using only natural language description
4. Compare the output to your hand-written version

Share the most interesting finding from your experiment in #AI-Tuesdays.
