# TrustNet build plan

Team Sophons · Hacktoberfest 2026 Hack Day Sonipat · Problem 7: Decentralized Trust Network for Open Source Contributions.
Repo freeze and submission: 6:30 AM, 1 Nov 2026. Demo from 8:30 AM (8 min pitch, 4 min Q&A).

This file is the single source of truth. If your memory of the project disagrees with it, this file wins until the code says otherwise.

## What we are building

Projects publish vouch and denounce lists. TrustNet lets each project choose which other projects it trusts, and decides, from that project's own point of view, what to do with a contributor: ACCEPT, PROVISIONAL (review queue) or HOLD. It also detects coordinated spam campaigns that hit many projects at once. A contributor with no history is unknown, never auto-rejected.

Scoring (100): 70 automated on the frozen repo (CI green on the final commit and real features 30, open-weight model genuinely used 15, tests and evidence 15, PR and CI workflow 10) and 30 from judges (design Q&A, live demo, problem understanding).

## Who owns what

| Person | Role | Owns (edit only these) | Progress file |
|---|---|---|---|
| 1 Shaurya | Trust engine, integration, merges | `trustnet/models.py loaders.py trust.py`, `policy.json`, `tests/test_trust.py test_loaders.py`, this file | `docs/progress/p1-shaurya.md` |
| 2 Anubhav | Similarity, campaigns, adversarial lab | `trustnet/similarity.py campaigns.py lab.py`, their tests | `docs/progress/p2-anubhav.md` |
| 3 Piyush | Simulator, HTML report, CLI, examples; repo-owner settings | `trustnet/simulate.py report.py cli.py`, `examples/`, their tests | `docs/progress/p3-piyush.md` |
| 4 Arnav | CI, license, PR template, README, fixtures, docs, submission | `.github/`, `LICENSE`, `README.md`, `requirements.txt`, `tests/fixtures/`, `docs/` (except this file and other people's progress files) | `docs/progress/p4-arnav.md` |

## Design (decided, do not redesign)

All numbers live in `policy.json`. Defaults:

- Project trust T(V,P): strongest single path from viewer V to project P. Multiply edge weights, times 0.6 for each hop after the first. Max 3 hops. Ignore paths below 0.25. Viewer trusts itself at 1.0. Take the maximum, never the sum.
- Belief b = 1 − Π(1 − 0.8·T_i) over up to 3 vouching projects with T_i ≥ 0.25.
- Disbelief d = same over denouncing projects. Halve a denounce with no `evidence_url`. Skip expired denounces. Ignore denounces from projects with T < 0.25 and report them as "ignored: source not trusted".
- Uncertainty u = max(0, 1 − b − d). If b + d > 1, scale both down together.
- Decision: d ≥ 0.5 and d > b → HOLD. Else b ≥ 0.5 → ACCEPT. Else PROVISIONAL. A member of a flagged campaign → HOLD.
- Campaign: PR text similarity ≥ 0.85; a cluster has ≥ 8 PRs, ≥ 5 projects, all inside 6 hours, and ≥ 70% of authors with accounts younger than 14 days at PR time. Score = 0.4·min(1,size/20) + 0.3·min(1,projects/10) + 0.3·young_share. Flag at ≥ 0.6. A legitimate maintainer sending one dependency bump to ten projects (old account, vouched) must not be flagged.
- Similarity: TF-IDF cosine always works. `nomic-embed-text` through a local Ollama server adds embeddings; combine by taking the larger score. If Ollama is unreachable, fall back to TF-IDF and record `embedding_used=false`. Rules decide; the model only supplies a similarity score.
- Outputs include the policy hash so runs are reproducible.

These thresholds are our own defaults, tuned on our own simulation. Say so if asked.

## Data contract

```
network/projects/<id>.json  {"id","name","trusts":[{"project","weight"}],
                             "vouches":[{"handle","date","evidence_url"}],
                             "denounces":[{"handle","reason_code","evidence_url","date","expires"}]}
network/accounts.json       [{"handle","created_at"}]
network/prs.json            [{"id","project","author","created_at","title","body","diff_text"}]
network/labels.json         simulator only, the engine never reads it:
                            {"campaign_pr_ids","newcomer_handles","attack_handles"}
```

## Interfaces (package `trustnet/`, Python 3.11)

```
models.py      Project, Trust, Vouch, Denounce, Account, PR, Network(projects, accounts, prs),
               Decision(pr_id, viewer, author, decision, belief, disbelief, uncertainty,
                        reasons, paths, ignored, in_campaign),
               Campaign(id, pr_ids, projects, authors, score, flagged, evidence, embedding_used)
loaders.py     load_network(path) -> Network ; load_policy(path=None) -> (policy dict, 12-hex hash)
models.py      also parse_time(value) -> aware UTC datetime (timestamps stay as given: ISO string or datetime)
trust.py       project_trust(net, viewer, target) -> (float, list[str])
               evaluate_author(net, viewer, handle, campaign_handles=frozenset(), now=None) -> Decision
               evaluate_pr(net, viewer, pr, campaigns) -> Decision
               naive_score(net, handle) -> float          # baseline for the lab
similarity.py  similarity_matrix(texts, use_embeddings=True) -> (ndarray, embedding_used)
campaigns.py   detect(net, use_embeddings=True) -> list[Campaign]
lab.py         run(seed=42) -> dict                       # naive vs defended per attack
simulate.py    generate(n_projects=30, seed=42) -> Network ; write_network(net, labels, out_dir)
report.py      render(net, decisions, campaigns, lab_results, out_path)
cli.py         main(argv=None); run as `python -m trustnet <cmd>` (add trustnet/__main__.py calling cli.main)
               commands: simulate | evaluate --as PROJ --pr ID | campaigns | lab | report
```

## Build order

Tick a box only when the PR is merged and CI is green. Shaurya keeps this table current.

| # | Step | Owner | Done when | Status |
|---|---|---|---|---|
| 1 | Collaborator invites, branch protection on `main` | Piyush | Everyone can open PRs; direct pushes blocked | [ ] |
| 2 | PR 1: LICENSE, CI, PR template, README stub, requirements, empty package, smoke test, these docs | Shaurya (with Claude Code) | CI green on the PR, then merged | [x] |
| 3 | PR 2: `models.py`, `loaders.py`, `policy.json` | Shaurya | Others can import the contract (until it merges, code against the signatures above) | [x] |
| 4 | PR 3: tiny hand-made test networks in `tests/fixtures/` | Arnav | newcomer, brigade, bulk_bump, campaign fixtures load | [ ] |
| 5 | `trust.py` with tests | Shaurya | transitive 0.486, cycles end, brigade ignored, newcomer PROVISIONAL | [x] |
| 6 | `similarity.py`, real Ollama call plus TF-IDF fallback | Anubhav | fallback test passes without Ollama; real call verified by hand | [ ] |
| 7 | `simulate.py` with planted attacks | Piyush | same seed gives identical files; loader reads them | [ ] |
| 8 | `campaigns.py` | Anubhav | planted campaign found, bulk bump not flagged | [ ] |
| 9 | `cli.py` | Piyush | all five commands run on the simulated network | [ ] |
| 10 | `lab.py` | Anubhav | defended beats naive in every scenario, table printed | [ ] |
| 11 | `report.py` | Piyush | one HTML file, light and dark, readable on a phone | [ ] |
| 12 | `examples/` from a real run | Piyush | input plus real outputs committed | [ ] |
| 13 | README, DESIGN, DEMO script, slides outline | Arnav | judges can run it from the README | [ ] |
| 14 | Feature freeze 5:00 AM; rehearse twice; secret scan; submit on OrganizerHQ before 6:30 AM | all | CI green on the last commit | [ ] |

If we fall behind, cut in this order: Vouch-file adapter, SVG trust graph, extra lab scenarios. Never cut: tests, CI, real examples, the Ollama call, the newcomer rule.

## Decision log

Append a line when a decision changes. Shaurya edits this.

- Python 3.11, pytest, scikit-learn, requests. No web server; CLI plus a static HTML report.
- Viewpoint-relative evaluation is how we show decentralization: the same author can get two answers from two projects.
- Newcomers are PROVISIONAL, never rejected for lack of history.
- Timestamps stay as given (ISO string or datetime) in the data classes and are parsed on use with `models.parse_time`; `loaders.load_network` rejects unparseable ones. `load_policy` returns `(policy, 12-hex hash)`; `policy.json` has sections `trust`, `decision`, `campaigns`.
- Trust engine simplification: belief and disbelief are reported and decided on raw (no rescaling when b + d > 1); uncertainty = max(0, 1 - b - d). A project that both vouches and denounces an author counts in both. `evaluate_pr` judges denounce expiry as of the PR's own time. `naive_score` counts projects (one vouch or denounce per project), unweighted.
- Embedding model: `nomic-embed-text` via Ollama, pending a mentor answer on whether the organizers allow it. If not allowed, change `HACKATHON.md` and the code together.

## Open questions

- Input format of the organizers' simulated network (ask a mentor; our loader reads our own JSON).
- Which models the organizers' server offers.
- Whether `nomic-embed-text` is accepted.

## Resume checklist for an AI with no memory

1. Read this file and your progress file.
2. `git log --oneline -15`, `ls trustnet tests`, `pytest -q`.
3. Compare the build-order table to what exists. Do the next unchecked step you own.
4. Open a PR, add a log entry to your progress file, and say what you did not finish.
