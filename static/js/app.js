// ════════════════════════════════════════════
//  SONA — Live Gold Rates
//  Sona.* = data + helpers (fetch live rates, stats, sparkline, chart);
//  the IIFE at the bottom renders the page.
// ════════════════════════════════════════════
window.Sona = (function () {
    const KEY = { '22k': 'gold_22k', '24k': 'gold_24k', '18k': 'gold_18k' };
    const OTHERS = { '22k': ['24k', '18k'], '24k': ['22k', '18k'], '18k': ['22k', '24k'] };
    const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
    const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ESC[c]);
    const safeUrl = u => { const s = String(u ?? '').trim(); return /^https?:\/\//i.test(s) ? s : ''; };
    const inr = v => v == null ? '₹—' : '₹' + Number(v).toLocaleString('en-IN', { maximumFractionDigits: 0 });
    const inrShort = v => v == null ? '—' : Number(v).toLocaleString('en-IN', { maximumFractionDigits: 0 });
    const median = a => { const s = [...a].sort((x, y) => x - y); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
    const fullDate = s => { const d = new Date(s + 'T00:00:00'); return d.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' }); };
    const shortDate = s => { const d = new Date(s + 'T00:00:00'); return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }); };

    async function load() {
        const [t, h, s] = await Promise.all([
            fetch('/api/rates/today').then(r => r.json()).catch(() => ({ rates: [] })),
            fetch('/api/history?days=30').then(r => r.json()).catch(() => ({ history: [] })),
            fetch('/api/stores').then(r => r.json()).catch(() => ({ stores: [] })),
        ]);
        return { date: t.date, rates: t.rates || [], history: h.history || [], stores: s.stores || [] };
    }

    // Sorted store rows for a purity. mode: 'price-asc' | 'price-desc' | 'name'
    function sortedRates(rates, purity, mode = 'price-asc') {
        const k = KEY[purity]; const rows = [...rates];
        if (mode === 'price-asc') rows.sort((a, b) => (a[k] ?? 1e9) - (b[k] ?? 1e9));
        else if (mode === 'price-desc') rows.sort((a, b) => (b[k] ?? -1) - (a[k] ?? -1));
        else rows.sort((a, b) => a.store_name.localeCompare(b.store_name));
        return rows;
    }

    function stats(rates, purity) {
        const k = KEY[purity];
        const priced = rates.filter(r => r[k] != null);
        const vals = priced.map(r => r[k]);
        if (!vals.length) return { priced: [], vals: [], min: null, max: null, median: null, best: null, count: 0 };
        const min = Math.min(...vals), max = Math.max(...vals);
        const best = priced.reduce((a, b) => (a[k] < b[k] ? a : b));
        return { priced, vals, min, max, median: Math.round(median(vals)), best, count: priced.length };
    }

    function marketSeries(history, purity) {
        const k = KEY[purity], by = {};
        history.forEach(x => { if (x[k] != null) (by[x.rate_date] ||= []).push(x[k]); });
        return Object.keys(by).sort().map(d => ({ x: d, y: Math.round(median(by[d])) }));
    }

    // Crisp inline-SVG sparkline (returns inner markup for an existing <svg viewBox="0 0 w h">)
    function sparkSvg(vals, w, h, stroke, fill) {
        if (!vals || vals.length < 2) return '';
        const min = Math.min(...vals), max = Math.max(...vals), rng = max - min || 1;
        const pts = vals.map((v, i) => [i / (vals.length - 1) * w, h - 4 - ((v - min) / rng) * (h - 8)]);
        const line = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
        const area = line + ` L${w},${h} L0,${h} Z`;
        return (fill ? `<path d="${area}" fill="${fill}"/>` : '') +
            `<path d="${line}" fill="none" stroke="${stroke}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>`;
    }

    // Build the trend chart into a <canvas>. Returns the Chart instance (destroy before rebuild).
    function trendChart(canvas, history, purity, opts = {}) {
        if (typeof Chart === 'undefined' || !canvas) return null;  // never break the page if Chart.js failed to load
        const k = KEY[purity];
        const market = marketSeries(history, purity);
        const byStore = {};
        history.forEach(x => { if (x[k] != null) (byStore[x.store_name] ||= []).push({ x: x.rate_date, y: x[k] }); });
        const multi = Object.entries(byStore).filter(([, p]) => new Set(p.map(q => q.x)).size >= 2);
        const palette = ['#e8897a', '#74c78e', '#7fb0e0', '#c79ce0', '#e0a06f', '#7fd0c0'];
        const line = opts.line || '#f6dd8b';
        const ds = [];
        if (market.length >= 2) {
            ds.push({
                label: 'Market trend', data: market, borderColor: line,
                backgroundColor: opts.fill || 'rgba(244,215,128,0.12)',
                borderWidth: 3, pointRadius: 0, pointHoverRadius: 5, tension: 0.38, fill: 'origin', spanGaps: true,
            });
        }
        multi.forEach(([n, p], i) => ds.push({
            label: n, data: p.sort((a, b) => a.x.localeCompare(b.x)),
            borderColor: palette[i % palette.length], borderWidth: 1.5, pointRadius: 0, pointHoverRadius: 4,
            tension: 0.38, fill: false, spanGaps: true,
        }));
        const labels = [...new Set(history.map(x => x.rate_date))].sort();
        const tick = opts.tick || '#9d9177', grid = opts.grid || 'rgba(212,175,55,0.06)';
        return new Chart(canvas, {
            type: 'line', data: { labels, datasets: ds },
            options: {
                responsive: true, maintainAspectRatio: false,
                animation: opts.animate === false ? false : { duration: 900, easing: 'easeOutCubic' },
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { display: opts.legend !== false, position: 'bottom', labels: { color: tick, usePointStyle: true, pointStyle: 'line', boxWidth: 20, padding: 12, font: { family: 'Manrope', size: 10 } } },
                    tooltip: { backgroundColor: '#1a140c', borderColor: 'rgba(212,175,55,0.3)', borderWidth: 1, titleColor: '#f6dd8b', bodyColor: '#f4eddc', padding: 10, callbacks: { title: it => it.length ? shortDate(it[0].label) : '', label: c => ' ' + c.dataset.label + ': ₹' + (c.parsed.y == null ? '' : c.parsed.y.toLocaleString('en-IN')) } },
                },
                scales: {
                    x: { grid: { color: grid }, ticks: { color: tick, maxRotation: 0, autoSkip: true, maxTicksLimit: 6, font: { family: 'Manrope', size: 10 }, callback: function (v) { return shortDate(this.getLabelForValue(v)); } } },
                    y: { grid: { color: grid }, ticks: { color: tick, maxTicksLimit: 6, font: { family: 'JetBrains Mono', size: 10 }, callback: v => '₹' + v.toLocaleString('en-IN') } },
                },
            },
        });
    }

    // Purity segmented control helper: wires buttons[data-purity] and calls onChange(purity)
    function bindPurity(container, onChange) {
        container.querySelectorAll('[data-purity]').forEach(btn => {
            btn.addEventListener('click', () => {
                container.querySelectorAll('[data-purity]').forEach(b => { b.classList.remove('active'); b.setAttribute('aria-pressed', 'false'); });
                btn.classList.add('active'); btn.setAttribute('aria-pressed', 'true');
                onChange(btn.dataset.purity);
            });
        });
    }

    return { KEY, OTHERS, esc, safeUrl, inr, inrShort, median, fullDate, shortDate, load, sortedRates, stats, marketSeries, sparkSvg, trendChart, bindPurity };
})();

// ─────────── Page render (editorial layout) ───────────
(function () {
    var REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var chart;

    var el = {
        ebDate: document.getElementById('eb-date'),
        num: document.getElementById('hero-num'),
        best: document.getElementById('hero-best'),
        spark: document.getElementById('hero-spark'),
        median: document.getElementById('stat-median'),
        spread: document.getElementById('stat-spread'),
        count: document.getElementById('stat-count'),
        stores: document.getElementById('stores'),
        chartCap: document.getElementById('chart-cap'),
    };

    function purityLabel(p) { return p.toUpperCase(); }

    function heroBestHtml(best, purity) {
        if (!best) return '<span class="sep">No live rate available</span>';
        var name = Sona.esc(best.store_name);
        var logo = Sona.safeUrl(best.logo);
        var img = logo ? '<img class="b-logo" src="' + logo + '" alt="" loading="lazy" onerror="this.remove()">' : '';
        return img + '<span>best ' + purityLabel(purity) + '</span><span class="sep">·</span><b>' + name + '</b>';
    }

    function othersHtml(r, purity) {
        return Sona.OTHERS[purity].map(function (p) {
            return '<span class="opair">' + p.toUpperCase() + ' <b>' + Sona.inrShort(r[Sona.KEY[p]]) + '</b></span>';
        }).join('<span class="odiv">·</span>');
    }

    function changeHtml(r, purity) {
        var c = r['change_' + purity];
        if (c == null || c === 0) return '';
        var up = c > 0;
        var arrow = up ? '&#9650;' : '&#9660;';
        return '<span class="chg ' + (up ? 'up' : 'down') + '">' + arrow + ' ' + Sona.inrShort(Math.abs(c)) + '</span>';
    }

    function cardHtml(r, purity, k, min, idx) {
        var v = r[k];
        var url = Sona.safeUrl(r.store_url || r.source_url);
        var tag = url ? 'a' : 'div';
        var href = url ? ' href="' + url + '" target="_blank" rel="noopener noreferrer"' : '';
        var isBest = idx === 0 && v != null && v === min;
        var name = Sona.esc(r.store_name);

        var logoUrl = Sona.safeUrl(r.logo);
        var initial = Sona.esc(((r.store_name || '?').trim().charAt(0) || '?').toUpperCase());
        var logo = '<div class="c-logo"><span class="ini">' + initial + '</span>'
            + (logoUrl ? '<img src="' + logoUrl + '" alt="" loading="lazy" onerror="this.remove()">' : '')
            + '</div>';

        var metaBits = [];
        if (v == null) {
            metaBits.push('<span class="vs na">No live rate</span>');
        } else if (isBest) {
            metaBits.push('<span class="tag-best">Best price</span>');
        } else if (v === min) {
            metaBits.push('<span class="vs">Matches best</span>');
        } else {
            metaBits.push('<span class="vs">+' + Sona.inr(v - min) + ' vs best</span>');
        }
        var ch = changeHtml(r, purity);
        if (ch) metaBits.push(ch);

        var priceCls = v == null ? 'c-price na' : 'c-price';
        var priceTxt = Sona.inr(v);

        return '<' + tag + ' class="card' + (isBest ? ' best' : '') + '"' + href + '>'
            + logo
            + '<div class="c-main">'
            + '<div class="c-name">' + name + '</div>'
            + '<div class="c-meta">' + metaBits.join('') + '</div>'
            + '<div class="c-others">' + othersHtml(r, purity) + '</div>'
            + '</div>'
            + '<div class="c-price-wrap"><div class="' + priceCls + ' num">' + priceTxt + '</div></div>'
            + '</' + tag + '>';
    }

    function render(d, purity) {
        var k = Sona.KEY[purity];
        var s = Sona.stats(d.rates, purity);

        el.num.textContent = Sona.inr(s.min);
        el.best.innerHTML = heroBestHtml(s.best, purity);

        var series = Sona.marketSeries(d.history, purity).map(function (p) { return p.y; });
        if (series.length >= 2) {
            el.spark.innerHTML = '<svg viewBox="0 0 320 44" preserveAspectRatio="none" role="img" aria-label="Recent market trend">'
                + Sona.sparkSvg(series, 320, 44, '#fbbf24', 'rgba(251,191,36,0.12)') + '</svg>';
        } else { el.spark.innerHTML = ''; }

        el.median.textContent = Sona.inr(s.median);
        el.spread.textContent = Sona.inr(s.max != null ? s.max - s.min : null);
        el.count.textContent = s.count;

        var rows = Sona.sortedRates(d.rates, purity, 'price-asc');
        el.stores.innerHTML = rows.map(function (r, i) { return cardHtml(r, purity, k, s.min, i); }).join('');

        el.chartCap.textContent = 'Median · ' + purity.toUpperCase();
        if (chart) chart.destroy();
        chart = Sona.trendChart(document.getElementById('chart'), d.history, purity, {
            line: '#fbbf24', fill: 'rgba(251,191,36,0.14)', tick: '#a1a1aa', grid: 'rgba(255,255,255,0.06)',
            animate: !REDUCED
        });
    }

    var currentPurity = '22k';
    var data = null;

    function paint() { if (data) render(data, currentPurity); }

    // Wire the purity toggle up-front so it responds even while data is loading.
    Sona.bindPurity(document.getElementById('purity'), function (p) { currentPurity = p; paint(); });

    // Returns true once real rates are present. On a cold start the server's
    // database is still being filled by the first scrape, so rates arrive empty
    // for the first ~30–60s — show a "fetching" state instead of looking dead.
    function load(isRetry) {
        return Sona.load().then(function (d) {
            data = d;
            el.ebDate.textContent = d.date ? Sona.fullDate(d.date) : '—';
            if (d.rates.length) { paint(); return true; }
            el.num.textContent = '₹—';
            el.best.innerHTML = '<span class="sep">Fetching live rates… the first load can take up to a minute.</span>';
            return false;
        }).catch(function () {
            if (!isRetry) el.best.innerHTML = '<span class="sep">Live rates are unavailable right now.</span>';
            return false;
        });
    }

    load(false).then(function (ok) {
        if (ok) return;
        var tries = 0;
        var timer = setInterval(function () {
            tries++;
            load(true).then(function (done) { if (done || tries >= 18) clearInterval(timer); });
        }, 5000);  // poll every 5s for ~90s until the scrape lands
    });
})();
