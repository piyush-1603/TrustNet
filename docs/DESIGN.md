# TrustNet Design — Formulas and Algorithms

All numbers referenced here live in `policy.json`. These are our own defaults,
tuned on our own simulation. Say so if a judge asks.

---

## 1. Project Trust — T(V, P)

How much does viewer **V** trust project **P**?

### Formula

```
T(V, P) = max over all paths { ∏ weight(eᵢ) × 0.6^(hops − 1) }
```

Where:
- Each **edge** `eᵢ` is a directed trust declaration `{"project": P, "weight": w}`
- **hops** = number of edges in the path (1 hop = direct trust)
- **0.6** = per-hop decay factor (`policy.json: hop_decay`)
- Maximum path length = **3 hops** (`policy.json: max_hops`)
- Paths with value < **0.25** are ignored (`policy.json: min_trust`)
- Viewer always trusts itself: `T(V, V) = 1.0`
- Take the **maximum** over all valid paths, never the sum

### Examples

| Path | Weights | Value |
|---|---|---|
| A → B (direct) | 0.9 | `0.9` |
| A → B → C | 0.9 × 0.9 | `0.81 × 0.6 = 0.486` |
| A → B → C → D | 0.9 × 0.9 × 0.9 | `0.729 × 0.6² = 0.262` |
| A → B → C → D → E | 4 hops | `0` (exceeds max_hops) |

### Algorithm

Bounded best-path search (DFS, cycle-safe via visited set):

```
function project_trust(net, viewer, target):
    if viewer == target: return 1.0
    best = 0.0
    stack = [(viewer, 1.0, 0, [viewer])]    # (node, score, hops, path)
    while stack:
        node, score, hops, path = stack.pop()
        if hops >= max_hops: continue
        for edge in net.projects[node].trusts:
            neighbour, w = edge.project, edge.weight
            if neighbour in path: continue  # cycle guard
            new_score = score * w * (hop_decay if hops > 0 else 1.0)
            if new_score < min_trust: continue
            if neighbour == target: best = max(best, new_score)
            else: stack.append((neighbour, new_score, hops+1, path+[neighbour]))
    return best
```

---

## 2. Belief and Disbelief

Given viewer **V** evaluating author **A**:

### Vouching projects

Collect all projects **Pᵢ** that vouch for **A** where `T(V, Pᵢ) ≥ 0.25`.
Take the top **3** by trust value (`policy.json: top_k`).

```
b = 1 − ∏ᵢ (1 − vouch_weight × T(Pᵢ))
```

`vouch_weight = 0.8` (`policy.json`)

### Denouncing projects

Collect all projects **Pⱼ** that denounce **A** where `T(V, Pⱼ) ≥ 0.25`.
Take the top **3** by trust value.

Apply modifiers before inserting into formula:
- Denounce has no `evidence_url` → multiply by **0.5** (`policy.json: no_evidence_factor`); record `"halved: no evidence link"`
- Denounce is expired (`expires` date is in the past) → **skip entirely**; record `"ignored: expired"`
- Source project has `T < 0.25` → **skip entirely**; record `"ignored: source not trusted"`

```
d = 1 − ∏ⱼ (1 − vouch_weight × T(Pⱼ) × modifier)
```

### Uncertainty

```
u = max(0, 1 − b − d)
```

If `b + d > 1`: scale both down proportionally so they sum to 1, then `u = 0`.

---

## 3. Decision Rule

```
if   in_campaign:            → HOLD
elif d ≥ 0.5 and d > b:     → HOLD
elif b ≥ 0.5:               → ACCEPT
else:                        → PROVISIONAL
```

Thresholds in `policy.json`: `hold_threshold = 0.5`, `accept_threshold = 0.5`.

A contributor with **no vouches and no denounces** yields `b = 0`, `d = 0`, `u = 1.0`
→ **PROVISIONAL**. They are never auto-rejected for lack of history.

---

## 4. Campaign Detection

### Step 1 — Similarity clustering

For all PRs in the network, compute a pairwise similarity matrix.

**TF-IDF cosine** (always available, scikit-learn):
```
texts → TfidfVectorizer → L2-normalised matrix M
similarity(i, j) = M[i] · M[j]
```

**nomic-embed-text via Ollama** (optional, adds semantic similarity):
```
POST http://localhost:11434/api/embed
body: {"model": "nomic-embed-text", "input": [text1, text2, ...]}
→ embedding vectors → L2-normalise → cosine similarity matrix E
```

Combine: `S(i,j) = max(TF-IDF(i,j), Ollama(i,j))`

If Ollama is unreachable → use TF-IDF only, set `embedding_used = False`.

Cluster PRs using union-find (connected components) where `S(i,j) ≥ 0.85`
(`policy.json: similarity_threshold`).

### Step 2 — Cluster filters

A cluster is a **campaign candidate** only if ALL four conditions hold:

| Condition | Threshold | `policy.json` key |
|---|---|---|
| Number of PRs | ≥ 8 | `campaign_min_prs` |
| Distinct projects | ≥ 5 | `campaign_min_projects` |
| Time window | ≤ 6 hours | `campaign_max_hours` |
| Young authors (account < 14 days at PR time) | ≥ 70% | `campaign_young_share` |

### Step 3 — Campaign score

```
score = 0.4 × min(1, size / 20)
      + 0.3 × min(1, projects / 10)
      + 0.3 × young_share
```

`flagged = True` if `score ≥ 0.6` (`policy.json: campaign_flag_threshold`).

### Hard negative — legitimate bulk update

A maintainer with an **old account** (> 14 days) sending the same PR to many projects
may produce a high-similarity cluster. It is NOT flagged because the young-account share
will be 0%, driving the score below 0.6.

### Evidence strings (human-readable)

```
"38 PRs, 25 projects, 2h10m window, 84% accounts under 14 days"
```

---

## 5. Naive Baseline (for the lab)

```
naive_score(net, handle) = Σ vouches_across_all_projects
                          − Σ denounces_across_all_projects
```

All projects are weighted equally — no trust graph, no decay, no expiry checks.
Used only as a comparison baseline in `lab.py` to show how much the trust-weighted
approach reduces false positives and resists manipulation.

---

## 6. Policy hash

`load_policy(path)` returns `(dict, sha256_hex[:8])` — a short hash of the JSON
content. Every output includes this hash so runs are reproducible and judges can
confirm which thresholds were active.

---

## Summary of all thresholds

| Key | Value | Meaning |
|---|---|---|
| `hop_decay` | 0.6 | Multiplied per hop after the first |
| `max_hops` | 3 | Maximum path length |
| `min_trust` | 0.25 | Paths below this are pruned |
| `vouch_weight` | 0.8 | Scales each vouch/denounce contribution |
| `top_k` | 3 | Max vouching/denouncing projects used |
| `no_evidence_factor` | 0.5 | Denounce weight when no evidence_url |
| `hold_threshold` | 0.5 | d must reach this to trigger HOLD |
| `accept_threshold` | 0.5 | b must reach this to trigger ACCEPT |
| `similarity_threshold` | 0.85 | Minimum cosine similarity to cluster |
| `campaign_min_prs` | 8 | Minimum PRs in a campaign cluster |
| `campaign_min_projects` | 5 | Minimum distinct projects |
| `campaign_max_hours` | 6 | Maximum time window in hours |
| `campaign_young_share` | 0.70 | Minimum fraction of young accounts |
| `campaign_flag_threshold` | 0.6 | Minimum score to flag a campaign |
