# Progress: Person 2, Anubhav (similarity, campaigns, lab)

Owner of this file: Anubhav only. Add one log entry per PR, newest at the bottom.

## Checklist
- [ ] similarity.py: TF-IDF cosine
- [ ] similarity.py: real Ollama call (`nomic-embed-text`), response shape written down in a code comment, fallback on any error
- [ ] campaigns.py: cluster, size/projects/window/young-account rules, score, readable evidence
- [ ] test: legitimate bulk dependency bump is NOT flagged
- [ ] test: reworded spam lands in one cluster when embeddings are on
- [ ] test: Ollama call mocked so CI never needs Ollama; fallback test returns embedding_used=false
- [ ] lab.py: brigade, sybil clique, trust laundering, collusive cluster; naive vs defended; Markdown table

## Log
Format: `date time | PR title | what changed | what is next | gotchas`

2026-10-31 22:30 IST | Similarity, campaign detection and lab | Added TF-IDF/Ollama max similarity with whole-batch validation and offline fallback, connected-component campaign rules and evidence, seeded four-scenario lab with Markdown results, and 31 new tests (33 total passing locally on Python 3.14). | Verify live Ollama and Python 3.11 CI; integrate models/loaders/trust when Person 1 merges. | Production models and trust engine are absent: test substitutes are orchestration checks, not real benchmark results. Assumes Network.projects/accounts are mappings and records accept contract field keywords. Proposed policy layout: load_policy() returns dict or (dict, hash), thresholds under `campaigns` matching DEFAULTS; temporary defaults only while loaders is absent. Full-component time window; young share uses distinct authors at earliest cluster PR. Relative reduction compares native naive score change with belief/disbelief change; confirm baseline scale before interpreting magnitudes. No fabricated winning results; CLI/report hookup belongs to Person 3.
