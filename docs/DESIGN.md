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
- **0.6** = per-hop decay factor (`policy.json: trust.decay`)
- Maximum path length = **3 hops** (`policy.json: trust.max_hops`)
- Paths with value < **0.25** are ignored (`policy.json: trust.min_trust`)
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
Take the top **3** by trust value (`policy.json: trust.top_k`).

```
b = 1 − ∏ᵢ (1 − vouch_weight × T(Pᵢ))
```

`trust.vouch_weight = 0.8` (`policy.json`)

### Denouncing projects

Collect all projects **Pⱼ** that denounce **A** where `T(V, Pⱼ) ≥ 0.25`.
Take the top **3** by trust value.

Apply modifiers before inserting into formula:
- Denounce has no `evidence_url` → multiply by **0.5** (`policy.json: trust.no_evidence_factor`); record `"halved: no evidence link"`
- Denounce is expired (`expires` date is in the past) → **skip entirely**; record `"ignored: expired"`
- Source project has `T < 0.25` → **skip entirely**; record `"ignored: source not trusted"`

```
d = 1 − ∏ⱼ (1 − vouch_weight × T(Pⱼ) × modifier)
```

### Uncertainty

```
u = max(0, 1 − b − d)
```

If `b + d > 1`, `u = 0`. `b` and `d` are reported and used as computed; they are never rescaled.

---

## 3. Decision Rule

```
if   in_campaign:            → HOLD
elif d ≥ 0.5 and d > b:     → HOLD
elif b ≥ 0.5:               → ACCEPT
else:                        → PROVISIONAL
```

Thresholds in `policy.json`: `decision.hold_threshold = 0.5`, `decision.accept_threshold = 0.5`.

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
(`policy.json: campaigns.similarity_threshold`).

### Step 2 — Cluster filters

A cluster is a **campaign candidate** only if ALL four conditions hold:

| Condition | Threshold | `policy.json` key |
|---|---|---|
| Number of PRs | ≥ 8 | `campaigns.min_prs` |
| Distinct projects | ≥ 5 | `campaigns.min_projects` |
| Time window | ≤ 6 hours | `campaigns.window_hours` |
| Young authors (account < 14 days at PR time) | ≥ 70% | `campaigns.min_young_share` |

### Step 3 — Campaign score

```
score = 0.4 × min(1, size / 20)
      + 0.3 × min(1, projects / 10)
      + 0.3 × young_share
```

`flagged = True` if `score ≥ 0.6` (`policy.json: campaigns.flag_threshold`).

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

`load_policy(path=None)` returns `(dict, 12 hex characters)` — the first 12 characters of the
SHA-256 of the policy's canonical JSON. Every output includes this hash so runs are reproducible and judges can
confirm which thresholds were active.

---

## 7. Path to trust (what would move a newcomer to ACCEPT)

For an author who is PROVISIONAL with belief `b`, one more vouch of strength `c` gives
`b' = 1 − (1 − b)(1 − c)`. Setting `b' = accept_threshold` (0.5) gives `c = 1 − (1 − 0.5)/(1 − b)`,
so the vouching project must be trusted by the viewer at `t = c / vouch_weight`. With `b = 0`,
`t = 0.5 / 0.8 = 0.625`, shown as 0.63 (rounded up, never below `trust.min_trust`).
The card lists up to three projects the viewer trusts at least that much, strongest first
(the viewer itself counts, at 1.00). If `t > 1`, one vouch cannot be enough and the card says so.

---

## 8. Campaign advisories (how projects exchange findings)

`trustnet advisory --as PROJ` writes `{format: "trustnet-advisory/1", issuer, issued_at, policy_hash,
campaigns: [{id, authors, pr_ids, projects, score, evidence, embedding_used}]}` for the flagged campaigns only.
No PR text is published. When another project passes the file to `evaluate --advisory`, the engine computes
`T = project_trust(viewer, issuer)`. If `T ≥ trust.min_trust` and the PR author is listed, the decision is
HOLD with the issuer and trust path as the reason. If not, the advisory is ignored and the output says
`ignored: advisory from <issuer> (source not trusted)`.

---

## 9. Cost of vouching for campaign accounts

Let `F` be every account flagged by a local campaign or listed in an advisory from a trusted issuer.
When evaluating author `A ∉ F`, any voucher project that also vouched for some account in `F` has its
contribution multiplied by `trust.flagged_endorser_factor` (0.5) and the output lists
`discounted: <project> also vouched for a flagged campaign account`. This lowers belief; it never
creates a HOLD by itself. Projects that only received campaign PRs are not affected. It is a heuristic:
an honest project that vouched for one bot loses half the weight of its other vouches.

---

## Summary of all thresholds

| Key | Value | Meaning |
|---|---|---|
| `trust.decay` | 0.6 | Multiplied per hop after the first |
| `trust.max_hops` | 3 | Maximum path length |
| `trust.min_trust` | 0.25 | Paths below this are pruned |
| `trust.vouch_weight` | 0.8 | Scales each vouch/denounce contribution |
| `trust.top_k` | 3 | Max vouching/denouncing projects used |
| `trust.no_evidence_factor` | 0.5 | Denounce weight when no evidence_url |
| `trust.flagged_endorser_factor` | 0.5 | Vouch weight multiplier for a project that also vouched for a flagged account |
| `decision.hold_threshold` | 0.5 | d must reach this to trigger HOLD |
| `decision.accept_threshold` | 0.5 | b must reach this to trigger ACCEPT |
| `campaigns.similarity_threshold` | 0.85 | Minimum cosine similarity to cluster |
| `campaigns.min_prs` | 8 | Minimum PRs in a campaign cluster |
| `campaigns.min_projects` | 5 | Minimum distinct projects |
| `campaigns.window_hours` | 6 | Maximum time window in hours |
| `campaigns.min_young_share` | 0.70 | Minimum fraction of young accounts |
| `campaigns.flag_threshold` | 0.6 | Minimum score to flag a campaign |
