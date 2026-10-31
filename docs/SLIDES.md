# TrustNet — Presentation Slides Outline

> **Team Sophons** · Hacktoberfest 2026 Hack Day, Sonipat · Problem 7  
> **Pitch Format:** 8-minute presentation + 4-minute judges Q&A

---

## Slide 1: Title & The Hook

### Visual / Layout:
- Title: **TrustNet**
- Subtitle: *Decentralized Trust Network for Open Source Contributions*
- Team: **Sophons** (Piyush Tharwani, Arnav Gupta, Anubhav Jaiswal, Shaurya Pratap Singh)
- Background graphic: Graph of interconnected open-source repositories with incoming PR signals.

### Talking Points (0:00 – 0:45):
- "Imagine waking up to find 38 identical pull requests hitting 25 of your repositories within two hours."
- "To each individual maintainer, it looks like a single harmless PR. Across the ecosystem, it's a coordinated spam campaign."
- "Today, maintainers either burn out reviewing spam or lock down their repositories—cutting off legitimate newcomers."

---

## Slide 2: The Core Problem — Fragile Trust & False Dichotomy

### Visual / Layout:
- Two contrasting columns:
  - **Column A (Overly Open):** Naive contributor acceptance $\rightarrow$ Sybil attacks, spam campaigns, credential theft.
  - **Column B (Overly Closed):** Account age barriers, strict pre-approvals $\rightarrow$ Newcomers blocked, open source stales.
- Center callout: **"Lack of history is not evidence of malice."**

### Talking Points (0:45 – 1:30):
- "Centralized reputation systems fail because there is no universal maintainer consensus on who is trustworthy."
- "Naive counting systems treat all upvotes and downvotes equally—making them trivially exploitable by bot brigades."
- "We need a system that is **decentralized, viewpoint-relative, and newcomer-friendly**."

---

## Slide 3: Our Solution — TrustNet Architecture

### Visual / Layout:
- Three-pillar diagram:
  1. **Viewpoint-Relative Trust Engine:** Every project has its own perspective; no central oracle.
  2. **Deterministic Trust Propagation:** Mathematically bounded transitive trust with decay.
  3. **Campaign Intelligence:** Open-weight semantic embeddings (`nomic-embed-text`) + cluster heuristics.

### Talking Points (1:30 – 2:15):
- "TrustNet is built on three core pillars:
  1. **Decentralization:** Project A and Project B can view the exact same contributor and reach different, valid conclusions based on their own network of trust.
  2. **Deterministic Rules:** Trust scores, vouches, and denounces are transparent and auditable.
  3. **Semantic Campaign Detection:** AI is used strictly where it excels—finding semantic similarity in text—while all decisions remain rule-based."

---

## Slide 4: Mathematics of Trust Propagation

### Visual / Layout:
- Graph diagram showing path: $A \xrightarrow{0.9} B \xrightarrow{0.9} C$
- Formula display:
  $$T(V, P) = \max_{\text{paths}} \left( \prod e_i \times 0.6^{\text{hops}-1} \right)$$
- Calculation badge: $T(A, C) = 0.9 \times 0.9 \times 0.6 = 0.486$
- Guardrails callout box:
  - Max hops: 3
  - Min trust cutoff: 0.25
  - Cycle-safe DFS

### Talking Points (2:15 – 3:00):
- "How does trust travel? We use bounded best-path search."
- "Direct trust has no decay. Each transitive hop multiplies a 0.6 decay factor."
- "We cap paths at 3 hops and prune anything under 0.25 trust. We take the **maximum** path, never the sum, preventing sybil path inflation."

---

## Slide 5: Belief, Disbelief, and the Newcomer Principle

### Visual / Layout:
- Formula cards:
  - **Belief ($b$):** $1 - \prod (1 - 0.8 \cdot T_i)$ over top-3 vouches.
  - **Disbelief ($d$):** Weighted over denounces (halved if no evidence link; zero if expired or source untrusted).
  - **Uncertainty ($u$):** $\max(0, 1 - b - d)$.
- Decision matrix:
  - $d \ge 0.5$ and $d > b \implies$ **HOLD**
  - $b \ge 0.5 \implies$ **ACCEPT**
  - Else $\implies$ **PROVISIONAL** (Review queue)
  - Campaign match $\implies$ **HOLD** (Override)

### Talking Points (3:00 – 3:45):
- "For newcomers with zero vouches and zero denounces: $b=0, d=0, u=1.0$."
- "The decision is **PROVISIONAL**—never rejected, never blocked. They go to a standard human review queue."
- "Fake denounces from untrusted sources ($T < 0.25$) are completely discarded and marked `ignored: source not trusted`."

---

## Slide 6: Semantic Campaign Detection

### Visual / Layout:
- Pipeline diagram:
  $$\text{PR Texts} \xrightarrow{\text{TF-IDF} \,+\, \text{nomic-embed-text}} \text{Cosine Matrix} \xrightarrow{\text{Similarity} \ge 0.85} \text{Clusters}$$
- Heuristic Filter checklist:
  - $\ge 8$ Pull Requests
  - $\ge 5$ Distinct Repositories
  - $\le 6$-Hour Time Window
  - $\ge 70\%$ Young Accounts ($< 14$ days old)
- Score formula:
  $$\text{Score} = 0.4 \cdot \min(1, \frac{\text{size}}{20}) + 0.3 \cdot \min(1, \frac{\text{projects}}{10}) + 0.3 \cdot \text{young\_share}$$

### Talking Points (3:45 – 4:30):
- "Spammers reword messages to evade regex and naive filters. We use `nomic-embed-text` locally via Ollama to generate semantic embeddings, taking the max with TF-IDF."
- "If Ollama is down, our graceful fallback ensures TF-IDF still works."
- "**Crucial Negative Control:** An established maintainer bumping a dependency across 10 repos has an old account—yielding 0% young share. They will **never** be flagged."

---

## Slide 7: Adversarial Lab & Synthetic Regression Results

### Visual / Layout:
- Categorical Decision Matrix (Synthetic Regressions):

| Attack Fixture | Threat Model | Naive Baseline | Defended Outcome | Result |
|---|---|---|---|---|
| **Brigade Denounce** | 5 untrusted fake projects denounce honest author | HOLD (Blocked) | **ACCEPT → ACCEPT** | Defended (untrusted denounces ignored) |
| **Sybil Clique** | Fake projects mutually vouch for spammer | ACCEPT | **PROVISIONAL → PROVISIONAL** | Defended (isolated ring has $T < 0.25$) |
| **Trust Laundering** | Long vouch chain through puppet projects | ACCEPT | **PROVISIONAL → PROVISIONAL** | Defended (pruned beyond 3 hops) |
| **Collusive PR Swarm** | Coordinated multi-project near-duplicate PRs | PROVISIONAL | **PROVISIONAL → HOLD** | Defended (flagged by campaign detector) |
| **Compromised Source** | Directly trusted project account compromised | ACCEPT | **PROVISIONAL → ACCEPT** | ⚠️ **Defense Fails (Explicit Limitation)** |

### Talking Points (4:30 – 5:30):
- "We evaluated TrustNet against five synthetic regression attack fixtures."
- "Naive counting loses all five fixtures—either blocking honest authors or auto-accepting attackers."
- "TrustNet correctly preserves categorical decisions across the first four scenarios: ignoring fake brigades, isolating sybil rings, pruning laundered chains, and flagging coordinated PR swarms into HOLD."
- "**Transparent System Limitation:** In the fifth scenario (Compromised Trusted Source), if a maintainer's direct ally is compromised and vouches for a malicious actor, trust is inherited until denunciations propagate. These are synthetic regression fixtures, not general attack-resistance guarantees, and we state this boundary clearly."
- "Across all synthetic tests, newcomer false-positive rate remains strictly **0%**."

---

## Slide 8: Technical Architecture & Open-Weight Model

### Visual / Layout:
- Stack badges: Python 3.11 | Ollama | `nomic-embed-text` | Scikit-Learn | Pytest | GitHub Actions CI
- Box diagram highlighting:
  - Deterministic Core (Standard library + policy.json)
  - Zero-internet CI: Test suite mocks model endpoints; 100% offline reproducible
  - Reproducibility: Policy hash included in every output card

### Talking Points (5:30 – 6:15):
- "We use `nomic-embed-text`, an open-weight 137M parameter model via local Ollama."
- "All tests run without requiring Ollama or active internet connections, guaranteeing green CI."
- "Outputs include the policy SHA-256 hash for complete auditability."

---

## Slide 9: Live Demo & What We Honestly Did Not Build

### Visual / Layout:
- Side-by-side terminal & HTML report screenshot.
- Transparent "Scope Boundaries" callout:
  - ✅ **Built:** Seeded simulation, viewpoint-relative evaluator, campaign detector, adversarial lab, static HTML report with SVG graph.
  - ❌ **Not Built:** Web backend/SaaS, live GitHub webhook integration, Ghostty flat-file vouch adapter.

### Talking Points (6:15 – 7:15):
- "Maintainers don't need another heavy SaaS dashboard. TrustNet runs as a clean CLI and outputs a self-contained HTML report with dark mode and SVG trust graphs."
- "We stayed strictly within hackathon scope and documented every trade-off honestly."

---

## Slide 10: Conclusion & Summary

### Visual / Layout:
- Three summary takeaways:
  1. **Decentralized:** Decisions belong to individual project viewpoints.
  2. **Safe for Newcomers:** Zero history means review queue, not rejection.
  3. **Robust Against Coordinated Attacks:** Semantic detection + mathematical trust propagation.
- GitHub link & team credits.
- Center text: **"Questions & Live Inspection"**

### Talking Points (7:15 – 8:00):
- "TrustNet restores trust in open-source collaboration without building walls against the next generation of contributors."
- "Thank you! We're ready for your questions."
