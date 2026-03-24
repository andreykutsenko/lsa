/* LSA Web UI — Single-page application */

const state = {
  step: 'snapshot',
  snapshot: null,
  snapshots: null,
  plan: null,
  candidates: [],
  selectedCandidate: 0,
  prompt: null,
  lang: 'en',
  stats: null,
  searchResults: null,
  loading: false,
};

/* ── Mermaid setup ────────────────────────────────────── */

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

/* ── API helper ───────────────────────────────────────── */

async function api(method, path, body) {
  const opts = {
    method,
    headers: {},
  };
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

/* ── Utilities ────────────────────────────────────────── */

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
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

let mermaidCounter = 0;
async function renderMermaid(code, container) {
  mermaidCounter += 1;
  const id = `mermaid-svg-${mermaidCounter}`;
  try {
    const { svg } = await mermaid.render(id, code);
    container.innerHTML = svg;
  } catch {
    container.innerHTML = `<span class="inline-error">Failed to render diagram</span>`;
  }
}

function setLoading(el, on) {
  if (on) {
    el.innerHTML = '<div class="loading">Loading...</div>';
  }
}

/* ── Navigation ───────────────────────────────────────── */

const GUARDED_STEPS = {
  bundle: () => state.snapshot !== null,
  prompt: () => state.plan !== null,
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

/* ── Router ───────────────────────────────────────────── */

function render() {
  const el = document.getElementById('content');
  switch (state.step) {
    case 'snapshot': renderSnapshotStep(el); break;
    case 'bundle':   renderBundleStep(el);   break;
    case 'prompt':   renderPromptStep(el);   break;
    case 'stats':    renderStatsPage(el);    break;
    case 'search':   renderSearchPage(el);   break;
  }
}

/* ── Step 1: Snapshot ─────────────────────────────────── */

async function renderSnapshotStep(el) {
  el.innerHTML = `
    <h2 class="page-title">Snapshots</h2>
    <p class="page-subtitle">Select an indexed snapshot or create a new one from production.</p>
    <div class="btn-row" style="margin-bottom:20px">
      <button class="btn btn--primary" id="btn-new-snap">New Snapshot</button>
      <button class="btn" id="btn-refresh-snaps">Refresh</button>
    </div>
    <div id="new-snap-form" hidden></div>
    <div id="snap-list"></div>`;

  document.getElementById('btn-new-snap').addEventListener('click', () => toggleNewSnapForm());
  document.getElementById('btn-refresh-snaps').addEventListener('click', () => {
    state.snapshots = null;
    loadSnapList();
  });

  await loadSnapList();
}

function toggleNewSnapForm() {
  const form = document.getElementById('new-snap-form');
  if (!form.hidden) { form.hidden = true; return; }
  form.hidden = false;
  form.innerHTML = `
    <div class="card" style="margin-bottom:20px">
      <div class="card-title">Create New Snapshot</div>
      <div class="card-sub">Sync directories from production server via rsync, then index.</div>
      <div class="field"><label>Snapshot name</label><input id="ns-name" placeholder="e.g. wccu_20260323"></div>
      <div class="btn-row">
        <button class="btn btn--primary" id="btn-create-snap">Create & Index</button>
        <button class="btn" id="btn-cancel-snap">Cancel</button>
      </div>
      <div id="ns-status"></div>
    </div>`;

  document.getElementById('btn-cancel-snap').addEventListener('click', () => { form.hidden = true; });
  document.getElementById('btn-create-snap').addEventListener('click', async () => {
    const name = document.getElementById('ns-name').value.trim();
    if (!name) { toast('Enter a snapshot name'); return; }

    const status = document.getElementById('ns-status');
    status.innerHTML = `
      <div class="progress-container">
        <div class="progress-bar"><div class="progress-fill" id="ns-progress-fill"></div></div>
        <div class="progress-label" id="ns-progress-label">Starting...</div>
      </div>`;
    const btn = document.getElementById('btn-create-snap');
    btn.disabled = true;

    try {
      const res = await fetch('/api/snapshot/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
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
        let msg = `Snapshot "${escapeHtml(finalResult.name)}" created.`;
        if (finalResult.rsync_errors?.length) {
          msg += ` ${finalResult.rsync_errors.length} dir(s) had errors.`;
        }
        msg += finalResult.scan_ok ? ' Indexed successfully.' : ` Indexing failed: ${escapeHtml(finalResult.scan_error ?? 'unknown')}`;
        if (finalResult.path_win) {
          msg += `<br><a href="#" class="ws-open-link" data-winpath>Explorer: ${escapeHtml(finalResult.path_win)}</a>`;
        }
        status.innerHTML = `<div style="margin-top:12px;color:${finalResult.scan_ok ? 'var(--ok)' : 'var(--warn)'}">${msg}</div>`;
        if (finalResult.path_win) {
          status.querySelector('[data-winpath]').addEventListener('click', (e) => {
            e.preventDefault();
            copyToClipboard(finalResult.path_win);
            toast('Path copied — paste in Explorer address bar');
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
    list.innerHTML = '<div class="muted" style="padding:16px 0">No snapshots found.</div>';
    return;
  }

  list.innerHTML = state.snapshots.map((snap, i) => {
    const selected = state.snapshot?.path === snap.path;
    const status = snap.has_db ? 'Ready' : 'Needs scan';
    const statusColor = snap.has_db ? 'var(--ok)' : 'var(--warn)';
    return `
      <div class="snap-row${selected ? ' snap-row--selected' : ''}" data-action="select-snap" data-idx="${i}">
        <div class="snap-name">${escapeHtml(snap.name)}</div>
        <div class="snap-meta">${escapeHtml(snap.date ?? '')}</div>
        <div class="snap-status" style="color:${statusColor}">${status}</div>
        <button class="btn btn--sm btn--danger" data-action="delete-snap" data-idx="${i}" title="Delete snapshot" onclick="event.stopPropagation()">Delete</button>
      </div>`;
  }).join('');

  bindSnapEvents();
}

function bindSnapEvents() {
  document.querySelectorAll('[data-action="select-snap"]').forEach(row => {
    row.addEventListener('click', async () => {
      const snap = state.snapshots[Number(row.dataset.idx)];
      if (!snap.has_db) { toast('Snapshot needs indexing first (lsa scan)'); return; }
      row.style.opacity = '0.6';
      try {
        await api('POST', `/api/snapshot/select?path=${encodeURIComponent(snap.path)}`);
        state.snapshot = snap;
        state.plan = null;
        state.prompt = null;
        state.candidates = [];
        state.selectedCandidate = 0;
        state.stats = null;
        document.getElementById('current-snap').textContent = snap.name;
        navigate('bundle');
      } catch (err) {
        toast(err.message);
        row.style.opacity = '1';
      }
    });
  });

  document.querySelectorAll('[data-action="delete-snap"]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const snap = state.snapshots[Number(btn.dataset.idx)];
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
    <p>Are you sure you want to delete <strong>${escapeHtml(snap.name)}</strong>?</p>
    <p style="color:var(--warn);margin:12px 0">This will permanently remove the snapshot directory and all its data. This cannot be undone.</p>
    <div class="btn-row" style="margin-top:16px">
      <button class="btn btn--danger" id="btn-confirm-delete">Delete permanently</button>
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
        document.getElementById('current-snap').textContent = 'none';
      }
      await loadSnapList();
    } catch (err) {
      status.innerHTML = `<div class="inline-error">${escapeHtml(err.message)}</div>`;
      btn.disabled = false;
    }
  });
}

/* ── Step 2: Bundle ───────────────────────────────────── */

function renderBundleStep(el) {
  let html = `
    <h2 class="page-title">Build Bundle</h2>
    <div class="section">
      <div class="field"><label>Title (optional)</label><input id="f-title" placeholder="Investigation title"></div>
      <div class="field"><label>CID</label><input id="f-cid" placeholder="Case ID"></div>
      <div class="field"><label>Job ID</label><input id="f-jobid" placeholder="Job name or ID"></div>
      <div class="field"><label>Limit</label><input id="f-limit" type="number" value="5" min="1" max="20"></div>
      <div class="btn-row">
        <button class="btn btn--primary" id="btn-plan">Find Bundle</button>
      </div>
    </div>
    <div id="plan-results"></div>`;
  el.innerHTML = html;

  if (state.plan) {
    renderPlanResults();
  }

  document.getElementById('btn-plan').addEventListener('click', async () => {
    const body = {};
    const title = document.getElementById('f-title').value.trim();
    const cid = document.getElementById('f-cid').value.trim();
    const jobid = document.getElementById('f-jobid').value.trim();
    const limit = Number(document.getElementById('f-limit').value) || 5;
    if (title) body.title = title;
    if (cid) body.cid = cid;
    if (jobid) body.jobid = jobid;
    body.limit = limit;

    const results = document.getElementById('plan-results');
    setLoading(results, true);
    try {
      state.plan = await api('POST', '/api/plan', body);
      state.candidates = state.plan.all_candidates ?? [];
      state.selectedCandidate = 0;
      renderPlanResults();
    } catch (err) {
      results.innerHTML = `<div class="inline-error">${escapeHtml(err.message)}</div>`;
    }
  });
}

async function renderPlanResults() {
  const results = document.getElementById('plan-results');
  if (!state.plan) return;

  const plan = state.plan;
  const cands = state.candidates;
  const selIdx = state.selectedCandidate;
  const sel = cands[selIdx];

  let html = '';

  if (plan.intent) {
    html += `<div class="section"><div class="section-title">Intent</div><div class="card"><div class="card-body">${escapeHtml(plan.intent)}</div></div></div>`;
  }

  if (cands.length > 0) {
    html += '<div class="section"><div class="section-title">Candidates</div><div class="card-grid">';
    cands.forEach((c, i) => {
      html += `
        <div class="card clickable${i === selIdx ? ' selected' : ''}" data-action="select-cand" data-idx="${i}" style="animation-delay:${i * 0.04}s">
          <div class="card-title">${escapeHtml(c.display_name ?? c.name ?? c.key)} <span class="score-badge">${c.score ?? '-'}</span></div>
          <div class="card-sub">${escapeHtml(c.key ?? '')}</div>
          <div class="card-body">${c.files?.length ?? 0} files</div>
        </div>`;
    });
    html += '</div></div>';
  }

  if (sel?.files?.length) {
    const grouped = groupFilesByKind(sel.files);
    html += '<div class="section"><div class="section-title">Files</div><div class="file-list">';
    for (const [kind, files] of Object.entries(grouped)) {
      html += `<div class="file-group-header">${escapeHtml(kind)} (${files.length})</div>`;
      files.forEach(f => {
        html += `<div class="file-item" data-action="preview-file" data-path="${escapeHtml(f.path ?? f.abs_path)}">`
          + `<span class="file-kind">${escapeHtml(f.kind ?? kind)}</span>`
          + `<span>${escapeHtml(f.path ?? f.abs_path)}</span></div>`;
      });
    }
    html += '</div><div class="btn-row">'
      + '<button class="btn btn--sm" data-action="copy-filelist">Copy file list</button>'
      + '<button class="btn btn--sm" data-action="copy-json">Copy as JSON</button>'
      + '<button class="btn btn--sm btn--primary" data-action="create-workspace">Create Workspace</button>'
      + '</div></div>';
  }

  html += '<div id="workspace-output" class="section" hidden></div>';

  html += '<div class="section"><div class="section-title">Dependency Graph</div><div id="mermaid-target"><div class="loading">Loading diagram...</div></div></div>';

  results.innerHTML = html;

  bindBundleEvents();

  try {
    const mermaidData = await api('POST', '/api/plan/mermaid', { candidate_index: selIdx });
    const container = document.getElementById('mermaid-target');
    if (container && mermaidData.mermaid_code) {
      const code = mermaidData.mermaid_code;
      const encoded = btoa(unescape(encodeURIComponent(JSON.stringify({ code }))));
      const liveUrl = `https://mermaid.live/edit#base64:${encoded}`;
      container.innerHTML = `
        <pre class="prompt-output" style="max-height:200px;margin-bottom:10px">${escapeHtml(code)}</pre>
        <div class="btn-row">
          <button class="btn btn--sm" data-action="copy-mermaid">Copy Mermaid Code</button>
          <a class="btn btn--sm btn--primary" href="${liveUrl}" target="_blank" rel="noopener">Open in Mermaid Live</a>
        </div>`;
      container.querySelector('[data-action="copy-mermaid"]')?.addEventListener('click', () => copyToClipboard(code));
      state._lastMermaidCode = code;
    } else if (container) {
      container.innerHTML = '<span class="muted">No diagram available</span>';
    }
  } catch {
    const container = document.getElementById('mermaid-target');
    if (container) container.innerHTML = '<span class="inline-error">Failed to load diagram</span>';
  }
}

function groupFilesByKind(files) {
  const groups = {};
  for (const f of files) {
    const kind = f.kind ?? 'other';
    (groups[kind] ??= []).push(f);
  }
  return groups;
}

function bindBundleEvents() {
  document.querySelectorAll('[data-action="select-cand"]').forEach(card => {
    card.addEventListener('click', () => {
      state.selectedCandidate = Number(card.dataset.idx);
      renderPlanResults();
    });
  });

  document.querySelectorAll('[data-action="preview-file"]').forEach(item => {
    item.addEventListener('click', async () => {
      const path = item.dataset.path;
      try {
        const data = await api('GET', `/api/file?path=${encodeURIComponent(path)}`);
        const content = data.content ?? '(empty)';
        showModal(data.path ?? path, content);
      } catch (err) {
        toast(err.message);
      }
    });
  });

  document.querySelector('[data-action="copy-filelist"]')?.addEventListener('click', () => {
    const sel = state.candidates[state.selectedCandidate];
    if (!sel?.files) return;
    const text = sel.files.map(f => f.path ?? f.abs_path).join('\n');
    copyToClipboard(text);
  });

  document.querySelector('[data-action="copy-json"]')?.addEventListener('click', () => {
    const sel = state.candidates[state.selectedCandidate];
    if (!sel) return;
    copyToClipboard(JSON.stringify(sel, null, 2));
  });

  document.querySelector('[data-action="create-workspace"]')?.addEventListener('click', () => {
    const section = document.getElementById('workspace-output');
    if (!section) return;
    section.hidden = false;
    section.innerHTML = `
      <div class="section-title">Create Workspace</div>
      <div class="card">
        <div class="card-sub">Create a workspace directory with selected bundle files.</div>
        <div class="field"><label>Ticket ID (optional)</label><input id="ws-ticket" placeholder="e.g. INC0123456"></div>
        <div class="field"><label>Title (optional)</label><input id="ws-title" placeholder="Investigation title"></div>
        <div class="field">
          <label>Copy mode</label>
          <div class="radio-group" id="ws-mode">
            <label><input type="radio" name="ws-mode" value="snap" checked><span>From Snapshot</span></label>
            <label><input type="radio" name="ws-mode" value="ssh"><span>From RHS (SSH)</span></label>
          </div>
        </div>
        <div class="btn-row">
          <button class="btn btn--primary" id="btn-ws-create">Create</button>
          <button class="btn" id="btn-ws-cancel">Cancel</button>
        </div>
        <div id="ws-status"></div>
      </div>`;

    document.getElementById('btn-ws-cancel')?.addEventListener('click', () => { section.hidden = true; });
    document.getElementById('btn-ws-create')?.addEventListener('click', async () => {
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
            msg += `<br><a href="#" class="ws-open-link" data-winpath>Open in Explorer: ${escapeHtml(finalResult.workspace_win)}</a>`;
          }
          msg += `<br>${finalResult.files_copied} file(s) copied.`;
          if (finalResult.copy_errors?.length) {
            msg += `<br><span style="color:var(--warn)">${finalResult.copy_errors.length} file(s) had errors.</span>`;
          }
          msg += `<br>Pull script: <code>${escapeHtml(finalResult.pull_script)}</code>`;
          status.innerHTML = `<div style="margin-top:12px">${msg}</div>`;
          if (finalResult.workspace_win) {
            status.querySelector('[data-winpath]').addEventListener('click', (e) => {
              e.preventDefault();
              copyToClipboard(finalResult.workspace_win);
              toast('Path copied — paste in Explorer address bar');
            });
          }
        }
      } catch (err) {
        status.innerHTML = `<div class="inline-error">${escapeHtml(err.message)}</div>`;
      } finally {
        btn.disabled = false;
      }
    });
  });
}

/* ── Step 3: Prompt ───────────────────────────────────── */

function renderPromptStep(el) {
  const modes = ['cursor', 'deep', 'explain'];
  state.promptMode ??= 'cursor';
  const currentMode = state.promptMode;

  let html = `
    <h2 class="page-title">Generate Prompt</h2>
    <div class="section">
      <div class="field"><label>Error Text (optional)</label><textarea id="f-error" placeholder="Paste error message or log excerpt..."></textarea></div>
      <div class="field">
        <label>Mode</label>
        <div class="radio-group" id="rg-mode">
          ${modes.map(m => `<label class="${m === currentMode ? '' : ''}"><input type="radio" name="mode" value="${m}" ${m === currentMode ? 'checked' : ''}><span>${escapeHtml(m.charAt(0).toUpperCase() + m.slice(1))}</span></label>`).join('')}
        </div>
      </div>
      <div class="field">
        <label>Language</label>
        <div class="lang-toggle" id="lang-toggle">
          <button class="${state.lang === 'en' ? 'active' : ''}" data-lang="en">EN</button>
          <button class="${state.lang === 'ru' ? 'active' : ''}" data-lang="ru">RU</button>
        </div>
      </div>
      <div class="field">
        <label>Candidate</label>
        <select id="f-cand-idx">
          ${state.candidates.map((c, i) => `<option value="${i}" ${i === state.selectedCandidate ? 'selected' : ''}>${escapeHtml(c.display_name ?? c.name ?? c.key)}</option>`).join('')}
        </select>
      </div>
      <div class="btn-row">
        <button class="btn btn--primary" id="btn-prompt">Generate Prompt</button>
      </div>
    </div>
    <div id="prompt-output-section"></div>`;
  el.innerHTML = html;

  if (state.prompt) {
    renderPromptOutput();
  }

  document.getElementById('rg-mode').addEventListener('change', (e) => {
    if (e.target.name === 'mode') state.promptMode = e.target.value;
  });

  document.getElementById('lang-toggle').addEventListener('click', (e) => {
    const lang = e.target.dataset?.lang;
    if (!lang) return;
    state.lang = lang;
    document.querySelectorAll('#lang-toggle button').forEach(b =>
      b.classList.toggle('active', b.dataset.lang === lang)
    );
  });

  document.getElementById('btn-prompt').addEventListener('click', async () => {
    const mode = document.querySelector('input[name="mode"]:checked')?.value ?? state.promptMode;
    state.promptMode = mode;
    const errorText = document.getElementById('f-error').value.trim();
    const candidateIndex = Number(document.getElementById('f-cand-idx').value);

    const body = { mode, lang: state.lang, candidate_index: candidateIndex };
    if (errorText) body.error_text = errorText;

    const section = document.getElementById('prompt-output-section');
    setLoading(section, true);
    try {
      state.prompt = await api('POST', '/api/prompt', body);
      renderPromptOutput();
    } catch (err) {
      section.innerHTML = `<div class="inline-error">${escapeHtml(err.message)}</div>`;
    }
  });
}

function renderPromptOutput() {
  const section = document.getElementById('prompt-output-section');
  if (!section || !state.prompt) return;

  const p = state.prompt;
  section.innerHTML = `
    <div class="section">
      <div class="section-title">Generated Prompt</div>
      <pre class="prompt-output">${escapeHtml(p.prompt_text)}</pre>
      <div class="btn-row">
        <button class="btn btn--primary btn--sm" data-action="copy-prompt">Copy to Clipboard</button>
        ${p.saved_path ? `<span class="muted" style="font-size:12px;align-self:center">Saved: ${escapeHtml(p.saved_path)}</span>` : ''}
      </div>
    </div>`;

  section.querySelector('[data-action="copy-prompt"]')?.addEventListener('click', () => {
    copyToClipboard(p.prompt_text);
  });
}

/* ── Stats page ───────────────────────────────────────── */

async function renderStatsPage(el) {
  el.innerHTML = '<h2 class="page-title">Overview</h2><div id="stats-body"></div>';
  const body = document.getElementById('stats-body');
  setLoading(body, true);

  try {
    const stats = await api('GET', '/api/stats');
    state.stats = stats;

    let html = '<div class="stat-grid">';
    const mainStats = [
      ['Artifacts', stats.artifacts],
      ['Nodes', stats.nodes],
      ['Edges', stats.edges],
      ['Incidents', stats.incidents],
      ['Case Cards', stats.case_cards],
      ['Message Codes', stats.message_codes],
    ];
    mainStats.forEach(([label, value], i) => {
      html += `<div class="stat" style="animation-delay:${i * 0.04}s"><div class="stat-label">${escapeHtml(label)}</div><div class="stat-value">${value ?? '-'}</div></div>`;
    });
    html += '</div>';

    if (stats.artifacts_by_kind && Object.keys(stats.artifacts_by_kind).length > 0) {
      html += '<div class="section"><div class="section-title">Artifacts by Kind</div><div class="stat-grid">';
      const entries = Object.entries(stats.artifacts_by_kind).sort((a, b) => b[1] - a[1]);
      entries.forEach(([kind, count], i) => {
        html += `<div class="stat" style="animation-delay:${(i + 6) * 0.04}s"><div class="stat-label">${escapeHtml(kind)}</div><div class="stat-value">${count}</div></div>`;
      });
      html += '</div></div>';
    }

    body.innerHTML = html;
  } catch (err) {
    body.innerHTML = `<div class="inline-error">${escapeHtml(err.message)}</div>`;
  }
}

/* ── Search page ──────────────────────────────────────── */

function renderSearchPage(el) {
  el.innerHTML = `
    <h2 class="page-title">Search</h2>
    <div class="field">
      <input id="search-input" placeholder="Search artifacts, files, content..." autofocus>
    </div>
    <div id="search-results"></div>`;

  let debounce = null;
  const input = document.getElementById('search-input');
  input.addEventListener('input', () => {
    clearTimeout(debounce);
    debounce = setTimeout(() => performSearch(input.value.trim()), 300);
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      clearTimeout(debounce);
      performSearch(input.value.trim());
    }
  });
}

async function performSearch(query) {
  const results = document.getElementById('search-results');
  if (!query) {
    results.innerHTML = '';
    return;
  }

  setLoading(results, true);
  try {
    const data = await api('GET', `/api/search?q=${encodeURIComponent(query)}&limit=20`);
    state.searchResults = data;

    if (data.length === 0) {
      results.innerHTML = '<div class="muted" style="padding:16px 0">No results found</div>';
      return;
    }

    results.innerHTML = '<div class="search-results">' + data.map(hit => `
      <div class="search-hit" data-action="search-preview" data-path="${escapeHtml(hit.path)}">
        <div class="search-hit-path">
          <span class="file-kind">${escapeHtml(hit.kind ?? 'file')}</span>
          ${escapeHtml(hit.path)}
        </div>
        ${hit.snippet ? `<div class="search-hit-snippet">${highlightSnippet(hit.snippet, query)}</div>` : ''}
      </div>`).join('') + '</div>';

    bindSearchEvents();
  } catch (err) {
    results.innerHTML = `<div class="inline-error">${escapeHtml(err.message)}</div>`;
  }
}

function highlightSnippet(snippet, query) {
  const escaped = escapeHtml(snippet);
  if (!query) return escaped;
  const pattern = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return escaped.replace(new RegExp(`(${pattern})`, 'gi'), '<mark>$1</mark>');
}

function bindSearchEvents() {
  document.querySelectorAll('[data-action="search-preview"]').forEach(item => {
    item.addEventListener('click', async () => {
      const path = item.dataset.path;
      try {
        const data = await api('GET', `/api/file?path=${encodeURIComponent(path)}`);
        const lines = (data.content ?? '').split('\n');
        const numbered = lines.map((line, i) => `${String(i + 1).padStart(4)} | ${line}`).join('\n');
        showModal(data.path ?? path, numbered);
      } catch (err) {
        toast(err.message);
      }
    });
  });
}

/* ── Modal events ─────────────────────────────────────── */

document.getElementById('modal-close').addEventListener('click', hideModal);
document.querySelector('.modal-backdrop').addEventListener('click', hideModal);
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') hideModal();
});

/* ── Boot ─────────────────────────────────────────────── */

render();
