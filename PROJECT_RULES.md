# Project Development Rules

## 1. Communication Rules

* The user may write prompts in Korean or English.
* Analyze instructions in the original language.
* Prefer responding in Korean.
* Use English only when technical accuracy would be improved.
* Keep explanations concise and practical.
* Avoid unnecessary theory unless requested.

---

## 2. Architecture Rules

* Preserve existing project architecture whenever possible.
* Prefer extending existing modules over creating new parallel structures.
* Do not introduce unnecessary frameworks.
* Avoid over-engineering.
* Keep the codebase understandable for junior developers.

---

## 3. Object-Oriented Design

* Use classes only when they provide clear value.
* Do not create classes for simple procedural logic.
* Prefer composition over inheritance.
* Avoid deep inheritance chains.
* Keep responsibilities explicit.

---

## 4. Single Responsibility Principle

Each function should have one responsibility.

Good:

* fetch_html()
* parse_jobs()
* analyze_jobs()
* save_jobs()

Bad:

* process_everything()

---

## 5. Function Design

* Functions should be small and readable.
* Split long conditional logic.
* Avoid nested if statements when possible.
* Use meaningful function names.
* Prefer early returns.

---

## 6. Naming Rules

Use clear names.

Good:

* analyze_jobs
* calculate_match_score
* extract_skills

Bad:

* func1
* data_process
* tmp

---

## 7. Configuration Rules

* Avoid hardcoded values.
* Move configurable values to config files.
* Use constants for scoring rules.
* Use environment variables for secrets.

---

## 8. Error Handling

* Fail safely.
* Log errors with useful context.
* Never silently swallow exceptions.
* Provide actionable error messages.

---

## 9. Logging Rules

* Use structured logging when possible.
* Avoid excessive print statements.
* Important actions should be logged.

---

## 10. Data Rules

* Remove duplicates whenever possible.
* Normalize data before analysis.
* Validate external data.
* Handle missing fields gracefully.
* Normalize deadline values into `deadline_date` whenever possible.
* Treat missing or unparseable deadline values as low-confidence data and expose them in health checks.
* Final reports should prefer active, non-expired job postings over only newly updated postings.

---

## 11. Analyzer Rules

Job matching logic must be explainable.

Each score should provide:

* score
* matched_skills
* missing_skills
* reason

Avoid black-box scoring.

---

## 12. Modification Rules

Before making changes:

1. Explain the implementation plan.
2. Show files to create.
3. Show files to modify.

After implementation:

1. Summarize changes.
2. Explain risks.
3. Explain how to test.

Never modify files without first explaining the plan.

---

## 13. Code Quality Rules

* Prefer readability over cleverness.
* Prefer maintainability over brevity.
* Write code that can be understood six months later.
* Minimize technical debt.

---

## 14. AI Collaboration Rules

When uncertain:

* Ask before making assumptions.
* Do not invent requirements.
* Do not fabricate data.
* Clearly distinguish facts from assumptions.

If repository structure is unclear:

* Inspect first.
* Then propose changes.

Never rewrite large parts of the project unless explicitly requested.

---

## 15. Tami Rules

* Preserve existing project flow.
* Do not rename files without reason.
* Do not change working behavior unless requested.
* Prefer incremental improvements.
* Provide complete runnable code.
* Explain why structural changes are necessary.
* Keep solutions practical and production-oriented.

---

## 16. Dependency Rules

* Do not add new dependencies unless necessary.
* Prefer Python standard library first.
* Explain why a new dependency is required.
* Show alternative approaches before introducing large libraries.

---

## 17. Repository Awareness Rules

* Always inspect existing code before proposing changes.
* Reuse existing modules when possible.
* Avoid creating duplicate functionality.
* Respect current folder structure.
* Check for similar implementations before adding new code.

---

## 18. Crawling Ethics & Site Safety Rules

* Respect robots.txt and site terms where applicable.
* Do not overload the target site.
* Use reasonable request delays.
* Avoid aggressive parallel crawling.
* Do not bypass authentication, paywalls, or access controls.
* Stop crawling when blocked or rate-limited.

---

## 19. Request Strategy Rules

* Use headers that represent a normal browser request.
* Configure timeout for every HTTP request.
* Configure retry count and retry delay.
* Do not retry endlessly.
* Log failed URLs with reason.
* Separate list-page crawling and detail-page crawling.
* Detect unhealthy responses such as empty pages, blocked pages, captcha pages, or unusually short HTML.
* Retry transient collection failures with bounded backoff.
* Do not save clearly unhealthy HTML as successful crawl data.
* Keep enough raw response context to debug parser failures.

---

## 20. Data Schema Rules

Each job posting should keep consistent fields.

Required fields:

* job_id
* title
* company_name
* job_url
* location
* career
* education
* employment_type
* deadline
* deadline_date
* source
* collected_at

Optional fields:

* salary
* skills
* preferred_conditions
* main_tasks
* qualifications
* benefits
* company_size
* industry

---

## 21. Duplicate Detection Rules

* Use job_id as the primary duplicate key when available.
* If job_id is missing, use normalized job_url.
* If both are missing, use company_name + title + deadline.
* Do not save duplicated postings.
* When existing postings change, update them instead of inserting duplicates.

---

## 22. Parser Stability Rules

* Parser functions must handle missing elements safely.
* Do not assume every page has the same HTML structure.
* Keep CSS selectors centralized when possible.
* Return empty values instead of crashing on missing optional fields.
* Log parsing failures with URL and selector context.

---

## 23. Output Rules

* Exported data must be readable without additional processing.
* CSV column names must be consistent.
* Use UTF-8 with BOM when exporting CSV for Excel compatibility.
* Keep raw collected data and analyzed data separable.
* Include collected_at and source fields in every output.
* JobKorea match report CSV files must use the `YYYYMMDD_jobkorea_match.csv` naming format.
* JobKorea match report XLSX files must be generated next to the CSV with the same base filename.
* XLSX report URL cells must be real clickable hyperlinks from the first open.
* JobKorea match reports must include only Seoul, Gyeonggi, and Incheon locations unless the user explicitly changes the region scope.
* JobKorea match reports must exclude postings with normalized `deadline_date` earlier than the current Korea date.
* JobKorea reports should keep existing non-expired postings as candidates, not only postings updated today.

---

## 24. JobKorea Collection Accuracy Rules

* Crawl enough list pages per keyword to reduce missing active postings.
* Do not assume today's updated postings are the full candidate set.
* Existing postings should remain eligible while their deadline has not passed.
* Detail collection should backfill important missing fields, especially deadline, skills, tasks, qualifications, and benefits.
* Run collection health checks after crawling and before trusting the final report.
* Health checks should report at least total postings, active regional postings, missing normalized deadlines, missing detail data, duplicate source IDs, and latest crawl timestamps.
* If missing deadlines or failed detail pages remain high, clearly report the remaining data confidence risk.
* Prefer resumable or repeatable collection flows over one-shot crawls when the target site is unstable.

---

## 25. Personal Matching Rules

Matching analysis should be based on explicit criteria.

Each result should include:

* match_score
* matched_keywords
* missing_keywords
* positive_reasons
* negative_reasons
* recommendation_level

Do not produce a score without explanation.

---

## 26. Execution Safety Rules

* Avoid subprocess, shell execution, and background process spawning unless necessary.
* If subprocess is required, explain why before using it.
* Set timeout for every external process.
* Never run destructive commands automatically.
* Do not create infinite loops or uncontrolled schedulers.
* Prefer explicit one-time execution over background automation.

---
