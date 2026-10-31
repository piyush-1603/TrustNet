# TrustNet

**Team:** Sophons

**Members:**
- Piyush Tharwani
- Arnav Gupta
- Anubhav Jaiswal
- Shaurya Pratap Singh

**Problem statement:** Problem 7 — Decentralized Trust Network for Open Source Contributions

**What we are building:** A tool that lets open-source projects share vouch and denounce records, decides from each project's own point of view what to do with a contributor, detects coordinated spam campaigns across projects, and treats newcomers as "unknown" rather than "distrusted".

**Models:**
- `nomic-embed-text` (open-weight), run locally through Ollama.

**Why this model:** It converts pull-request text into embeddings so we can find near-duplicate spam even when the wording has been changed. All trust decisions are made by deterministic rules; the model only supplies a similarity score. If the model is unavailable, the tool falls back to TF-IDF.