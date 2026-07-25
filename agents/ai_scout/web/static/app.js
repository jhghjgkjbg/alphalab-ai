(() => {
  const currentPath = location.pathname === '/en' ? '/en' : location.pathname === '/ru' ? '/ru' : '/';
  const currentLanguage = currentPath === '/en' ? 'en' : currentPath === '/ru' ? 'ru' : '';
  document.querySelectorAll('.site-nav a').forEach(link => {
    if (link.getAttribute('href') === currentPath) link.classList.add('active');
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
    if (currentLanguage) p.set('language', currentLanguage);
    if ($('category').value) p.set('category', $('category').value);
    if ($('source').value) p.set('source', $('source').value);
    try {
      const r = await fetch('/api/articles?' + p, { signal: controller.signal });
      if (!r.ok) throw Error('API request failed');
      let d = await r.json();
      if (currentLanguage === 'ru' && !d.total) {
        const fallbackParams = new URLSearchParams(p);
        fallbackParams.delete('language');
        const fallbackResponse = await fetch('/api/articles?' + fallbackParams, { signal: controller.signal });
        if (!fallbackResponse.ok) throw Error('API request failed');
        d = await fallbackResponse.json();
      }
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
  function render(x) { const card = document.createElement('article'); card.className = 'card'; const h = document.createElement('h2'); h.textContent = x.title || 'Untitled'; const p = document.createElement('p'); p.textContent = x.summary || ''; const m = document.createElement('div'); m.className = 'meta'; m.textContent = `${x.source || ''} · ${x.category || ''} · ${x.published_at || ''}`; const s = document.createElement('div'); s.className = 'score'; s.textContent = `AI Scout score ${Math.round((x.score || 0) * 100)}/100`; const a = document.createElement('a'); a.href = '/article/' + encodeURIComponent(x.id); a.textContent = 'Read article'; const o = document.createElement('a'); o.href = x.url || '#'; o.target = '_blank'; o.rel = 'noopener'; o.textContent = 'Original source'; card.append(h, p, m, s, a, o); list.append(card); }
  $('search').addEventListener('input', () => { clearTimeout(state.searchTimer); state.searchTimer = setTimeout(() => load(true), 350); });
  ['category', 'source', 'sort'].forEach(id => $(id).addEventListener('change', () => load(true)));
  more.addEventListener('click', () => { state.page++; load(false); });
  fetch('/api/categories').then(r => r.json()).then(d => Object.keys(d).forEach(x => option($('category'), x))).catch(() => {});
  fetch('/api/sources').then(r => r.json()).then(d => Object.keys(d).forEach(x => option($('source'), x))).catch(() => {});
  load();
})();
