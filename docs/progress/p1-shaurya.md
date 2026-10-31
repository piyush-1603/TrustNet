# Progress: Person 1, Shaurya (trust engine, integration)

Owner of this file: Shaurya only. Add one log entry per PR, newest at the bottom.

## Checklist
- [x] models.py, loaders.py, policy.json (+ load_policy with hash) (PR open: p1/models-loader)
- [ ] project_trust (3 hops, decay 0.6, cycle-safe)
- [ ] evaluate_author (b, d, u, decision, reasons, ignored)
- [ ] evaluate_pr + campaign override to HOLD
- [ ] naive_score baseline
- [ ] tests: transitive 0.486, 4 hops = 0, cycle, brigade ignored, newcomer PROVISIONAL, two viewpoints differ, no-evidence halves, expired ignored
- [ ] Keep PLAN.md status table and decision log current
- [ ] Review and merge teammates' PRs; run the full pipeline end to end

## Log
Format: `date time | PR title | what changed | what is next | gotchas`

2026-10-31 | PR: models, loaders, policy.json | Added the data classes (models.py), network and policy loaders with input validation (loaders.py), policy.json with trust/decision/campaigns sections, 25 tests | Next: trust.py (project_trust, evaluate_author, evaluate_pr, naive_score) on p1/trust-engine | Timestamps are stored as given and parsed with models.parse_time; Anubhav's campaigns.py/lab.py already match these signatures
