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
2026-10-31 | PR: remove fake embedding server (into p3/simulator) | Deleted examples/ollama_embed_server.py (TF-IDF + random projection pretending to be nomic-embed-text) and the script fallback that started it; make_examples.sh now exits unless real Ollama has nomic-embed-text; regenerated examples/ with real Ollama (23 POST /api/embed calls seen in the Ollama log) | Next: merge #8 once Piyush has pulled this; Arnav fixes DEMO.md commands (real PR ids pr-001..pr-202; no --verbose flag) | The old committed outputs were identical in content, but they were produced by the fake server and are now reproduced by the real model
2026-10-31 | PR: docs accuracy | Merged #5, #6; fixed DESIGN.md/README to match the engine (policy key names, no b/d rescaling, 12-hex policy hash) | Next: review #2 (draft) and Piyush's simulator PR, then run the full pipeline | README/DEMO command examples (--projects, --verbose, PR ids) are guesses until cli.py lands: re-check them then
2026-11-01 | PR: demo fixes | Newcomers now each open one PR (pr-203..pr-217; labels.newcomer_pr_ids) so the demo can evaluate one; examples/ regenerated with real Ollama (23 /api/embed calls); DEMO.md and README commands rewritten to ids and flags that exist (pr-203 newcomer, pr-001 proj-01 vs proj-05, pr-002 brigade, pr-202 trusted denounce, pr-151 campaign, pr-189 bump; no --verbose); ran every documented command in a clean dir, all exit 0 | Next: final fresh-clone check of main, mentor answers | simulate.py is Piyush's and DEMO/README are Arnav's: edited as integrator, please glance
