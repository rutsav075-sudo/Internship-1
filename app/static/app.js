'use strict';
const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const escapeHTML = (value) =>
  String(value ?? '').replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]
  );
const uuid = () =>
  globalThis.crypto?.randomUUID
    ? crypto.randomUUID()
    : '10000000-1000-4000-8000-100000000000'.replace(/[018]/g, (c) =>
        (
          Number(c) ^
          (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (Number(c) / 4)))
        ).toString(16)
      );
let session = uuid(),
  adminToken = '',
  authEpoch = 0,
  knowledge = [],
  busy = false,
  toastTimer;
const labels = {
  overview: 'Overview',
  assistant: 'AI assistant',
  knowledge: 'Knowledge base',
  evaluation: 'Model lab',
  settings: 'Settings & connection',
};
function toast(message) {
  $('#toast').textContent = message;
  $('#toast').hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ($('#toast').hidden = true), 5500);
}
async function api(path, options = {}) {
  const { auth, ...rest } = options;
  const headers = {
    ...(rest.body ? { 'Content-Type': 'application/json' } : {}),
    ...(auth ? { Authorization: `Bearer ${adminToken}` } : {}),
    ...rest.headers,
  };
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 45000);
  try {
    const response = await fetch(path, { ...rest, headers, signal: controller.signal });
    if (!response.ok) {
      let detail;
      try {
        detail = (await response.json()).detail;
      } catch {
        /* Non-JSON proxy error. */
      }
      const message =
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
            ? detail.map((e) => e.msg).join('. ')
            : `Request failed (${response.status}). Please try again.`;
      throw new Error(message);
    }
    if (response.headers.get('Content-Type')?.includes('application/json'))
      return await response.json();
    return response;
  } catch (error) {
    if (error.name === 'AbortError')
      throw new Error('The request took too long. Please try again.', { cause: error });
    if (error instanceof TypeError)
      throw new Error('Connection lost. Check your network and try again.', { cause: error });
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

function route() {
  const view = Object.hasOwn(labels, location.hash.slice(1)) ? location.hash.slice(1) : 'overview';
  $$('.view').forEach((el) => (el.hidden = el.id !== `view-${view}`));
  $$('[data-nav]').forEach((el) => {
    el.classList.toggle('active', el.dataset.nav === view);
    if (el.dataset.nav === view) el.setAttribute('aria-current', 'page');
    else el.removeAttribute('aria-current');
  });
  $('#breadcrumb').textContent = labels[view];
  document.title = `${labels[view]} · Edxso`;
  $('#menu-toggle').setAttribute('aria-expanded', 'false');
  $('.sidebar').classList.remove('open');
  if (view === 'overview') refreshAnalytics();
  if (view === 'evaluation') loadEvaluation();
  if (view === 'settings' && adminToken) {
    refreshProviderDiagnostics();
    loadOperations();
  }
}
async function health() {
  try {
    const h = await api('/api/health');
    $('#hero-status').textContent = h.provider_configured
      ? 'Gemini configured · source-grounded answers'
      : 'Reference FAQ mode · connect Gemini in settings';
    $('#chat-status').textContent = h.provider_configured
      ? 'Gemini configured · with reference fallback'
      : 'Reference FAQ mode · no API key configured';
    $('#engine-label').textContent = h.provider_configured
      ? `Gemini · ${h.model}`
      : 'FAQ retrieval (no LLM)';
    $('#provider-description').textContent = h.provider_configured
      ? `A server key is configured for ${h.model}. Live requests may still fail if the key, model access or quota is invalid.`
      : 'No Gemini key is configured. The assistant returns reference FAQ answers without calling an LLM.';
  } catch {
    $('#hero-status').textContent = 'Server connection unavailable';
    toast('Unable to reach the server. Please refresh.');
  }
}
function emptyAnalytics() {
  ['total', 'sessions', 'latency', 'helpful'].forEach((k) => ($(`#metric-${k}`).textContent = '—'));
  $('#feedback-caption').textContent = 'Based on conversation feedback';
  $('#updated-label').textContent = 'Live workspace data';
  $('#intent-chart').innerHTML =
    '<div class="locked-note">⊞ &nbsp; Unlock analytics to see your workspace data.</div>' +
    ['Admissions', 'Fees', 'Academics', 'Transport', 'Support']
      .map(
        (label) =>
          `<div class="bar-row"><span>${label}</span><div class="bar-track"></div><span class="bar-count">—</span></div>`
      )
      .join('');
  $('#recent-conversations').innerHTML =
    '<div class="empty-state"><span class="empty-icon">⊞</span><strong>Conversation insights stay private.</strong><p>Unlock analytics using your server admin token to view real activity.</p><a href="#settings">Unlock workspace analytics ↗</a></div>';
}
async function refreshAnalytics() {
  if (!adminToken) return emptyAnalytics();
  const requestToken = adminToken;
  try {
    const data = await api('/api/analytics', { auth: true });
    if (adminToken !== requestToken) return;
    $('#metric-total').textContent = data.total.toLocaleString();
    $('#metric-sessions').textContent = data.sessions.toLocaleString();
    $('#metric-latency').textContent = data.total
      ? `${(data.avg_latency_ms / 1000).toFixed(2)}s`
      : '—';
    $('#metric-helpful').textContent =
      data.helpful_percent === null ? '—' : `${data.helpful_percent}%`;
    $('#feedback-caption').textContent =
      `${data.rated} rated ${data.rated === 1 ? 'answer' : 'answers'} · thumbs up / down`;
    $('#updated-label').textContent =
      `Updated ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    const max = Math.max(1, ...Object.values(data.intents));
    $('#intent-chart').innerHTML = ['Admissions', 'Fees', 'Academics', 'Transport', 'Support']
      .map(
        (label) =>
          `<div class="bar-row"><span>${label}</span><div class="bar-track"><div class="bar-fill" data-width="${(100 * (data.intents[label] || 0)) / max}"></div></div><span class="bar-count">${data.intents[label] || 0}</span></div>`
      )
      .join('');
    $$('.bar-fill').forEach((el) => (el.style.width = `${el.dataset.width}%`));
    if (!data.recent.length)
      $('#recent-conversations').innerHTML =
        '<div class="empty-state"><span class="empty-icon">☏</span><strong>Your next insight starts with a question.</strong><p>No conversations yet. Ask the assistant something to get started.</p><a href="#assistant">Start a conversation ↗</a></div>';
    else
      $('#recent-conversations').innerHTML =
        '<div class="table-wrap"><table><thead><tr><th>QUESTION</th><th>PREDICTED INTENT</th><th>ANSWER MODE</th><th>RECEIVED</th></tr></thead><tbody>' +
        data.recent
          .map(
            (e) =>
              `<tr><td>${escapeHTML(e.question)}</td><td><span class="intent-chip">${escapeHTML(e.intent)}</span></td><td>${escapeHTML(e.mode)}</td><td>${escapeHTML(new Date(e.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }))}</td></tr>`
          )
          .join('') +
        '</tbody></table></div>';
  } catch (err) {
    if (adminToken === requestToken) {
      emptyAnalytics();
      toast(err.message);
    }
  }
}
function welcome() {
  $('#messages').replaceChildren();
  const box = document.createElement('div');
  box.className = 'message assistant';
  box.innerHTML =
    '<div class="message-label"><span>✧</span> SCHOOL ASSISTANT</div><div class="message-body">Hello! A little help for your school day.\n\nI can answer questions about admissions, fees, learning and transport using our sample school FAQs. What would you like to know?</div>';
  $('#messages').append(box);
}
function addMessage(text, role, result) {
  const el = document.createElement('div');
  el.className = `message ${role}`;
  const label = document.createElement('div');
  label.className = 'message-label';
  label.textContent = role === 'user' ? 'YOU' : '✧ SCHOOL ASSISTANT';
  const body = document.createElement('div');
  body.className = 'message-body';
  body.textContent = text;
  el.append(label, body);
  if (result) {
    if (result.notice) {
      const n = document.createElement('p');
      n.className = 'message-notice';
      n.textContent = result.notice;
      el.append(n);
    }
    const meta = document.createElement('div');
    meta.className = 'message-meta';
    [
      result.mode === 'gemini'
        ? 'Gemini answer'
        : result.mode === 'no_match'
          ? 'No source match'
          : 'Reference FAQ',
      result.intent,
      `Model score: ${Math.round(result.confidence * 100)}%`,
      `${result.latency_ms} ms`,
    ].forEach((t) => {
      const s = document.createElement('span');
      s.textContent = t;
      meta.append(s);
    });
    for (const [value, text] of [
      [1, 'Helpful ↑'],
      [-1, 'Not helpful ↓'],
    ]) {
      const b = document.createElement('button');
      b.className = 'vote-button';
      b.textContent = text;
      b.setAttribute('aria-pressed', 'false');
      b.addEventListener('click', async () => {
        try {
          await api(`/api/feedback/${result.id}`, {
            method: 'POST',
            body: JSON.stringify({ session_id: session, value }),
          });
          $$('.vote-button', meta).forEach((v) => {
            v.classList.toggle('selected', v === b);
            v.setAttribute('aria-pressed', String(v === b));
          });
          toast('Thank you. Feedback recorded.');
        } catch (err) {
          toast(err.message);
        }
      });
      meta.append(b);
    }
    el.append(meta);
    if (result.sources.length) {
      const details = document.createElement('details');
      details.className = 'sources';
      const summary = document.createElement('summary');
      summary.textContent = `${result.sources.length} retrieved reference${result.sources.length > 1 ? 's' : ''} · model score is not calibrated accuracy`;
      details.append(summary);
      const ul = document.createElement('ul');
      result.sources.forEach((s) => {
        const li = document.createElement('li');
        li.textContent = s.question;
        ul.append(li);
      });
      details.append(ul);
      el.append(details);
    }
  }
  $('#messages').append(el);
  $('#messages').scrollTop = $('#messages').scrollHeight;
  return el;
}
async function sendQuestion(question) {
  if (busy) return;
  const message = question.trim();
  if (message.length < 2 || message.length > 2000) {
    toast('Please enter a question between 2 and 2,000 characters.');
    return;
  }
  busy = true;
  $('#chat-form').setAttribute('aria-busy', 'true');
  $('#send-button').disabled = true;
  $('#new-chat').disabled = true;
  $('#question').value = '';
  addMessage(message, 'user');
  const loading = addMessage('Looking through the school knowledge base…', 'assistant');
  loading.classList.add('loading');
  try {
    const result = await api('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message, session_id: session }),
    });
    loading.remove();
    addMessage(result.answer, 'assistant', result);
  } catch (err) {
    loading.remove();
    addMessage(`Sorry, that question could not be answered. ${err.message}`, 'assistant');
    $('#question').value = message;
  } finally {
    busy = false;
    $('#chat-form').setAttribute('aria-busy', 'false');
    $('#send-button').disabled = false;
    $('#new-chat').disabled = false;
    $('#question').focus();
  }
}
async function loadKnowledge() {
  try {
    knowledge = await api('/api/knowledge');
    renderKnowledge();
  } catch (err) {
    $('#knowledge-list').textContent = err.message;
  }
}
function renderKnowledge() {
  const term = $('#knowledge-search').value.toLowerCase();
  const filtered = knowledge.filter((k) =>
    `${k.question} ${k.answer} ${k.category}`.toLowerCase().includes(term)
  );
  $('#knowledge-count').textContent = `${filtered.length} references`;
  $('#knowledge-list').innerHTML = filtered.length
    ? filtered
        .map(
          (k) =>
            `<article class="panel knowledge-card"><span class="tag green">${escapeHTML(k.category.toUpperCase())}</span><h3>${escapeHTML(k.question)}</h3><p>${escapeHTML(k.answer)}</p><footer><span>REFERENCE · ${escapeHTML(k.id)}</span><a href="#assistant" class="text-link" data-ask="${escapeHTML(k.question)}">Ask this question ↗</a></footer></article>`
        )
        .join('')
    : '<div class="empty-state">No matching references. Try a different search.</div>';
  $$('[data-ask]').forEach((a) =>
    a.addEventListener('click', () => {
      $('#question').value = a.dataset.ask;
      $('#question').focus();
    })
  );
}
async function loadEvaluation() {
  try {
    const e = await api('/api/evaluation');
    $('#evaluation-content').innerHTML =
      `<div class="metrics"><article class="metric"><div>Held-out accuracy</div><strong>${(e.accuracy * 100).toFixed(1)}%</strong><small>Intent predictions · not LLM answer quality</small></article><article class="metric"><div>Macro F1</div><strong>${e.macro_f1.toFixed(3)}</strong><small>Equal weight across all five categories</small></article><article class="metric"><div>Training examples</div><strong>${e.train_samples}</strong><small>Synthetic examples · evaluation split</small></article><article class="metric"><div>Test examples</div><strong>${e.test_samples}</strong><small>Fixed original test split · 15 examples</small></article></div><div class="eval-grid"><article class="panel"><h3>Per-category evaluation</h3><div class="table-wrap"><table><thead><tr><th>INTENT</th><th>PRECISION</th><th>RECALL</th><th>F1</th><th>N</th></tr></thead><tbody>${e.labels.map((l) => `<tr><td>${escapeHTML(l)}</td><td>${e.report[l].precision.toFixed(2)}</td><td>${e.report[l].recall.toFixed(2)}</td><td>${e.report[l]['f1-score'].toFixed(2)}</td><td>${e.report[l].support}</td></tr>`).join('')}</tbody></table></div><p class="eval-note">Evaluation fits TF–IDF on the training split only to avoid feature leakage. The serving classifier fits all ${e.serving_samples} synthetic examples. The original 15-example test partition is preserved; added examples affect evaluation training only.</p></article><article class="panel"><h3>Confusion matrix</h3><p class="eval-note">Rows = actual intent · columns = predicted intent</p><div class="table-wrap"><table class="matrix-table"><thead><tr><th>ACTUAL ↓</th>${e.labels.map((l) => `<th>${escapeHTML(l)}</th>`).join('')}</tr></thead><tbody>${e.confusion_matrix.map((row, i) => `<tr><th>${escapeHTML(e.labels[i])}</th>${row.map((n, j) => `<td class="${i === j ? 'diagonal' : ''}">${n}</td>`).join('')}</tr>`).join('')}</tbody></table></div><p class="eval-note">Small test counts can produce unstable metrics. Gather a representative, consented real-world dataset before setting production thresholds.</p></article><article class="panel wide"><h3>Reproducible by design</h3><div class="tech-list"><div><span>FEATURE ENGINEERING</span><strong>Word TF–IDF · unigrams + bigrams · English stop-word removal · sublinear term frequency</strong></div><div><span>CLASSIFIER</span><strong>Logistic Regression · C=4 · maximum 1,000 iterations · random seed 42</strong></div><div><span>RETRIEVAL & GENERATION</span><strong>Cosine similarity · top 3 FAQ references · minimum similarity 0.09 · optional Gemini generation</strong></div></div><p class="eval-note">${escapeHTML(e.caveat)} Model scores are uncalibrated; they must not be interpreted as accuracy guarantees. FAQ relevance and Gemini factuality require separate evaluation.</p></article></div>`;
  } catch (err) {
    $('#evaluation-content').textContent = err.message;
  }
}
$('#chat-form').addEventListener('submit', (e) => {
  e.preventDefault();
  sendQuestion($('#question').value);
});
$('#question').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    sendQuestion(e.currentTarget.value);
  }
});
$$('[data-prompt]').forEach((b) =>
  b.addEventListener('click', () => sendQuestion(b.dataset.prompt))
);
$('#new-chat').addEventListener('click', () => {
  session = uuid();
  $('#question').value = '';
  welcome();
  toast('New session started. Existing server records are unchanged.');
});
$('#knowledge-search').addEventListener('input', renderKnowledge);
$('#refresh-status').addEventListener('click', () => {
  health();
  if (adminToken) refreshProviderDiagnostics();
  toast('Refreshing server connection status.');
});
$('#unlock-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const candidate = $('#admin-token').value.trim();
  if (!candidate) return toast('Enter your server admin token.');
  const epoch = ++authEpoch;
  $('#unlock-form button').disabled = true;
  try {
    await api('/api/analytics', { headers: { Authorization: `Bearer ${candidate}` } });
    if (epoch !== authEpoch) return;
    adminToken = candidate;
    $('#unlock-status').textContent = 'Analytics unlocked for this page session.';
    $('#admin-token').value = '';
    location.hash = 'overview';
    toast('Analytics unlocked for this page session.');
  } catch (err) {
    if (epoch === authEpoch) toast(err.message);
  } finally {
    $('#unlock-form button').disabled = false;
  }
});
$('#lock-button').addEventListener('click', () => {
  authEpoch++;
  adminToken = '';
  $('#unlock-status').textContent = 'Analytics is locked.';
  $('#operations-summary').textContent = 'Unlock analytics to view operational monitoring.';
  $('#operations-warnings').replaceChildren();
  $('#operations-meta').textContent = 'Metrics are a snapshot, not an external alerting service.';
  $('#admin-token').value = '';
  $('#provider-diagnostics').textContent =
    'Analytics locked. Unlock it to view provider diagnostics.';
  emptyAnalytics();
  toast('Analytics locked.');
});
$('#export-button').addEventListener('click', async () => {
  if (!adminToken) {
    location.hash = 'settings';
    return toast('Unlock analytics before exporting.');
  }
  try {
    const r = await api('/api/export', { auth: true });
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'edxso-conversations.csv';
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (err) {
    toast(err.message);
  }
});
$('#delete-data').addEventListener('click', async () => {
  if (!adminToken) return toast('Unlock analytics first.');
  if (
    !confirm(
      'Permanently delete ALL server conversation records and feedback? This cannot be undone.'
    )
  )
    return;
  try {
    await api('/api/conversations', { method: 'DELETE', auth: true });
    toast('All conversation records deleted.');
    await refreshAnalytics();
  } catch (err) {
    toast(err.message);
  }
});
$('#handoff-button').addEventListener('click', () => $('#handoff-dialog').showModal());
$('#close-dialog').addEventListener('click', () => $('#handoff-dialog').close());
$('#menu-toggle').addEventListener('click', () => {
  const open = $('.sidebar').classList.toggle('open');
  $('#menu-toggle').setAttribute('aria-expanded', String(open));
});
document.addEventListener('click', (e) => {
  if (!$('.sidebar').contains(e.target) && !$('#menu-toggle').contains(e.target)) {
    $('.sidebar').classList.remove('open');
    $('#menu-toggle').setAttribute('aria-expanded', 'false');
  }
});
window.addEventListener('hashchange', route);

async function refreshProviderDiagnostics() {
  if (!adminToken) return;
  const tokenAtStart = adminToken;
  try {
    const status = await api('/api/provider/status', { auth: true });
    if (tokenAtStart !== adminToken) return;
    $('#provider-diagnostics').textContent = !status.configured
      ? 'No Gemini key is configured on the server.'
      : status.last_error
        ? `${status.message} ${status.cooldown_seconds ? `Automatic calls paused for ${status.cooldown_seconds}s.` : ''}`
        : status.last_success_at
          ? `Gemini generation verified at ${new Date(status.last_success_at).toLocaleString()}. Model: ${status.model}.`
          : 'Key configured, but generation has not been verified in this server process. Run a live test.';
  } catch (error) {
    if (tokenAtStart === adminToken) $('#provider-diagnostics').textContent = error.message;
  }
}
$('#test-provider').addEventListener('click', async () => {
  if (!adminToken) return toast('Unlock analytics with your admin token first.');
  const tokenAtStart = adminToken;
  $('#test-provider').disabled = true;
  $('#provider-diagnostics').textContent = 'Testing one real Gemini generation…';
  try {
    const result = await api('/api/provider/check', { method: 'POST', auth: true });
    if (tokenAtStart !== adminToken) return;
    $('#provider-diagnostics').textContent = result.ok
      ? `Live generation succeeded with ${result.model}. No conversation record was created.`
      : result.message;
  } catch (error) {
    if (tokenAtStart === adminToken) $('#provider-diagnostics').textContent = error.message;
  } finally {
    $('#test-provider').disabled = false;
  }
});

welcome();
route();
health();
loadKnowledge();

async function loadOperations() {
  if (!adminToken) return toast('Unlock analytics to view monitoring.');
  const tokenAtStart = adminToken;
  $('#refresh-operations').disabled = true;
  try {
    const result = await api('/api/operations', { auth: true });
    if (tokenAtStart !== adminToken) return;
    const latency = (value) => (value === null ? '—' : `${value} ms`);
    const cards = [
      ['Database', result.database.connected ? 'SQLite · connected' : 'Unavailable'],
      ['Provider state', result.provider.state],
      ['Server p95 answer time', latency(result.traffic.p95_latency_ms)],
      [
        'Reference / no-match share',
        result.traffic.fallback_percent === null ? '—' : `${result.traffic.fallback_percent}%`,
      ],
      ['Serving model examples', `${result.model.serving_samples} · synthetic`],
      ['Process uptime', `${result.application.uptime_seconds} seconds`],
    ];
    $('#operations-summary').innerHTML = cards
      .map(
        ([label, value]) =>
          `<div class="operation-metric"><span>${escapeHTML(label)}</span><strong>${escapeHTML(value)}</strong></div>`
      )
      .join('');
    $('#operations-warnings').replaceChildren();
    result.warnings.forEach((warning) => {
      const item = document.createElement('li');
      item.textContent = warning;
      $('#operations-warnings').append(item);
    });
    $('#operations-meta').textContent =
      `${result.metric_scope} Dataset SHA-256: ${result.model.dataset_sha256}`;
  } catch (error) {
    if (tokenAtStart === adminToken) {
      $('#operations-summary').textContent = error.message;
      $('#operations-warnings').replaceChildren();
    }
  } finally {
    $('#refresh-operations').disabled = false;
  }
}
$('#refresh-operations').addEventListener('click', loadOperations);
