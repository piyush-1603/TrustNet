# TrustNet Test Fixtures

Four hand-crafted networks in the exact [data contract](../../docs/PLAN.md#data-contract) format.
Each fixture is a self-contained folder that `loaders.load_network()` can read.

---

## Fixture overview

| Folder | Scenario | Expected outcome |
|---|---|---|
| `newcomer/` | Contributor with **zero history** (no vouches, no denounces) submits a PR | `PROVISIONAL` — never auto-rejected |
| `brigade/` | **5 untrusted fake projects** denounce an honest, vouched author | Decision **unchanged** — denounces from untrusted sources are ignored |
| `bulk_bump/` | **Old, vouched maintainer** posts the same dependency-bump PR to 10 projects | **NOT flagged** as a campaign — account age and trust matter |
| `campaign/` | **12 near-identical PRs** from 12 fresh accounts across 8 projects in <2 hours | **Flagged** as a coordinated spam campaign |

---

## Folder structure (same for all four)

```
<fixture>/
  projects/
    <id>.json     one file per project
  accounts.json   all accounts referenced by PRs or vouch/denounce lists
  prs.json        all pull requests in the network
  labels.json     ground-truth metadata (engine never reads this)
```

### `labels.json` fields

| Field | Used by | Meaning |
|---|---|---|
| `campaign_pr_ids` | campaign tests | IDs of PRs that belong to the planted campaign |
| `newcomer_handles` | newcomer tests | Handles that must have no vouches or denounces |
| `attack_handles` | campaign/brigade tests | Handles of attacker/spam accounts |
| `honest_handle` | brigade tests | The author the brigade is targeting |
| `attack_project_ids` | brigade tests | Project IDs whose denounces should be ignored |
| `maintainer_handle` | bulk_bump tests | The legitimate maintainer's handle |

---

## newcomer/

**Network:** 5 projects (`proj-01` to `proj-05`). `proj-01` is the viewer.
Trust path: `proj-01 → proj-02 (0.9) → proj-03 (0.8)`. `alice` is vouched by proj-02 and proj-03.

**Key property:** `new_dev` has **no vouch and no denounce** anywhere in the network.
A call to `evaluate_author(net, "proj-01", "new_dev")` must return `PROVISIONAL`.

---

## brigade/

**Network:** 7 projects. `proj-01` (viewer) trusts only `proj-02` (weight 0.9).
`proj-02` vouches for `honest_alice`. `fake-01` through `fake-05` all denounce `honest_alice`
but have **no trust path** from `proj-01`.

**Key property:** `evaluate_author(net, "proj-01", "honest_alice")` must still return `ACCEPT`
(or at minimum `PROVISIONAL`), never `HOLD`. The brigade denounces are ignored because
their source trust is below 0.25.

---

## bulk_bump/

**Network:** 12 projects. `proj-viewer` trusts `proj-hub` (0.9). `proj-hub` vouches for
`dep_maintainer`. `dep_maintainer` posts the **same dependency-bump PR** to `proj-01`
through `proj-10`.

**Key property:** `dep_maintainer`'s account was created in 2018 (>8 years old).
`detect(net)` must return an **empty campaign list** — this is a legitimate batch update,
not spam.

---

## campaign/

**Network:** 8 projects (`proj-01` to `proj-08`). 12 spam accounts (`spam-01` to `spam-12`),
all created 2026-10-20 (11 days before the PRs). 12 near-identical PRs spread across the 8
projects, all within a 1h50m window on 2026-10-31.

**Key property:** `detect(net)` must return at least one `Campaign` with `flagged=True`.
Meets all thresholds from `policy.json`:
- ≥ 8 PRs ✓ (12)
- ≥ 5 projects ✓ (8)
- ≤ 6h window ✓ (1h50m)
- ≥ 70% young accounts ✓ (100% — all 11 days old)
