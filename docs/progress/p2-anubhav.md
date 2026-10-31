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

