# CODEVERSE: First 20 developers validation kit

This is a **local pilot analytics prototype**, not evidence of 20 recruited developers. The CSV is intentionally empty.

## Journey definition
Consent → CV extracted → GitHub evidence connected (or alternate verified evidence) → target job chosen → readiness explained → project recommended → project verified → rescoring completed → feedback collected. Each step must occur in order. Record a completion only if the step truly happened.

## Data collection
Use randomized participant IDs, not names, account handles, email, CV text, GitHub tokens, IP addresses, or job application data in the CSV. Collect consent and an appropriate privacy notice *before* recording pilot participation. Allow withdrawal and deletion. Keep the crosswalk between real participant identities and their pseudonyms outside this analytics file, in access-controlled storage, only if strictly necessary. A pseudonym is still personal data when reidentifiable.

Only record relevant scores and milestone events in the application's protected evidence ledger. `skill_improved` is self-reported in this local template, not a validated learning measurement. For objective skill improvement, use a comparable baseline/post-project assessment and record the test protocol, rubric, result and reviewer separately.

## Recruitment protocol
Recruit at least 20 eligible developers through voluntary opt-in (aim to invite more to account for drop-off); do not record a completed journey until all steps pass. Avoid promising employment outcomes. Let participants leave at any time. Collect optional willingness-to-pay as a specific monthly amount, and record the actual offer/pricing context separately for interpretation.

## Validation
Manually audit a stratified sample of extracted skills and jobs against reference labels. Report precision/recall and annotation disagreements with denominators. For recommendation usefulness, ask a consistent 1–5 question (1 not useful; 5 very useful). For objective learning gains, verify completed project criteria and compare assessment results, not merely score increases.

Run from repository root:

```bash
python -m unittest tests_python.test_pilot -v
python -m pilot.metrics pilot/journeys.csv --output pilot/report.json
```

The report aggregates counts and does not contain participant identifiers. Do not publish per-user data without a separate lawful basis and disclosure review.

## Release gate
20 consented complete journeys, reviewed extraction and job-matching quality, passing privacy/security review, documented incident response, and an explicit decision on pricing informed by willingness-to-pay feedback. A value of `target_reached: true` is *not* evidence of independent audit or GDPR compliance.
