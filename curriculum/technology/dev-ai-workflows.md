---
difficulty: intermediate
---

# AI-Assisted Development Workflows

## Context

The Technology department is 219 people, the largest at Digital Science, building and maintaining products across Overleaf, Dimensions, Symplectic Elements, Metaphacts, ReadCube, Altmetric, Writefull, and more. AI coding tools are not a nice-to-have for this team. They are a fundamental shift in how software gets built, and adopting them well is how we stay ahead of AI-native competitors entering our space.

This guide covers the three main AI coding tools available to the Technology team and practical workflows for integrating them into daily development.

## GitHub Copilot

Copilot is the most established AI coding assistant. It runs inside your IDE and suggests code as you type. The key to getting value from Copilot is learning to guide it rather than just accepting its suggestions.

**Effective Copilot habits:**

* **Write descriptive comments before writing code.** Copilot reads your comments to understand intent. "// Function to validate Overleaf user session tokens against the OIDC provider" will produce much better suggestions than "// validate token."
* **Use Copilot Chat for explanations.** Highlight unfamiliar code (especially in legacy codebases like Elements or IFI Claims) and ask: "Explain what this function does and identify any edge cases."
* **Generate tests first.** Write a comment describing the test case, let Copilot generate the test, then write the implementation. This forces test-driven development even if you do not normally practice it.
* **Refactoring assistance.** Select a block of code and ask Copilot Chat: "Refactor this to be more readable and add error handling." Review every suggestion carefully, as Copilot sometimes introduces subtle bugs during refactoring.

**What Copilot is NOT good at:**
* Understanding your full project architecture (it works mostly file-by-file)
* Making design decisions (it will write whatever pattern you start with, even if it is the wrong one)
* Knowing about your internal libraries or custom frameworks without context

## Claude Code

Claude Code is a command-line tool that works with your entire codebase, not just the file you have open. It can read your project structure, understand relationships between files, and make changes across multiple files at once.

**Where Claude Code shines at DS:**

* **Multi-file refactoring.** "Rename the UserAuth class to OIDCAuthProvider across all files in this project and update all references." Claude Code understands import graphs and dependency chains.
* **Architecture exploration.** Point it at an unfamiliar codebase and ask: "Explain the data flow from API request to database write in this application." Especially useful when onboarding to a new product team or working with the Dimensions Data Pipeline.
* **Building new features with guidance.** Describe what you want at a high level: "Add a new API endpoint that returns aggregated grant funding data filtered by institution, with pagination and rate limiting." Claude Code will scaffold the implementation across models, routes, tests, and documentation.
* **Debugging complex issues.** Paste an error trace and ask: "What is causing this error and what is the fix?" Claude Code can examine the relevant source files to provide context-aware debugging.

**Practical workflow for Claude Code:**
1. Start with a clear description of what you want to build or change
2. Let Claude Code propose an approach; review it before accepting
3. Ask it to implement in stages, reviewing each stage
4. Run your test suite after each stage to catch issues early
5. Use it to generate the commit message summarizing the changes

## Cursor

Cursor is an AI-native editor built on VS Code. It combines the in-editor experience of Copilot with deeper project understanding similar to Claude Code.

**Cursor's advantages:**
* It indexes your entire codebase and understands cross-file relationships
* You can chat with it about your project architecture while editing
* It supports multi-file editing in a single operation
* The Composer feature lets you describe changes in natural language and see diffs before applying

**When to use Cursor vs. Copilot vs. Claude Code:**
* **Copilot:** Quick in-line completions while typing. Best for boilerplate and patterns.
* **Cursor:** When you need project-wide awareness in an editor. Best for feature development.
* **Claude Code:** When you want command-line control or are working across multiple projects. Best for large refactors and exploration.

## AI-Assisted Code Review

AI tools can catch issues that humans miss, but they should supplement review, not replace it.

**Practical code review workflow:**
1. Before submitting a PR, ask your AI tool: "Review this diff for bugs, security issues, and readability problems."
2. Pay special attention to AI suggestions about error handling, edge cases, and resource cleanup.
3. Use AI to generate the PR description: paste the diff and ask for a summary of what changed and why.
4. During review of others' code, use AI to quickly understand unfamiliar code: "What does this function do and what are its failure modes?"

**What AI review catches well:** Null pointer risks, missing error handling, SQL injection vulnerabilities, unused variables, inconsistent naming.

**What AI review misses:** Business logic errors, architectural appropriateness, performance implications specific to your infrastructure, whether the code actually solves the right problem.

## Automated Test Generation

One of the highest-value uses of AI for developers is generating test cases, because test writing is time-consuming and often skipped under deadline pressure.

**Workflow:**
1. Point your AI tool at a function or class
2. Ask: "Generate unit tests for this function covering normal operation, edge cases, and error conditions"
3. Review the generated tests. AI often reveals edge cases you had not considered.
4. Run the tests. Fix any that fail due to incorrect assumptions about your codebase.
5. Add your own tests for business logic that the AI cannot infer

**For the Dimensions Data Pipeline team:** AI can generate tests for data transformation functions, ETL validation steps, and API response parsing. Given the pipeline's complexity (grants, publications, clinical trials, patents), automated test generation can significantly improve coverage.

**For the DevOps team:** AI can generate infrastructure-as-code tests, validate Kubernetes configurations, and generate monitoring alert rules. Ask: "What could go wrong with this Terraform configuration?" and review the edge cases it identifies.

## AI for DevOps and Infrastructure

The DevOps team (22 people) and Group IT & Security team (10 people) have specific AI use cases:

* **Infrastructure-as-code generation:** Describe what you need in plain language and let AI generate Terraform, CloudFormation, or Kubernetes manifests. Always review the output against your security requirements and FedRAMP compliance needs.
* **Incident response:** During an incident, paste log output into an AI tool and ask: "What is the likely root cause? What should I check next?" This accelerates triage without replacing your judgment.
* **Runbook automation:** Take an existing runbook and ask AI to convert it into executable scripts, or identify steps that could be automated.
* **Monitoring and alerting:** Ask AI to analyze historical alert data and suggest which alerts are noisy and which thresholds should be adjusted.

## Security Considerations for Developers

* **Never paste production secrets, API keys, or credentials into AI tools.** Use placeholder values if you need to discuss code that involves authentication.
* **Review generated code for security.** AI may suggest patterns with known vulnerabilities, especially around authentication, input validation, and data serialization.
* **Be careful with generated dependencies.** AI sometimes suggests importing packages that do not exist ("hallucinated packages"), which can be a supply chain attack vector. Verify every package name before adding it.
* **Code generated by AI may contain patterns from open-source projects.** Be aware of license implications, especially for code destined for proprietary DS products.

## Try This Today

1. Pick a function in your current project that lacks test coverage
2. Ask your preferred AI tool to generate comprehensive tests for it
3. Run the tests. Note which pass, which fail, and which edge cases you had not considered.
4. Fix any failing tests and add any missing cases the AI overlooked
5. Commit the new tests and share your experience in #AI-Tuesdays

This exercise typically takes 30-45 minutes and produces real, usable test coverage for your codebase.
