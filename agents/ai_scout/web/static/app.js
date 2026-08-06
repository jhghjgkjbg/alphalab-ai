(() => {
  const trackAnalyticsEvent = (eventType, payload = {}) => {
    const allowed = new Set(['article_id', 'source', 'category', 'referrer_group', 'utm_source', 'utm_medium', 'utm_campaign']);
    const body = { event_type: eventType };
    const query = new URLSearchParams(location.search);
    ['utm_source', 'utm_medium', 'utm_campaign'].forEach(key => { const value = query.get(key); if (value) payload[key] = value.toLowerCase().replace(/[^a-z0-9_-]/g, '').slice(0, 100); });
    Object.keys(payload).forEach(key => { if (allowed.has(key) && typeof payload[key] === 'string') body[key] = payload[key].slice(0, 120); });
    try {
      const data = JSON.stringify(body);
      if (navigator.sendBeacon && navigator.sendBeacon('/api/analytics/event', new Blob([data], { type: 'application/json' }))) return;
      fetch('/api/analytics/event', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: data, keepalive: true }).catch(() => {});
    } catch (_) {}
  };
  window.trackAnalyticsEvent = trackAnalyticsEvent;
  if (!document.documentElement.dataset.analyticsBound) {
    document.documentElement.dataset.analyticsBound = '1';
    document.addEventListener('click', event => {
      const target = event.target.closest('[data-analytics-event], .card a, .article-actions a, a');
      if (!target) return;
      let type = target.dataset.analyticsEvent;
      if (!type && target.textContent.trim() === 'Original source') type = 'original_source_click';
      if (!type && target.textContent.trim() === 'Join Telegram') type = 'telegram_click';
      if (!type && target.textContent.trim() === 'Open RSS Feed') type = 'rss_click';
      if (!type) return;
      const payload = {};
      if (target.dataset.articleId) payload.article_id = target.dataset.articleId;
      if (type === 'original_source_click' && !payload.article_id) payload.article_id = target.closest('article')?.querySelector('a[href^="/article/"]')?.getAttribute('href')?.split('/').pop() || '';
      if (target.dataset.source) payload.source = target.dataset.source;
      if (target.dataset.category) payload.category = target.dataset.category;
      trackAnalyticsEvent(type, payload);
    }, { passive: true });
    document.addEventListener('submit', event => {
      if (event.target.id === 'subscribe-form') {
        trackAnalyticsEvent('subscribe_submit');
        const status = document.getElementById('subscribe-status');
        if (status && !status.dataset.analyticsSuccessBound) {
          status.dataset.analyticsSuccessBound = '1';
          new MutationObserver(() => { if (/^Check your inbox/i.test(status.textContent) && !status.dataset.analyticsSuccess) { status.dataset.analyticsSuccess = '1'; trackAnalyticsEvent('subscribe_success'); } }).observe(status, { childList: true, characterData: true, subtree: true });
        }
      }
    }, { passive: true });
  }
  const applyTheme = theme => { document.documentElement.dataset.theme = theme; localStorage.setItem('alphalab-theme', theme); };
  const savedTheme = localStorage.getItem('alphalab-theme');
  if (savedTheme === 'dark' || savedTheme === 'light') applyTheme(savedTheme);
  const header = document.querySelector('.site-header__inner');
  if (header && !document.getElementById('theme-toggle')) {
    const toggle = document.createElement('button'); toggle.id = 'theme-toggle'; toggle.type = 'button'; toggle.className = 'theme-toggle'; toggle.setAttribute('aria-label', 'Toggle dark mode'); toggle.textContent = savedTheme === 'dark' ? '☀' : '☾';
    toggle.addEventListener('click', () => { const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'; applyTheme(next); toggle.textContent = next === 'dark' ? '☀' : '☾'; }); header.append(toggle);
  }
  document.querySelectorAll('.site-nav a').forEach(link => {
    if (link.getAttribute('href') === '/') link.classList.add('active');
  });
  const state = { page: 1, limit: 12, controller: null, requestId: 0, searchTimer: null };
  const $ = id => document.getElementById(id);
  const status = $('status'), list = $('articles'), more = $('load-more'), search = $('search');
  if (!status || !list || !more || !search) return;
  search.setAttribute('aria-label', 'Search articles');
  const clearSearch = document.createElement('button');
  clearSearch.type = 'button'; clearSearch.className = 'search-clear'; clearSearch.setAttribute('aria-label', 'Clear search'); clearSearch.textContent = '×'; clearSearch.hidden = true;
  search.insertAdjacentElement('afterend', clearSearch);
  const syncClear = () => { clearSearch.hidden = !search.value; };
  const resetFilters = () => { clearTimeout(state.searchTimer); search.value = ''; $('category').value = ''; $('source').value = ''; $('sort').value = 'latest'; syncClear(); load(true); };
  const showEmpty = () => { const e = document.createElement('div'); e.className = 'empty'; e.setAttribute('role', 'status'); e.setAttribute('aria-live', 'polite'); const h = document.createElement('h2'); h.textContent = 'No articles found'; const x = document.createElement('p'); x.textContent = 'Try another search or reset filters.'; const b = document.createElement('button'); b.type = 'button'; b.className = 'empty-clear'; b.textContent = 'Clear filters'; b.addEventListener('click', resetFilters); e.append(h, x, b); list.append(e); };
  function option(select, value) { const o = document.createElement('option'); o.value = value; o.textContent = value; select.appendChild(o); }
  async function load(reset = true) {
    if (state.controller) state.controller.abort();
    const controller = new AbortController(); const requestId = ++state.requestId; state.controller = controller;
    if (reset) { state.page = 1; list.replaceChildren(); }
    more.disabled = true; more.textContent = 'Loading...'; list.setAttribute('aria-busy', 'true'); status.textContent = 'Loading articles…';
    const p = new URLSearchParams({ page: state.page, limit: state.limit, sort: $('sort').value });
    const q = search.value.trim(); if (q) p.set('q', q);
    if ($('category').value) p.set('category', $('category').value);
    if ($('source').value) p.set('source', $('source').value);
    try {
      const r = await fetch('/api/articles?' + p, { signal: controller.signal });
      if (!r.ok) throw Error('API request failed');
      const d = await r.json();
      if (requestId !== state.requestId) return;
      if (reset && !d.items.length) { showEmpty(); status.textContent = 'No articles found'; more.hidden = true; }
      else if (!d.items.length) { status.textContent = 'No more articles'; more.hidden = true; }
      else { d.items.forEach(render); status.textContent = `${d.total} published articles`; more.hidden = state.page * state.limit >= d.total; }
    } catch (e) {
      if (e.name !== 'AbortError' && requestId === state.requestId) { status.textContent = 'Unable to load articles. Please try again.'; more.hidden = true; }
    } finally {
      if (requestId === state.requestId) { list.setAttribute('aria-busy', 'false'); more.disabled = false; more.textContent = 'Load more'; }
    }
  }
  function relativeTime(value) { const date = new Date(value); if (Number.isNaN(date.getTime())) return value || ''; const minutes = Math.max(0, Math.floor((Date.now() - date.getTime()) / 60000)); if (minutes < 1) return 'just now'; if (minutes < 60) return `${minutes} min ago`; const hours = Math.floor(minutes / 60); if (hours < 24) return `${hours} hours ago`; return `${Math.floor(hours / 24)} days ago`; }
  function validImage(value) { try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) ? url.href : ''; } catch (_) { return ''; } }
  const sourceLabels = { hacker_news: 'Hacker News', openai_news: 'OpenAI', github_blog: 'GitHub Blog', huggingface_blog: 'Hugging Face', microsoft_research: 'Microsoft Research', cloudflare_blog: 'Cloudflare Blog', linux_foundation: 'Linux Foundation', jetbrains_blog: 'JetBrains Blog', gitlab_blog: 'GitLab Blog', python_insider: 'Python Insider', eclipse_foundation: 'Eclipse Foundation', arxiv: 'arXiv', devto: 'Dev.to', lobsters: 'Lobsters', dockerhub: 'Docker Hub' };
  const displaySource = value => sourceLabels[String(value || '').toLowerCase()] || String(value || '').replace(/[_-]+/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  function highlights(value) { const parts = String(value || '').match(/[^.!?]+[.!?]+|[^.!?]+$/g) || []; return parts.map(part => part.trim()).filter(Boolean).slice(0, 2).map(part => { if (part.length <= 150) return part; const cut = part.slice(0, 150).lastIndexOf(' '); return (cut > 20 ? part.slice(0, cut) : part.slice(0, 150)).trim(); }); }
  function render(x) { const card = document.createElement('article'); card.className = 'card'; const image = validImage(x.image_url); if (image) { const img = document.createElement('img'); img.className = 'card-image'; img.src = image; img.alt = x.title || 'Article image'; img.loading = 'lazy'; card.append(img); } else { const visual = document.createElement('div'); visual.className = 'card-visual-fallback'; visual.setAttribute('aria-hidden', 'true'); card.append(visual); } const h = document.createElement('h2'); h.textContent = x.title || 'Untitled'; const points = highlights(x.summary); const p = document.createElement('p'); p.textContent = x.summary || ''; const preview = points.length >= 2 ? document.createElement('ul') : p; if (points.length >= 2) { preview.className = 'card-highlights'; points.forEach(point => { const li = document.createElement('li'); li.textContent = point; preview.append(li); }); } const m = document.createElement('div'); m.className = 'meta'; if (x.category) { const badge = document.createElement('span'); badge.className = 'category-badge category-' + String(x.category).toLowerCase().replace(/[^a-z0-9]+/g, '-'); badge.textContent = x.category; m.append(badge); } if (x.source) { const source = document.createElement('span'); source.className = 'source'; source.textContent = displaySource(x.source); m.append(source); } const time = relativeTime(x.published_at); if (time) { const stamp = document.createElement('time'); stamp.dateTime = x.published_at || ''; stamp.textContent = time; m.append(stamp); } const s = document.createElement('div'); const score = Math.round((Number(x.score) || 0) * 100); s.className = `score-badge ${score < 40 ? 'low' : score < 70 ? 'medium' : score < 85 ? 'high' : 'excellent'}`; s.textContent = `Editorial score ${score}/100`; const a = document.createElement('a'); a.href = '/article/' + encodeURIComponent(x.id); a.textContent = 'Read article'; const o = document.createElement('a'); o.href = x.url || '#'; o.target = '_blank'; o.rel = 'noopener'; o.textContent = 'Original source'; card.append(h, preview, m, s, a, o); list.append(card); }
  search.addEventListener('input', () => { syncClear(); clearTimeout(state.searchTimer); state.searchTimer = setTimeout(() => load(true), 280); });
  search.addEventListener('keydown', event => { if (event.key === 'Enter') event.preventDefault(); if (event.key === 'Escape') { event.preventDefault(); resetFilters(); } });
  clearSearch.addEventListener('click', resetFilters);
  ['category', 'source', 'sort'].forEach(id => $(id).addEventListener('change', () => { clearTimeout(state.searchTimer); load(true); }));
  more.addEventListener('click', () => { state.page++; load(false); });
  fetch('/api/categories').then(r => r.json()).then(d => Object.keys(d).forEach(x => option($('category'), x))).catch(() => {});
  fetch('/api/sources').then(r => r.json()).then(d => Object.keys(d).forEach(x => option($('source'), x))).catch(() => {});
  load();
})();
