# Mentor Notes

Questions submitted to the hackathon mentor during Hacktoberfest 2026 Hack Day, Sonipat.
Status at submission: the data question is answered; the two model questions were not.

---

## Q1 — Input file format of the organizers' simulated network

**Question asked:**
> Our loader reads a folder of JSON files in this structure:
> ```
> network/
>   projects/<id>.json   { "id", "name", "trusts", "vouches", "denounces" }
>   accounts.json        [ { "handle", "created_at" } ]
>   prs.json             [ { "id", "project", "author", "created_at", "title", "body", "diff_text" } ]
> ```
> Will the organizers' evaluation network use this same layout and field names,
> or will it use a different format? If different, can you share a sample file or schema?

**Answer:** Confirmed with the organizers: no network data is provided to teams. Each team shows its own demo, so
the loader only has to read the format documented in `docs/PLAN.md`.

**Impact on code:**
- If format matches → no change needed; our `loaders.load_network()` reads it directly.
- If format differs → Shaurya adds an adapter in `loaders.py`; tell him immediately.

---

## Q2 — Which models does the organizers' server offer?

**Question asked:**
> We are using `nomic-embed-text` through a local Ollama server for PR text embeddings.
> Will the evaluation environment have an Ollama server running, and if so,
> which models will be available on it? We fall back to TF-IDF if Ollama is unreachable,
> so the tool works either way.

**Answer:** Not answered by the time of submission. We declare only `nomic-embed-text`, which the code calls
through a local Ollama server. If the model or server is unavailable, the tool falls back to TF-IDF and reports
`embedding_used: false`; it never claims a model result it did not get.

**Impact on code:**
- If `nomic-embed-text` is available → no change; real Ollama path runs during demo.
- If a different model is available → Anubhav updates the model name in `similarity.py`.
- If no Ollama → TF-IDF fallback already in place; update `HACKATHON.md` to reflect this.

---

## Q3 — Is `nomic-embed-text` an accepted model for this problem?

**Question asked:**
> Our `HACKATHON.md` lists `nomic-embed-text` (open-weight, run locally via Ollama)
> as the AI model we use. It converts PR text to embeddings for similarity detection.
> All trust decisions are made by deterministic rules; the model only supplies a
> similarity score. Is this an accepted model for Problem 7?

**Answer:** Not answered by the time of submission. The model is open-weight and runs locally; the decision
logic does not depend on it (see `python -m trustnet ablation` for what it adds).

**Impact on code:**
- If accepted → no change needed.
- If not accepted → update `HACKATHON.md` model field and remove the Ollama call;
  TF-IDF becomes the primary path. Tell Shaurya and Anubhav immediately.

---
