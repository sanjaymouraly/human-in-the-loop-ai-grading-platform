# Evaluation Methodology

## Purpose
This platform implements trustworthy human-in-the-loop evaluation for LLM responses, following best practices from AI evaluation literature.

## Core Principles

### 1. Independent Human Judgments as Source of Truth
- Human judgments are primary; any automated hints must be labeled as suggestions
- No LLM auto-grading that undermines independent evaluation
- Reviewer notes, evidence, and rationale required

### 2. Blind Review & Balanced Presentation
- When blind_review enabled, model identities (model_a, model_b) hidden from reviewers
- A/B order randomized per assignment via `display_a_is_original_a`
- Balancing: random 50/50 distribution, prevents position bias
- Original IDs preserved for reporting despite randomized display

### 3. Distinct Preference Semantics
- **Response A**: A is better than B
- **Response B**: B is better than A
- **Tie**: Equally good (not "both bad")
- **Both Unacceptable**: Both fail, neither acceptable
- These outcomes have distinct meanings and are not silently merged

### 4. Structured Rubrics
Dimensions (default 9):
1. Instruction following
2. Factual accuracy
3. Completeness
4. Relevance
5. Reasoning quality
6. Clarity and readability
7. Safety and harmful-content handling
8. Conciseness and usefulness
9. Overall response quality

Each dimension:
- Scale (e.g., 1-5) with anchored descriptions (e.g., 1="Poor", 5="Excellent")
- Weight (affects aggregate but not kappa)
- Allow N/A
- Order
- Required flag

Rubric versioning:
- Version auto-increments per project
- Review stores FK to rubric version used
- Historical reviews remain interpretable after rubric revisions

### 5. Factual Error & Instruction Violation Reporting
Issue records:
- Category: hallucination, incorrect calculation, unsupported claim, missed constraint, formatting, omitted requirement, broken code, reasoning mistake, unsafe content, other
- Severity: low, medium, high, critical
- Excerpt (relevant response part)
- Evidence/source
- Explanation
- Verification status
- Correction (optional)

Filters and analytics for recurring failure patterns.

### 6. Multi-Reviewer Workflow
- Same item assigned to multiple reviewers for double-review
- Assignment queue, progress, draft vs submitted, workload distribution
- Prevent duplicate final submissions, assignment collisions
- Database transactions and concurrency controls

### 7. Disagreement Management
- Disagreement = same item, ≥2 submitted reviews, differing preferences
- Manager/adjudicator inspects both independent reviews, compares evidence, records final adjudication with rationale
- Original judgments preserved permanently in review history
- Adjudication stores snapshot of reviews at decision time
- Never overwrites original reviewer submissions

### 8. Inter-Rater Agreement Statistics

#### Cohen's Kappa (2 reviewers)
- For categorical agreement (preference labels)
- Computed only on items rated by both reviewers with matching rubric
- Formula: (Po - Pe) / (1 - Pe) where Po=observed agreement, Pe=expected agreement
- Implemented via sklearn.metrics.cohen_kappa_score

Edge cases handled:
- No paired items → error "No paired observations", kappa None
- Different rating schemes → not computed (labels must match)
- Empty datasets → error
- Single-category outcomes → kappa undefined (perfect agreement but single label), warning issued
- Undefined kappa (NaN) → handled, error message
- Missing/abstained (skipped, draft) → excluded from denominator, not merged into ordinary categories

Also reported:
- Raw percent agreement
- Number of paired observations
- Category distributions
- Confusion matrices
- Missing/abstained counts

#### Weighted Kappa (ordered scales)
- For ordered rating scales (dimension scores)
- Linear or quadratic weights
- Documented: weights penalize larger disagreements more

#### Fleiss' Kappa (>2 reviewers)
- For compatible designs where same number of raters per item
- Computed when >2 reviewers and consistent rater count
- Clearly explained when unavailable (different rater counts, insufficient observations)

#### Uncertainty & Small Samples
- Show caution for small samples (n < 10, warning)
- Do not label agreement as objectively "good" or "bad" using unexplained thresholds
- Provide raw numbers and allow user interpretation

### 9. Analytics & Reporting
- Total tasks, completion %
- Reviewer productivity
- Model A vs B win/tie/rejection distributions (with sample sizes)
- Average dimension scores (only where scales comparable, weights noted)
- Common factual-error categories
- Instruction-violation frequency
- Severity breakdowns
- Reviewer disagreement and adjudication rates
- Review-time distributions when reliably measured
- Model-level comparisons with limitations
- Date filters, project filters, reviewer filters with access controls
- Downloadable reports (CSV, JSON, JSONL)

Distinguish human preference from factual correctness: preferred response is not necessarily factually verified.

### 10. Calibration & Quality
- Reviewer calibration examples with known reference labels (future)
- Blind review and balanced A/B
- Reviewer-level agreement reports
- Audit trails for admin and review actions
- Rubric guidance accessible during evaluation

## Limitations & Cautions
- Weighted averages of dimensions not automatically valid (different constructs)
- Preference ≠ correctness; track both
- Small sample kappa has high variance
- Single-category kappa undefined (not "perfect")
- Human evaluation is subjective; agreement measures reliability, not ground truth
- Timing data only if reliably measured

## References
- Cohen (1960) A coefficient of agreement for nominal scales
- Fleiss (1971) Measuring nominal scale agreement among many raters
- Best practices from AI evaluation: HELM, LMSYS Chatbot Arena, etc.
