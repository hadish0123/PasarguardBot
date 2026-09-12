from __future__ import annotations

import hashlib
import hmac
import html
import secrets
import time
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import settings
from app.db.models import TenantStatus
from app.services.central_admin import CentralAdminService


_SESSION_TTL = 12 * 60 * 60


def _sign(value: str) -> str:
    secret = settings.web_admin_session_secret or settings.secret_key
    return hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def _make_session() -> str:
    payload = f"{settings.web_admin_username}:{int(time.time())}:{secrets.token_urlsafe(12)}"
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
        return time.time() - int(parts[1]) < _SESSION_TTL
    except ValueError:
        return False


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang=\"fa\" dir=\"rtl\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>{html.escape(title)}</title>
<style>
body{{margin:0;background:#0b1020;color:#e8ecf7;font-family:Tahoma,Arial,sans-serif}}a{{color:#7dd3fc;text-decoration:none}}.wrap{{max-width:1180px;margin:35px auto;padding:0 18px}}.card{{background:#121a2d;border:1px solid #263451;border-radius:16px;padding:20px;margin:14px 0;box-shadow:0 8px 30px #0003}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}}.stat{{font-size:28px;font-weight:700;margin-top:8px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:11px;border-bottom:1px solid #263451;text-align:right}}button{{border:0;border-radius:9px;padding:8px 12px;cursor:pointer;background:#2563eb;color:white}}button.danger{{background:#b91c1c}}input{{box-sizing:border-box;width:100%;padding:12px;border-radius:9px;border:1px solid #334155;background:#0b1020;color:white;margin:7px 0}}.muted{{color:#94a3b8}}.ok{{color:#4ade80}}.bad{{color:#f87171}}.top{{display:flex;justify-content:space-between;gap:12px;align-items:center}}small{{color:#94a3b8}}
</style></head><body><div class=\"wrap\">{body}</div></body></html>"""


def _login_page(error: str = "") -> str:
    message = f'<div class="card bad">{html.escape(error)}</div>' if error else ""
    return _page("ورود پنل مدیریت", f"""
<div class=\"card\" style=\"max-width:430px;margin:90px auto\"><h1>🛠 پنل مدیریت PasarguardBot</h1>
<p class=\"muted\">ورود مدیر سیستم</p>{message}<form method=\"post\" action=\"/login\">
<input name=\"username\" placeholder=\"نام کاربری\" autocomplete=\"username\" required>
<input name=\"password\" type=\"password\" placeholder=\"رمز عبور\" autocomplete=\"current-password\" required>
<button type=\"submit\" style=\"width:100%\">ورود</button></form></div>""")


def create_web_admin_app() -> FastAPI:
    app = FastAPI(title="PasarguardBot Web Admin", docs_url=None, redoc_url=None)
    service = CentralAdminService()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "PasarguardBot"}

    @app.get("/login", response_class=HTMLResponse)
    async def login(request: Request):
        if _valid_session(request):
            return RedirectResponse("/", status_code=303)
        return HTMLResponse(_login_page())

    @app.post("/login")
    async def login_submit(username: str = Form(...), password: str = Form(...)):
        if hmac.compare_digest(username.strip(), settings.web_admin_username) and hmac.compare_digest(
            password, settings.web_admin_password
        ):
            response = RedirectResponse("/", status_code=303)
            response.set_cookie(
                "web_admin_session",
                _make_session(),
                max_age=_SESSION_TTL,
                httponly=True,
                secure=False,
                samesite="strict",
            )
            return response
        return HTMLResponse(_login_page("نام کاربری یا رمز عبور نادرست است."), status_code=401)

    @app.get("/logout")
    async def logout():
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie("web_admin_session")
        return response

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        if not _valid_session(request):
            return RedirectResponse("/login", status_code=303)
        pending = await service.pending()
        tenants = await service.tenants()
        active = sum(1 for t in tenants if t.status == TenantStatus.ACTIVE.value)
        suspended = sum(1 for t in tenants if t.status == TenantStatus.SUSPENDED.value)
        failed = sum(1 for t in tenants if t.status == TenantStatus.FAILED.value)
        rows = []
        for tenant in tenants:
            status = tenant.status
            status_class = "ok" if status == TenantStatus.ACTIVE.value else "bad" if status == TenantStatus.FAILED.value else ""
            action = ""
            if status == TenantStatus.ACTIVE.value:
                action = f'<form method="post" action="/bots/{quote(tenant.id, safe="")}/suspend"><button class="danger">تعلیق</button></form>'
            elif status == TenantStatus.SUSPENDED.value:
                action = f'<form method="post" action="/bots/{quote(tenant.id, safe="")}/enable"><button>فعال‌سازی</button></form>'
            rows.append(
                f"<tr><td>{html.escape(tenant.brand)}</td><td>{tenant.bot_id}</td><td>{html.escape(tenant.bot_username or '-')}</td>"
                f"<td class=\"{status_class}\">{html.escape(status)}</td><td>{action}</td></tr>"
            )
        table = "".join(rows) or '<tr><td colspan="5" class="muted">رباتی ثبت نشده است.</td></tr>'
        return HTMLResponse(_page("پنل مدیریت", f"""
<div class=\"top\"><div><h1>🛠 پنل مدیریت PasarguardBot</h1><div class=\"muted\">مدیریت مرکزی نمایندگان</div></div><a href=\"/logout\">خروج</a></div>
<div class=\"grid\"><div class=\"card\">درخواست‌های در انتظار<div class=\"stat\">{len(pending)}</div></div><div class=\"card\">ربات‌های فعال<div class=\"stat ok\">{active}</div></div><div class=\"card\">معلق<div class=\"stat\">{suspended}</div></div><div class=\"card\">خطادار<div class=\"stat bad\">{failed}</div></div></div>
<div class=\"card\"><h2>🤖 ربات‌های نمایندگان</h2><table><thead><tr><th>برند</th><th>Bot ID</th><th>Username</th><th>وضعیت</th><th>عملیات</th></tr></thead><tbody>{table}</tbody></table></div>
<div class=\"card\"><h2>📝 درخواست‌های در انتظار</h2>{''.join(f'<p>#{r.id} — {html.escape(r.brand or "بدون نام")} — Bot ID: {r.bot_id or "-"}</p>' for r in pending) or '<p class="muted">موردی وجود ندارد.</p>'}</div>
<div class=\"card\"><small>/health مستقل از Telegram polling اجرا می‌شود.</small></div>
"""))

    async def _change_status(request: Request, tenant_id: str, status: TenantStatus):
        if not _valid_session(request):
            return RedirectResponse("/login", status_code=303)
        await service.set_tenant_status(tenant_id, status)
        return RedirectResponse("/", status_code=303)

    @app.post("/bots/{tenant_id}/suspend")
    async def suspend(request: Request, tenant_id: str):
        return await _change_status(request, tenant_id, TenantStatus.SUSPENDED)

    @app.post("/bots/{tenant_id}/enable")
    async def enable(request: Request, tenant_id: str):
        return await _change_status(request, tenant_id, TenantStatus.ACTIVE)

    return app
