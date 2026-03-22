---
difficulty: intermediate
---

# Process Automation with AI

## Context

The Operations team of 39 people is the operational backbone of Digital Science, covering sales operations, marketing operations, business analysis, proposals/RFPs, purchasing, and workforce planning. The team uses Salesforce CRM, Pardot for marketing automation, Float for resource planning, and Front for customer communications. VP of Operational Excellence Alex Rauseo is already evaluating AI tools including Perplexity, Atlas AI, Scribe, and LinkSquares.

This team has a natural advantage in AI Tuesdays: you already think in processes and workflows. The skill to build now is identifying which parts of those processes AI can handle.

## The Process Automation Audit

The Operations team's first AI Tuesday activity is a "Process Automation Audit." This is a structured approach to finding where AI can save time.

**Step 1: Map your repetitive processes (15 minutes)**
List every task you do at least weekly. Be specific:
* "Update Salesforce pipeline report every Monday"
* "Route incoming RFPs to the right team member"
* "Clean up CRM data: fix duplicates, standardize company names"
* "Generate weekly email campaign performance summary from Pardot"
* "Create resource allocation plan in Float"

**Step 2: Score each task (10 minutes)**
For each task, rate on a 1-5 scale:
* Time spent per week (1 = minutes, 5 = hours)
* Repetitiveness (1 = unique each time, 5 = nearly identical)
* Data dependency (1 = requires judgment, 5 = follows clear rules)

Tasks scoring high on all three are your best automation candidates.

**Step 3: Identify the AI approach (15 minutes)**
For each high-scoring task, ask: What kind of AI assistance would help?
* **Drafting:** AI generates a first draft you review (report narratives, email templates)
* **Extraction:** AI pulls specific data from documents (RFP requirements, contract terms)
* **Classification:** AI categorizes inputs (ticket routing, data tagging)
* **Transformation:** AI converts data between formats (CRM export to presentation, meeting notes to action items)

**Step 4: Test one process today**
Pick the highest-scoring task and try automating it with AI right now.

## CRM Data Operations

Sales Operations Associates and the CRM team spend significant time on data quality. AI can help at every stage.

**Data enrichment:**
"Here is a list of 50 company names from our CRM. For each, find and add: headquarters location, approximate employee count, whether they are a university/government/corporate entity, and their primary research focus area. Format as a table I can import back into Salesforce."

Review the output carefully. AI may hallucinate company details, especially for smaller or newer organizations.

**Duplicate detection and cleanup:**
"Here are 100 account records from Salesforce. Identify likely duplicates based on: similar company names (accounting for abbreviations and variations), matching domains, or matching addresses. Group the duplicates and suggest which record to keep as primary."

**Data standardization:**
"Standardize these CRM entries:
* Company names: use the full legal name (not abbreviations)
* Countries: use ISO 3166-1 alpha-2 codes
* Phone numbers: format as +[country code] [number]
* Job titles: normalize to standard categories (VP Sales, Director of Research, etc.)"

## Proposal and RFP Workflow

The Proposal/RFP Coordinator handles a steady stream of RFP responses. AI can accelerate this process significantly.

**RFP triage:**
"Read this RFP document and extract:
* Issuing organization and deadline
* Products/services they are requesting
* Key evaluation criteria and their weightings
* Mandatory requirements (must-haves)
* Any disqualifying factors for Digital Science
* Estimated effort to respond (based on scope and complexity)"

**Response drafting from templates:**
"Here is the RFP question: [paste]. Here is our standard response from our template library: [paste]. Tailor the standard response to match the specific language and requirements of this RFP. Adjust the tone to match a [government/academic/enterprise] audience."

**Proposal assembly:**
"I need to compile a proposal for [customer]. I have these sections from our template library: [list sections]. The customer's specific requirements are: [paste requirements]. Identify which template sections address which requirements. Flag any requirements that our templates do not cover."

## Marketing Operations and Pardot

**Campaign analysis:**
"Here are the results from our last 10 Pardot email campaigns: [paste metrics]. Analyze:
* Which campaigns generated the most engagement?
* Are there patterns by send time, subject line style, or audience segment?
* Which campaigns contributed to pipeline (if attribution data is available)?
* Recommendations for optimizing our next campaign batch"

**List management:**
"I need to create a Pardot list for an upcoming campaign targeting research universities in Europe with more than 10,000 students. Here are the criteria and the data I have available: [describe]. Write the segmentation logic I should use."

**Workflow optimization:**
"Here is a description of our current lead nurture workflow in Pardot: [describe steps]. Identify:
* Steps that could be more personalized with AI
* Decision points that could use more sophisticated criteria
* Where we are likely losing leads and why
* Suggestions for improving conversion at each stage"

## Business Analysis and Reporting

Business analysts can use AI to accelerate their reporting and analysis workflows.

**Report generation:**
"Here is raw data from our monthly operations dashboard: [paste]. Write a brief (one-page) executive summary highlighting: key operational metrics, trends, areas of concern, and recommendations. Target audience is the VP of Operational Excellence."

**Process documentation:**
The team is evaluating Scribe for process documentation. AI can help in the meantime:
"I am going to describe a process step by step. Document it as a standard operating procedure with: numbered steps, decision points, expected inputs and outputs for each step, and common error conditions. The process is: [describe]"

**Scenario analysis:**
"We are considering three options for improving our RFP response process: [describe options]. For each, analyze: estimated time savings, implementation effort, risks, and dependencies. Recommend which option provides the best return on investment."

## Salesforce AI Features (Agentforce)

The Operations team has identified capitalizing on AI features embedded in existing systems (like Salesforce's Agentforce) as a key use case. This is smart because it does not require learning new tools.

**What Agentforce can do:**
* Automate lead scoring and routing based on engagement patterns
* Generate email drafts within Salesforce using account context
* Summarize account activity and suggest next best actions
* Predict deal outcomes based on historical patterns

**Where to start:**
1. Identify one Salesforce workflow that involves manual data interpretation or routing
2. Check whether Agentforce has a feature that addresses it
3. Configure a pilot with a small subset of data
4. Compare the AI's decisions to what a human would have done
5. If the accuracy is acceptable, roll out more broadly

## Contract Analysis (LinkSquares)

The team is already evaluating LinkSquares for contract analysis. Whether using LinkSquares or a general AI tool, the workflow is:

"Summarize this contract. Extract: key terms (duration, value, renewal conditions), obligations for each party, liability and indemnification provisions, data processing terms, and any unusual or non-standard clauses."

"Compare these two vendor contracts side by side. What are the key differences in: pricing structure, service levels, termination rights, and data handling?"

**Caution:** Contract analysis by AI should always be reviewed by someone with contract expertise. AI can miss nuances in legal language and may not understand the implications of specific clauses.

## Sharing Automation Solutions

One of the Operations team's goals is to "establish a framework for sharing automated solutions across the team." AI Tuesdays is the time to build this.

**Practical approach:**
1. When you successfully automate a process, document it: the problem, the AI approach, the prompt(s) used, and the results
2. Share the documentation in #AI-Tuesdays or a dedicated Operations AI channel
3. Each week, one team member demos their most useful automation in the team meeting
4. Build a shared library of prompts and workflows that the entire Ops team can use

## Try This Today

1. Complete the Process Automation Audit described above
2. Pick your highest-scoring task
3. Try using AI to perform that task right now
4. Document: What worked? What did not? How much time did it save?
5. Share your audit results and your first automation attempt in #AI-Tuesdays

The goal by Week 12 is for each Operations team member to have at least one validated process where AI automation reduces time spent by 20% or more.
