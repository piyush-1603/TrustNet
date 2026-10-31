"""Demo of the text-independent behavior flag: three people, ten different PRs each, ten projects, two hours.

No two PRs share any text, so the text detector sees nothing. Only behavior separates them:
- fresh-ai-user:    3 days old, nobody vouches for them.
- busy-maintainer:  600 days old, vouched by proj-01.
- eager-newcomer:   4 days old, but vouched by proj-01 (a real, trusted contributor who is just getting started).
"""

from datetime import timedelta

from .ablation import HONEST, NOW, _diff
from .campaigns import detect
from .models import Account, Network, PR, Project, Vouch
from .trust import evaluate_pr

VIEWER = "proj-01"
ACTORS = [  # (handle, account age in days, vouched by the viewer?)
    ("fresh-ai-user", 3, False),
    ("busy-maintainer", 600, True),
    ("eager-newcomer", 4, True),
]


def build_network():
    projects = {f"proj-{i + 1:02d}": Project(id=f"proj-{i + 1:02d}", name=f"proj-{i + 1:02d}") for i in range(10)}
    accounts, prs = {}, []
    for a, (handle, age, vouched) in enumerate(ACTORS):
        accounts[handle] = Account(handle=handle, created_at=(NOW - timedelta(days=age)).isoformat())
        if vouched:
            projects[VIEWER].vouches.append(Vouch(handle=handle, date=(NOW - timedelta(days=30)).isoformat()))
        for i in range(10):
            title, body, path = HONEST[a * 10 + i]  # ten different, ordinary changes per person
            prs.append(PR(id=f"{handle}-{i:02d}", project=f"proj-{i + 1:02d}", author=handle,
                          created_at=(NOW + timedelta(minutes=11 * i + 3 * a)).isoformat(),
                          title=title, body=body, diff_text=_diff(path, "changed line")))
    return Network(projects=projects, accounts=accounts, prs=prs)


def run():
    net = build_network()
    campaigns = detect(net, use_embeddings=False)  # keyword mode: this demo needs no model
    by_id = {pr.id: pr for pr in net.prs}
    rows = []
    for handle, age, vouched in ACTORS:
        decision = evaluate_pr(net, VIEWER, by_id[f"{handle}-00"], campaigns)
        flag = next((c for c in campaigns if c.flagged and handle in c.authors), None)
        rows.append({"handle": handle, "account_age_days": age, "vouched_by_viewer": vouched,
                     "behavior_flag": flag is not None, "decision": decision.decision,
                     "evidence": flag.evidence[0] if flag else None, "ignored": decision.ignored})
    return {"viewer": VIEWER, "prs_per_person": 10, "projects": 10,
            "text_campaigns": [c.id for c in campaigns if c.kind == "text"], "people": rows}
