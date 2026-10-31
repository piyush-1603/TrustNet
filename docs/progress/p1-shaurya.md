# Progress: Person 1, Shaurya (trust engine, integration)

Owner of this file: Shaurya only. Add one log entry per PR, newest at the bottom.

## Checklist
- [x] models.py, loaders.py, policy.json (+ load_policy with hash) (PR open: p1/models-loader)
- [x] project_trust (3 hops, decay 0.6, cycle-safe) (PR open: p1/trust-engine)
- [x] evaluate_author (b, d, u, decision, reasons, ignored) (PR open: p1/trust-engine)
- [x] evaluate_pr + campaign override to HOLD (PR open: p1/trust-engine)
- [x] naive_score baseline (PR open: p1/trust-engine)
- [x] tests: transitive 0.486, 4 hops = 0, cycle, brigade ignored, newcomer PROVISIONAL, two viewpoints differ, no-evidence halves, expired ignored (PR open: p1/trust-engine)
- [ ] Keep PLAN.md status table and decision log current
- [ ] Review and merge teammates' PRs; run the full pipeline end to end

## Log
Format: `date time | PR title | what changed | what is next | gotchas`

2026-10-31 | PR: models, loaders, policy.json | Added the data classes (models.py), network and policy loaders with input validation (loaders.py), policy.json with trust/decision/campaigns sections, 25 tests | Next: trust.py (project_trust, evaluate_author, evaluate_pr, naive_score) on p1/trust-engine | Timestamps are stored as given and parsed with models.parse_time; Anubhav's campaigns.py/lab.py already match these signatures
2026-10-31 | PR: trust engine | Added trust.py (project_trust, evaluate_author, evaluate_pr, naive_score) and 25 tests; ran Anubhav's p2/similarity merged with it: 82 tests pass and lab.run() gives defended inflation 0 on all four attacks, collusive cluster -> HOLD | Next: review teammates' PRs, run the full pipeline when simulate/cli land, then the Vouch-file reader | evaluate_pr judges expiry as of the PR time; b and d are not rescaled when b+d>1 (see PLAN decision log)
2026-10-31 | PR: docs accuracy | Merged #5, #6; fixed DESIGN.md/README to match the engine (policy key names, no b/d rescaling, 12-hex policy hash) | Next: review #2 (draft) and Piyush's simulator PR, then run the full pipeline | README/DEMO command examples (--projects, --verbose, PR ids) are guesses until cli.py lands: re-check them then
