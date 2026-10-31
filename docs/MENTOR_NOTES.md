# Mentor Notes

Questions submitted to the hackathon mentor during Hacktoberfest 2026 Hack Day, Sonipat.
**Answers must be shared with Shaurya immediately** — they affect `loaders.py`, `HACKATHON.md`,
and the campaign scoring code.

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

**Answer:** *(fill in when received from mentor)*

```
[PENDING]
```

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

**Answer:** *(fill in when received from mentor)*

```
[PENDING]
```

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

**Answer:** *(fill in when received from mentor)*

```
[PENDING]
```

**Impact on code:**
- If accepted → no change needed.
- If not accepted → update `HACKATHON.md` model field and remove the Ollama call;
  TF-IDF becomes the primary path. Tell Shaurya and Anubhav immediately.

---

## Action checklist once answers arrive

- [ ] Fill in the three answer blocks above
- [ ] Tell Shaurya (`p1`) the format answer → he updates `loaders.py` if needed
- [ ] Tell Anubhav (`p2`) the model answer → he updates `similarity.py` if needed
- [ ] If `nomic-embed-text` rejected: update `HACKATHON.md` (Piyush owns the repo settings)
- [ ] Commit this file with the filled-in answers before the 5:00 AM feature freeze
