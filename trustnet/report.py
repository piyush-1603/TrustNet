"""Self-contained, guided demonstrations backed by production engine decisions."""
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from .loaders import load_policy
from .models import parse_time


def _e(value):
    return escape(str(value), quote=True)


def _badge(decision):
    return f'<span class="badge {_e(decision.lower())}">{_e(decision)}</span>'


def _path_svg(paths):
    if not paths:
        return '<p class="muted">No contributing trust path.</p>'
    rows = []
    for i, path in enumerate(paths):
        y = 26 + i * 52
        for j, project in enumerate(path):
            x = 16 + j * 145
            if j:
                rows.append(f'<path d="M{x-35} {y}h35" class="link"/>')
            rows.append(f'<rect x="{x}" y="{y-17}" width="110" height="34" rx="6"/>')
            rows.append(f'<text x="{x+55}" y="{y+5}">{_e(project)}</text>')
    return (f'<svg role="img" aria-label="Contributing trust paths" viewBox="0 0 590 {len(paths)*52+10}">'
            + ''.join(rows) + '</svg>')


def _card(d):
    reasons = ''.join(f'<li>{_e(r)}</li>' for r in d.reasons)
    ignored = ''.join(f'<li>{_e(r)}</li>' for r in d.ignored)
    steps = ''.join(f'<li>{_e(r)}</li>' for r in getattr(d, 'next_steps', []))
    return f'''<article class="decision">
    <div class="card-head"><span class="eyebrow">VIEWER / {_e(d.viewer)}</span>{_badge(d.decision)}</div>
    <h3>{_e(d.author)}</h3><p class="muted">PR {_e(d.pr_id)}</p>
    <div class="metrics"><div><strong>{d.belief:.2f}</strong><span>Belief · trusted support</span></div>
    <div><strong>{d.disbelief:.2f}</strong><span>Disbelief · trusted opposition</span></div>
    <div><strong>{d.uncertainty:.2f}</strong><span>Uncertainty</span></div></div>
    <h4>Why this decision?</h4><ul>{reasons}</ul>
    <div class="paths">{_path_svg(d.paths)}</div>
    {f'<div class="next"><h4>Path to trust</h4><ul>{steps}</ul></div>' if steps else ''}
    <details><summary>Inspect excluded evidence ({len(d.ignored)})</summary>
    {f'<ul>{ignored}</ul>' if ignored else '<p>No evidence was excluded.</p>'}</details>
    </article>'''


def _lab(results):
    rows = []
    for name, row in results.get('scenarios', {}).items():
        rows.append(f'''<tr><th scope="row">{_e(name)}</th><td>{_e(row['naive_before'])} → {_e(row['naive_after'])}</td>
        <td>{_e(row['defended_before'])} → {_e(row['defended_after'])}</td><td><span class="badge {'accept' if row['defense_goal_met'] else 'hold'}">
        {'Goal met' if row['defense_goal_met'] else 'Goal missed'}</span></td>
        <td>{row['campaign_false_positive_rate']:.1%} of {row['honest_newcomers']} honest PRs</td>
        <td>{row['newcomer_hold_rate']:.1%}</td></tr>''')
    return f'''<p class="lead">Five controlled attacks. Every outcome stays visible, including failure.</p>
    <div class="table-wrap"><table><thead><tr><th>Fixture</th><th>Naive BEFORE → AFTER</th><th>TrustNet BEFORE → AFTER</th>
    <th>Defense goal</th><th>Campaign false positives</th><th>Newcomer HOLD rate</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
    <div class="callout warning"><strong>The boundary: a compromised trusted source.</strong><p>A false endorsement from a directly trusted source can still produce ACCEPT. These synthetic regression fixtures establish specific behavior, not general attack resistance.</p></div>'''


def _repo_panel(project, prs, decisions, net, campaign_prs):
    trusts = ''.join(f'<li><strong>{_e(net.projects[t.project].name if t.project in net.projects else t.project)}</strong> <span>{_e(t.project)} · trust {t.weight:.2f}</span></li>' for t in project.trusts)
    vouches = ''.join(f'<li><strong>{_e(v.handle)}</strong> · {_e(v.date)}{f" · {_e(v.evidence_url)}" if v.evidence_url else ""}</li>' for v in project.vouches)
    denounces = ''.join(f'<li><strong>{_e(d.handle)}</strong> · {_e(d.reason_code)}{f" · {_e(d.evidence_url)}" if d.evidence_url else ""}</li>' for d in project.denounces)
    rows = []
    for pr in prs:
        decision = decisions.get(pr.id)
        account = net.accounts.get(pr.author)
        if account:
            age = (parse_time(pr.created_at) - parse_time(account.created_at)).days
            age_text = f'{age} days old at PR' if age >= 0 else 'account date follows PR date'
        else:
            age_text = 'account age unavailable'
        campaign = '<span class="campaign-tag">Flagged campaign</span>' if pr.id in campaign_prs else ''
        details = _card(decision) if decision else '<p class="muted">No decision was supplied for this PR.</p>'
        rows.append(f'''<details class="pr-record"><summary><span><strong>{_e(pr.id)} · {_e(pr.title)}</strong><small>{_e(pr.author)} · {age_text} {campaign}</small></span>{_badge(decision.decision) if decision else ''}</summary>
        <div class="pr-details">{details}<details><summary>PR text and change</summary><h4>{_e(pr.title)}</h4><p>{_e(pr.body) or 'No description provided.'}</p><pre>{_e(pr.diff_text) or 'No diff provided.'}</pre></details></div></details>''')
    return f'''<article class="repo-card" data-project="{_e(project.id)}">
    <div class="repo-heading"><div><p class="eyebrow">REPOSITORY / PROJECT</p><h3>{_e(project.name)}</h3><p class="muted">{_e(project.id)} · {len(prs)} incoming PRs</p></div><span class="badge provisional">Decision viewpoint: {_e(next(iter(decisions.values())).viewer if decisions else 'not available')}</span></div>
    <p class="dataset-note">This fixture stores trust links, vouches, denunciations, contributor account dates, and PR title, description, and diff.</p>
    <div class="repo-columns"><section><h4>Projects this repo trusts ({len(project.trusts)})</h4><ul class="compact">{trusts or '<li>None listed</li>'}</ul>
    <details><summary>Vouches ({len(project.vouches)})</summary><ul class="compact">{vouches or '<li>None listed</li>'}</ul></details>
    <details><summary>Denunciations ({len(project.denounces)})</summary><ul class="compact">{denounces or '<li>None listed</li>'}</ul></details></section>
    <section><h4>Incoming PRs ({len(prs)})</h4><div class="pr-list">{''.join(rows) or '<p>No PRs in this snapshot.</p>'}</div></section></div></article>'''


def render(net, decisions, campaigns, lab_results, out_path):
    policy, digest = load_policy()
    viewer = decisions[0].viewer if decisions else next(iter(sorted(net.projects)), '')
    decision_by_pr = {d.pr_id: d for d in decisions}
    project_prs = {pid: [] for pid in net.projects}
    for pr in net.prs:
        project_prs.setdefault(pr.project, []).append(pr)
    campaign_prs = {pr_id for c in campaigns if c.flagged for pr_id in c.pr_ids}
    ordered_projects = sorted(net.projects.items(), key=lambda item: (not bool(project_prs.get(item[0])), item[1].name.casefold(), item[0]))
    initial_project = viewer if viewer in net.projects else (ordered_projects[0][0] if ordered_projects else '')
    def repo_options(items):
        return ''.join(f'<button type="button" role="option" tabindex="-1" aria-selected="{str(pid == initial_project).lower()}" class="repo-option" data-project="{_e(pid)}"><span class="repo-mark" aria-hidden="true">{_e(project.name[:2].upper())}</span><span class="repo-option-name"><strong>{_e(project.name)}</strong><small>{_e(pid)}</small></span><span class="repo-count">{len(project_prs.get(pid, []))} PRs</span></button>' for pid, project in items)
    active_repos = [(pid, project) for pid, project in ordered_projects if project_prs.get(pid)]
    quiet_repos = [(pid, project) for pid, project in ordered_projects if not project_prs.get(pid)]
    repo_choices = (f'<div class="repo-option-group" role="group" aria-label="Repositories with PRs"><p class="repo-group-label">Repositories with PRs <span>{len(active_repos)}</span></p>{repo_options(active_repos)}</div>'
                   f'<div class="repo-option-group" role="group" aria-label="Trust nodes without PRs"><p class="repo-group-label">Trust nodes without PRs <span>{len(quiet_repos)}</span></p>{repo_options(quiet_repos)}</div>')
    selected = net.projects.get(initial_project)
    selected_name = selected.name if selected else 'No repository available'
    selected_count = len(project_prs.get(initial_project, []))
    repo_panels = ''.join(_repo_panel(project, project_prs.get(pid, []), decision_by_pr, net, campaign_prs) for pid, project in sorted(net.projects.items()))
    campaign_cards = []
    for campaign in campaigns:
        method = ('Behavior only · text model not used' if getattr(campaign, 'kind', 'text') == 'behavior'
                  else 'nomic-embed-text + TF-IDF · embedding model ran' if campaign.embedding_used
                  else 'TF-IDF only · embedding model not used')
        members = [pr for pr in net.prs if pr.id in campaign.pr_ids]
        people = ''.join(f'<li><strong>{_e(author)}</strong> · account linked to this campaign</li>' for author in campaign.authors)
        member_rows = ''.join(f'<li>{_e(pr.id)} · {_e(pr.project)} · {_e(pr.author)} · {_badge(decision_by_pr[pr.id].decision) if pr.id in decision_by_pr else ""}</li>' for pr in members)
        campaign_cards.append(f'''<article class="campaign-card"><div class="card-head"><h3>{_e(campaign.id)}</h3><span class="badge {'hold' if campaign.flagged else 'provisional'}">{'FLAGGED' if campaign.flagged else 'NOT FLAGGED'}</span></div>
        <p>{len(campaign.pr_ids)} PRs · {len(campaign.projects)} repositories · {len(campaign.authors)} accounts · score {campaign.score:.2f}</p>
        <p class="muted">{method}</p><ul>{''.join(f'<li>{_e(item)}</li>' for item in campaign.evidence)}</ul>
        <details><summary>Inspect linked PRs and accounts</summary><div class="repo-columns"><ul class="compact">{member_rows}</ul><ul class="compact">{people}</ul></div></details></article>''')
    counts = {label: sum(d.decision == label for d in decisions) for label in ('ACCEPT', 'PROVISIONAL', 'HOLD')}
    text_campaigns = [c for c in campaigns if getattr(c, 'kind', 'text') == 'text']
    model_status = ('nomic-embed-text + TF-IDF' if any(c.embedding_used for c in text_campaigns) else 'TF-IDF only') if text_campaigns else 'no text group; scan method not retained'
    pipeline = f'''<ol class="pipeline">
    <li><b>1 · Load snapshot</b><span>{len(net.projects)} repos · {len(net.accounts)} accounts · {len(net.prs)} PRs</span></li>
    <li><b>2 · Find coordination</b><span>{len(campaigns)} campaign groups · {len(campaign_prs)} linked PRs · {_e(model_status)}</span></li>
    <li><b>3 · Evaluate PRs</b><span>{len(decisions)} decisions as {_e(viewer)} · {counts['ACCEPT']} ACCEPT · {counts['PROVISIONAL']} PROVISIONAL · {counts['HOLD']} HOLD</span></li>
    <li><b>4 · Run attack fixtures</b><span>{len(lab_results.get('scenarios', {}))} scenarios · synthetic regression checks</span></li></ol>'''
    rules = ''.join(f'<tr><th>{_e(section)}.{_e(key)}</th><td>{_e(value)}</td></tr>' for section, block in policy.items() if isinstance(block, dict) for key, value in block.items())
    now = datetime.now(timezone.utc).strftime('%d %b %Y · %H:%M UTC')
    html = f'''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>TrustNet Report</title><style>{_CSS}</style></head><body>
    <header><a class="brand" href="#top"><span class="brand-mark" aria-hidden="true">T</span>TrustNet <span>run console</span></a><nav aria-label="Report sections"><a href="#repositories">Repositories</a><a href="#campaigns">Campaigns</a><a href="#lab">Test cases</a></nav><span class="run">Policy {_e(digest)} · {_e(now)}</span></header>
    <main id="top"><section class="run-summary"><div><p class="eyebrow">NETWORK SNAPSHOT</p><h1>Follow the evidence through the run.</h1><p>Inspect the repositories, pull requests, campaign links, and decisions produced from this input.</p></div>{pipeline}</section>
    <section id="repositories"><div class="section-heading"><div><p class="eyebrow">INPUT → TRUST ENGINE</p><h2>Repository explorer</h2></div><span class="muted">Decisions are from {_e(viewer)}’s point of view. Choose a PR to inspect its evidence.</span></div>
    <div class="repo-controls"><label for="repo-trigger">Repository</label><div class="repo-picker" id="repo-picker"><button type="button" id="repo-trigger" class="repo-trigger" aria-haspopup="listbox" aria-expanded="false" aria-controls="repo-options" {'disabled' if not selected else ''}><span class="repo-trigger-name"><strong id="selected-repo-name">{_e(selected_name)}</strong><small id="selected-repo-id">{_e(initial_project)}</small></span><span id="selected-repo-count" class="repo-count">{selected_count} PRs</span><span class="chevron" aria-hidden="true">⌄</span></button>
    <div class="repo-menu" id="repo-menu" hidden><label class="repo-search-label" for="repo-search">Search repositories</label><input id="repo-search" type="search" placeholder="Name or project ID"><div id="repo-options" class="repo-options" role="listbox" aria-label="Repositories">{repo_choices}</div><p id="repo-empty" class="repo-empty" hidden>No repositories match.</p></div></div><label for="record-search">Find PR or account</label><input id="record-search" type="search" placeholder="e.g. pr-151 or bot-00"></div>
    <div id="repo-panels">{repo_panels or '<p class="empty">No repositories in this snapshot.</p>'}</div></section>
    <section id="campaigns"><div class="section-heading"><div><p class="eyebrow">SIMILARITY → BEHAVIORAL RULES</p><h2>Campaign findings</h2></div><p class="muted">A campaign link is a coordination signal, not proof that an account is fraudulent.</p></div><div class="campaign-list">{''.join(campaign_cards) or '<p class="empty">No qualifying campaign found.</p>'}</div></section>
    <section id="lab"><div class="section-heading"><div><p class="eyebrow">REGRESSION FIXTURES</p><h2>What the defenses do</h2></div><p class="muted">The lab checks these five known cases; it does not estimate real-world attack rates.</p></div>{_lab(lab_results)}</section>
    <details class="policy-details"><summary>Decision rules and project limits</summary><p>Strongest trust path multiplies edge weights and applies 0.6 decay per extra hop, up to 3 hops; alternate paths are not summed. Belief and disbelief combine trusted vouches and denunciations separately. They are support scores, not calibrated probabilities.</p><p>No live GitHub integration or Vouch-file adapter; organizer input compatibility is unverified. Advisory files are not signed. A compromised trusted source can defeat the defense.</p><table>{rules}</table></details></main>
    <script>{_JS}</script></body></html>'''
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding='utf-8')


_JS = '''
const picker = document.getElementById('repo-picker');
const trigger = document.getElementById('repo-trigger');
const menu = document.getElementById('repo-menu');
const repoSearch = document.getElementById('repo-search');
const options = Array.from(document.querySelectorAll('.repo-option'));
const search = document.getElementById('record-search');
const repos = Array.from(document.querySelectorAll('.repo-card'));
let selectedProject = options.find(option => option.getAttribute('aria-selected') === 'true')?.dataset.project || '';
function visibleOptions() { return options.filter(option => !option.hidden); }
function filterOptions() {
  const query = repoSearch.value.trim().toLowerCase();
  for (const option of options)
    option.hidden = !option.textContent.toLowerCase().includes(query);
  document.getElementById('repo-empty').hidden = visibleOptions().length !== 0;
  document.querySelectorAll('.repo-option-group').forEach(group => {
    group.hidden = !group.querySelector('.repo-option:not([hidden])');
  });
  options.forEach(option => option.tabIndex = -1);
  const first = visibleOptions().find(option => option.getAttribute('aria-selected') === 'true') || visibleOptions()[0];
  if (first) first.tabIndex = 0;
}
function updateRepos() {
  const query = search.value.trim().toLowerCase();
  for (const repo of repos) {
    const matches = !query || repo.textContent.toLowerCase().includes(query);
    repo.hidden = !matches || (!query && repo.dataset.project !== selectedProject);
    for (const pr of repo.querySelectorAll('.pr-record'))
      pr.hidden = !!query && !pr.querySelector('summary').textContent.toLowerCase().includes(query);
  }
}
function closePicker() {
  menu.hidden = true;
  trigger.setAttribute('aria-expanded', 'false');
}
function openPicker() {
  menu.hidden = false;
  menu.classList.toggle('opens-up', window.innerHeight - trigger.getBoundingClientRect().bottom < 280);
  trigger.setAttribute('aria-expanded', 'true');
  repoSearch.value = '';
  filterOptions();
  repoSearch.focus();
}
function choose(option) {
  selectedProject = option.dataset.project;
  options.forEach(item => item.setAttribute('aria-selected', String(item === option)));
  document.getElementById('selected-repo-name').textContent = option.querySelector('strong').textContent;
  document.getElementById('selected-repo-id').textContent = option.querySelector('small').textContent;
  document.getElementById('selected-repo-count').textContent = option.querySelector('.repo-count').textContent;
  search.value = '';
  updateRepos();
  closePicker();
  trigger.focus();
}
trigger.addEventListener('click', () => {
  if (menu.hidden) openPicker(); else closePicker();
});
trigger.addEventListener('keydown', event => {
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); openPicker(); }
});
options.forEach(option => {
  option.addEventListener('click', () => choose(option));
  option.addEventListener('keydown', event => {
    const available = visibleOptions();
    const current = available.indexOf(option);
    if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? available.length - 1 : (current + (event.key === 'ArrowDown' ? 1 : -1) + available.length) % available.length;
      available.forEach(item => item.tabIndex = -1);
      available[next].tabIndex = 0;
      available[next].focus();
    } else if (event.key === 'Escape') { closePicker(); trigger.focus(); }
  });
});
repoSearch.addEventListener('input', filterOptions);
repoSearch.addEventListener('keydown', event => {
  if (event.key === 'ArrowDown') { event.preventDefault(); visibleOptions()[0]?.focus(); }
  else if (event.key === 'Escape') { closePicker(); trigger.focus(); }
  else if (event.key === 'Enter' && visibleOptions().length) { event.preventDefault(); choose(visibleOptions()[0]); }
});
document.addEventListener('click', event => { if (!picker.contains(event.target)) closePicker(); });
picker.addEventListener('focusout', event => { if (!picker.contains(event.relatedTarget)) closePicker(); });
search.addEventListener('input', updateRepos);
updateRepos();
'''

_CSS = '''
:root{color-scheme:light;--bg:#f5f5f5;--surface:#fff;--ink:#111;--muted:#555;--line:#d5d5d5;--accent:#222;--accept:#176b4a;--amber:#805b15;--red:#a52f3f;--soft:#ededed}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(125deg,#fff 0%,#f7f7f7 48%,#e9e9e9 100%) fixed;color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}button,input,select{font:inherit}a,button,input,select,summary{outline-offset:4px}a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:3px solid var(--accent)}[hidden]{display:none!important}
header{display:flex;justify-content:space-between;align-items:center;gap:24px;padding:16px max(20px,calc((100% - 1400px)/2));background:linear-gradient(90deg,#fff,#eee);border-top:3px solid #171717;border-bottom:1px solid var(--line)}.brand{display:flex;align-items:center;gap:8px;font-size:21px;font-weight:750;color:var(--ink);text-decoration:none;white-space:nowrap}.brand span,.run{font-size:12px;font-weight:450;color:var(--muted)}.brand .brand-mark{display:grid;place-items:center;width:32px;height:32px;border-radius:9px;background:linear-gradient(145deg,#444,#090909);box-shadow:0 3px 6px #0002;color:#fff;font-size:17px;font-weight:800}.run{font-family:ui-monospace,monospace;font-size:10px}header nav{display:flex;gap:3px}header nav a{padding:7px 11px;border-radius:7px;color:#555;text-decoration:none;font-size:12px;font-weight:600}header nav a:hover{background:#e5e5e5;color:#111}
main{max-width:1400px;margin:auto;padding:30px 28px 70px}.eyebrow{font:10px/1.5 ui-monospace,monospace;letter-spacing:1px;color:var(--muted);margin:0 0 8px}h1{font-size:30px;letter-spacing:-1px;margin:0}h2{font-size:22px;letter-spacing:-.4px;margin:0}h3{font-size:17px;margin:0}h4{font-size:13px;margin:0 0 8px}.muted{color:var(--muted);font-size:12px}.run-summary{display:grid;grid-template-columns:minmax(230px,.8fr) minmax(500px,1.7fr);gap:30px;align-items:start;padding-bottom:28px;border-bottom:1px solid var(--line)}.run-summary>div:first-child>p:last-child{color:var(--muted);max-width:330px}
.pipeline{list-style:none;padding:0;margin:0;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border:1px solid #ccc;border-top:3px solid #272727;border-radius:12px;background:linear-gradient(130deg,#fff,#e8e8e8);box-shadow:0 8px 22px #00000008;overflow:hidden}.pipeline li{padding:17px 14px;border-right:1px solid var(--line);font-size:12px}.pipeline li:last-child{border:0}.pipeline b,.pipeline span{display:block}.pipeline b{font-size:12px;margin-bottom:7px}.pipeline span{color:var(--muted);font-size:11px}
section{margin-top:34px}.section-heading{display:flex;justify-content:space-between;align-items:end;gap:20px;margin-bottom:15px}.section-heading>.muted{max-width:460px;text-align:right}
.repo-controls{display:grid;grid-template-columns:auto minmax(200px,1fr) auto minmax(180px,1fr);align-items:center;gap:12px;margin-bottom:18px;padding:14px;background:linear-gradient(120deg,#fff,#f1f1f1);border:1px solid #d4d4d4;border-radius:14px;box-shadow:0 6px 18px #00000006;font-size:12px;font-weight:600}.repo-controls input{width:100%;min-height:52px;padding:10px 13px;border:1px solid var(--line);border-radius:9px;background:var(--surface);color:var(--ink);font-weight:400}.repo-controls input::placeholder{color:#777}.repo-picker{position:relative;min-width:0}.repo-trigger{display:flex;align-items:center;gap:12px;width:100%;min-height:52px;text-align:left;padding:9px 13px;border:1px solid #bcbcbc;border-radius:9px;background:linear-gradient(110deg,#fff,#eee);color:#111;cursor:pointer;box-shadow:0 2px 4px #00000005;transition:border-color .15s,box-shadow .15s}.repo-trigger:hover,.repo-trigger[aria-expanded=true]{border-color:#222;box-shadow:0 0 0 3px #00000008}.repo-trigger-name{min-width:0;flex:1}.repo-trigger strong,.repo-trigger small{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.repo-trigger strong{font-size:13px;line-height:1.4}.repo-trigger small{font:10px/1.4 ui-monospace,monospace;color:#666;margin-top:2px}.repo-count{flex-shrink:0;padding:4px 7px;background:#e7e7e7;border:1px solid #d5d5d5;border-radius:6px;font:10px/1.3 ui-monospace,monospace;color:#333}.chevron{font-size:19px;color:#555;transition:transform .15s}.repo-trigger[aria-expanded=true] .chevron{transform:rotate(180deg)}.repo-trigger:disabled{opacity:.5;cursor:default}
.repo-menu{position:absolute;top:calc(100% + 8px);left:0;right:0;z-index:30;padding:10px;background:linear-gradient(150deg,#fff,#f7f7f7);border:1px solid #c8c8c8;border-radius:14px;box-shadow:0 20px 50px #0003,0 3px 8px #00000010}.repo-menu.opens-up{top:auto;bottom:calc(100% + 8px)}.repo-search-label{display:block;margin:2px 3px 6px;font-size:10px;color:#666}.repo-menu input{min-height:38px;padding:8px 10px;background:#f1f1f1;font-size:12px;border-color:#ddd}.repo-options{max-height:min(340px,43vh);overflow:auto;overscroll-behavior:contain;padding-top:5px;scrollbar-width:thin}.repo-group-label{display:flex;justify-content:space-between;align-items:center;margin:8px 5px 5px;font:9px/1.5 ui-monospace,monospace;letter-spacing:.6px;text-transform:uppercase;color:#6a6a6a}.repo-group-label span{letter-spacing:0;background:#e8e8e8;padding:1px 5px;border-radius:4px}.repo-option{display:flex;align-items:center;gap:10px;width:100%;padding:10px 8px;margin:2px 0;border:1px solid transparent;border-radius:9px;background:transparent;text-align:left;color:#222;cursor:pointer}.repo-option:hover,.repo-option:focus-visible{background:#eaeaea;border-color:#d4d4d4;outline-offset:-2px}.repo-mark{display:grid;place-items:center;flex-shrink:0;width:32px;height:32px;border:1px solid #d8d8d8;border-radius:8px;background:linear-gradient(140deg,#fff,#ddd);color:#555;font:700 10px ui-monospace,monospace}.repo-option-name{min-width:0;flex:1}.repo-option strong,.repo-option small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.repo-option strong{font-size:12px;font-weight:650}.repo-option small{font:10px/1.4 ui-monospace,monospace;color:#777;margin-top:2px}.repo-option[aria-selected=true]{background:linear-gradient(110deg,#343434,#111);color:#fff;border-color:#111;box-shadow:0 3px 7px #0002}.repo-option[aria-selected=true] small{color:#c8c8c8}.repo-option[aria-selected=true] .repo-mark{color:#fff;background:#ffffff12;border-color:#ffffff26}.repo-option[aria-selected=true] .repo-count{background:#ffffff15;color:#eee;border-color:#ffffff26}.repo-empty{padding:16px 8px;margin:0;color:#666;text-align:center;font-size:12px}
.repo-card,.campaign-card{background:linear-gradient(145deg,#fff 0%,#f0f0f0 100%);border:1px solid var(--line);border-radius:9px;padding:20px}.repo-heading{display:flex;justify-content:space-between;align-items:center;gap:12px}.repo-heading h3{font-size:21px}.repo-heading .muted{margin:3px 0}.dataset-note{font-size:12px;color:var(--muted);margin:15px 0;border-top:1px solid var(--line);padding-top:13px}.repo-columns{display:grid;grid-template-columns:minmax(190px,.7fr) minmax(320px,1.5fr);gap:26px}.repo-columns>section{margin:0}.compact{list-style:none;padding:0;margin:0;font-size:12px}.compact li{padding:7px 0;border-bottom:1px solid var(--line);overflow-wrap:anywhere}.compact li span{display:block;color:var(--muted);font-size:11px}.repo-card details,.campaign-card details,.policy-details{border-top:1px solid var(--line);padding-top:10px;margin-top:12px}.repo-card summary,.campaign-card summary,.policy-details summary{font-size:12px;font-weight:650;cursor:pointer}.pr-list{max-height:650px;overflow:auto;border-top:1px solid var(--line)}.pr-record{padding:10px 4px;border-bottom:1px solid var(--line)}.pr-record summary{display:flex;justify-content:space-between;align-items:center;gap:10px;cursor:pointer;list-style:none}.pr-record summary::-webkit-details-marker{display:none}.pr-record summary strong,.pr-record small{display:block}.pr-record summary strong{font-size:12px}.pr-record small{font-size:11px;color:var(--muted);margin-top:3px}.pr-details{padding-top:12px}.pr-details>.decision{margin:0 0 12px}.pr-details pre{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--soft);padding:10px;border-radius:5px;font:11px/1.5 ui-monospace,monospace;max-height:300px;overflow:auto}.campaign-tag{display:inline-block;background:#e5e5e5;color:#222;border-radius:3px;padding:1px 5px;font-size:10px}
.decision{background:linear-gradient(135deg,#fff,#f0f0f0);border:1px solid var(--line);border-radius:7px;padding:14px}.card-head{display:flex;justify-content:space-between;gap:10px;align-items:center}.card-head .eyebrow{margin:0}.decision h3{margin:10px 0 0}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:10px 0;border-block:1px solid var(--line);margin:12px 0}.metrics strong{display:block;font:20px ui-monospace,monospace}.metrics span{font-size:10px;color:var(--muted)}.decision ul,.campaign-card ul{font-size:11px;padding-left:18px;overflow-wrap:anywhere}.decision li+li,.campaign-card li+li{margin-top:5px}.paths{margin:12px 0}svg{width:100%;max-height:200px}svg rect{fill:var(--soft);stroke:var(--line)}svg text{font:11px ui-monospace,monospace;fill:var(--ink);text-anchor:middle}.link{stroke:#666;stroke-width:2;fill:none}.next{background:#e9e9e9;padding:8px;border-radius:5px}.badge{font:700 10px ui-monospace,monospace;border:1px solid currentColor;border-radius:4px;padding:4px 7px;white-space:nowrap}.accept{color:var(--accept)}.provisional{color:var(--amber)}.hold{color:var(--red)}
.campaign-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,440px),1fr));gap:12px}.campaign-card .card-head{align-items:start}.campaign-card>p{font-size:13px}.table-wrap{overflow:auto;background:var(--surface);border:1px solid var(--line);border-radius:8px}table{width:100%;border-collapse:collapse;font-size:11px;text-align:left}th,td{padding:11px;border-bottom:1px solid var(--line);vertical-align:top}thead th{background:var(--soft);color:var(--muted)}.callout{background:var(--surface);border-left:3px solid var(--red);padding:12px 16px;margin-top:14px;font-size:12px}.callout p{margin:4px 0}.policy-details{font-size:12px}.policy-details table{margin-top:12px}.empty{padding:20px;border:1px dashed var(--line)}
@media(max-width:900px){.run-summary{grid-template-columns:1fr}.pipeline{grid-template-columns:repeat(2,minmax(0,1fr))}.pipeline li:nth-child(2){border-right:0}.pipeline li:nth-child(-n+2){border-bottom:1px solid var(--line)}.repo-columns{grid-template-columns:1fr}.repo-controls{grid-template-columns:auto 1fr}.section-heading{align-items:start;flex-direction:column}.section-heading>.muted{text-align:left}}
@media(max-width:1100px){.run{display:none}}
@media(max-width:560px){header{padding:14px 16px}.run{display:none}main{padding:20px 14px}.pipeline li{padding:10px}.repo-controls{grid-template-columns:1fr;gap:4px}.repo-heading{align-items:start;flex-direction:column}.repo-card,.campaign-card{padding:14px}.metrics strong{font-size:18px}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
.repo-trigger,.chevron,header nav a{transition:background .15s,border-color .15s,box-shadow .15s,transform .15s}
@media(max-width:560px){header nav{display:none}}
@media(prefers-reduced-motion:reduce){.repo-trigger,.chevron,header nav a{transition:none}}
'''
