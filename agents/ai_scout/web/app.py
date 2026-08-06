from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.responses import PlainTextResponse, Response
from html import escape
import json, os, re, hashlib, secrets, smtplib
from email.message import EmailMessage
from datetime import timedelta
from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import quote, unquote
from fastapi.staticfiles import StaticFiles
from core.api import PublishedArticlesStore

_HTMLResponse = HTMLResponse
_UNIFIED_HEADER = "<header class='site-header'><div class='site-header__inner'><a class='site-brand' href='/' aria-label='AlphaLab AI home'><span class='site-brand__mark' aria-hidden='true'>A</span><span class='site-brand__text'><strong>AlphaLab AI</strong><small>Signal, not noise.</small></span></a><nav class='site-nav' aria-label='Primary navigation'><a href='/'>Latest News</a><a href='/about'>About</a><a href='/subscribe'>Subscribe</a></nav></div></header>"
_UNIFIED_FOOTER = "<footer class='site-footer'><div class='container footer-inner'><div class='footer-brand-block'><a class='footer-brand' href='/' aria-label='AlphaLab AI home'><strong>AlphaLab AI</strong></a><p>Signal, not noise.</p></div><nav class='footer-links' aria-label='Footer navigation'><a href='/'>Latest News</a><a href='/about'>About</a><a href='/subscribe'>Subscribe</a><a href='/rss'>RSS Feed</a></nav></div></footer>"

class HTMLResponse(_HTMLResponse):
    def __init__(self, content="", *args, **kwargs):
        if isinstance(content, str):
            content = content.replace("AlphaLab AI also publishes updates through dedicated English and Russian Telegram channels.", "AlphaLab AI also publishes updates through the official English Telegram channel.")
        if isinstance(content, str) and "site-header" in content and "<body" in content:
            header_marker = "<header class='site-header'>" if "<header class='site-header'>" in content else '<header class="site-header">'
            start, end = content.find(header_marker), content.find("</header>")
            if start >= 0 and end >= start:
                content = content[:start] + _UNIFIED_HEADER + content[end + len("</header>"):]
            footer_marker = "<footer class='site-footer'>" if "<footer class='site-footer'>" in content else '<footer class="site-footer">'
            footer_start = content.find(footer_marker)
            if footer_start >= 0:
                content = content[:footer_start] + _UNIFIED_FOOTER + content[content.find("</footer>", footer_start) + len("</footer>"):]
            content = content.replace("</header>", "<button id='theme-toggle' class='theme-toggle' type='button' aria-label='Toggle dark mode'>☾</button></header>", 1)
            theme_script = "<script>(function(){try{var t=localStorage.getItem('alphalab-theme');if(t==='dark'||t==='light')document.documentElement.dataset.theme=t;var b=document.getElementById('theme-toggle');if(b&&!b.dataset.bound){b.dataset.bound='1';b.addEventListener('click',function(){var n=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=n;localStorage.setItem('alphalab-theme',n);b.textContent=n==='dark'?'☀':'☾';});}}catch(e){}})();</script>"
            content = content.replace("</head>", theme_script + "<script src='/static/app.js' defer></script></head>", 1)
        if isinstance(content, str) and "<h1>Subscribe to AlphaLab AI</h1>" in content and "id='subscribe-form'" not in content:
            content = content.replace("http://127.0.0.1:8080", "https://alphalabai.online")
            content = content.replace("<h2>Telegram</h2><p>AlphaLab AI also publishes updates through the official English Telegram channel.</p>", "<h2>Telegram</h2><p>Follow AlphaLab AI Scout on Telegram for real-time AI news.</p><p><a class='button primary' href='https://t.me/alphalabai_en' target='_blank' rel='noopener noreferrer'>Join Telegram</a></p>")
            form = "<form id='subscribe-form' class='subscribe-form' novalidate><label for='subscriber-email'>Email</label><input id='subscriber-email' name='email' type='email' placeholder='your@email.com' required maxlength='254' autocomplete='email'><label class='consent-label'><input name='consent' type='checkbox' required> I agree to receive AlphaLab AI updates by email.</label><button class='button primary' type='submit'>Subscribe</button><p id='subscribe-status' role='status' aria-live='polite'></p></form><script>(function(){const f=document.getElementById('subscribe-form'),s=document.getElementById('subscribe-status');f.addEventListener('submit',async function(e){e.preventDefault();s.textContent='Subscribing...';const b=f.querySelector('button');b.disabled=true;try{if(!f.email.value.trim()){s.textContent='Please enter a valid email.';return;}if(!f.consent.checked){s.textContent='Please accept the subscription consent.';return;}const r=await fetch('/api/subscribe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:f.email.value,consent:f.consent.checked})});const d=await r.json();if(!r.ok){s.textContent=r.status===422?(f.email.validity.valid?'Please accept the subscription consent.':'Please enter a valid email.'):(d.detail||'Unable to subscribe right now.');return;}s.textContent=d.already_subscribed?'You\'re already subscribed.':(d.pending?'Check your inbox. We sent you a confirmation link.':'Check your inbox.');f.reset();}catch(err){s.textContent='Unable to subscribe right now.';}finally{b.disabled=false;}})})();</script>"
            content = content.replace("</article>", form + "</article>", 1)
            content = re.sub(r"<p class='feed-url'>.*?</p>", "", content, count=1)
        super().__init__(content, *args, **kwargs)

def create_app(store=None, email_sender=None):
    app=FastAPI(title="AI Scout", docs_url=None, redoc_url=None)
    admin_sessions = set(); admin_failures = {}
    root = Path(__file__).resolve().parents[3]
    app.mount("/static", StaticFiles(directory=str(Path(__file__).with_name("static"))), name="static")
    if store is None:
        try:
            from core.storage import SQLitePublishedArticlesStore
            store = SQLitePublishedArticlesStore()
        except Exception:
            store = PublishedArticlesStore(path=root / "runtime" / "published_articles.json")
    if hasattr(store, "purge_analytics"):
        try: store.purge_analytics(int(os.getenv("ALPHALAB_ANALYTICS_RETENTION_DAYS", "90")))
        except Exception: pass
    if hasattr(store, "purge_telegram_delivery"):
        try: days=int(os.getenv("TELEGRAM_DELIVERY_RETENTION_DAYS", "90")); days=days if days > 0 else 90; store.purge_telegram_delivery(days)
        except Exception: pass
    def _api_row(row):
        return {key: value for key, value in row.items() if key != "en_body"}
    analytics_limit = {}
    def record_event(event_type, **fields):
        if hasattr(store, "record_analytics_event"):
            try: store.record_analytics_event(event_type, **fields)
            except Exception: pass
    def request_context(request):
        from urllib.parse import urlparse, parse_qs
        ref=str(request.headers.get("referer") or "").lower(); host=urlparse(ref).netloc
        group="direct" if not host else next((x for x in ("google","bing","telegram","reddit","github") if x in host), "internal" if host and request.url.hostname in host else "social" if host else "other")
        query=parse_qs(str(request.url.query)); clean=lambda k: re.sub(r"[^a-z0-9_\-]", "", (query.get(k,[""])[0] or "").strip().lower())[:100]
        return {"referrer_group":group,"utm_source":clean("utm_source"),"utm_medium":clean("utm_medium"),"utm_campaign":clean("utm_campaign")}
    @app.get("/api/health")
    def health(): return {"status":"ok","articles":store.count() if hasattr(store,"count") else len(store._items),"storage":"sqlite" if hasattr(store,"database") else "json"}
    @app.post("/api/analytics/event", status_code=204)
    async def analytics_event(request: Request):
        if int(request.headers.get("content-length", "0") or 0) > 4096: raise HTTPException(413, "request too large")
        try: payload=await request.json()
        except Exception: raise HTTPException(400, "invalid event")
        allowed={"original_source_click","subscribe_submit","subscribe_success","telegram_click","rss_click"}
        if not isinstance(payload, dict) or payload.get("event_type") not in allowed: raise HTTPException(422, "invalid event")
        record_event(payload["event_type"], article_id=str(payload.get("article_id") or "")[:200], source=str(payload.get("source") or "")[:120], category=str(payload.get("category") or "")[:120], referrer_group=str(payload.get("referrer_group") or "direct")[:20], utm_source=str(payload.get("utm_source") or "")[:100].lower(), utm_medium=str(payload.get("utm_medium") or "")[:100].lower(), utm_campaign=str(payload.get("utm_campaign") or "")[:100].lower())
        return Response(status_code=204)
    @app.get("/api/articles")
    def articles(page:int=Query(1,ge=1), limit:int=Query(20,ge=1,le=100), q:str|None=None, category:str|None=None, source:str|None=None, language:str|None=None, sort:str="latest"):
        rows=store.search(q) if q else (store.latest(10000) if hasattr(store,"latest") else list(store._items))
        if category: rows=[x for x in rows if x.get("category","").casefold()==category.casefold()]
        if source: rows=[x for x in rows if x.get("source","").casefold()==source.casefold()]
        if language: rows=[x for x in rows if x.get("language","").casefold()==language.casefold()]
        if sort=="score": rows.sort(key=lambda x: float(x.get("score",0)), reverse=True)
        total=len(rows); start=(page-1)*limit
        return {"items":[_api_row(row) for row in rows[start:start+limit]],"page":page,"limit":limit,"total":total,"pages":(total+limit-1)//limit}
    @app.get("/api/articles/{article_id}")
    def article(article_id:str):
        for row in (store.latest(10000) if hasattr(store,"latest") else store._items):
            if str(row.get("id"))==article_id: return _api_row(row)
        raise HTTPException(404,"article not found")
    @app.get("/api/categories")
    def categories():
        out={}
        for x in (store.latest(10000) if hasattr(store,"latest") else store._items): out[x.get("category","")]=out.get(x.get("category",""),0)+1
        return out
    @app.get("/api/sources")
    def sources():
        out={}
        for x in (store.latest(10000) if hasattr(store,"latest") else store._items): out[x.get("source","")]=out.get(x.get("source",""),0)+1
        return out
    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        record_event("page_view", **request_context(request)); return HTMLResponse(Path(__file__).with_name("index.html").read_text(encoding="utf-8"))
    @app.get("/en", include_in_schema=False)
    def english_redirect(): return RedirectResponse("/", status_code=308)
    @app.get("/ru", include_in_schema=False)
    def russian_redirect(): return RedirectResponse("/", status_code=308)
    def admin_guard(request):
        expected=os.getenv("ALPHALAB_ADMIN_TOKEN", "")
        if not expected: raise HTTPException(404, "not found")
        supplied = request.headers.get("X-Admin-Token") or request.cookies.get("alphalab_admin")
        if not supplied or not secrets.compare_digest(supplied, expected) and supplied not in admin_sessions: raise HTTPException(401, "admin authentication required")
    def admin_headers(response): response.headers["Cache-Control"] = "no-store"; return response
    def admin_shell(title, body):
        nav="<nav class='admin-nav'><a href='/admin'>Dashboard</a><a href='/admin/subscribers'>Subscribers</a><a href='/admin/articles'>Articles</a><a href='/admin/analytics'>Analytics</a><form method='post' action='/admin/logout'><button type='submit'>Logout</button></form></nav>"
        return admin_headers(HTMLResponse(f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{escape(title)}</title><link rel='stylesheet' href='/static/styles.css'></head><body>{nav}<main class='admin-page'><h1>{escape(title)}</h1>{body}</main></body></html>"))
    @app.get("/admin/login", response_class=HTMLResponse)
    def admin_login():
        if not os.getenv("ALPHALAB_ADMIN_TOKEN"): raise HTTPException(404, "not found")
        return HTMLResponse("<!doctype html><html><head><title>Admin login</title><link rel='stylesheet' href='/static/styles.css'></head><body><main class='admin-page'><h1>Admin login</h1><form method='post'><label for='admin-token'>Admin token</label><input id='admin-token' name='token' type='password' required autocomplete='current-password'><button class='button primary' type='submit'>Sign in</button><p>Invalid credentials.</p></form></main></body></html>")
    @app.post("/admin/login")
    async def admin_login_post(request: Request):
        expected=os.getenv("ALPHALAB_ADMIN_TOKEN", ""); raw=await request.body(); from urllib.parse import parse_qs
        token=parse_qs(raw.decode("utf-8"), keep_blank_values=True).get("token", [""])[0] if len(raw)<=8192 else ""
        if not expected or not secrets.compare_digest(token, expected): raise HTTPException(401, "Invalid credentials.")
        sid=secrets.token_urlsafe(32); admin_sessions.add(sid); response=RedirectResponse("/admin", status_code=303); response.set_cookie("alphalab_admin", sid, httponly=True, samesite="strict", secure=os.getenv("ALPHALAB_PUBLIC_BASE_URL", "").startswith("https://"), max_age=3600); return response
    @app.post("/admin/logout")
    def admin_logout(request: Request):
        sid=request.cookies.get("alphalab_admin"); admin_sessions.discard(sid); response=RedirectResponse("/admin/login", status_code=303); response.delete_cookie("alphalab_admin"); return response
    @app.get("/admin", response_class=HTMLResponse)
    def admin_home(request: Request):
        admin_guard(request)
        stats = store.admin_summary() if hasattr(store, "admin_summary") else {}
        tg = store.telegram_status() if hasattr(store, "telegram_status") else {"rows":[],"success_24h":0,"failure_24h":0}; rows=tg.get("rows",[]); successes=[r for r in rows if r["success"]]; failures=[r for r in rows if not r["success"]]; en_ok=next((r["attempted_at"] for r in successes if r["language"]=="en"), "none"); ru_ok=next((r["attempted_at"] for r in successes if r["language"]=="ru"), "none"); last_fail=failures[0] if failures else {}
        tg_html=f"<section class='admin-grid'><div class='card'><h2>Telegram EN configured</h2><p>{'yes' if os.getenv('ALPHALAB_TELEGRAM_BOT_TOKEN') and os.getenv('ALPHALAB_TELEGRAM_EN_CHAT_ID') else 'no'}</p></div><div class='card'><h2>Telegram RU configured</h2><p>{'yes' if os.getenv('ALPHALAB_TELEGRAM_BOT_TOKEN') and os.getenv('ALPHALAB_TELEGRAM_RU_CHAT_ID') else 'no'}</p></div><div class='card'><h2>Last EN success</h2><p>{escape(en_ok)}</p></div><div class='card'><h2>Last RU success</h2><p>{escape(ru_ok)}</p></div><div class='card'><h2>Last failure</h2><p>{escape(str(last_fail.get('attempted_at','none')))} {escape(str(last_fail.get('error_kind','')))}</p></div><div class='card'><h2>Deliveries last 24h</h2><p>success {tg.get('success_24h',0)} / failure {tg.get('failure_24h',0)}</p></div></section>"
        body = "<section class='admin-grid'>" + "".join(f"<div class='card'><h2>{escape(str(k).replace('_',' ').title())}</h2><p>{escape(str(v))}</p></div>" for k,v in stats.items()) + "</section>" + tg_html
        return admin_shell("AI Scout Admin", body)
    @app.get("/admin/subscribers", response_class=HTMLResponse)
    def admin_subscribers(request: Request, status: str = "all", page: int = Query(1, ge=1), sort: str = "latest"):
        admin_guard(request); limit=50; rows=store.admin_subscribers(status if status in {"pending","confirmed"} else None, limit, (page-1)*limit, sort == "oldest") if hasattr(store, "admin_subscribers") else []
        items="".join(f"<tr><td>{escape(str(r['email'])[:1]+'***@'+str(r['email']).split('@')[-1])}</td><td>{escape(str(r['status']))}</td><td>{escape(str(r['created_at']))}</td><td>{escape(str(r.get('confirmed_at') or ''))}</td></tr>" for r in rows)
        return admin_shell("Subscribers", f"<p>Filter: {escape(status)}</p><table><thead><tr><th>Email</th><th>Status</th><th>Created</th><th>Confirmed</th></tr></thead><tbody>{items or '<tr><td colspan=4>No subscribers</td></tr>'}</tbody></table>")
    @app.get("/admin/articles", response_class=HTMLResponse)
    def admin_articles(request: Request, source: str|None=None, category: str|None=None, page: int=Query(1, ge=1), sort: str="latest"):
        admin_guard(request); limit=50; rows=store.admin_articles(source, category, limit, (page-1)*limit, sort == "score") if hasattr(store, "admin_articles") else []
        items="".join(f"<tr><td><a href='/article/{quote(str(r['id']),safe='')}'>{escape(str(r['title']))}</a></td><td>{escape(str(r['source']))}</td><td>{escape(str(r['category']))}</td><td>{escape(str(r['published_at']))}</td><td>{float(r['score'] or 0):.2f}</td></tr>" for r in rows)
        return admin_shell("Articles", f"<table><thead><tr><th>Title</th><th>Source</th><th>Category</th><th>Published</th><th>Score</th></tr></thead><tbody>{items or '<tr><td colspan=5>No articles</td></tr>'}</tbody></table>")
    @app.get("/admin/analytics", response_class=HTMLResponse)
    def admin_analytics(request: Request):
        admin_guard(request); stats=store.analytics_summary(7) if hasattr(store,"analytics_summary") else {}; tops=store.analytics_top_articles("article_view") if hasattr(store,"analytics_top_articles") else []; clicks=store.analytics_top_articles("original_source_click") if hasattr(store,"analytics_top_articles") else []; daily=store.analytics_daily() if hasattr(store,"analytics_daily") else []; acq=store.analytics_breakdown("referrer_group") if hasattr(store,"analytics_breakdown") else []
        cards="<section class='admin-grid'>"+"".join(f"<div class='card'><h2>{escape(k.replace('_',' ').title())}</h2><p>{int(v)}</p></div>" for k,v in stats.items())+"</section>"
        table=lambda rows: "<table><thead><tr><th>Article</th><th>Count</th></tr></thead><tbody>"+"".join(f"<tr><td>{escape(str(r.get('title') or r.get('article_id')))}</td><td>{r['count']}</td></tr>" for r in rows)+"</tbody></table>"
        body=cards+"<h2>Top article views</h2>"+table(tops)+"<h2>Top source clicks</h2>"+table(clicks)+"<h2>Acquisition</h2>"+table([{"title":r['value'] or 'direct','count':r['count']} for r in acq])+"<h2>Daily totals</h2>"+table([{"title":r['day'],'count':r['page_views']} for r in daily])
        return admin_shell("Analytics", body)
    @app.get("/admin/publications", response_class=HTMLResponse)
    def admin_publications(request: Request, status: str|None=None):
        admin_guard(request); rows=store.latest(10000) if hasattr(store,"latest") else list(store._items)
        if status: rows=[r for r in rows if str(r.get("status", "published")).casefold()==status.casefold()]
        rows.sort(key=lambda r:str(r.get("created_at") or r.get("published_at") or ""), reverse=True)
        body="".join(f"<li><a href='/admin/publication/{quote(str(r.get('publication_id') or r.get('id')),safe='')}'>{escape(str(r.get('en_title') or r.get('title') or 'Untitled'))}</a> Р Р†Р вЂљРІР‚Сњ {escape(str(r.get('source','')))} Р Р†Р вЂљРІР‚Сњ {escape(str(r.get('status','published')))} Р Р†Р вЂљРІР‚Сњ {escape(str(r.get('editorial_score',0)))}</li>" for r in rows)
        return HTMLResponse(f"<!doctype html><html><head><link rel='stylesheet' href='/static/styles.css'><title>Publications</title></head><body><main><h1>Publications</h1><ul>{body or '<li>No publications</li>'}</ul></main></body></html>")
    @app.get("/admin/publication/{publication_id:path}", response_class=HTMLResponse)
    def admin_publication(request: Request, publication_id: str):
        admin_guard(request); decoded=unquote(publication_id); rows=store.latest(10000) if hasattr(store,"latest") else list(store._items); row=next((r for r in rows if str(r.get("publication_id") or r.get("id"))==decoded), None)
        if not row: raise HTTPException(404, "publication not found")
        title=row.get("en_title") or row.get("title") or "Untitled"
        return HTMLResponse(f"<!doctype html><html><head><link rel='stylesheet' href='/static/styles.css'><title>{escape(str(title))}</title></head><body><main><h1>{escape(str(title))}</h1><p>Source: {escape(str(row.get('source','')))}</p><p>Status: {escape(str(row.get('status','published')))}</p><p>Editorial score: {escape(str(row.get('editorial_score',0)))}</p><p>Publication date: {escape(str(row.get('created_at') or row.get('published_at') or ''))}</p></main></body></html>")
    @app.post("/admin/publication/{publication_id:path}/action")
    def admin_action(request: Request, publication_id: str, action: str):
        admin_guard(request); decoded=unquote(publication_id); rows=store.latest(10000) if hasattr(store,"latest") else list(store._items); row=next((r for r in rows if str(r.get("publication_id") or r.get("id"))==decoded), None)
        if not row: raise HTTPException(404, "publication not found")
        if action not in {"publish","retry_ai","retry_telegram","retry_website","mark_failed","mark_draft"}: raise HTTPException(400, "unknown action")
        current=str(row.get("status", "draft"))
        if action == "publish" and current == "published": raise HTTPException(409, "duplicate publication prevented")
        status = "published" if action == "publish" else "failed" if action == "mark_failed" else "draft" if action == "mark_draft" else current
        if hasattr(store, "update_status"): store.update_status(decoded, status)
        return {"ok": True, "action": action, "publication_id": decoded, "status": status}
    @app.post("/admin/publication/{publication_id:path}/{action}")
    def admin_action_alias(request: Request, publication_id: str, action: str):
        return admin_action(request, publication_id, action)
    @app.get("/article/{article_id:path}", response_class=HTMLResponse)
    def page(request: Request, article_id:str):
        decoded = unquote(article_id)
        row = None; matched = None
        for candidate in (store.latest(10000) if hasattr(store,"latest") else store._items):
            for field in ("id", "publication_id", "canonical_url", "url"):
                if str(candidate.get(field) or "") == decoded:
                    row, matched = candidate, field
                    break
            if row: break
        if row:
            record_event("article_view", article_id=decoded, source=str(row.get("source") or ""), category=str(row.get("category") or ""), **request_context(request))
        if not row:
            return HTMLResponse("<!doctype html><html><head><link rel='stylesheet' href='/static/styles.css'><title>Article not found &mdash; AI Scout</title></head><body><header class='site-header'><div class='site-header__inner'><a class='site-brand' href='/' aria-label='AlphaLab AI home'><span class='site-brand__mark' aria-hidden='true'>A</span><span class='site-brand__text'><strong>AlphaLab AI</strong><small>Signal, not noise.</small></span></a><nav class='site-nav' aria-label='Primary navigation'><a href='/'>Latest News</a><a href='/rss'>RSS</a></nav></div></header><main class='article-page'><article class='article-card'><h1>Article not found</h1><p>The requested article is unavailable.</p><a class='button secondary' href='/'>&larr; Back to feed</a></article></main></body></html>", status_code=404)
        base=os.getenv("ALPHALAB_PUBLIC_BASE_URL","http://127.0.0.1:8080").rstrip("/"); canonical=f"{base}/article/{quote(article_id,safe='') }"; title=str(row.get("en_title") or row.get("title") or "Untitled"); article_text=str(row.get("en_body") or row.get("summary") or "").strip(); meta_description=article_text[:300]; url=str(row.get("source_url") or row.get("url") or ""); data={"@context":"https://schema.org","@type":"Article","headline":title,"description":meta_description,"datePublished":row.get("published_at") or row.get("created_at"),"mainEntityOfPage":canonical,"publisher":{"@type":"Organization","name":"AI Scout"}}
        related_rows = store.latest(10000) if hasattr(store, "latest") else list(store._items)
        current_keys = {str(row.get(field)) for field in ("id", "publication_id", "canonical_url", "url") if row.get(field)}
        related = []
        for candidate in related_rows:
            candidate_keys = {str(candidate.get(field)) for field in ("id", "publication_id", "canonical_url", "url") if candidate.get(field)}
            if current_keys & candidate_keys: continue
            candidate_title = candidate.get("en_title") or candidate.get("title") or "Untitled"
            candidate_slug = candidate.get("publication_id") or candidate.get("id") or candidate.get("canonical_url") or candidate.get("url")
            if not candidate_slug: continue
            candidate_date = candidate.get("published_at") or candidate.get("created_at") or ""
            related.append(f"<article class='related-card'><h3>{escape(str(candidate_title))}</h3><small>{escape(str(candidate_date)[:10])}</small><a href='/article/{quote(str(candidate_slug), safe='')}'>Read article</a></article>")
            if len(related) >= 4: break
        related_html = "<section class='related-articles' aria-labelledby='related-title'><h2 id='related-title'>Related articles</h2><div class='related-grid'>" + "".join(related) + "</div></section>" if related else ""

        from urllib.parse import urlparse
        parsed=urlparse(url); original=(f"<a class='button primary' href='{escape(url,quote=True)}' target='_blank' rel='noopener noreferrer'>Original source</a>" if parsed.scheme in ('http','https') else '')
        image_url = str(row.get('image_url') or row.get('thumbnail_url') or row.get('image') or '').strip()
        image_parsed = urlparse(image_url)
        image_meta = (f"<meta property='og:image' content='{escape(image_url,quote=True)}'><meta name='twitter:image' content='{escape(image_url,quote=True)}'>"
                      if image_parsed.scheme in ('http', 'https') and image_parsed.netloc else '')
        category = f"<span class='badge'>{escape(str(row.get('category')))}</span>" if row.get('category') else ''; source=escape(str(row.get('source') or '')); score=float(row.get('score') or 0); score=int(score*100) if score<=1 else int(score); score_class='low' if score < 40 else 'medium' if score < 70 else 'high' if score < 85 else 'excellent'; verdict=f"<span>{escape(str(row.get('editorial_verdict')))}</span>" if row.get('editorial_verdict') else ''
        image_html = f"<img class='article-hero-image' src='{escape(image_url,quote=True)}' alt='' loading='lazy'>" if image_meta else ''
        published_value = str(row.get('published_at') or row.get('created_at') or '')
        published_label = published_value[:10]
        try:
            dt = datetime.fromisoformat(published_value.replace('Z', '+00:00')); now = datetime.now(dt.tzinfo or timezone.utc); minutes=max(0, int((now-dt).total_seconds()//60)); published_label = 'just now' if minutes < 1 else f'{minutes} min ago' if minutes < 60 else f'{minutes//60} hours ago' if minutes < 1440 else f'{minutes//1440} days ago'
        except (ValueError, TypeError):
            pass
        return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><link rel='stylesheet' href='/static/styles.css'><title>{escape(title)} &mdash; AI Scout</title><meta name='description' content='{escape(meta_description,quote=True)}'><link rel='canonical' href='{escape(canonical,quote=True)}'><meta property='og:type' content='article'><meta property='og:title' content='{escape(title,quote=True)}'><meta property='og:description' content='{escape(meta_description,quote=True)}'><meta property='og:url' content='{escape(canonical,quote=True)}'><meta property='og:site_name' content='AI Scout'>{image_meta}<meta name='twitter:card' content='summary_large_image'><meta name='twitter:title' content='{escape(title,quote=True)}'><meta name='twitter:description' content='{escape(meta_description,quote=True)}'><script type='application/ld+json'>{json.dumps(data,ensure_ascii=False)}</script></head><body><header class='site-header'><div class='site-header__inner'><a class='site-brand' href='/' aria-label='AlphaLab AI home'><span class='site-brand__mark' aria-hidden='true'>A</span><span class='site-brand__text'><strong>AlphaLab AI</strong><small>Signal, not noise.</small></span></a><nav class='site-nav' aria-label='Primary navigation'><a href='/'>Latest News</a><a href='/rss'>RSS</a></nav></div></header><main class='article-page'><a class='back-link' href='/'>&larr; Back to feed</a><article class='article-card'>{image_html}<div class='article-kicker'>{category}<span class='article-source'>{source}</span><time>{escape(published_label)}</time><span class='article-score {score_class}'>AI Scout score {score}/100</span>{verdict}</div><h1>{escape(title)}</h1><p class='article-summary'>{escape(article_text)}</p><div class='article-actions'>{original}<a class='button secondary' href='/'>&larr; Back to feed</a></div></article>{related_html}</main><footer class='site-footer'><div class='container footer-inner'><div><a class='brand footer-brand' href='/'><span class='brand-mark' aria-hidden='true'>A</span><strong>AlphaLab <em>AI</em></strong></a><p>Signal, not noise.</p></div><div class='footer-links'><a href='/'>Latest News</a><a href='/rss'>RSS</a></div><p class='copyright'>&copy; AlphaLab AI</p></div></footer></body></html>")
    @app.get("/about", response_class=HTMLResponse)
    def about():
        base = os.getenv("ALPHALAB_PUBLIC_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
        return HTMLResponse(f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>About AlphaLab AI</title><meta name='description' content='Learn about AlphaLab AI, an independent platform for AI news, analysis, and technology intelligence.'><link rel='canonical' href='{escape(base + '/about', quote=True)}'><link rel='stylesheet' href='/static/styles.css'></head><body><header class='site-header'><div class='site-header__inner'><a class='site-brand' href='/' aria-label='AlphaLab AI home'><span class='site-brand__mark' aria-hidden='true'>A</span><span class='site-brand__text'><strong>AlphaLab AI</strong><small>Signal, not noise.</small></span></a><nav class='site-nav' aria-label='Primary navigation'><a href='/'>Latest News</a><a class='active' href='/about'>About</a><a href='/rss'>RSS</a></nav></div></header><main class='about-page'><article class='article-card'><h1>About AlphaLab AI</h1><p>AlphaLab AI is an independent AI news and intelligence platform focused on identifying meaningful developments in artificial intelligence and emerging technology.</p><h2>What we do</h2><p>We collect news from selected technology sources, analyze it with AI-assisted editorial workflows, and publish concise coverage for readers who want signal instead of noise.</p><h2>Our editorial approach</h2><p>AlphaLab AI prioritizes relevance, clarity, source attribution, and practical importance. Automated systems assist with discovery and analysis, while the platform is designed to preserve transparent links to original sources.</p><h2>Distribution</h2><p>Articles are published on the AlphaLab AI website and distributed through dedicated English and Russian Telegram channels.</p><h2>Contact</h2><p>For partnerships, sponsorships, corrections, or editorial inquiries, contact AlphaLab AI.</p><p>Contact details will be published here soon.</p><p><a class='button secondary' href='/'>Back to latest news</a></p></article></main><footer class='site-footer'><strong>AlphaLab AI</strong><span>Signal, not noise.</span><nav aria-label='Footer navigation'><a href='/'>Latest News</a><a href='/about'>About</a><a href='/rss'>RSS</a></nav><small>&copy; AlphaLab AI</small></footer></body></html>")
    @app.get("/subscribe", response_class=HTMLResponse)
    def subscribe(request: Request):
        record_event("subscribe_page_view", **request_context(request))
        base = os.getenv("ALPHALAB_PUBLIC_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
        return HTMLResponse(f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>Subscribe to AlphaLab AI</title><meta name='description' content='Subscribe to AlphaLab AI updates through RSS and follow the latest developments in artificial intelligence and emerging technology.'><link rel='canonical' href='{escape(base + '/subscribe', quote=True)}'><link rel='stylesheet' href='/static/styles.css'></head><body><header class='site-header'><div class='site-header__inner'><a class='site-brand' href='/' aria-label='AlphaLab AI home'><span class='site-brand__mark' aria-hidden='true'>A</span><span class='site-brand__text'><strong>AlphaLab AI</strong><small>Signal, not noise.</small></span></a><nav class='site-nav' aria-label='Primary navigation'><a href='/'>Latest News</a><a href='/about'>About</a><a class='active' href='/subscribe'>Subscribe</a><a href='/rss'>RSS</a></nav></div></header><main class='about-page'><article class='article-card'><h1>Subscribe to AlphaLab AI</h1><p>Follow the latest AI news and technology intelligence without relying on social media algorithms.</p><h2>RSS Feed</h2><p>Use the AlphaLab AI RSS feed in Feedly, Inoreader, NewsBlur, or another RSS reader.</p><p><a class='button primary' href='{escape(base + '/rss', quote=True)}'>Open RSS Feed</a></p><p>Copy the feed address and add it to your preferred RSS reader.</p><p class='feed-url'>{escape(base + '/rss')}</p><h2>Telegram</h2><p>AlphaLab AI also publishes updates through dedicated English and Russian Telegram channels.</p></article></main><footer class='site-footer'><strong>AlphaLab AI</strong><span>Signal, not noise.</span><nav aria-label='Footer navigation'><a href='/'>Latest News</a><a href='/about'>About</a><a href='/subscribe'>Subscribe</a><a href='/rss'>RSS</a></nav><small>&copy; AlphaLab AI</small></footer></body></html>")
    def send_confirmation(recipient, confirmation_url):
        sender = email_sender
        if sender is not None:
            sender(recipient, "Confirm your AlphaLab AI subscription", "Confirm your subscription to AlphaLab AI by opening this link:\n\n" + confirmation_url + "\n\nIf you did not request this, ignore this email.")
            return
        host, port, username, password, sender_address = (os.getenv(name, "") for name in ("EMAIL_SMTP_HOST", "EMAIL_SMTP_PORT", "EMAIL_SMTP_USERNAME", "EMAIL_SMTP_PASSWORD", "EMAIL_FROM_ADDRESS"))
        if not all((host, port, sender_address)):
            raise RuntimeError("email confirmation unavailable")
        message = EmailMessage(); message["Subject"] = "Confirm your AlphaLab AI subscription"; message["From"] = sender_address; message["To"] = recipient; message.set_content("Confirm your subscription to AlphaLab AI by opening this link:\n\n" + confirmation_url + "\n\nIf you did not request this, ignore this email.")
        with smtplib.SMTP(host, int(port), timeout=10) as smtp:
            if os.getenv("EMAIL_USE_TLS", "true").lower() in {"1", "true", "yes", "on"}: smtp.starttls()
            if username and password: smtp.login(username, password)
            smtp.send_message(message)
    @app.post("/api/subscribe")
    async def subscribe_api(request: Request):
        if int(request.headers.get("content-length", "0") or 0) > 16_384:
            raise HTTPException(413, "request too large")
        try:
            raw = await request.body()
            if len(raw) > 16_384:
                raise HTTPException(413, "request too large")
            content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
            if content_type == "application/json":
                payload = json.loads(raw.decode("utf-8"))
            elif content_type == "application/x-www-form-urlencoded":
                from urllib.parse import parse_qs
                values = parse_qs(raw.decode("utf-8"), keep_blank_values=True)
                payload = {key: values.get(key, [""])[0] for key in values}
            else:
                raise HTTPException(415, "unsupported content type")
        except HTTPException:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
            raise HTTPException(400, "invalid request")
        email = str(payload.get("email") or "").strip().lower() if isinstance(payload, dict) else ""
        consent = payload.get("consent") if isinstance(payload, dict) else False
        consent_ok = consent is True or str(consent).strip().lower() in {"1", "true", "yes", "on"}
        if len(email) > 254 or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+", email) or not consent_ok:
            raise HTTPException(422, "valid email and consent are required")
        if not hasattr(store, "create_pending_subscriber"):
            raise HTTPException(500, "subscription storage unavailable")
        raw_token = secrets.token_urlsafe(32); token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest(); expires = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        try:
            state = store.create_pending_subscriber(email, token_hash, expires)
            if state == "confirmed": return {"ok": True, "already_subscribed": True}
            if state == "cooldown": return {"ok": True, "pending": True}
            base = (os.getenv("ALPHALAB_PUBLIC_BASE_URL") or "https://alphalabai.online").rstrip("/"); send_confirmation(email, base + "/subscribe/confirm?token=" + quote(raw_token, safe=""))
        except Exception:
            raise HTTPException(503, "Email confirmation is temporarily unavailable.")
        return {"ok": True, "pending": True}
    @app.get("/subscribe/confirm", response_class=HTMLResponse)
    def confirm_subscribe(token: str = Query("")):
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest() if token else ""
        ok = bool(token_hash and hasattr(store, "confirm_subscriber") and store.confirm_subscriber(token_hash))
        title = "Subscription confirmed" if ok else "Confirmation link is invalid or has expired."
        body = "You're now subscribed to AlphaLab AI updates." if ok else "Please request a new confirmation link if needed."
        return HTMLResponse(f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{title}</title><link rel='stylesheet' href='/static/styles.css'></head><body>{_UNIFIED_HEADER}<main class='about-page'><article class='article-card'><h1>{title}</h1><p>{body}</p></article></main>{_UNIFIED_FOOTER}</body></html>", status_code=200 if ok else 400)
    @app.get("/robots.txt", response_class=PlainTextResponse)
    def robots(): return f"User-agent: *\nAllow: /\n\nSitemap: {os.getenv('ALPHALAB_PUBLIC_BASE_URL','http://127.0.0.1:8080').rstrip('/')}/sitemap.xml\n"
    @app.get("/sitemap.xml")
    def sitemap():
        base = os.getenv("ALPHALAB_PUBLIC_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
        rows = store.latest(5000) if hasattr(store, "latest") else list(store._items)
        urls = [f"<url><loc>{escape(base + '/')}</loc></url>"]
        for row in rows:
            slug = row.get("publication_id") or row.get("id") or row.get("canonical_url") or row.get("url")
            if not slug:
                continue
            article_url = base + "/article/" + quote(str(slug), safe="")
            lastmod = row.get("published_at") or row.get("created_at")
            lastmod_xml = f"<lastmod>{escape(str(lastmod))}</lastmod>" if lastmod else ""
            urls.append(f"<url><loc>{escape(article_url)}</loc>{lastmod_xml}</url>")
        xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(urls) + "</urlset>"
        return Response(xml, media_type="application/xml")
    def rss(language=None):
        def rss_date(value):
            if not value:
                return None
            try:
                parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return format_datetime(parsed.astimezone(timezone.utc), usegmt=False)
            except (TypeError, ValueError, OverflowError):
                return None

        rows = store.latest(50) if hasattr(store, "latest") else list(store._items)[:50]
        base = (os.getenv("ALPHALAB_PUBLIC_BASE_URL") or os.getenv("PUBLIC_BASE_URL") or "https://alphalabai.online").rstrip("/")
        items = []
        for row in rows:
            title = row.get(f"{language}_title") if language else row.get("title")
            summary = row.get(f"{language}_body") if language else row.get("summary")
            title = title or row.get("title") or "Untitled"
            summary = summary or row.get("summary") or row.get("en_body") or row.get("body") or ""
            summary = str(summary).strip()[:500]
            slug = row.get("publication_id") or row.get("id") or row.get("canonical_url") or row.get("url")
            published = row.get("published_at") or row.get("created_at")
            pub_date = rss_date(published)
            if not slug:
                continue
            article_url = base + "/article/" + quote(str(slug), safe="")
            pub_date_xml = f"<pubDate>{escape(pub_date)}</pubDate>" if pub_date else ""
            items.append(f"<item><title>{escape(str(title))}</title><link>{escape(article_url)}</link><guid isPermaLink=\"true\">{escape(article_url)}</guid>{pub_date_xml}<description>{escape(summary)}</description></item>")
        channel_title = "AlphaLab AI"
        description = "AI news and analysis"
        xml = '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>' + channel_title + '</title><link>' + escape(base) + '</link><description>' + description + '</description><language>en</language>' + "".join(items) + '</channel></rss>'
        return Response(xml, media_type="application/rss+xml")
    @app.get("/rss")
    def rss_all(): return rss()
    @app.get("/en/rss")
    def rss_en(): return rss("en")
    @app.get("/ru/rss")
    def rss_ru(): return rss("ru")
    return app
