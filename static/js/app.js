// ════════════════════════════════════════════
//  SONA — Live Gold Rates
// ════════════════════════════════════════════

const KEY = { '22k': 'gold_22k', '24k': 'gold_24k', '18k': 'gold_18k' };
const state = {
    purity: '22k',
    sort: 'price-asc',
    rates: [],
    history: [],
    stores: [],
    lastUpdated: null,
};
let chart = null;

document.addEventListener('DOMContentLoaded', init);

async function init() {
    bindPurity();
    await Promise.all([loadStores(), loadRates(), loadHistory()]);
    positionSegInd();
    setInterval(updateAgo, 30000);
}

// ─────────── Data ───────────
async function loadStores() {
    try {
        const d = await (await fetch('/api/stores')).json();
        state.stores = d.stores || [];
        renderManualStores();
    } catch { state.stores = []; }
}

async function loadRates() {
    try {
        const d = await (await fetch('/api/rates/today')).json();
        state.rates = d.rates || [];
        state.lastUpdated = freshest(state.rates);
        const el = document.getElementById('bm-date');
        if (el && d.date) el.textContent = fmtDate(d.date);
        render();
        updateAgo();
    } catch {
        document.getElementById('cards').innerHTML = emptyState();
    }
}

async function loadHistory() {
    try {
        const days = document.getElementById('chart-days').value;
        const d = await (await fetch(`/api/history?days=${days}`)).json();
        state.history = d.history || [];
        loadChart();
        render();
    } catch { state.history = []; }
}

function freshest(rates) {
    let t = null;
    rates.forEach(r => { if (r.scraped_at && (!t || r.scraped_at > t)) t = r.scraped_at; });
    return t;
}

// ─────────── Sort + render ───────────
function render() {
    state.sort = document.getElementById('sort-select').value;
    const k = KEY[state.purity];
    let rows = [...state.rates];
    const priced = rows.filter(r => r[k] != null);

    if (state.sort === 'price-asc') rows.sort((a, b) => (a[k] ?? 1e9) - (b[k] ?? 1e9));
    else if (state.sort === 'price-desc') rows.sort((a, b) => (b[k] ?? -1) - (a[k] ?? -1));
    else rows.sort((a, b) => a.store_name.localeCompare(b.store_name));

    const vals = priced.map(r => r[k]);
    const min = vals.length ? Math.min(...vals) : null;
    const max = vals.length ? Math.max(...vals) : null;

    renderBenchmark(priced, min, max);
    renderCards(rows, min, k);
    renderTable(rows, min);
    document.getElementById('count-tag').textContent = `${state.rates.length} stores`;
}

function renderBenchmark(priced, min, max) {
    document.getElementById('bm-purity').textContent = state.purity.toUpperCase();
    document.getElementById('bm-count').textContent = priced.length;

    if (!priced.length) {
        document.getElementById('bm-figure').textContent = '₹—';
        document.getElementById('bm-store').textContent = 'no data yet';
        document.getElementById('bm-range').textContent = '—';
        return;
    }
    const k = KEY[state.purity];
    const best = priced.reduce((a, b) => (a[k] < b[k] ? a : b));
    document.getElementById('bm-figure').textContent = inr(min);
    document.getElementById('bm-store').textContent = best.store_name;
    document.getElementById('bm-range').textContent = `${inr(min)} – ${inr(max)}`;
    drawBenchSpark();
}

function renderCards(rows, min, k) {
    const el = document.getElementById('cards');
    if (!rows.length) { el.innerHTML = emptyState(); return; }
    el.innerHTML = rows.map((r, i) => {
        const v = r[k];
        const best = v != null && v === min;
        const delta = deltaHtml(r[`change_${state.purity}`]);
        return `
        <article class="card ${best ? 'best' : ''}" style="animation-delay:${i * 45}ms" data-slug="${r.store_slug}" onclick="toggleCard(this)">
            <div class="rank">${best ? '★' : i + 1}</div>
            <div class="store-id">
                ${r.logo ? `<img class="store-logo" src="${r.logo}" onerror="this.remove()" alt="">` : ''}
                <span class="store-name">${r.store_name}</span>
                ${best ? '<span class="ribbon">Best</span>' : ''}
            </div>
            <div class="chips">
                ${chip('22K', r.gold_22k)} ${chip('24K', r.gold_24k)} ${chip('18K', r.gold_18k)}
            </div>
            <div class="price-col">
                ${v != null ? `<span class="price">${inr(v)}</span>` : '<span class="price-na">—</span>'}
                ${delta}
            </div>
            <div class="card-expand">${expandHtml(r)}</div>
        </article>`;
    }).join('');
}

function chip(label, val) {
    if (val == null) return `<span class="chip">${label} <b>—</b></span>`;
    return `<span class="chip">${label} <b>${inrShort(val)}</b></span>`;
}

function expandHtml(r) {
    const hist = storeHistory(r.store_slug);
    return `
        <div class="mini-rows">
            <div class="mini-stat">22K /10g<b>${r.gold_22k != null ? '₹' + (r.gold_22k * 10).toLocaleString('en-IN') : '—'}</b></div>
            <div class="mini-stat">24K /10g<b>${r.gold_24k != null ? '₹' + (r.gold_24k * 10).toLocaleString('en-IN') : '—'}</b></div>
            <div class="mini-stat">18K /10g<b>${r.gold_18k != null ? '₹' + (r.gold_18k * 10).toLocaleString('en-IN') : '—'}</b></div>
        </div>
        ${hist.length > 1 ? `<svg class="mini-spark" viewBox="0 0 300 56" preserveAspectRatio="none">${sparkPath(hist, 300, 56)}</svg>` : '<div class="mini-stat">History builds up daily.</div>'}
        ${r.store_url || r.source_url ? `<a class="visit" href="${r.store_url || r.source_url}" target="_blank" rel="noopener">Visit ${r.store_name} ↗</a>` : ''}`;
}

function renderTable(rows, min) {
    const k = KEY[state.purity];
    document.getElementById('table-body').innerHTML = rows.map((r, i) => {
        const best = r[k] != null && r[k] === min;
        return `
        <tr class="${best ? 'best-row' : ''}" onclick="window.open('${r.store_url || r.source_url || '#'}','_blank')">
            <td class="t-rank">${best ? '★' : i + 1}</td>
            <td><div class="t-store">${r.logo ? `<img class="store-logo" src="${r.logo}" onerror="this.remove()">` : ''}${r.store_name}</div></td>
            <td class="t-price ${state.purity === '22k' && best ? 'lead' : ''}">${cell(r.gold_22k)}</td>
            <td class="t-price ${state.purity === '24k' && best ? 'lead' : ''}">${cell(r.gold_24k)}</td>
            <td class="t-price ${state.purity === '18k' && best ? 'lead' : ''}">${cell(r.gold_18k)}</td>
            <td>${deltaHtml(r.change_22k, true)}</td>
            <td class="t-price">${r[k] != null ? '₹' + (r[k] * 10).toLocaleString('en-IN') : '—'}</td>
        </tr>`;
    }).join('');
}

const cell = v => v != null ? inr(v) : '<span style="color:var(--ink-faint)">—</span>';

function deltaHtml(d, inline) {
    if (d == null) return inline ? '<span style="color:var(--ink-faint)">—</span>' : '';
    if (d > 0) return `<span class="delta up">▲ ₹${Math.abs(d).toFixed(0)}</span>`;
    if (d < 0) return `<span class="delta down">▼ ₹${Math.abs(d).toFixed(0)}</span>`;
    return '<span class="delta flat">—</span>';
}

function toggleCard(el) { el.classList.toggle('open'); }

// ─────────── Purity segmented ───────────
function bindPurity() {
    document.querySelectorAll('.seg-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.seg-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.purity = btn.dataset.purity;
            positionSegInd();
            document.getElementById('chart-purity-label').textContent = state.purity.toUpperCase();
            render();
            loadChart();
        });
    });
    window.addEventListener('resize', positionSegInd);
}
function positionSegInd() {
    const active = document.querySelector('.seg-btn.active');
    const ind = document.getElementById('seg-ind');
    if (active && ind) { ind.style.width = active.offsetWidth + 'px'; ind.style.transform = `translateX(${active.offsetLeft - 4}px)`; }
}

// ─────────── Sparklines ───────────
function storeHistory(slug) {
    return state.history
        .filter(h => h.store_slug === slug && h[KEY[state.purity]] != null)
        .sort((a, b) => a.rate_date.localeCompare(b.rate_date))
        .map(h => h[KEY[state.purity]]);
}
function sparkPath(vals, w, h) {
    if (vals.length < 2) return '';
    const min = Math.min(...vals), max = Math.max(...vals), rng = max - min || 1;
    const pts = vals.map((v, i) => [i / (vals.length - 1) * w, h - 6 - ((v - min) / rng) * (h - 12)]);
    const d = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
    const area = d + ` L${w},${h} L0,${h} Z`;
    const up = vals[vals.length - 1] >= vals[0];
    const col = up ? '#e08070' : '#6fbf86';
    return `<path d="${area}" fill="${col}" opacity="0.1"/><path d="${d}" fill="none" stroke="${col}" stroke-width="2" stroke-linejoin="round"/>`;
}
function drawBenchSpark() {
    const c = document.getElementById('bm-spark');
    if (!c) return;
    const ctx = c.getContext('2d');
    ctx.clearRect(0, 0, c.width, c.height);
    const byDate = {}, k = KEY[state.purity];
    state.history.forEach(h => { if (h[k] != null) (byDate[h.rate_date] ||= []).push(h[k]); });
    const dates = Object.keys(byDate).sort();
    const vals = dates.map(d => byDate[d].reduce((a, b) => a + b, 0) / byDate[d].length);
    if (vals.length < 2) return;
    const min = Math.min(...vals), max = Math.max(...vals), rng = max - min || 1;
    ctx.beginPath();
    vals.forEach((v, i) => {
        const x = i / (vals.length - 1) * c.width;
        const y = c.height - 4 - ((v - min) / rng) * (c.height - 8);
        i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    });
    ctx.strokeStyle = '#f4d780'; ctx.lineWidth = 2; ctx.lineJoin = 'round'; ctx.stroke();
}

// ─────────── History chart ───────────
async function loadChart() {
    if (!state.history.length) return;
    const ctx = document.getElementById('history-chart');
    const k = KEY[state.purity];
    const byStore = {};
    state.history.forEach(h => { if (h[k] != null) (byStore[h.store_name] ||= []).push({ x: h.rate_date, y: h[k] }); });

    const palette = ['#f4d780', '#e08070', '#6fbf86', '#7fb0e0', '#c79ce0', '#e0a06f', '#7fd0c0', '#d0c060', '#e09cc0', '#9ce0a8'];
    const datasets = Object.entries(byStore).map(([name, pts], i) => ({
        label: name,
        data: pts.sort((a, b) => a.x.localeCompare(b.x)),
        borderColor: palette[i % palette.length],
        backgroundColor: palette[i % palette.length] + '18',
        borderWidth: 2, pointRadius: 1.5, pointHoverRadius: 5, tension: 0.35, fill: false,
    }));
    const labels = [...new Set(state.history.map(h => h.rate_date))].sort();

    if (chart) chart.destroy();
    chart = new Chart(ctx, {
        type: 'line',
        data: { labels, datasets },
        options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'bottom', labels: { color: '#c9bfa8', usePointStyle: true, padding: 14, font: { family: 'Manrope', size: 11 } } },
                tooltip: {
                    backgroundColor: '#1b160e', borderColor: 'rgba(212,175,55,0.3)', borderWidth: 1,
                    titleColor: '#f4d780', bodyColor: '#f3ecdc', padding: 12,
                    callbacks: { label: c => ` ${c.dataset.label}: ₹${c.parsed.y?.toLocaleString('en-IN')}` },
                },
            },
            scales: {
                x: { grid: { color: 'rgba(212,175,55,0.06)' }, ticks: { color: '#8e836b', maxRotation: 0, autoSkip: true, maxTicksLimit: 8, font: { family: 'JetBrains Mono', size: 10 } } },
                y: { grid: { color: 'rgba(212,175,55,0.06)' }, ticks: { color: '#8e836b', font: { family: 'JetBrains Mono', size: 10 }, callback: v => '₹' + v.toLocaleString('en-IN') } },
            },
        },
    });
}

// ─────────── Tabs ───────────
function switchTab(name) {
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
    document.querySelectorAll('.panel').forEach(p => p.classList.toggle('active', p.id === 'panel-' + name));
    if (name === 'history') loadChart();
}

// ─────────── Manual add ───────────
function renderManualStores() {
    const sel = document.getElementById('m-store');
    sel.innerHTML = '<option value="">Select store…</option>' +
        state.stores.map(s => `<option value='${JSON.stringify({ slug: s.slug, name: s.name })}'>${s.name}</option>`).join('') +
        '<option value=\'{"slug":"custom","name":"Other local jeweller"}\'>Other local jeweller…</option>';
}
async function submitManual(e) {
    e.preventDefault();
    const raw = document.getElementById('m-store').value;
    if (!raw) return;
    const store = JSON.parse(raw);
    const body = {
        store_slug: store.slug, store_name: store.name,
        gold_22k: parseFloat(document.getElementById('m-22k').value) || null,
        gold_24k: parseFloat(document.getElementById('m-24k').value) || null,
        gold_18k: parseFloat(document.getElementById('m-18k').value) || null,
        source_url: document.getElementById('m-url').value || 'manual',
    };
    if (!body.gold_22k && !body.gold_24k && !body.gold_18k) return showMsg('Enter at least one rate.', true);
    try {
        const r = await fetch('/api/rates/manual', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        if (r.ok) { showMsg('Saved!'); e.target.reset(); loadRates(); toast('Rate added'); }
        else { const er = await r.json(); showMsg(er.detail || 'Failed', true); }
    } catch { showMsg('Network error', true); }
}
function showMsg(m, err) {
    const el = document.getElementById('m-msg');
    el.textContent = m; el.className = 'form-msg ' + (err ? 'err' : 'ok'); el.style.display = 'block';
    setTimeout(() => el.style.display = 'none', 4000);
}

// ─────────── Refresh ───────────
async function refreshAll() {
    const btn = document.getElementById('refresh-btn');
    btn.classList.add('spinning');
    try {
        await fetch('/api/scrape', { method: 'POST' });
        await Promise.all([loadRates(), loadHistory()]);
        toast('Rates refreshed');
    } catch { toast('Refresh failed', true); }
    finally { btn.classList.remove('spinning'); }
}

// ─────────── Helpers ───────────
function inr(v) { return '₹' + Number(v).toLocaleString('en-IN', { maximumFractionDigits: 0 }); }
function inrShort(v) { return Number(v).toLocaleString('en-IN', { maximumFractionDigits: 0 }); }
function fmtDate(s) {
    const d = new Date(s + 'T00:00:00');
    return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}
function emptyState() {
    return `<div style="grid-column:1/-1;text-align:center;padding:50px 20px;color:var(--ink-mute);">
        <div style="font-size:2.4rem;margin-bottom:10px;">🪙</div>
        <div style="font-weight:700;color:var(--ink-soft);margin-bottom:4px;">No rates yet</div>
        <div style="font-size:0.86rem;">Tap refresh to pull live rates, or add a store manually.</div>
    </div>`;
}
function updateAgo() {
    const el = document.getElementById('updated-ago');
    if (!state.lastUpdated) { el.textContent = 'live'; return; }
    const then = new Date(state.lastUpdated.replace(' ', 'T') + 'Z');
    const mins = Math.round((Date.now() - then.getTime()) / 60000);
    el.textContent = mins < 1 ? 'just now' : mins < 60 ? `${mins}m ago` : `${Math.round(mins / 60)}h ago`;
}
function toast(m, err) {
    const t = document.getElementById('toast');
    t.textContent = m; t.className = 'toast show' + (err ? ' err' : '');
    setTimeout(() => t.className = 'toast' + (err ? ' err' : ''), 2600);
}
