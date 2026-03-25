/* LSA Web UI — Single-page application */

const state = {
  step: 'snapshot',
  snapshot: null,
  snapshots: null,
  plan: null,
  candidates: [],
  selectedCandidate: 0,
  prompt: null,
  promptScenario: 'incident',
  lang: 'ru',
  stats: null,
  searchResults: null,
  loading: false,
  searchMode: 'content',
  searchScope: 'snapshot',
  searchKind: 'all',
  searchSpace: 'all',
  openWorkspaceComposer: false,
  bundleFocus: null,
};

mermaid.initialize({
  startOnLoad: false,
  theme: 'default',
  themeVariables: {
    primaryColor: '#ccfbf1',
    primaryBorderColor: '#0d9488',
    primaryTextColor: '#1a1a2e',
    lineColor: '#d1d5db',
    secondaryColor: '#f0fdfa',
    tertiaryColor: '#f8f9fb',
  },
});

async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str ?? '';
  return div.innerHTML;
}

let toastTimer = null;
function toast(message) {
  const el = document.getElementById('toast');
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 2200);
}

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast('Copied to clipboard');
  } catch {
    toast('Copy failed');
  }
}

function showModal(title, content) {
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-body').textContent = content;
  document.getElementById('modal').hidden = false;
}

function hideModal() {
  document.getElementById('modal').hidden = true;
}

function setLoading(el, on) {
  if (on) {
    el.innerHTML = '<div class="loading-panel"><div class="loading">Loading</div></div>';
  }
}

function renderPageHeader(title, subtitle, meta = '') {
  return `
    <div class="page-head">
      <div class="page-head-main">
        <div class="page-kicker">Operator Console</div>
        <h2 class="page-title">${escapeHtml(title)}</h2>
        ${subtitle ? `<p class="page-subtitle">${escapeHtml(subtitle)}</p>` : ''}
      </div>
      ${meta ? `<div class="page-head-side"><div class="page-meta">${escapeHtml(meta)}</div></div>` : ''}
    </div>`;
}

function renderEmptyState(message, title = 'No data available') {
  return `
    <div class="empty-state">
      <div class="empty-state__title">${escapeHtml(title)}</div>
      <div class="empty-state__body">${escapeHtml(message)}</div>
    </div>`;
}

function formatRelativeTime(dateStr) {
  if (!dateStr) return 'unknown';
  const parsed = new Date(dateStr.replace(' ', 'T'));
  if (Number.isNaN(parsed.getTime())) return dateStr;
  const diff = Date.now() - parsed.getTime();
  const hours = Math.round(diff / 36e5);
  if (hours < 1) return 'fresh';
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 14) return `${days}d ago`;
  return `${Math.round(days / 7)}w ago`;
}

function normalizeKind(kind) {
  switch (kind) {
    case 'script':
    case 'master':
      return 'scripts';
    case 'control':
      return 'controls';
    case 'insert':
      return 'inserts';
    case 'docdef':
      return 'docdef';
    case 'procs':
      return 'procs';
    case 'logs_inbox':
      return 'logs';
    case 'refs':
      return 'refs';
    default:
      return kind || 'other';
  }
}

function kindLabel(kind) {
  const normalized = normalizeKind(kind);
  const labels = {
    all: 'All',
    message_code: 'message code',
    case_card: 'case card',
    procs: 'procs',
    scripts: 'scripts',
    controls: 'controls',
    inserts: 'inserts',
    docdef: 'docdef',
    logs: 'logs',
    refs: 'refs',
    other: 'other',
  };
  return labels[normalized] || normalized;
}

function getSelectedCandidate() {
  return state.candidates[state.selectedCandidate] ?? null;
}

function hasCurrentScope() {
  return Boolean(state.snapshot && getSelectedCandidate());
}

function getScopeFiles() {
  return getSelectedCandidate()?.files ?? [];
}

function getScopeCounts(files = getScopeFiles()) {
  const counts = {
    total: files.length,
    procs: 0,
    scripts: 0,
    controls: 0,
    inserts: 0,
    docdef: 0,
    refs: 0,
    logs: 0,
    other: 0,
  };
  files.forEach(file => {
    const normalized = normalizeKind(file.kind);
    if (counts[normalized] !== undefined) counts[normalized] += 1;
    else counts.other += 1;
  });
  return counts;
}

function getScopeEntryPoints(candidate = getSelectedCandidate()) {
  if (!candidate) {
    return { primaryProc: null, runsScripts: [], controls: [], docdefs: [], readOrder: [] };
  }
  const runsScripts = candidate.files.filter(file => file.source === 'RUNS_edge').slice(0, 5);
  const controls = candidate.files.filter(file => file.kind === 'control').slice(0, 4);
  const docdefs = candidate.files.filter(file => file.kind === 'docdef').slice(0, 3);
  const readOrder = [
    `proc: ${candidate.proc_name ?? candidate.name ?? candidate.key}`,
    ...runsScripts.slice(0, 3).map(file => `script: ${file.path.split('/').pop()}`),
    ...controls.slice(0, 2).map(file => `control: ${file.path.split('/').pop()}`),
    ...docdefs.slice(0, 1).map(file => `docdef: ${file.path.split('/').pop()}`),
  ];
  return {
    primaryProc: candidate.proc_name ?? candidate.name ?? candidate.key,
    runsScripts,
    controls,
    docdefs,
    readOrder,
  };
}

function renderScopePills(counts) {
  const items = [
    ['files', counts.total],
    ['procs', counts.procs],
    ['scripts', counts.scripts],
    ['controls', counts.controls],
    ['inserts', counts.inserts],
    ['docdef', counts.docdef],
  ];
  return `
    <div class="pill-row">
      ${items.map(([label, value]) => `<span class="scope-pill"><strong>${value}</strong> ${escapeHtml(label)}</span>`).join('')}
    </div>`;
}

function renderScopeActions(disabled) {
  return `
    <div class="btn-row scope-actions">
      <button class="btn btn--sm" data-scope-action="open-files" ${disabled ? 'disabled' : ''}>Open files</button>
      <button class="btn btn--sm" data-scope-action="create-workspace" ${disabled ? 'disabled' : ''}>Create workspace</button>
      <button class="btn btn--sm" data-scope-action="copy-file-list" ${disabled ? 'disabled' : ''}>Copy file list</button>
      <button class="btn btn--sm btn--primary" data-scope-action="generate-prompt" ${disabled ? 'disabled' : ''}>Generate prompt</button>
      <button class="btn btn--sm" data-scope-action="open-diagram" ${disabled ? 'disabled' : ''}>Open diagram</button>
    </div>`;
}

function renderCurrentScopeBlock({ compact = false, title = 'Current scope' } = {}) {
  const candidate = getSelectedCandidate();
  const disabled = !hasCurrentScope();
  const counts = getScopeCounts();
  const body = candidate ? `
    <div class="scope-grid${compact ? ' scope-grid--compact' : ''}">
      <div class="scope-main">
        <div class="scope-heading">${escapeHtml(candidate.display_name ?? candidate.name ?? candidate.key)}</div>
        <div class="scope-subline">
          <span class="scope-meta-item">snapshot / ${escapeHtml(state.snapshot?.name ?? 'none')}</span>
          <span class="scope-meta-item">proc / ${escapeHtml(candidate.proc_name ?? candidate.key ?? 'unknown')}</span>
        </div>
        ${renderScopePills(counts)}
      </div>
      <div class="scope-side">
        <div class="scope-side-title">Scope composition</div>
        <div class="scope-side-list">
          <span>has .procs: ${counts.procs > 0 ? 'yes' : 'no'}</span>
          <span>scripts: ${counts.scripts}</span>
          <span>controls: ${counts.controls}</span>
          <span>inserts: ${counts.inserts}</span>
          <span>docdef: ${counts.docdef}</span>
        </div>
      </div>
    </div>
    ${renderScopeActions(disabled)}
  ` : `
    ${renderEmptyState('Build or select a candidate scope first. Overview, Prompt and Search become more useful once a scope is selected.', 'No current scope')}
    ${renderScopeActions(true)}
  `;
  return `
    <section class="section">
      <div class="surface surface--raised ${compact ? 'surface--compact' : ''}">
        <div class="section-title">${escapeHtml(title)}</div>
        ${body}
      </div>
    </section>`;
}

function bindScopeActions(root = document) {
  root.querySelectorAll('[data-scope-action]').forEach(button => {
    button.addEventListener('click', async () => {
      const action = button.dataset.scopeAction;
      if (!hasCurrentScope()) return;
      if (action === 'open-files') {
        state.bundleFocus = 'files';
        navigate('bundle');
        return;
      }
      if (action === 'create-workspace') {
        state.openWorkspaceComposer = true;
        state.bundleFocus = 'workspace';
        navigate('bundle');
        return;
      }
      if (action === 'copy-file-list') {
        const text = getScopeFiles().map(file => file.path ?? file.abs_path).join('\n');
        copyToClipboard(text);
        return;
      }
      if (action === 'generate-prompt') {
        navigate('prompt');
        return;
      }
      if (action === 'open-diagram') {
        await openCurrentDiagram();
      }
    });
  });
}

async function openCurrentDiagram() {
  if (!hasCurrentScope()) return;
  const popup = window.open('', '_blank', 'noopener');
  try {
    const data = await api('POST', '/api/plan/mermaid', { candidate_index: state.selectedCandidate });
    const liveUrl = data.live_url;
    if (popup) popup.location = liveUrl;
    else window.open(liveUrl, '_blank', 'noopener');
  } catch (err) {
    if (popup) popup.close();
    toast(err.message);
  }
}

async function previewFile(path) {
  const data = await api('GET', `/api/file?path=${encodeURIComponent(path)}`);
  const lines = (data.content ?? '').split('\n');
  const numbered = lines.map((line, i) => `${String(i + 1).padStart(4)} | ${line}`).join('\n');
  showModal(data.path ?? path, numbered);
}

function renderIntentSummary(intent) {
  if (!intent) return '';
  const parts = [];
  if (intent.cid) parts.push(`CID ${intent.cid}`);
  if (intent.job_id) parts.push(`Job ${intent.job_id}`);
  if (intent.letter_number) parts.push(`Letter ${intent.letter_number}`);
  if (intent.raw_title) parts.push(intent.raw_title);
  return parts.join(' • ') || 'No explicit intent captured';
}

function showKnowledgeModal(title, content) {
  showModal(title, content || '(empty)');
}

const GUARDED_STEPS = {
  bundle: () => state.snapshot !== null,
  prompt: () => state.plan !== null,
  stats: () => state.snapshot !== null,
  search: () => state.snapshot !== null,
};

document.querySelectorAll('.step').forEach(el => {
  el.addEventListener('click', () => {
    const step = el.dataset.step;
    const guard = GUARDED_STEPS[step];
    if (guard && !guard()) {
      toast('Complete the previous step first');
      return;
    }
    navigate(step);
  });
});

function navigate(step) {
  state.step = step;
  document.querySelectorAll('.step').forEach(s =>
    s.classList.toggle('active', s.dataset.step === step)
  );
  render();
}

function render() {
  const el = document.getElementById('content');
  switch (state.step) {
    case 'snapshot': renderSnapshotStep(el); break;
    case 'bundle': renderBundleStep(el); break;
    case 'prompt': renderPromptStep(el); break;
    case 'stats': renderStatsPage(el); break;
    case 'search': renderSearchPage(el); break;
    default: renderSnapshotStep(el); break;
  }
}

async function renderSnapshotStep(el) {
  el.innerHTML = `
    ${renderPageHeader('Snapshots', 'Operational snapshot inventory and snapshot creation flow.', state.snapshot?.name ?? 'no active snapshot')}
    <div class="toolbar toolbar--tight">
      <button class="btn btn--primary" id="btn-new-snap">New snapshot</button>
      <button class="btn" id="btn-refresh-snaps">Refresh</button>
    </div>
    <div class="help-line">Base snapshot copies production scripts, procs, control, insert and docdef. Optional sources stay hidden until needed.</div>
    <div id="new-snap-form" hidden></div>
    <div id="snap-list" class="section"></div>
  `;

  document.getElementById('btn-new-snap').addEventListener('click', () => toggleNewSnapForm());
  document.getElementById('btn-refresh-snaps').addEventListener('click', () => {
    state.snapshots = null;
    loadSnapList();
  });
  await loadSnapList();
}

function countEnabledAdvancedSources() {
  const ids = ['ns-pdf', 'ns-incidents', 'ns-research', 'ns-related', 'ns-prox', 'ns-control', 'ns-insert'];
  return ids.reduce((sum, id) => sum + (document.getElementById(id)?.value.trim() ? 1 : 0), 0);
}

function updateAdvancedSummary() {
  const summary = document.getElementById('ns-advanced-summary');
  if (!summary) return;
  const count = countEnabledAdvancedSources();
  summary.textContent = count > 0 ? `${count} optional sources enabled` : 'No optional sources enabled';
}

function toggleNewSnapForm() {
  const form = document.getElementById('new-snap-form');
  if (!form.hidden) {
    form.hidden = true;
    return;
  }
  form.hidden = false;
  form.innerHTML = `
    <div class="surface surface--raised section">
      <div class="section-title">Create snapshot</div>
      <div class="field">
        <label>Snapshot name</label>
        <input id="ns-name" placeholder="e.g. wccu_20260323">
      </div>
      <div class="help-line">Base snapshot includes remote scripts, procs, controls, inserts and docdef. Use Advanced sources only for extra research material.</div>
      <button class="btn btn--sm" id="btn-toggle-advanced" type="button">Advanced sources</button>
      <span class="muted inline-note" id="ns-advanced-summary">No optional sources enabled</span>
      <div id="ns-advanced-panel" class="advanced-panel" hidden>
        <div class="advanced-grid">
          <div class="field">
            <label>Papyrus PDF</label>
            <input id="ns-pdf" placeholder="/path/to/Papyrus_DocExec_message_codes.pdf">
            <div class="field-help">Imports message codes into the snapshot knowledge base.</div>
          </div>
          <div class="field">
            <label>Incidents / histories folder</label>
            <input id="ns-incidents" placeholder="/path/to/incidents_or_histories">
            <div class="field-help">Imports prior investigation notes when available.</div>
          </div>
          <div class="field">
            <label>Research / logs folder</label>
            <input id="ns-research" placeholder="/path/to/research_or_logs">
            <div class="field-help">Copies logs or prior research into snapshot refs.</div>
          </div>
          <div class="field">
            <label>Related files folder</label>
            <input id="ns-related" placeholder="/path/to/related_files">
            <div class="field-help">Adds extra local context that is not on the Linux server.</div>
          </div>
          <div class="field">
            <label>Prox folder</label>
            <input id="ns-prox" placeholder="/path/to/prox">
            <div class="field-help">Copies local prox material into snapshot refs for operator review.</div>
          </div>
          <div class="field">
            <label>Optional control folder</label>
            <input id="ns-control" placeholder="/path/to/local_control">
            <div class="field-help">Adds extra control material that is not part of the base remote sync.</div>
          </div>
          <div class="field">
            <label>Optional insert folder</label>
            <input id="ns-insert" placeholder="/path/to/local_insert">
            <div class="field-help">Adds extra insert material for V1 operator review without changing the base snapshot flow.</div>
          </div>
        </div>
      </div>
      <div class="btn-row">
        <button class="btn btn--primary" id="btn-create-snap">Create & index</button>
        <button class="btn" id="btn-cancel-snap">Cancel</button>
      </div>
      <div id="ns-status"></div>
    </div>`;

  document.getElementById('btn-cancel-snap').addEventListener('click', () => { form.hidden = true; });
  document.getElementById('btn-toggle-advanced').addEventListener('click', () => {
    const panel = document.getElementById('ns-advanced-panel');
    panel.hidden = !panel.hidden;
  });
  ['ns-pdf', 'ns-incidents', 'ns-research', 'ns-related', 'ns-prox', 'ns-control', 'ns-insert'].forEach(id => {
    document.getElementById(id).addEventListener('input', updateAdvancedSummary);
  });
  updateAdvancedSummary();

  document.getElementById('btn-create-snap').addEventListener('click', async () => {
    const name = document.getElementById('ns-name').value.trim();
    if (!name) {
      toast('Enter a snapshot name');
      return;
    }

    const status = document.getElementById('ns-status');
    status.innerHTML = `
      <div class="progress-container">
        <div class="progress-bar"><div class="progress-fill" id="ns-progress-fill"></div></div>
        <div class="progress-label" id="ns-progress-label">Starting...</div>
      </div>`;
    const btn = document.getElementById('btn-create-snap');
    btn.disabled = true;

    const body = { name };
    const pdf = document.getElementById('ns-pdf').value.trim();
    const incidents = document.getElementById('ns-incidents').value.trim();
    const research = document.getElementById('ns-research').value.trim();
    const related = document.getElementById('ns-related').value.trim();
    const prox = document.getElementById('ns-prox').value.trim();
    const control = document.getElementById('ns-control').value.trim();
    const insert = document.getElementById('ns-insert').value.trim();
    if (pdf) body.pdf_path = pdf;
    if (incidents) body.incidents_path = incidents;
    if (research) body.research_path = research;
    if (related) body.related_path = related;
    if (prox) body.prox_path = prox;
    if (control) body.control_path = control;
    if (insert) body.insert_path = insert;

    try {
      const res = await fetch('/api/snapshot/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const text = await res.text().catch(() => res.statusText);
        throw new Error(`${res.status}: ${text}`);
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let finalResult = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let boundary;
        while ((boundary = buffer.indexOf('\n\n')) !== -1) {
          const chunk = buffer.slice(0, boundary).trim();
          buffer = buffer.slice(boundary + 2);
          if (!chunk.startsWith('data: ')) continue;
          const data = JSON.parse(chunk.slice(6));
          const pct = Math.round((data.step / data.total) * 100);
          const fill = document.getElementById('ns-progress-fill');
          const label = document.getElementById('ns-progress-label');
          if (fill) fill.style.width = `${pct}%`;
          if (label) label.textContent = `${data.label} (${pct}%)`;
          if (data.done) finalResult = data;
        }
      }

      if (finalResult) {
        const optional = (finalResult.optional_copy_results ?? []).filter(item => item.ok).map(item => item.label);
        let msg = `Snapshot "${escapeHtml(finalResult.name)}" created.`;
        msg += finalResult.scan_ok ? ' Indexed successfully.' : ` Indexing failed: ${escapeHtml(finalResult.scan_error ?? 'unknown')}`;
        if (finalResult.rsync_errors?.length) msg += ` ${finalResult.rsync_errors.length} remote sync error(s).`;
        if (optional.length) msg += ` Optional sources: ${escapeHtml(optional.join(', '))}.`;
        if (finalResult.path_win) {
          msg += `<br><a href="#" class="ws-open-link" data-winpath>Explorer: ${escapeHtml(finalResult.path_win)}</a>`;
        }
        status.innerHTML = `<div class="callout callout--info">${msg}</div>`;
        if (finalResult.path_win) {
          status.querySelector('[data-winpath]').addEventListener('click', e => {
            e.preventDefault();
            copyToClipboard(finalResult.path_win);
            toast('Path copied');
          });
        }
      }
      state.snapshots = null;
      await loadSnapList();
    } catch (err) {
      status.innerHTML = `<div class="inline-error">${escapeHtml(err.message)}</div>`;
    } finally {
      btn.disabled = false;
    }
  });
}

function renderSnapshotSummary(stats) {
  if (!stats) return '<span class="muted">No index summary</span>';
  const contents = stats.contents ?? {};
  return `
    <div class="snap-summary">
      <span>${contents.procs ?? 0} procs</span>
      <span>${contents.scripts ?? 0} scripts</span>
      <span>${contents.controls ?? 0} controls</span>
      <span>${contents.docdef ?? 0} docdef</span>
    </div>`;
}

async function loadSnapList() {
  const list = document.getElementById('snap-list');
  if (!state.snapshots) {
    setLoading(list, true);
    try {
      state.snapshots = await api('GET', '/api/snapshots');
    } catch (err) {
      list.innerHTML = `<div class="inline-error">${escapeHtml(err.message)}</div>`;
      return;
    }
  }
  if (state.snapshots.length === 0) {
    list.innerHTML = renderEmptyState('No snapshots found.');
    return;
  }

  list.innerHTML = `
    <div class="ops-table">
      <div class="ops-table__head ops-table__head--snapshots">
        <span>Snapshot</span>
        <span>Captured</span>
        <span>Ready</span>
        <span>Freshness</span>
        <span>Contents summary</span>
        <span>Incidents</span>
        <span>Actions</span>
      </div>
      ${state.snapshots.map((snap, idx) => {
        const selected = state.snapshot?.path === snap.path;
        return `
          <div class="ops-table__row ops-table__row--snapshots${selected ? ' ops-table__row--selected' : ''}" data-snap-row="${idx}">
            <div class="ops-cell ops-cell--primary">
              <div class="ops-title">${escapeHtml(snap.name)}</div>
              <div class="ops-sub">${escapeHtml(snap.path)}</div>
            </div>
            <div class="ops-cell">${escapeHtml(snap.date ?? 'unknown')}</div>
            <div class="ops-cell"><span class="status-dot ${snap.has_db ? 'is-ready' : 'is-warn'}"></span>${snap.has_db ? 'Ready' : 'Needs scan'}</div>
            <div class="ops-cell">${escapeHtml(formatRelativeTime(snap.date))}</div>
            <div class="ops-cell">${renderSnapshotSummary(snap.stats)}</div>
            <div class="ops-cell">${snap.stats?.incidents ?? '-'}</div>
            <div class="ops-cell ops-cell--actions">
              <button class="btn btn--sm" data-action="select-snap" data-idx="${idx}">Use</button>
              <button class="btn btn--sm btn--danger btn--danger-subtle" data-action="delete-snap" data-idx="${idx}">Delete</button>
            </div>
          </div>`;
      }).join('')}
    </div>`;
  bindSnapEvents();
}

function bindSnapEvents() {
  document.querySelectorAll('[data-action="select-snap"]').forEach(button => {
    button.addEventListener('click', async e => {
      e.stopPropagation();
      const snap = state.snapshots[Number(button.dataset.idx)];
      if (!snap.has_db) {
        toast('Snapshot needs indexing first');
        return;
      }
      button.disabled = true;
      try {
        await api('POST', `/api/snapshot/select?path=${encodeURIComponent(snap.path)}`);
        state.snapshot = snap;
        state.plan = null;
        state.prompt = null;
        state.candidates = [];
        state.selectedCandidate = 0;
        state.stats = null;
        state.searchResults = null;
        document.getElementById('current-snap').textContent = snap.name;
        const sidebarSnap = document.getElementById('current-snap-sidebar');
        if (sidebarSnap) sidebarSnap.textContent = snap.name;
        navigate('bundle');
      } catch (err) {
        toast(err.message);
      } finally {
        button.disabled = false;
      }
    });
  });
  document.querySelectorAll('[data-action="delete-snap"]').forEach(button => {
    button.addEventListener('click', e => {
      e.stopPropagation();
      const snap = state.snapshots[Number(button.dataset.idx)];
      showDeleteConfirm(snap);
    });
  });
}

function showDeleteConfirm(snap) {
  const modal = document.getElementById('modal');
  const title = document.getElementById('modal-title');
  const body = document.getElementById('modal-body');
  title.textContent = 'Delete Snapshot';
  body.innerHTML = `
    <p>Delete <strong>${escapeHtml(snap.name)}</strong>?</p>
    <div class="callout callout--warn" style="margin-top:12px">This removes the snapshot directory and its indexed data.</div>
    <div class="btn-row" style="margin-top:16px">
      <button class="btn btn--danger" id="btn-confirm-delete">Delete</button>
      <button class="btn" id="btn-cancel-delete">Cancel</button>
    </div>
    <div id="delete-status"></div>`;
  modal.hidden = false;
  document.getElementById('btn-cancel-delete').addEventListener('click', hideModal);
  document.getElementById('btn-confirm-delete').addEventListener('click', async () => {
    const btn = document.getElementById('btn-confirm-delete');
    const status = document.getElementById('delete-status');
    btn.disabled = true;
    status.innerHTML = '<div class="loading">Deleting...</div>';
    try {
      await api('DELETE', `/api/snapshot?path=${encodeURIComponent(snap.path)}`);
      hideModal();
      toast(`Snapshot "${snap.name}" deleted`);
      state.snapshots = null;
      if (state.snapshot?.path === snap.path) {
        state.snapshot = null;
        state.plan = null;
        state.candidates = [];
        state.stats = null;
        document.getElementById('current-snap').textContent = 'No snapshot selected';
        const sidebarSnap = document.getElementById('current-snap-sidebar');
        if (sidebarSnap) sidebarSnap.textContent = 'none';
      }
      await loadSnapList();
    } catch (err) {
      status.innerHTML = `<div class="inline-error">${escapeHtml(err.message)}</div>`;
      btn.disabled = false;
    }
  });
}

function renderBundleStep(el) {
  el.innerHTML = `
    ${renderPageHeader('Scope Builder', 'Find the right candidate and assemble a focused working scope.', state.snapshot?.name ?? 'no snapshot')}
    <section class="section">
      <div class="surface surface--raised">
        <div class="section-title">Find scope</div>
        <div class="field"><label>Title</label><input id="f-title" placeholder="Incident title or change request"></div>
        <div class="field"><label>CID</label><input id="f-cid" placeholder="Case ID"></div>
        <div class="field"><label>Job ID</label><input id="f-jobid" placeholder="Job name or ID"></div>
        <div class="field"><label>Candidate limit</label><input id="f-limit" type="number" value="5" min="1" max="20"></div>
        <div class="btn-row">
          <button class="btn btn--primary" id="btn-plan">Find scope</button>
        </div>
        <div class="help-line">Use CID or Job ID for a tighter scope. After selection, open files, create a workspace, generate a prompt, or open the diagram from the Current scope action row.</div>
      </div>
    </section>
    <div id="plan-results"></div>`;

  if (state.plan) renderPlanResults();

  document.getElementById('btn-plan').addEventListener('click', async () => {
    const body = { limit: Number(document.getElementById('f-limit').value) || 5 };
    const title = document.getElementById('f-title').value.trim();
    const cid = document.getElementById('f-cid').value.trim();
    const jobid = document.getElementById('f-jobid').value.trim();
    if (title) body.title = title;
    if (cid) body.cid = cid;
    if (jobid) body.jobid = jobid;
    const results = document.getElementById('plan-results');
    setLoading(results, true);
    try {
      state.plan = await api('POST', '/api/plan', body);
      state.candidates = state.plan.all_candidates ?? [];
      state.selectedCandidate = 0;
      state.prompt = null;
      renderPlanResults();
    } catch (err) {
      results.innerHTML = `<div class="inline-error">${escapeHtml(err.message)}</div>`;
    }
  });
}

function groupFilesByKind(files) {
  const groups = {};
  files.forEach(file => {
    const kind = normalizeKind(file.kind);
    (groups[kind] ??= []).push(file);
  });
  return groups;
}

function renderWorkspaceComposer(target) {
  target.hidden = false;
  target.innerHTML = `
    <div class="section-title">Create workspace</div>
    <div class="surface">
      <div class="field"><label>Ticket ID</label><input id="ws-ticket" placeholder="e.g. INC0123456"></div>
      <div class="field"><label>Title</label><input id="ws-title" placeholder="Investigation title"></div>
      <div class="field">
        <label>Copy mode</label>
        <div class="radio-group" id="ws-mode">
          <label><input type="radio" name="ws-mode" value="snap" checked><span>From snapshot</span></label>
          <label><input type="radio" name="ws-mode" value="ssh"><span>From RHS</span></label>
        </div>
      </div>
      <div class="btn-row">
        <button class="btn btn--primary" id="btn-ws-create">Create</button>
        <button class="btn" id="btn-ws-cancel">Cancel</button>
      </div>
      <div id="ws-status"></div>
    </div>`;

  document.getElementById('btn-ws-cancel').addEventListener('click', () => {
    target.hidden = true;
    state.openWorkspaceComposer = false;
  });
  document.getElementById('btn-ws-create').addEventListener('click', async () => {
    const ticket = document.getElementById('ws-ticket').value.trim();
    const title = document.getElementById('ws-title').value.trim();
    const mode = document.querySelector('input[name="ws-mode"]:checked')?.value ?? 'snap';
    const btn = document.getElementById('btn-ws-create');
    const status = document.getElementById('ws-status');
    btn.disabled = true;
    status.innerHTML = `
      <div class="progress-container">
        <div class="progress-bar"><div class="progress-fill" id="ws-progress-fill"></div></div>
        <div class="progress-label" id="ws-progress-label">Starting...</div>
      </div>`;
    try {
      const body = { mode, candidate_index: state.selectedCandidate };
      if (ticket) body.ticket = ticket;
      if (title) body.title = title;
      const res = await fetch('/api/workspace/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const text = await res.text().catch(() => res.statusText);
        throw new Error(`${res.status}: ${text}`);
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let finalResult = null;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let boundary;
        while ((boundary = buffer.indexOf('\n\n')) !== -1) {
          const chunk = buffer.slice(0, boundary).trim();
          buffer = buffer.slice(boundary + 2);
          if (!chunk.startsWith('data: ')) continue;
          const data = JSON.parse(chunk.slice(6));
          const pct = Math.round((data.step / data.total) * 100);
          const fill = document.getElementById('ws-progress-fill');
          const label = document.getElementById('ws-progress-label');
          if (fill) fill.style.width = `${pct}%`;
          if (label) label.textContent = `${data.label} (${pct}%)`;
          if (data.done) finalResult = data;
        }
      }
      if (finalResult) {
        let msg = `Workspace created: <code>${escapeHtml(finalResult.workspace)}</code>`;
        if (finalResult.workspace_win) {
          msg += `<br><a href="#" class="ws-open-link" data-winpath>Open in Explorer</a>`;
        }
        msg += `<br>${finalResult.files_copied} file(s) copied.`;
        msg += `<br>Pull script: <code>${escapeHtml(finalResult.pull_script)}</code>`;
        status.innerHTML = `<div class="callout callout--info">${msg}</div>`;
        if (finalResult.workspace_win) {
          status.querySelector('[data-winpath]').addEventListener('click', e => {
            e.preventDefault();
            copyToClipboard(finalResult.workspace_win);
            toast('Path copied');
          });
        }
      }
    } catch (err) {
      status.innerHTML = `<div class="inline-error">${escapeHtml(err.message)}</div>`;
    } finally {
      btn.disabled = false;
    }
  });
}

async function renderPlanResults() {
  const results = document.getElementById('plan-results');
  if (!state.plan) return;
  const candidate = getSelectedCandidate();
  const grouped = groupFilesByKind(candidate?.files ?? []);
  let html = `
    <section class="section">
      <div class="surface">
        <div class="section-title">Intent</div>
        <div class="help-line">${escapeHtml(renderIntentSummary(state.plan.intent))}</div>
      </div>
    </section>`;

  if (state.candidates.length > 0) {
    html += `
      <section class="section">
        <div class="section-title">Candidates</div>
        <div class="candidate-grid">
          ${state.candidates.map((cand, index) => `
            <button class="candidate-card${index === state.selectedCandidate ? ' is-selected' : ''}" data-action="select-cand" data-idx="${index}">
              <span class="candidate-card__title">${escapeHtml(cand.display_name ?? cand.name ?? cand.key)}</span>
              <span class="candidate-card__sub">${escapeHtml(cand.key ?? '')}</span>
              <span class="candidate-card__meta">score ${cand.score ?? '-'} • ${cand.files?.length ?? 0} files</span>
            </button>
          `).join('')}
        </div>
      </section>`;
  }

  html += renderCurrentScopeBlock({ compact: true, title: 'Selected scope' });

  if (candidate?.files?.length) {
    html += `
      <section class="section" id="scope-files-panel">
        <div class="section-title">Scope files</div>
        <div class="file-list" data-title="Scope file explorer">
          ${Object.entries(grouped).map(([kind, files]) => `
            <div class="file-group-header">${escapeHtml(kindLabel(kind))} (${files.length})</div>
            ${files.map(file => `
              <div class="file-item" data-action="preview-file" data-path="${escapeHtml(file.path ?? file.abs_path)}">
                <span class="file-kind">${escapeHtml(kindLabel(file.kind))}</span>
                <span>${escapeHtml(file.path ?? file.abs_path)}</span>
              </div>
            `).join('')}
          `).join('')}
        </div>
      </section>
      <section class="section" id="workspace-panel">
        <div id="workspace-output" ${state.openWorkspaceComposer ? '' : 'hidden'}></div>
      </section>`;
  }

  results.innerHTML = html;
  bindScopeActions(results);
  bindBundleEvents();
  if (state.openWorkspaceComposer) {
    const target = document.getElementById('workspace-output');
    if (target) renderWorkspaceComposer(target);
  }
  focusBundlePanel();
}

function focusBundlePanel() {
  if (!state.bundleFocus) return;
  const panelId = state.bundleFocus === 'workspace' ? 'workspace-panel' : 'scope-files-panel';
  const panel = document.getElementById(panelId);
  state.bundleFocus = null;
  if (panel) {
    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

function bindBundleEvents() {
  document.querySelectorAll('[data-action="select-cand"]').forEach(button => {
    button.addEventListener('click', () => {
      state.selectedCandidate = Number(button.dataset.idx);
      state.prompt = null;
      state.searchResults = null;
      renderPlanResults();
    });
  });
  document.querySelectorAll('[data-action="preview-file"]').forEach(item => {
    item.addEventListener('click', async () => {
      try {
        await previewFile(item.dataset.path);
      } catch (err) {
        toast(err.message);
      }
    });
  });
}

async function renderStatsPage(el) {
  el.innerHTML = `
    ${renderPageHeader('Overview', 'Operator summary for the active snapshot and current scope.', state.snapshot?.name ?? 'no snapshot')}
    <div id="stats-body"></div>`;
  const body = document.getElementById('stats-body');
  setLoading(body, true);
  try {
    state.stats = await api('GET', '/api/stats');
    const stats = state.stats;
    const entry = getScopeEntryPoints();
    const contents = stats.contents ?? {};
    const incidents = stats.recent_incidents ?? [];
    const caseCards = stats.recent_case_cards ?? [];
    body.innerHTML = `
      ${renderCurrentScopeBlock({ title: 'Current scope' })}
      <section class="section">
        <div class="layout-grid layout-grid--split">
          <div class="surface">
            <div class="section-title">Entry points</div>
            ${entry.primaryProc ? `
              <div class="overview-list">
                <div><strong>Primary proc</strong><span>${escapeHtml(entry.primaryProc)}</span></div>
                <div><strong>RUNS scripts</strong><span>${entry.runsScripts.length ? escapeHtml(entry.runsScripts.map(item => item.path.split('/').pop()).join(', ')) : 'none in scope'}</span></div>
                <div><strong>Controls / docdef</strong><span>${escapeHtml([...entry.controls.map(item => item.path.split('/').pop()), ...entry.docdefs.map(item => item.path.split('/').pop())].slice(0, 4).join(', ') || 'none in scope')}</span></div>
                <div><strong>Open first</strong><span>${escapeHtml(entry.readOrder.join(' → ') || 'No cheap read order available')}</span></div>
              </div>
            ` : renderEmptyState('Select a scope to expose entry points and reading order.', 'No scope details')}
          </div>
          <div class="surface">
            <div class="section-title">Signals and incidents</div>
            <div class="overview-list">
              <div><strong>Incident history</strong><span>${stats.incidents ? `${stats.incidents} incidents indexed` : 'incident journal empty'}</span></div>
              <div><strong>Case cards</strong><span>${stats.case_cards ? `${stats.case_cards} knowledge entries` : 'no case cards yet'}</span></div>
              <div><strong>Recent incidents</strong><span>${incidents.length ? escapeHtml(incidents.slice(0, 3).map(item => PathLabel(item.log_path)).join(', ')) : 'none'}</span></div>
            </div>
            ${caseCards.length ? `
              <div class="section-title section-title--subtle" style="margin-top:16px">Recent case cards</div>
              <div class="mini-list">
                ${caseCards.map((card, idx) => `
                  <button class="mini-list__item" data-case-card="${idx}">
                    <span class="mini-list__title">${escapeHtml(card.title || PathLabel(card.source_path) || `Case card ${card.id}`)}</span>
                    <span class="mini-list__meta">${escapeHtml(card.source_path || 'history import')}</span>
                  </button>
                `).join('')}
              </div>
            ` : '<div class="help-line">No recent case cards to preview.</div>'}
          </div>
        </div>
      </section>
      <section class="section">
        <div class="surface">
          <div class="section-title">Snapshot contents</div>
          <div class="stat-grid stat-grid--dense">
            ${[
              ['procs', contents.procs],
              ['scripts', contents.scripts],
              ['controls', contents.controls],
              ['inserts', contents.inserts],
              ['docdef', contents.docdef],
              ['logs', contents.logs],
              ['refs', contents.refs],
            ].map(([label, value]) => `
              <div class="stat stat--compact">
                <div class="stat-label">${escapeHtml(label)}</div>
                <div class="stat-value">${value ?? 0}</div>
              </div>
            `).join('')}
          </div>
        </div>
      </section>
      <section class="section">
        <details class="diagnostics">
          <summary>Diagnostics</summary>
          <div class="diagnostics-grid">
            ${[
              ['Artifacts', stats.artifacts],
              ['Nodes', stats.nodes],
              ['Edges', stats.edges],
              ['Case cards', stats.case_cards],
              ['Message codes', stats.message_codes],
            ].map(([label, value]) => `
              <div class="meta-row">
                <span class="meta-label">${escapeHtml(label)}</span>
                <span class="meta-value">${value ?? '-'}</span>
              </div>
            `).join('')}
          </div>
        </details>
      </section>`;
    bindScopeActions(body);
    body.querySelectorAll('[data-case-card]').forEach(button => {
      button.addEventListener('click', () => {
        const card = caseCards[Number(button.dataset.caseCard)];
        showKnowledgeModal(
          card.title || `Case card ${card.id}`,
          [
            card.source_path ? `Source: ${card.source_path}` : null,
            card.updated_at || card.created_at ? `Updated: ${card.updated_at || card.created_at}` : null,
            '',
            card.root_cause ? `Root cause: ${card.root_cause}` : null,
            card.fix_summary ? `Fix summary: ${card.fix_summary}` : null,
          ].filter(Boolean).join('\n')
        );
      });
    });
  } catch (err) {
    body.innerHTML = `<div class="inline-error">${escapeHtml(err.message)}</div>`;
  }
}

function PathLabel(path) {
  if (!path) return 'unknown';
  const parts = String(path).split(/[\\/]/);
  return parts[parts.length - 1];
}

function renderSearchPage(el) {
  const currentScopeAvailable = hasCurrentScope();
  el.innerHTML = `
    ${renderPageHeader('Search', 'Search the indexed snapshot or narrow the query to the current scope.', state.snapshot?.name ?? 'no snapshot')}
    ${renderCurrentScopeBlock({ compact: true, title: 'Current scope summary' })}
    <section class="section">
      <div class="surface surface--raised">
        <div class="section-title">Search controls</div>
        <div class="search-controls">
          <div class="field field--grow">
            <label>Query</label>
            <input id="search-input" placeholder="Search files, content, controls, docdef..." autofocus>
          </div>
          <div class="field">
            <label>Mode</label>
            <div class="radio-group" id="search-mode">
              <label><input type="radio" name="search-mode" value="content" ${state.searchMode === 'content' ? 'checked' : ''}><span>Content</span></label>
              <label><input type="radio" name="search-mode" value="path" ${state.searchMode === 'path' ? 'checked' : ''}><span>Path</span></label>
            </div>
          </div>
          <div class="field">
            <label>Scope</label>
            <div class="radio-group" id="search-scope">
              <label><input type="radio" name="search-scope" value="snapshot" ${state.searchScope === 'snapshot' ? 'checked' : ''}><span>Whole snapshot</span></label>
              <label><input type="radio" name="search-scope" value="current" ${state.searchScope === 'current' ? 'checked' : ''} ${currentScopeAvailable ? '' : 'disabled'}><span>Current scope</span></label>
            </div>
          </div>
          <div class="field">
            <label>Kind</label>
            <select id="search-kind">
              ${['all', 'procs', 'scripts', 'controls', 'inserts', 'docdef', 'logs', 'refs'].map(kind => `
                <option value="${kind}" ${state.searchKind === kind ? 'selected' : ''}>${escapeHtml(kindLabel(kind))}</option>
              `).join('')}
            </select>
          </div>
          <div class="field">
            <label>Results</label>
            <div class="radio-group" id="search-space">
              <label><input type="radio" name="search-space" value="all" ${state.searchSpace === 'all' ? 'checked' : ''}><span>All</span></label>
              <label><input type="radio" name="search-space" value="files" ${state.searchSpace === 'files' ? 'checked' : ''}><span>Files</span></label>
              <label><input type="radio" name="search-space" value="knowledge" ${state.searchSpace === 'knowledge' ? 'checked' : ''}><span>Knowledge</span></label>
            </div>
          </div>
        </div>
        <div class="help-line">Use Files for artifact lookup, Knowledge for message codes and case cards, or All to see both in separate result groups. Knowledge is snapshot-wide, not scope-limited.</div>
      </div>
    </section>
    <div id="search-results">${renderEmptyState('Run a query to inspect paths and content snippets.')}</div>`;

  bindScopeActions(el);
  const input = document.getElementById('search-input');
  let debounce = null;
  input.addEventListener('input', () => {
    clearTimeout(debounce);
    debounce = setTimeout(() => performSearch(input.value.trim()), 250);
  });
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      clearTimeout(debounce);
      performSearch(input.value.trim());
    }
  });
  document.getElementById('search-mode').addEventListener('change', e => {
    if (e.target.name === 'search-mode') state.searchMode = e.target.value;
  });
  document.getElementById('search-scope').addEventListener('change', e => {
    if (e.target.name === 'search-scope') state.searchScope = e.target.value;
  });
  document.getElementById('search-kind').addEventListener('change', e => {
    state.searchKind = e.target.value;
  });
  document.getElementById('search-space').addEventListener('change', e => {
    if (e.target.name === 'search-space') state.searchSpace = e.target.value;
  });
}

async function performSearch(query) {
  const results = document.getElementById('search-results');
  if (!query) {
    results.innerHTML = renderEmptyState('Run a query to inspect paths and content snippets.');
    return;
  }
  if (state.searchScope === 'current' && !hasCurrentScope()) {
    toast('Current scope is not available yet');
    state.searchScope = 'snapshot';
    const snapshotRadio = document.querySelector('input[name="search-scope"][value="snapshot"]');
    if (snapshotRadio) snapshotRadio.checked = true;
  }
  setLoading(results, true);
  try {
    const params = new URLSearchParams({
      q: query,
      limit: '20',
      mode: state.searchMode,
      scope: state.searchScope,
      kind: state.searchKind,
      space: state.searchSpace,
      candidate_index: String(state.selectedCandidate),
    });
    const data = await api('GET', `/api/search?${params.toString()}`);
    state.searchResults = data;
    if (data.length === 0) {
      results.innerHTML = renderEmptyState('No results found.');
      return;
    }
    const knowledgeHits = data.filter(hit => hit.match_type === 'knowledge');
    const fileHits = data.filter(hit => hit.match_type !== 'knowledge');
    const renderHit = (hit, idx) => `
      <div class="search-hit">
        <div class="search-hit-path">${escapeHtml(hit.path)}</div>
        <div><span class="file-kind">${escapeHtml(kindLabel(hit.kind))}</span></div>
        <div class="search-hit-match">${escapeHtml(hit.match_type ?? state.searchMode)}</div>
        <div class="search-hit-snippet">${hit.snippet ? highlightSnippet(hit.snippet, query) : '<span class="muted">No snippet</span>'}</div>
        <div class="ops-actions">
          <button class="btn btn--sm" data-search-action="preview" data-idx="${idx}">Preview</button>
          <button class="btn btn--sm" data-search-action="copy" data-path="${escapeHtml(hit.path)}">Copy path</button>
          <button class="btn btn--sm" data-search-action="scope" data-path="${escapeHtml(hit.path)}" ${hasCurrentScope() && hit.match_type !== 'knowledge' ? '' : 'disabled'}>Open in scope</button>
        </div>
      </div>`;
    const renderSection = (title, rows) => rows.length ? `
      <div class="search-results search-results--section" data-title="${escapeHtml(title)}">
        <div class="search-table-head">
          <span>Path</span>
          <span>Kind</span>
          <span>Match</span>
          <span>Preview</span>
          <span>Actions</span>
        </div>
        ${rows.map(renderHit).join('')}
      </div>` : '';
    results.innerHTML = `
      ${renderSection(`Knowledge (${knowledgeHits.length})`, knowledgeHits)}
      ${renderSection(`Files (${fileHits.length})`, fileHits)}`;
    bindSearchEvents();
  } catch (err) {
    results.innerHTML = `<div class="inline-error">${escapeHtml(err.message)}</div>`;
  }
}

function highlightSnippet(snippet, query) {
  const escaped = escapeHtml(snippet);
  const pattern = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return escaped.replace(new RegExp(`(${pattern})`, 'gi'), '<mark>$1</mark>');
}

function bindSearchEvents() {
  document.querySelectorAll('[data-search-action="preview"]').forEach(button => {
    button.addEventListener('click', async () => {
      try {
        const hit = state.searchResults?.[Number(button.dataset.idx)];
        if (hit?.preview_content) {
          showKnowledgeModal(hit.preview_title || hit.path, hit.preview_content);
          return;
        }
        await previewFile(hit?.path ?? '');
      } catch (err) {
        toast(err.message);
      }
    });
  });
  document.querySelectorAll('[data-search-action="copy"]').forEach(button => {
    button.addEventListener('click', () => copyToClipboard(button.dataset.path));
  });
  document.querySelectorAll('[data-search-action="scope"]').forEach(button => {
    button.addEventListener('click', () => navigate('bundle'));
  });
}

function renderPromptInputLabel() {
  return state.promptScenario === 'incident'
    ? 'Error text / log / ticket text'
    : 'Change request description';
}

function renderPromptPageBody() {
  const candidate = getSelectedCandidate();
  if (!candidate) {
    return renderEmptyState('Build a current scope first so prompt generation can use the selected candidate and file set.', 'No current scope');
  }
  return `
    ${renderCurrentScopeBlock({ compact: true, title: 'Current scope summary' })}
    <section class="section">
      <div class="surface surface--raised">
        <div class="section-title">Generate prompt</div>
        <div class="field">
          <label>Scenario</label>
          <div class="radio-group" id="prompt-scenario">
            <label><input type="radio" name="prompt-scenario" value="incident" ${state.promptScenario === 'incident' ? 'checked' : ''}><span>Incident analysis</span></label>
            <label><input type="radio" name="prompt-scenario" value="change_request" ${state.promptScenario === 'change_request' ? 'checked' : ''}><span>Change request analysis</span></label>
          </div>
        </div>
        <div class="field">
          <label>${renderPromptInputLabel()}</label>
          <textarea id="prompt-input" placeholder="${state.promptScenario === 'incident' ? 'Paste error text, log excerpt, or ticket details...' : 'Describe the requested change, constraints, and expected outcome...'}"></textarea>
        </div>
        <div class="layout-grid layout-grid--split">
          <div class="field">
            <label>Language</label>
            <div class="lang-toggle" id="lang-toggle">
              <button class="${state.lang === 'en' ? 'active' : ''}" data-lang="en">EN</button>
              <button class="${state.lang === 'ru' ? 'active' : ''}" data-lang="ru">RU</button>
            </div>
          </div>
          <div class="field">
            <label>Options</label>
            <label class="checkbox-row"><input type="checkbox" id="prompt-include-diagram" checked><span>Include diagram</span></label>
          </div>
        </div>
        <div class="btn-row">
          <button class="btn btn--primary" id="btn-prompt-generate">Generate prompt</button>
          <button class="btn" id="btn-prompt-save">Save prompt</button>
        </div>
        <div class="help-line">The prompt is built from the current scope, not from a separate candidate picker.</div>
      </div>
    </section>
    <div id="prompt-output-section">${state.prompt ? renderPromptOutputMarkup() : ''}</div>`;
}

function renderPromptStep(el) {
  el.innerHTML = `
    ${renderPageHeader('Prompt', 'External-LLM handoff from the current scope.', getSelectedCandidate()?.display_name ?? state.snapshot?.name ?? 'no scope')}
    ${renderPromptPageBody()}`;

  bindScopeActions(el);
  if (!getSelectedCandidate()) return;

  document.getElementById('prompt-scenario').addEventListener('change', e => {
    if (e.target.name === 'prompt-scenario') {
      state.promptScenario = e.target.value;
      renderPromptStep(el);
    }
  });
  document.getElementById('lang-toggle').addEventListener('click', e => {
    const lang = e.target.dataset?.lang;
    if (!lang) return;
    state.lang = lang;
    renderPromptStep(el);
  });
  document.getElementById('btn-prompt-generate').addEventListener('click', () => requestPrompt({ savePrompt: false }));
  document.getElementById('btn-prompt-save').addEventListener('click', () => requestPrompt({ savePrompt: true }));
  bindPromptOutputEvents();
}

async function requestPrompt({ savePrompt }) {
  const section = document.getElementById('prompt-output-section');
  setLoading(section, true);
  try {
    state.prompt = await api('POST', '/api/prompt', {
      scenario: state.promptScenario,
      prompt_input: document.getElementById('prompt-input').value.trim(),
      include_diagram: document.getElementById('prompt-include-diagram').checked,
      candidate_index: state.selectedCandidate,
      lang: state.lang,
      save_prompt: savePrompt,
    });
    section.innerHTML = renderPromptOutputMarkup();
    bindPromptOutputEvents();
  } catch (err) {
    section.innerHTML = `<div class="inline-error">${escapeHtml(err.message)}</div>`;
  }
}

function renderPromptOutputMarkup() {
  if (!state.prompt) return '';
  return `
    <section class="section surface surface--raised">
      <div class="section-title">Generated prompt</div>
      <div class="pill-row">
        <span class="scope-pill">${escapeHtml(state.prompt.scenario ?? state.promptScenario)}</span>
        <span class="scope-pill">${escapeHtml(state.prompt.impl_mode ?? 'prompt')}</span>
        <span class="scope-pill">${state.prompt.mermaid_included ? 'diagram included' : 'diagram omitted'}</span>
      </div>
      ${state.prompt.saved_path ? `<div class="help-line">Saved: ${escapeHtml(state.prompt.saved_path)}</div>` : ''}
      <pre class="prompt-output">${escapeHtml(state.prompt.prompt_text)}</pre>
      <div class="btn-row">
        <button class="btn btn--primary btn--sm" data-action="copy-prompt">Copy prompt</button>
        <button class="btn btn--sm" data-action="save-prompt-again">Save prompt</button>
      </div>
    </section>`;
}

function bindPromptOutputEvents() {
  document.querySelector('[data-action="copy-prompt"]')?.addEventListener('click', () => {
    copyToClipboard(state.prompt?.prompt_text ?? '');
  });
  document.querySelector('[data-action="save-prompt-again"]')?.addEventListener('click', () => {
    requestPrompt({ savePrompt: true });
  });
}

document.getElementById('modal-close').addEventListener('click', hideModal);
document.querySelector('.modal-backdrop').addEventListener('click', hideModal);
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') hideModal();
});

render();
document.getElementById('current-snap').textContent = 'No snapshot selected';
const sidebarSnap = document.getElementById('current-snap-sidebar');
if (sidebarSnap) sidebarSnap.textContent = 'none';
