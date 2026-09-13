from __future__ import annotations

import hashlib
import hmac
import html
import secrets
import time
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, or_, select

from app.core.config import settings
from app.db.models import (
    Discount, Order, Plan, Referral, ReferralReward, RepresentativeLink,
    RepresentativeLog, RepresentativeRegistration, RepresentativeSetting,
    RepresentativeText, RepresentativeUser, SalesSetting, ServiceSubscription,
    TenantRecord, TenantStatus, TrialClaim, UserBalanceLog,
)
from app.db.session import SessionFactory
from app.services.central_admin import CentralAdminService

_SESSION_TTL = 12 * 60 * 60


def _sign(value: str) -> str:
    secret = settings.web_admin_session_secret or settings.secret_key
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def _make_session() -> str:
    payload = f"{settings.web_admin_username}:{int(time.time())}:{secrets.token_urlsafe(18)}"
    return f"{payload}.{_sign(payload)}"


def _valid_session(request: Request) -> bool:
    raw = request.cookies.get("web_admin_session", "")
    if "." not in raw:
        return False
    payload, signature = raw.rsplit(".", 1)
    if not hmac.compare_digest(signature, _sign(payload)):
        return False
    parts = payload.split(":", 2)
    if len(parts) != 3 or parts[0] != settings.web_admin_username:
        return False
    try:
        return 0 <= time.time() - int(parts[1]) < _SESSION_TTL
    except ValueError:
        return False


def _toman(value) -> str:
    try:
        return f"{round(float(value or 0)):,} تومان"
    except (TypeError, ValueError):
        return "0 تومان"


def _dt(value) -> str:
    if not value:
        return "—"
    if isinstance(value, datetime):
        return value.strftime("%Y/%m/%d %H:%M")
    return html.escape(str(value))


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def _page(title: str, body: str, active: str = "داشبورد") -> str:
    nav = [
        ("داشبورد", "/"), ("نمایندگان", "/representatives"), ("ربات‌ها", "/bots"),
        ("کاربران", "/users"), ("پلن‌ها", "/plans"), ("سفارش‌ها", "/orders"),
        ("پرداخت و کیف پول", "/finance"), ("تخفیف‌ها", "/discounts"),
        ("سرویس‌ها", "/services"), ("معرف‌ها", "/referrals"), ("لاگ‌ها", "/logs"),
        ("تنظیمات", "/settings"), ("سلامت سیستم", "/health"),
    ]
    links = "".join(f'<a class="navitem {"active" if active == n else ""}" href="{u}">{n}</a>' for n, u in nav)
    return f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{_esc(title)}</title>
<style>
:root{{--bg:#07111f;--panel:#0d1a2b;--panel2:#112238;--line:#21344d;--text:#edf4ff;--muted:#91a4bb;--brand:#5b8cff;--good:#32d583;--warn:#f5b84b;--bad:#ff6678}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 20% 0,#13294a 0,#07111f 38%,#050c16 100%);color:var(--text);font-family:Vazirmatn,Tahoma,Arial,sans-serif;min-height:100vh}}a{{color:inherit;text-decoration:none}}.shell{{display:flex;min-height:100vh}}.side{{width:245px;background:rgba(7,15,27,.92);border-left:1px solid var(--line);padding:20px 14px;position:sticky;top:0;height:100vh;overflow:auto}}.brand{{padding:12px 10px 22px;font-size:19px;font-weight:800}}.brand small{{display:block;color:var(--muted);font-size:11px;margin-top:6px}}.navitem{{display:block;padding:11px 13px;border-radius:10px;color:#b7c5d8;margin:3px 0;font-size:14px}}.navitem:hover,.navitem.active{{background:linear-gradient(90deg,#18345a,#12263f);color:white}}.main{{flex:1;min-width:0}}.top{{height:72px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 28px;background:rgba(5,13,23,.62);backdrop-filter:blur(12px);position:sticky;top:0;z-index:5}}.content{{max-width:1500px;margin:auto;padding:28px}}h1{{font-size:25px;margin:0 0 5px}}h2{{font-size:17px;margin:0 0 18px}}.muted,small{{color:var(--muted)}}.grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:18px}}.card{{background:linear-gradient(145deg,rgba(17,34,56,.95),rgba(10,24,41,.95));border:1px solid var(--line);border-radius:16px;padding:18px;box-shadow:0 12px 38px #0004;margin-bottom:16px}}.stat{{font-size:27px;font-weight:850;margin-top:9px}}.label{{color:var(--muted);font-size:13px}}.good{{color:var(--good)}}.bad{{color:var(--bad)}}.warn{{color:var(--warn)}}.toolbar{{display:flex;gap:9px;flex-wrap:wrap;align-items:center;margin-bottom:15px}}input,select,textarea{{background:#081525;border:1px solid #2a405c;color:var(--text);border-radius:9px;padding:10px 11px;outline:none}}input:focus,select:focus,textarea:focus{{border-color:var(--brand)}}input.search{{min-width:260px}}button,.btn{{border:0;background:var(--brand);color:#fff;border-radius:9px;padding:10px 14px;cursor:pointer;font-weight:700;display:inline-block}}button.secondary,.btn.secondary{{background:#21364f}}button.danger,.btn.danger{{background:#a92f43}}button.good,.btn.good{{background:#18794e}}table{{width:100%;border-collapse:collapse;min-width:780px}}.tablewrap{{overflow:auto}}th,td{{padding:12px 10px;border-bottom:1px solid #1e3149;text-align:right;font-size:13px;vertical-align:middle}}th{{color:#91a8c2;font-weight:600;background:#0b192a;position:sticky;top:0}}tr:hover td{{background:#102238}}.badge{{display:inline-flex;padding:5px 8px;border-radius:999px;background:#18304b;color:#cbd9e8;font-size:11px}}.badge.good{{background:#0d3d2c}}.badge.bad{{background:#431c28}}.badge.warn{{background:#44341a}}.actions{{display:flex;gap:6px;flex-wrap:wrap}}.empty{{padding:35px;text-align:center;color:var(--muted)}}.flash{{background:#103e2d;border:1px solid #1c7654;padding:11px;border-radius:10px;margin-bottom:15px}}.two{{display:grid;grid-template-columns:1.5fr 1fr;gap:16px}}.login{{max-width:430px;margin:10vh auto}}.metricline{{display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--line)}}@media(max-width:1050px){{.grid{{grid-template-columns:repeat(2,1fr)}}.side{{width:205px}}.two{{grid-template-columns:1fr}}}}@media(max-width:720px){{.shell{{display:block}}.side{{position:static;width:100%;height:auto;border-left:0;border-bottom:1px solid var(--line)}}.navitem{{display:inline-block;margin:2px;font-size:12px}}.top{{padding:0 15px}}.content{{padding:17px}}.grid{{grid-template-columns:1fr}}.top h1{{font-size:18px}}}}
</style></head><body><div class="shell"><aside class="side"><div class="brand">🛡️ PasarguardBot<small>مرکز مدیریت نمایندگان</small></div>{links}</aside>
<main class="main"><header class="top"><div><strong>{_esc(active)}</strong></div><div><a class="btn secondary" href="/logout">خروج</a></div></header><section class="content">{body}</section></main></div></body></html>'''


def _login_page(error: str = "") -> str:
    msg = f'<div class="flash" style="background:#431c28;border-color:#7a2c3c">{_esc(error)}</div>' if error else ""
    return _page("ورود", f'''<div class="card login"><h1>🔐 ورود مدیر</h1><p class="muted">پنل مرکزی مدیریت PasarguardBot</p>{msg}
<form method="post" action="/login"><label class="label">نام کاربری</label><input name="username" autocomplete="username" required style="width:100%;margin:6px 0 13px"><label class="label">رمز عبور</label><input name="password" type="password" autocomplete="current-password" required style="width:100%;margin:6px 0 16px"><button style="width:100%">ورود امن</button></form></div>''')


def _auth(request: Request):
    return _valid_session(request)


def create_web_admin_app() -> FastAPI:
    app = FastAPI(title="PasarguardBot Web Admin", docs_url=None, redoc_url=None)
    service = CentralAdminService()

    @app.get("/health")
    async def health():
        db = "ok"
        if SessionFactory is not None:
            try:
                async with SessionFactory() as s:
                    await s.execute(select(func.count()).select_from(TenantRecord))
            except Exception:
                db = "error"
        return {"status": "ok" if db == "ok" else "degraded", "service": "PasarguardBot", "database": db}

    @app.get("/login", response_class=HTMLResponse)
    async def login(request: Request):
        return HTMLResponse(_page("ورود", _login_page()[_login_page().find('<div class="card login">'):])) if not _auth(request) else RedirectResponse("/", 303)

    @app.post("/login")
    async def login_submit(username: str = Form(...), password: str = Form(...)):
        if hmac.compare_digest(username.strip(), settings.web_admin_username) and hmac.compare_digest(password, settings.web_admin_password):
            r = RedirectResponse("/", 303)
            r.set_cookie("web_admin_session", _make_session(), max_age=_SESSION_TTL, httponly=True, secure=False, samesite="strict")
            return r
        return HTMLResponse(_login_page("نام کاربری یا رمز عبور نادرست است."), 401)

    @app.get("/logout")
    async def logout():
        r = RedirectResponse("/login", 303); r.delete_cookie("web_admin_session"); return r

    async def counts():
        async with SessionFactory() as s:
            tenants = await s.scalar(select(func.count()).select_from(TenantRecord)) or 0
            active = await s.scalar(select(func.count()).select_from(TenantRecord).where(TenantRecord.status == TenantStatus.ACTIVE.value)) or 0
            pending = await s.scalar(select(func.count()).select_from(RepresentativeRegistration).where(RepresentativeRegistration.status == "pending")) or 0
            users = await s.scalar(select(func.count()).select_from(RepresentativeUser)) or 0
            orders = await s.scalar(select(func.count()).select_from(Order)) or 0
            sales = await s.scalar(select(func.coalesce(func.sum(Order.amount), 0)).select_from(Order).where(Order.status.in_(["paid", "fulfilled", "provisioning"]))) or 0
            services = await s.scalar(select(func.count()).select_from(ServiceSubscription).where(ServiceSubscription.status == "active")) or 0
            return tenants, active, pending, users, orders, sales, services

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        if not _auth(request): return RedirectResponse("/login", 303)
        tenants, active, pending, users, orders, sales, services = await counts()
        async with SessionFactory() as s:
            recent = (await s.scalars(select(Order).order_by(Order.created_at.desc()).limit(8))).all()
            bad = (await s.scalars(select(RepresentativeLog).where(RepresentativeLog.action.ilike("%error%")).order_by(RepresentativeLog.created_at.desc()).limit(6))).all()
        rows = "".join(f'<tr><td>#{o.id}</td><td>{o.telegram_user_id}</td><td>{_esc(o.plan_name)}</td><td>{_toman(o.amount)}</td><td>{_esc(o.status)}</td><td>{_dt(o.created_at)}</td></tr>' for o in recent) or '<tr><td colspan="6" class="empty">سفارشی ثبت نشده است.</td></tr>'
        errors = "".join(f'<div class="metricline"><span>{_esc(x.action)}</span><small>{_dt(x.created_at)}</small></div>' for x in bad) or '<div class="empty">خطای ثبت‌شده‌ای پیدا نشد.</div>'
        body = f'''<h1>داشبورد مرکزی</h1><p class="muted">نمای کلی عملیات، فروش و سلامت سیستم</p>
<div class="grid"><div class="card"><div class="label">کل نمایندگان</div><div class="stat">{tenants:,}</div></div><div class="card"><div class="label">نمایندگان فعال</div><div class="stat good">{active:,}</div></div><div class="card"><div class="label">درخواست‌های در انتظار</div><div class="stat warn">{pending:,}</div></div><div class="card"><div class="label">کاربران</div><div class="stat">{users:,}</div></div><div class="card"><div class="label">کل سفارش‌ها</div><div class="stat">{orders:,}</div></div><div class="card"><div class="label">فروش ثبت‌شده</div><div class="stat">{_toman(sales)}</div></div><div class="card"><div class="label">سرویس‌های فعال</div><div class="stat good">{services:,}</div></div><div class="card"><div class="label">وضعیت HTTP/DB</div><div class="stat good">● سالم</div></div></div>
<div class="two"><div class="card"><h2>🧾 آخرین سفارش‌ها</h2><div class="tablewrap"><table><tr><th>سفارش</th><th>کاربر</th><th>پلن</th><th>مبلغ</th><th>وضعیت</th><th>زمان</th></tr>{rows}</table></div></div><div class="card"><h2>🚨 خطاهای اخیر</h2>{errors}</div></div>'''
        return HTMLResponse(_page("داشبورد", body))

    @app.get("/representatives", response_class=HTMLResponse)
    async def representatives(request: Request, q: str = ""):
        if not _auth(request): return RedirectResponse("/login", 303)
        async with SessionFactory() as s:
            stmt = select(TenantRecord).order_by(TenantRecord.id.asc())
            if q.strip(): stmt = stmt.where(or_(TenantRecord.brand.ilike(f"%{q.strip()}%"), TenantRecord.bot_username.ilike(f"%{q.strip()}%")))
            tenants = (await s.scalars(stmt.limit(300))).all()
        rows = "".join(f'''<tr><td><b>{_esc(t.brand)}</b></td><td>{t.bot_id}</td><td>@{_esc(t.bot_username or "—")}</td><td>{t.owner_id}</td><td><span class="badge {"good" if t.status=="active" else "bad" if t.status=="failed" else "warn"}">{_esc(t.status)}</span></td><td>{_dt(t.created_at)}</td><td class="actions"><a class="btn secondary" href="/representatives/{quote(t.id,safe='')}">جزئیات</a>{"<form method='post' action='/representatives/"+quote(t.id,safe='')+"/suspend'><button class='danger'>تعلیق</button></form>" if t.status=="active" else "<form method='post' action='/representatives/"+quote(t.id,safe='')+"/enable'><button class='good'>فعال‌سازی</button></form>"}</td></tr>''' for t in tenants) or '<tr><td colspan="7" class="empty">نماینده‌ای پیدا نشد.</td></tr>'
        body=f'''<h1>👥 مدیریت نمایندگان</h1><div class="toolbar"><form><input class="search" name="q" value="{_esc(q)}" placeholder="جستجوی برند یا username"><button>جستجو</button></form></div><div class="card"><div class="tablewrap"><table><tr><th>برند</th><th>Bot ID</th><th>Username</th><th>مالک</th><th>وضعیت</th><th>ثبت</th><th>عملیات</th></tr>{rows}</table></div></div>'''
        return HTMLResponse(_page("نمایندگان", body, "نمایندگان"))

    @app.post("/representatives/{tenant_id}/suspend")
    async def suspend(request: Request, tenant_id: str):
        if not _auth(request): return RedirectResponse("/login",303)
        await service.set_tenant_status(tenant_id, TenantStatus.SUSPENDED); return RedirectResponse("/representatives",303)

    @app.post("/representatives/{tenant_id}/enable")
    async def enable(request: Request, tenant_id: str):
        if not _auth(request): return RedirectResponse("/login",303)
        await service.set_tenant_status(tenant_id, TenantStatus.ACTIVE); return RedirectResponse("/representatives",303)

    @app.get("/representatives/{tenant_id}", response_class=HTMLResponse)
    async def representative_detail(request: Request, tenant_id: str):
        if not _auth(request): return RedirectResponse("/login",303)
        t=await service.get_tenant(tenant_id)
        if not t: return HTMLResponse(_page("یافت نشد", '<div class="card"><h1>نماینده پیدا نشد</h1></div>'),404)
        async with SessionFactory() as s:
            uc=await s.scalar(select(func.count()).select_from(RepresentativeUser).where(RepresentativeUser.tenant_id==t.id)) or 0
            oc=await s.scalar(select(func.count()).select_from(Order).where(Order.tenant_id==t.id)) or 0
            sc=await s.scalar(select(func.count()).select_from(ServiceSubscription).where(ServiceSubscription.tenant_id==t.id,ServiceSubscription.status=="active")) or 0
            total=await s.scalar(select(func.coalesce(func.sum(Order.amount),0)).where(Order.tenant_id==t.id)) or 0
        body=f'''<h1>🏢 {_esc(t.brand)}</h1><p class="muted">نماینده / tenant</p><div class="grid"><div class="card"><div class="label">Bot ID</div><div class="stat">{t.bot_id}</div></div><div class="card"><div class="label">کاربران</div><div class="stat">{uc:,}</div></div><div class="card"><div class="label">سفارش‌ها</div><div class="stat">{oc:,}</div></div><div class="card"><div class="label">فروش</div><div class="stat">{_toman(total)}</div></div></div><div class="card"><div class="metricline"><span>Username</span><b>@{_esc(t.bot_username or "—")}</b></div><div class="metricline"><span>مالک</span><b>{t.owner_id}</b></div><div class="metricline"><span>وضعیت</span><b>{_esc(t.status)}</b></div><div class="metricline"><span>سرویس فعال</span><b>{sc:,}</b></div><div class="metricline"><span>Panel URL</span><b>{_esc(t.panel_url)}</b></div></div>'''
        return HTMLResponse(_page("جزئیات نماینده",body,"نمایندگان"))

    @app.get("/bots", response_class=HTMLResponse)
    async def bots(request: Request):
        if not _auth(request): return RedirectResponse("/login",303)
        async with SessionFactory() as s: tenants=(await s.scalars(select(TenantRecord).order_by(TenantRecord.updated_at.desc()).limit(300))).all()
        rows="".join(f'<tr><td>{t.bot_id}</td><td>{_esc(t.bot_username or "—")}</td><td>{_esc(t.brand)}</td><td><span class="badge {"good" if t.status=="active" else "bad"}">{_esc(t.status)}</span></td><td>{_dt(t.updated_at)}</td><td><a class="btn secondary" href="/representatives/{quote(t.id,safe="")}">مدیریت</a></td></tr>' for t in tenants) or '<tr><td colspan="6" class="empty">رباتی ثبت نشده است.</td></tr>'
        return HTMLResponse(_page("ربات‌ها",f'<h1>🤖 مدیریت ربات‌ها</h1><div class="card"><div class="tablewrap"><table><tr><th>Bot ID</th><th>Username</th><th>نماینده</th><th>وضعیت</th><th>آخرین تغییر</th><th></th></tr>{rows}</table></div></div>',"ربات‌ها"))

    @app.get("/users", response_class=HTMLResponse)
    async def users(request: Request, q: str = ""):
        if not _auth(request): return RedirectResponse("/login",303)
        async with SessionFactory() as s:
            stmt=select(RepresentativeUser).order_by(RepresentativeUser.last_seen_at.desc())
            if q.strip(): stmt=stmt.where(or_(RepresentativeUser.username.ilike(f"%{q.strip()}%"),RepresentativeUser.telegram_user_id==int(q) if q.isdigit() else RepresentativeUser.telegram_user_id<0))
            users=(await s.scalars(stmt.limit(300))).all()
        rows="".join(f'<tr><td>{u.telegram_user_id}</td><td>@{_esc(u.username or "—")}</td><td>{_esc((u.first_name or "")+" "+(u.last_name or ""))}</td><td>{u.tenant_id}</td><td>{_toman(u.balance)}</td><td>{"مسدود" if u.blocked else "فعال"}</td><td>{_dt(u.last_seen_at)}</td></tr>' for u in users) or '<tr><td colspan="7" class="empty">کاربری پیدا نشد.</td></tr>'
        return HTMLResponse(_page("کاربران",f'<h1>👤 کاربران</h1><div class="toolbar"><form><input class="search" name="q" value="{_esc(q)}" placeholder="Telegram ID یا username"><button>جستجو</button></form></div><div class="card"><div class="tablewrap"><table><tr><th>Telegram ID</th><th>Username</th><th>نام</th><th>Tenant</th><th>موجودی</th><th>وضعیت</th><th>آخرین فعالیت</th></tr>{rows}</table></div></div>',"کاربران"))

    @app.get("/plans", response_class=HTMLResponse)
    async def plans(request: Request):
        if not _auth(request): return RedirectResponse("/login",303)
        async with SessionFactory() as s: plans=(await s.scalars(select(Plan).order_by(Plan.tenant_id,Plan.id.desc()).limit(500))).all()
        rows="".join(f'<tr><td>#{p.id}</td><td>{_esc(p.tenant_id)}</td><td>{_esc(p.name)}</td><td>{p.volume_gb:g} GB</td><td>{p.days} روز</td><td><b>{_toman(p.price)}</b></td><td>{"فعال" if p.enabled else "غیرفعال"}</td></tr>' for p in plans) or '<tr><td colspan="7" class="empty">پلنی وجود ندارد.</td></tr>'
        return HTMLResponse(_page("پلن‌ها",f'<h1>📦 مدیریت پلن‌ها</h1><p class="muted">قیمت‌ها در کل پنل فقط تومان صحیح نمایش داده می‌شوند.</p><div class="card"><div class="tablewrap"><table><tr><th>ID</th><th>Tenant</th><th>نام</th><th>حجم</th><th>مدت</th><th>قیمت</th><th>وضعیت</th></tr>{rows}</table></div></div>',"پلن‌ها"))

    @app.get("/orders", response_class=HTMLResponse)
    async def orders(request: Request, status: str = ""):
        if not _auth(request): return RedirectResponse("/login",303)
        async with SessionFactory() as s:
            stmt=select(Order).order_by(Order.created_at.desc())
            if status: stmt=stmt.where(Order.status==status)
            orders=(await s.scalars(stmt.limit(500))).all()
        rows="".join(f'<tr><td>#{o.id}</td><td>{o.telegram_user_id}</td><td>{_esc(o.tenant_id)}</td><td>{_esc(o.plan_name)}</td><td>{_toman(o.amount)}</td><td><span class="badge">{_esc(o.status)}</span></td><td>{_dt(o.created_at)}</td></tr>' for o in orders) or '<tr><td colspan="7" class="empty">سفارشی وجود ندارد.</td></tr>'
        return HTMLResponse(_page("سفارش‌ها",f'<h1>🧾 سفارش‌ها و فروش</h1><div class="toolbar"><a class="btn secondary" href="/orders">همه</a><a class="btn secondary" href="/orders?status=pending">در انتظار</a><a class="btn secondary" href="/orders?status=paid">پرداخت‌شده</a><a class="btn secondary" href="/orders?status=fulfilled">تکمیل‌شده</a></div><div class="card"><div class="tablewrap"><table><tr><th>سفارش</th><th>کاربر</th><th>Tenant</th><th>پلن</th><th>مبلغ</th><th>وضعیت</th><th>زمان</th></tr>{rows}</table></div></div>',"سفارش‌ها"))

    @app.get("/finance", response_class=HTMLResponse)
    async def finance(request: Request):
        if not _auth(request): return RedirectResponse("/login",303)
        async with SessionFactory() as s:
            total=await s.scalar(select(func.coalesce(func.sum(Order.amount),0)).where(Order.status.in_(["paid","fulfilled","provisioning"]))) or 0
            wallet=await s.scalar(select(func.coalesce(func.sum(RepresentativeUser.balance),0))) or 0
            paid=await s.scalar(select(func.count()).select_from(Order).where(Order.status.in_(["paid","fulfilled"]))) or 0
            tx=(await s.scalars(select(UserBalanceLog).order_by(UserBalanceLog.created_at.desc()).limit(30))).all()
        rows="".join(f'<tr><td>{x.user_id}</td><td>{_toman(x.amount)}</td><td>{_esc(x.reason)}</td><td>{x.actor_id}</td><td>{_dt(x.created_at)}</td></tr>' for x in tx) or '<tr><td colspan="5" class="empty">تراکنشی نیست.</td></tr>'
        body=f'<h1>💰 پرداخت و کیف پول</h1><div class="grid"><div class="card"><div class="label">فروش</div><div class="stat">{_toman(total)}</div></div><div class="card"><div class="label">مجموع موجودی کاربران</div><div class="stat">{_toman(wallet)}</div></div><div class="card"><div class="label">سفارش‌های پرداخت‌شده</div><div class="stat">{paid:,}</div></div><div class="card"><div class="label">واحد پول</div><div class="stat">تومان</div></div></div><div class="card"><h2>تراکنش‌های کیف پول</h2><div class="tablewrap"><table><tr><th>کاربر</th><th>مبلغ</th><th>دلیل</th><th>مدیر</th><th>زمان</th></tr>{rows}</table></div></div>'
        return HTMLResponse(_page("امور مالی",body,"پرداخت و کیف پول"))

    @app.get("/discounts", response_class=HTMLResponse)
    async def discounts(request: Request):
        if not _auth(request): return RedirectResponse("/login",303)
        async with SessionFactory() as s: ds=(await s.scalars(select(Discount).order_by(Discount.created_at.desc()).limit(500))).all()
        rows="".join(f'<tr><td>{_esc(d.code)}</td><td>{d.percent:g}%</td><td>{d.used_count}/{d.max_uses if d.max_uses is not None else "∞"}</td><td>{"فعال" if d.enabled else "غیرفعال"}</td><td>{_dt(d.expires_at)}</td></tr>' for d in ds) or '<tr><td colspan="5" class="empty">کد تخفیفی وجود ندارد.</td></tr>'
        return HTMLResponse(_page("تخفیف‌ها",f'<h1>🎟 تخفیف‌ها</h1><div class="card"><div class="tablewrap"><table><tr><th>کد</th><th>درصد</th><th>مصرف</th><th>وضعیت</th><th>انقضا</th></tr>{rows}</table></div></div>',"تخفیف‌ها"))

    @app.get("/services", response_class=HTMLResponse)
    async def services(request: Request):
        if not _auth(request): return RedirectResponse("/login",303)
        async with SessionFactory() as s: ss=(await s.scalars(select(ServiceSubscription).order_by(ServiceSubscription.updated_at.desc()).limit(500))).all()
        rows="".join(f'<tr><td>#{x.id}</td><td>{x.telegram_user_id}</td><td>{_esc(x.tenant_id)}</td><td>{_esc(x.plan_name)}</td><td>{x.volume_gb:g} GB / {x.days} روز</td><td>{_esc(x.status)}</td><td>{_dt(x.expires_at)}</td></tr>' for x in ss) or '<tr><td colspan="7" class="empty">سرویسی وجود ندارد.</td></tr>'
        return HTMLResponse(_page("سرویس‌ها",f'<h1>🔌 سرویس‌ها</h1><div class="card"><div class="tablewrap"><table><tr><th>ID</th><th>کاربر</th><th>Tenant</th><th>پلن</th><th>حجم/مدت</th><th>وضعیت</th><th>انقضا</th></tr>{rows}</table></div></div>',"سرویس‌ها"))

    @app.get("/referrals", response_class=HTMLResponse)
    async def referrals(request: Request):
        if not _auth(request): return RedirectResponse("/login",303)
        async with SessionFactory() as s:
            rc=await s.scalar(select(func.count()).select_from(Referral)) or 0
            rewards=await s.scalar(select(func.coalesce(func.sum(ReferralReward.amount),0))) or 0
            rr=(await s.scalars(select(ReferralReward).order_by(ReferralReward.created_at.desc()).limit(50))).all()
        rows="".join(f'<tr><td>{x.inviter_user_id}</td><td>{x.order_id or "—"}</td><td>{_toman(x.amount)}</td><td>{_esc(x.reason)}</td><td>{_dt(x.created_at)}</td></tr>' for x in rr) or '<tr><td colspan="5" class="empty">پاداشی نیست.</td></tr>'
        return HTMLResponse(_page("معرف‌ها",f'<h1>🔗 سیستم معرف</h1><div class="grid"><div class="card"><div class="label">معرفی‌ها</div><div class="stat">{rc:,}</div></div><div class="card"><div class="label">کل پاداش</div><div class="stat">{_toman(rewards)}</div></div></div><div class="card"><h2>آخرین پاداش‌ها</h2><div class="tablewrap"><table><tr><th>معرف</th><th>سفارش</th><th>مبلغ</th><th>دلیل</th><th>زمان</th></tr>{rows}</table></div></div>',"معرف‌ها"))

    @app.get("/logs", response_class=HTMLResponse)
    async def logs(request: Request):
        if not _auth(request): return RedirectResponse("/login",303)
        async with SessionFactory() as s: ls=(await s.scalars(select(RepresentativeLog).order_by(RepresentativeLog.created_at.desc()).limit(500))).all()
        rows="".join(f'<tr><td>{_dt(x.created_at)}</td><td>{_esc(x.tenant_id)}</td><td>{x.actor_id or "system"}</td><td>{_esc(x.action)}</td><td>{_esc(x.details)}</td></tr>' for x in ls) or '<tr><td colspan="5" class="empty">لاگی نیست.</td></tr>'
        return HTMLResponse(_page("لاگ‌ها",f'<h1>📋 Audit و Runtime Logs</h1><div class="card"><div class="tablewrap"><table><tr><th>زمان</th><th>Tenant</th><th>Actor</th><th>Action</th><th>جزئیات</th></tr>{rows}</table></div></div>',"لاگ‌ها"))

    @app.get("/settings", response_class=HTMLResponse)
    async def settings_page(request: Request):
        if not _auth(request): return RedirectResponse("/login",303)
        async with SessionFactory() as s:
            settings_rows=(await s.scalars(select(RepresentativeSetting).order_by(RepresentativeSetting.tenant_id,RepresentativeSetting.key).limit(500))).all()
            sales=(await s.scalars(select(SalesSetting).order_by(SalesSetting.tenant_id,SalesSetting.key).limit(500))).all()
        rrows="".join(f'<tr><td>{_esc(x.tenant_id)}</td><td>{_esc(x.key)}</td><td>{_esc(x.value)}</td><td>{_dt(x.updated_at)}</td></tr>' for x in settings_rows) or '<tr><td colspan="4" class="empty">تنظیمی نیست.</td></tr>'
        srows="".join(f'<tr><td>{_esc(x.tenant_id)}</td><td>{_esc(x.key)}</td><td>{_esc(x.value)}</td><td>{_dt(x.updated_at)}</td></tr>' for x in sales) or '<tr><td colspan="4" class="empty">تنظیمی نیست.</td></tr>'
        body=f'<h1>⚙️ تنظیمات</h1><div class="card"><h2>تنظیمات نمایندگان</h2><div class="tablewrap"><table><tr><th>Tenant</th><th>کلید</th><th>مقدار</th><th>آخرین تغییر</th></tr>{rrows}</table></div></div><div class="card"><h2>تنظیمات فروش</h2><div class="tablewrap"><table><tr><th>Tenant</th><th>کلید</th><th>مقدار</th><th>آخرین تغییر</th></tr>{srows}</table></div></div>'
        return HTMLResponse(_page("تنظیمات",body,"تنظیمات"))

    return app
