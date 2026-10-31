"""
tests/test_fixtures.py

Validates the structure and intent of each hand-made fixture network.
Uses only the standard library so these tests pass before trustnet
logic (models.py / loaders.py) is merged.

Each test documents what property of the fixture makes the scenario
meaningful, so teammates can treat these as living specifications.
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


# ─── helpers ──────────────────────────────────────────────────────────────────

def load_fixture(name: str):
    """Return (projects_dict, accounts_dict, prs_list, labels_dict)."""
    base = FIXTURES / name
    projects = {}
    for p in sorted((base / "projects").iterdir()):
        data = json.loads(p.read_text())
        projects[data["id"]] = data
    accounts = {
        a["handle"]: a
        for a in json.loads((base / "accounts.json").read_text())
    }
    prs    = json.loads((base / "prs.json").read_text())
    labels = json.loads((base / "labels.json").read_text())
    return projects, accounts, prs, labels


def parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ─── structural sanity (all fixtures) ─────────────────────────────────────────

def test_all_fixtures_have_required_files():
    """Every fixture folder must contain projects/, accounts.json, prs.json, labels.json."""
    for name in ("newcomer", "brigade", "bulk_bump", "campaign"):
        base = FIXTURES / name
        assert (base / "projects").is_dir(),       f"{name}/projects/ missing"
        assert (base / "accounts.json").is_file(), f"{name}/accounts.json missing"
        assert (base / "prs.json").is_file(),      f"{name}/prs.json missing"
        assert (base / "labels.json").is_file(),   f"{name}/labels.json missing"


def test_all_projects_have_required_fields():
    """Every project JSON must carry id, name, trusts, vouches, denounces."""
    required = {"id", "name", "trusts", "vouches", "denounces"}
    for name in ("newcomer", "brigade", "bulk_bump", "campaign"):
        projects, *_ = load_fixture(name)
        for pid, proj in projects.items():
            missing = required - proj.keys()
            assert not missing, f"{name}/{pid} is missing fields: {missing}"


def test_all_prs_have_required_fields():
    """Every PR must have id, project, author, created_at, title, body, diff_text."""
    required = {"id", "project", "author", "created_at", "title", "body", "diff_text"}
    for name in ("newcomer", "brigade", "bulk_bump", "campaign"):
        _, _, prs, _ = load_fixture(name)
        for pr in prs:
            missing = required - pr.keys()
            assert not missing, f"{name}/pr {pr.get('id')} missing fields: {missing}"


def test_all_accounts_have_required_fields():
    """Every account must have handle and created_at."""
    for name in ("newcomer", "brigade", "bulk_bump", "campaign"):
        _, accounts, _, _ = load_fixture(name)
        for handle, acc in accounts.items():
            assert "handle"     in acc, f"{name}/{handle} missing 'handle'"
            assert "created_at" in acc, f"{name}/{handle} missing 'created_at'"


def test_pr_authors_exist_in_accounts():
    """Every PR author must have an account entry."""
    for name in ("newcomer", "brigade", "bulk_bump", "campaign"):
        _, accounts, prs, _ = load_fixture(name)
        for pr in prs:
            assert pr["author"] in accounts, (
                f"{name}: PR {pr['id']} author '{pr['author']}' not in accounts.json"
            )


def test_pr_projects_exist():
    """Every PR's project field must reference a known project id."""
    for name in ("newcomer", "brigade", "bulk_bump", "campaign"):
        projects, _, prs, _ = load_fixture(name)
        for pr in prs:
            assert pr["project"] in projects, (
                f"{name}: PR {pr['id']} references unknown project '{pr['project']}'"
            )


# ─── newcomer ─────────────────────────────────────────────────────────────────

def test_newcomer_has_no_vouches_or_denounces():
    """
    new_dev must appear in zero vouch/denounce lists across the whole network.
    With no trust history the engine must return PROVISIONAL, never HOLD.
    """
    projects, accounts, prs, labels = load_fixture("newcomer")
    newcomers = labels["newcomer_handles"]
    assert newcomers, "labels.newcomer_handles must list at least one handle"

    for handle in newcomers:
        assert handle in accounts, f"newcomer '{handle}' missing from accounts.json"
        for proj in projects.values():
            vouched   = [v["handle"] for v in proj.get("vouches", [])]
            denounced = [d["handle"] for d in proj.get("denounces", [])]
            assert handle not in vouched,   (
                f"newcomer '{handle}' must have no vouches (found in {proj['id']})"
            )
            assert handle not in denounced, (
                f"newcomer '{handle}' must have no denounces (found in {proj['id']})"
            )


def test_newcomer_has_at_least_one_pr():
    """There must be a PR from the newcomer so the engine has something to evaluate."""
    projects, accounts, prs, labels = load_fixture("newcomer")
    newcomers = set(labels["newcomer_handles"])
    newcomer_prs = [pr for pr in prs if pr["author"] in newcomers]
    assert len(newcomer_prs) >= 1, "newcomer fixture needs at least one PR from the newcomer"


# ─── brigade ──────────────────────────────────────────────────────────────────

def test_brigade_attack_projects_not_trusted_by_viewer():
    """
    proj-01 (the viewer) must have no trust edge to any fake/brigade project.
    Denounces from untrusted sources (T < 0.25) are ignored by the engine.
    """
    projects, _, _, labels = load_fixture("brigade")
    viewer = projects["proj-01"]
    trusted_by_viewer    = {t["project"] for t in viewer.get("trusts", [])}
    attack_project_ids   = set(labels.get("attack_project_ids", []))

    assert attack_project_ids, "labels.attack_project_ids must list the brigade projects"
    overlap = trusted_by_viewer & attack_project_ids
    assert not overlap, (
        f"Viewer (proj-01) must NOT trust brigade projects, but trusts: {overlap}"
    )


def test_brigade_all_attack_projects_denounce_honest_author():
    """Every brigade project must carry a denounce entry for the honest author."""
    projects, _, _, labels = load_fixture("brigade")
    honest = labels["honest_handle"]
    attack_ids = labels.get("attack_project_ids", [])
    for pid in attack_ids:
        proj = projects[pid]
        denounced_handles = [d["handle"] for d in proj.get("denounces", [])]
        assert honest in denounced_handles, (
            f"Brigade project {pid} must denounce '{honest}'"
        )


def test_brigade_honest_author_is_vouched_by_trusted_project():
    """
    The honest author must have at least one vouch from a project that
    the viewer (proj-01) actually trusts. Without this, the outcome would
    be PROVISIONAL, not ACCEPT — making the brigade test less interesting.
    """
    projects, _, _, labels = load_fixture("brigade")
    honest = labels["honest_handle"]
    viewer = projects["proj-01"]
    trusted_by_viewer = {t["project"] for t in viewer.get("trusts", [])}

    vouching_trusted = [
        pid for pid in trusted_by_viewer
        if any(v["handle"] == honest for v in projects[pid].get("vouches", []))
    ]
    assert vouching_trusted, (
        f"'{honest}' must be vouched by at least one project trusted by proj-01"
    )


# ─── bulk_bump ────────────────────────────────────────────────────────────────

def test_bulk_bump_maintainer_account_is_old():
    """
    dep_maintainer's account must be older than 14 days at the time of the PRs.
    This is the key property that separates a legitimate bulk update from a campaign.
    """
    _, accounts, prs, labels = load_fixture("bulk_bump")
    maintainer = labels["maintainer_handle"]
    assert maintainer in accounts, f"'{maintainer}' not in accounts.json"

    # Find the earliest PR time as the reference point
    pr_times = [parse_dt(pr["created_at"]) for pr in prs if pr["author"] == maintainer]
    assert pr_times, f"No PRs found from '{maintainer}'"
    earliest_pr = min(pr_times)

    created = parse_dt(accounts[maintainer]["created_at"])
    age_days = (earliest_pr - created).days
    assert age_days > 14, (
        f"dep_maintainer account is only {age_days} days old — must be >14 days"
    )


def test_bulk_bump_prs_are_near_identical():
    """
    All PRs from dep_maintainer share the same title.
    Near-identical text is what triggers similarity clustering;
    this fixture tests that an old, vouched account is not flagged despite that.
    """
    _, _, prs, labels = load_fixture("bulk_bump")
    maintainer = labels["maintainer_handle"]
    bump_prs = [pr for pr in prs if pr["author"] == maintainer]
    assert len(bump_prs) >= 5, (
        f"Need at least 5 bump PRs to be interesting, got {len(bump_prs)}"
    )
    titles = {pr["title"] for pr in bump_prs}
    assert len(titles) == 1, f"All bump PRs should share one title, got: {titles}"


def test_bulk_bump_maintainer_is_vouched():
    """dep_maintainer must be vouched by at least one project in the network."""
    projects, _, _, labels = load_fixture("bulk_bump")
    maintainer = labels["maintainer_handle"]
    vouching = [
        pid for pid, proj in projects.items()
        if any(v["handle"] == maintainer for v in proj.get("vouches", []))
    ]
    assert vouching, f"'{maintainer}' must have at least one vouch in bulk_bump"


def test_bulk_bump_produces_no_campaign():
    """labels.campaign_pr_ids must be empty — this is the NEGATIVE case."""
    _, _, _, labels = load_fixture("bulk_bump")
    assert labels["campaign_pr_ids"] == [], (
        "bulk_bump is the NEGATIVE case: campaign_pr_ids must be empty"
    )


# ─── campaign ─────────────────────────────────────────────────────────────────

def test_campaign_meets_size_threshold():
    """Planted campaign must have >=8 PRs across >=5 distinct projects (policy thresholds)."""
    projects, _, prs, labels = load_fixture("campaign")
    campaign_ids = set(labels["campaign_pr_ids"])
    campaign_prs = [pr for pr in prs if pr["id"] in campaign_ids]
    campaign_projects = {pr["project"] for pr in campaign_prs}
    assert len(campaign_prs) >= 8, (
        f"Campaign needs >=8 PRs, got {len(campaign_prs)}"
    )
    assert len(campaign_projects) >= 5, (
        f"Campaign needs >=5 distinct projects, got {len(campaign_projects)}"
    )


def test_campaign_within_6_hour_window():
    """All campaign PRs must fall within a 6-hour window (policy threshold)."""
    _, _, prs, labels = load_fixture("campaign")
    campaign_ids = set(labels["campaign_pr_ids"])
    campaign_prs = [pr for pr in prs if pr["id"] in campaign_ids]
    times = [parse_dt(pr["created_at"]) for pr in campaign_prs]
    window = max(times) - min(times)
    assert window <= timedelta(hours=6), (
        f"Campaign window is {window}, must be <=6 hours"
    )


def test_campaign_accounts_are_young():
    """
    >=70% of campaign authors must have accounts younger than 14 days at PR time.
    Policy threshold: young_share >= 0.7 contributes to the campaign score.
    """
    _, accounts, prs, labels = load_fixture("campaign")
    campaign_ids = set(labels["campaign_pr_ids"])
    campaign_prs = [pr for pr in prs if pr["id"] in campaign_ids]

    young = 0
    for pr in campaign_prs:
        pr_time = parse_dt(pr["created_at"])
        created = parse_dt(accounts[pr["author"]]["created_at"])
        if (pr_time - created).days < 14:
            young += 1

    young_share = young / len(campaign_prs)
    assert young_share >= 0.7, (
        f"Young-account share is {young_share:.0%}, need >=70%"
    )


def test_campaign_prs_have_similar_titles():
    """All campaign PRs share the same title (near-identical text signal)."""
    _, _, prs, labels = load_fixture("campaign")
    campaign_ids = set(labels["campaign_pr_ids"])
    campaign_prs = [pr for pr in prs if pr["id"] in campaign_ids]
    titles = {pr["title"] for pr in campaign_prs}
    assert len(titles) == 1, (
        f"Campaign PRs should share one title for similarity clustering, got: {titles}"
    )


def test_campaign_attack_handles_match_labels():
    """Every campaign PR author must be listed in labels.attack_handles."""
    _, _, prs, labels = load_fixture("campaign")
    campaign_ids    = set(labels["campaign_pr_ids"])
    attack_handles  = set(labels["attack_handles"])
    campaign_prs    = [pr for pr in prs if pr["id"] in campaign_ids]
    authors         = {pr["author"] for pr in campaign_prs}
    unlabelled      = authors - attack_handles
    assert not unlabelled, (
        f"Campaign PR authors not in attack_handles: {unlabelled}"
    )
