const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];
const list = value => value.split(',').map(item => item.trim()).filter(Boolean);
const number = value => value ? Number(value) : null;

function step(name) {
  $$('.tab,.panel').forEach(element => element.classList.remove('active'));
  $(`.tab[data-step="${name}"]`).classList.add('active');
  $(`#${name}`).classList.add('active');
}

$$('.tab').forEach(button => button.onclick = () => step(button.dataset.step));

async function api(path, options = {}) {
  const response = await fetch(path, {headers: {'Content-Type': 'application/json'}, ...options});
  const data = await response.json();
  if (!response.ok) throw Error(data.error || 'Request failed');
  return data;
}

function fillProfile(profile) {
  if (!profile) return;
  const form = $('#profile-form');
  for (const key of ['name', 'headline', 'master_resume']) form.elements[key].value = profile[key] || '';
  for (const key of ['target_roles', 'target_skills', 'work_modes', 'dealbreakers']) form.elements[key].value = (profile.preferences[key] || []).join(', ');
  for (const key of ['location', 'minimum_salary', 'target_salary', 'travel_max_percent']) form.elements[key].value = profile.preferences[key] ?? '';
  $('#fact-count').textContent = `${profile.facts.length} verified facts`;
}

$('#profile-form').onsubmit = async event => {
  event.preventDefault();
  const form = event.target, message = $('#profile-message');
  message.textContent = 'Saving...';
  try {
    const values = Object.fromEntries(new FormData(form));
    const payload = {name: values.name, headline: values.headline, master_resume: values.master_resume, preferences: {
      target_roles: list(values.target_roles), target_skills: list(values.target_skills), work_modes: list(values.work_modes),
      dealbreakers: list(values.dealbreakers), location: values.location, minimum_salary: number(values.minimum_salary),
      target_salary: number(values.target_salary), travel_max_percent: number(values.travel_max_percent)
    }};
    const data = await api('/api/profile', {method: 'POST', body: JSON.stringify(payload)});
    fillProfile(data.profile); message.textContent = 'Saved. Master resume preserved.'; setTimeout(() => step('job'), 500);
  } catch (error) { message.textContent = error.message; }
};

$('#job-form').onsubmit = async event => {
  event.preventDefault();
  const message = $('#job-message'); message.textContent = 'Analyzing...';
  try {
    const payload = Object.fromEntries(new FormData(event.target));
    const data = await api('/api/analyze', {method: 'POST', body: JSON.stringify(payload)});
    render(data.analysis); message.textContent = ''; step('results');
  } catch (error) { message.textContent = error.message; }
};

function listItems(items, empty) {
  return items.length ? items.map(item => `<li>${esc(item)}</li>`).join('') : `<li class="empty-item">${empty}</li>`;
}

function render(analysis) {
  $('#empty').hidden = true;
  const scores = Object.entries(analysis.score_breakdown).map(([name, value]) => `
    <div class="metric"><span>${esc(name)}</span><strong>${value}</strong><small>out of 100</small></div>`).join('');
  const evidence = analysis.evidence.map(item => `
    <article class="evidence"><p>${esc(item.fact)}</p><div class="evidence-meta"><code>${esc(item.fact_id)}</code><span>${item.matched_terms.map(esc).join(', ')}</span></div></article>`).join('') || '<p class="empty-state">No direct evidence found.</p>';
  const compensation = analysis.compensation.employer_posted || analysis.compensation.market_estimate;
  const pay = compensation ? `<div class="pay"><strong>$${compensation.minimum.toLocaleString()} - $${compensation.maximum.toLocaleString()}</strong><span>${esc(compensation.source.replaceAll('_', ' '))} · ${esc(compensation.confidence)} confidence</span><p>${esc(compensation.note)}</p></div>` : '<p class="empty-state">No posted compensation or candidate target was available. No estimate was made.</p>';
  const matched = analysis.matched_skills.length ? analysis.matched_skills.map(skill => `<span class="tag">${esc(skill)}</span>`).join('') : '<span class="empty-state">None detected</span>';
  const recommendationClass = analysis.recommendation.toLowerCase().replaceAll(' ', '-');

  $('#analysis').hidden = false;
  $('#analysis').innerHTML = `
    <section class="recommendation-summary ${recommendationClass}">
      <div class="score" style="--score:${analysis.overall_score}"><strong>${analysis.overall_score}</strong><span>/ 100</span></div>
      <div class="summary-copy"><span class="recommendation">${esc(analysis.recommendation)}</span><h2>${esc(analysis.job.title || 'Untitled role')}</h2><p class="company">${esc(analysis.job.company || 'Company not supplied')}</p><p>${esc(analysis.explanation)}</p></div>
    </section>
    <section aria-labelledby="score-heading"><div class="content-heading"><div><span class="kicker">Fit breakdown</span><h3 id="score-heading">How this recommendation was calculated</h3></div></div><div class="breakdown">${scores}</div></section>
    <div class="results-grid">
      <main class="results-main">
        <section class="card"><div class="card-heading"><div><span class="kicker">Source-grounded</span><h3>Verified evidence</h3></div><span class="count-badge">${analysis.evidence.length}</span></div>${evidence}</section>
        <section class="card"><span class="kicker">Direct overlap</span><h3>Matched skills</h3><div class="tags">${matched}</div></section>
      </main>
      <aside class="results-aside">
        <section class="card"><span class="kicker">Review before applying</span><h3>Gaps</h3><ul class="finding-list">${listItems(analysis.gaps, 'No material gaps detected.')}</ul></section>
        <section class="card"><span class="kicker">Decision blockers</span><h3>Disqualifiers</h3><ul class="finding-list danger">${listItems(analysis.disqualifiers, 'None detected.')}</ul></section>
        <section class="card"><span class="kicker">Compensation</span><h3>Pay signal</h3>${pay}</section>
      </aside>
    </div>
    <section class="next-step"><div><span class="kicker">Next step</span><h3>Create application materials</h3><p>Generate drafts that use only the verified evidence shown above.</p></div><button id="tailor" class="primary">Generate materials</button></section>
    <div id="material-output"></div>`;
  $('#tailor').onclick = generate;
}

async function generate() {
  const button = $('#tailor'); button.disabled = true; button.textContent = 'Generating...';
  try {
    const data = await api('/api/tailor', {method: 'POST', body: '{}'}), materials = data.materials;
    $('#material-output').innerHTML = `<section class="materials-section"><div class="content-heading"><div><span class="kicker">Evidence validated</span><h3>Your application materials</h3><p>${materials.validation.checked_fact_count} claims checked. Master resume SHA-256 unchanged.</p></div></div><div class="document-grid"><article class="document-card"><div class="document-title"><h3>Tailored resume</h3><button class="primary export" data-kind="resume">Download PDF</button></div><div class="materials">${esc(materials.tailored_resume)}</div></article><article class="document-card"><div class="document-title"><h3>Cover letter</h3><button class="primary export" data-kind="cover_letter">Download PDF</button></div><div class="materials">${esc(materials.cover_letter)}</div></article></div></section>`;
    $$('.export').forEach(exportButton => exportButton.onclick = () => downloadPdf(exportButton.dataset.kind));
  } catch (error) { alert(error.message); }
  finally { button.disabled = false; button.textContent = 'Generate materials'; }
}

async function downloadPdf(kind) {
  const response = await fetch('/api/export', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({kind})});
  if (!response.ok) { const data = await response.json(); throw Error(data.error || 'Export failed'); }
  const url = URL.createObjectURL(await response.blob()), anchor = document.createElement('a');
  anchor.href = url; anchor.download = `${kind}.pdf`; anchor.click(); URL.revokeObjectURL(url);
}

function esc(value) { const div = document.createElement('div'); div.textContent = value ?? ''; return div.innerHTML; }

Promise.all([api('/api/profile'), api('/api/analysis')]).then(([profile, analysis]) => { fillProfile(profile.profile); if (analysis.analysis) render(analysis.analysis); }).catch(() => {});
