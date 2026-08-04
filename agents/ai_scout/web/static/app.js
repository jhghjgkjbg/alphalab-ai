(() => {
  document.querySelectorAll('.site-nav a').forEach(link => {
    if (link.getAttribute('href') === '/') link.classList.add('active');
  });
  const state = { page: 1, limit: 12, controller: null, requestId: 0, searchTimer: null };
  const $ = id => document.getElementById(id);
  const status = $('status'), list = $('articles'), more = $('load-more');
  function option(select, value) { const o = document.createElement('option'); o.value = value; o.textContent = value; select.appendChild(o); }
  async function load(reset = true) {
    if (state.controller) state.controller.abort();
    const controller = new AbortController(); const requestId = ++state.requestId; state.controller = controller;
    if (reset) { state.page = 1; list.replaceChildren(); }
    more.disabled = true; list.setAttribute('aria-busy', 'true'); status.textContent = 'Loading articles…';
    const p = new URLSearchParams({ page: state.page, limit: state.limit, sort: $('sort').value });
    const q = $('search').value.trim(); if (q) p.set('q', q);
    if ($('category').value) p.set('category', $('category').value);
    if ($('source').value) p.set('source', $('source').value);
    try {
      const r = await fetch('/api/articles?' + p, { signal: controller.signal });
      if (!r.ok) throw Error('API request failed');
      const d = await r.json();
      if (requestId !== state.requestId) return;
      if (reset && !d.total) { const e = document.createElement('div'); e.className = 'empty'; const h = document.createElement('h2'); h.textContent = 'No published articles yet'; const x = document.createElement('p'); x.textContent = 'Run the AI Scout pipeline to publish the first article.'; e.append(h, x); list.append(e); }
      else if (!d.items.length) status.textContent = 'No results';
      else { d.items.forEach(render); status.textContent = `${d.total} published articles`; more.hidden = state.page * state.limit >= d.total; }
    } catch (e) {
      if (e.name !== 'AbortError' && requestId === state.requestId) { status.textContent = 'Unable to load articles. Please try again.'; more.hidden = true; }
    } finally {
      if (requestId === state.requestId) { list.setAttribute('aria-busy', 'false'); more.disabled = false; }
    }
  }
  function relativeTime(value) { const date = new Date(value); if (Number.isNaN(date.getTime())) return value || ''; const minutes = Math.max(0, Math.floor((Date.now() - date.getTime()) / 60000)); if (minutes < 1) return 'just now'; if (minutes < 60) return `${minutes} min ago`; const hours = Math.floor(minutes / 60); if (hours < 24) return `${hours} hours ago`; return `${Math.floor(hours / 24)} days ago`; }
  function validImage(value) { try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) ? url.href : ''; } catch (_) { return ''; } }
  function render(x) { const card = document.createElement('article'); card.className = 'card'; const image = validImage(x.image_url); if (image) { const img = document.createElement('img'); img.className = 'card-image'; img.src = image; img.alt = ''; img.loading = 'lazy'; card.append(img); } const h = document.createElement('h2'); h.textContent = x.title || 'Untitled'; const p = document.createElement('p'); p.textContent = x.summary || ''; const m = document.createElement('div'); m.className = 'meta'; if (x.category) { const badge = document.createElement('span'); badge.className = 'category-badge category-' + String(x.category).toLowerCase().replace(/[^a-z0-9]+/g, '-'); badge.textContent = x.category; m.append(badge); } if (x.source) { const source = document.createElement('span'); source.className = 'source'; source.textContent = x.source; m.append(source); } const time = relativeTime(x.published_at); if (time) { const stamp = document.createElement('time'); stamp.dateTime = x.published_at || ''; stamp.textContent = time; m.append(stamp); } const s = document.createElement('div'); const score = Math.round((Number(x.score) || 0) * 100); s.className = `score-badge ${score < 40 ? 'low' : score < 70 ? 'medium' : score < 85 ? 'high' : 'excellent'}`; s.textContent = `AI Scout ${score}/100`; const a = document.createElement('a'); a.href = '/article/' + encodeURIComponent(x.id); a.textContent = 'Read article'; const o = document.createElement('a'); o.href = x.url || '#'; o.target = '_blank'; o.rel = 'noopener'; o.textContent = 'Original source'; card.append(h, p, m, s, a, o); list.append(card); }
  $('search').addEventListener('input', () => { clearTimeout(state.searchTimer); state.searchTimer = setTimeout(() => load(true), 350); });
  ['category', 'source', 'sort'].forEach(id => $(id).addEventListener('change', () => load(true)));
  more.addEventListener('click', () => { state.page++; load(false); });
  fetch('/api/categories').then(r => r.json()).then(d => Object.keys(d).forEach(x => option($('category'), x))).catch(() => {});
  fetch('/api/sources').then(r => r.json()).then(d => Object.keys(d).forEach(x => option($('source'), x))).catch(() => {});
  load();
})();
