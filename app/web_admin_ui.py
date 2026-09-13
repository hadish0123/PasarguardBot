from __future__ import annotations

import html


def _esc(value):
    return html.escape(str(value if value is not None else ""))


def _login_page(error: str = "") -> str:
    message = ""
    if error:
        message = f'<div class="login-error">{_esc(error)}</div>'
    return f'''<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#08111f">
<title>ورود مدیر | PasarguardBot</title>
<style>
*{{box-sizing:border-box}}
html,body{{margin:0;min-height:100%;font-family:Tahoma,"Segoe UI",Arial,sans-serif;background:#07111f;color:#eef5ff}}
body{{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px;background:radial-gradient(circle at 50% -10%,#18365e 0,#0a1728 42%,#050b14 100%)}}
.login-wrap{{width:min(100%,430px)}}
.logo{{width:72px;height:72px;border-radius:22px;margin:0 auto 18px;display:grid;place-items:center;font-size:34px;background:linear-gradient(145deg,#3267d6,#16366e);box-shadow:0 18px 50px #0007;border:1px solid #5d8de866}}
.title{{text-align:center;font-size:25px;font-weight:800;margin-bottom:7px}}
.subtitle{{text-align:center;color:#91a4bb;font-size:13px;margin-bottom:24px}}
.login-card{{background:rgba(13,27,45,.94);border:1px solid #223a57;border-radius:24px;padding:24px;box-shadow:0 24px 80px #0008;backdrop-filter:blur(18px)}}
.field{{margin-bottom:17px}}label{{display:block;color:#b8c8da;font-size:13px;font-weight:700;margin-bottom:8px}}
input{{width:100%;height:50px;border:1px solid #29415e;border-radius:13px;background:#071321;color:#f4f8ff;padding:0 14px;font-size:15px;outline:none;transition:.2s}}
input:focus{{border-color:#5c8eff;box-shadow:0 0 0 3px #5c8eff22}}
.password{{position:relative}}.password input{{padding-left:48px}}
.toggle{{position:absolute;left:10px;top:10px;width:30px;height:30px;border:0;background:transparent;color:#8ea2ba;cursor:pointer;font-size:16px}}
button.submit{{width:100%;height:50px;border:0;border-radius:13px;background:linear-gradient(135deg,#4e83ff,#3564d6);color:white;font-size:15px;font-weight:800;cursor:pointer;box-shadow:0 10px 26px #3564d644}}
.login-error{{margin-bottom:16px;border:1px solid #7b3443;background:#3a1722;color:#ffb9c3;border-radius:12px;padding:11px 13px;font-size:13px}}
.security{{text-align:center;color:#71869f;font-size:11px;margin-top:17px}}
</style>
</head><body>
<div class="login-wrap">
<div class="logo">🛡️</div>
<div class="title">PasarguardBot</div>
<div class="subtitle">مرکز مدیریت و کنترل نمایندگان</div>
<div class="login-card">{message}
<form method="post" action="/login" autocomplete="on">
<div class="field"><label for="username">نام کاربری مدیر</label><input id="username" name="username" autocomplete="username" required autofocus></div>
<div class="field"><label for="password">رمز عبور</label><div class="password"><input id="password" name="password" type="password" autocomplete="current-password" required><button class="toggle" type="button" onclick="const x=document.getElementById('password');x.type=x.type==='password'?'text':'password'">◉</button></div></div>
<button class="submit" type="submit">ورود به پنل مدیریت</button>
</form></div>
<div class="security">🔒 دسترسی مدیریت محافظت‌شده است</div>
</div></body></html>'''


def _page(title: str, body: str, active: str = "داشبورد") -> str:
    nav = [
        ("داشبورد", "/", "⌂"), ("نمایندگان", "/representatives", "♙"),
        ("ربات‌ها", "/bots", "◈"), ("کاربران", "/users", "♟"),
        ("پلن‌ها", "/plans", "▣"), ("سفارش‌ها", "/orders", "▤"),
        ("پرداخت و کیف پول", "/finance", "◫"), ("تخفیف‌ها", "/discounts", "%"),
        ("سرویس‌ها", "/services", "◉"), ("معرف‌ها", "/referrals", "↗"),
        ("لاگ‌ها", "/logs", "≡"), ("تنظیمات", "/settings", "⚙"),
        ("سلامت سیستم", "/health", "♥"),
    ]
    links = "".join(f'<a class="nav-item {"active" if active == n else ""}" href="{u}"><span>{i}</span><b>{n}</b></a>' for n,u,i in nav)
    return f'''<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#07111f"><title>{_esc(title)} | PasarguardBot</title>
<style>
:root{{--bg:#07111f;--surface:#0d1a2b;--surface2:#101f33;--line:#213851;--text:#edf4ff;--muted:#8fa4bb;--brand:#4f83ff;--good:#2dcc86;--warn:#efb34b;--bad:#f06478}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;min-height:100vh;background:radial-gradient(circle at 80% -10%,#17375f 0,#07111f 36%,#050b13 100%);color:var(--text);font-family:Tahoma,"Segoe UI",Arial,sans-serif}}a{{color:inherit;text-decoration:none}}button,input,select,textarea{{font:inherit}}.app{{min-height:100vh;display:flex}}.sidebar{{width:258px;flex:0 0 258px;position:fixed;inset:0 auto 0 0;background:rgba(6,15,27,.97);border-right:1px solid var(--line);padding:20px 14px;overflow:auto;z-index:30}}[dir="rtl"] .sidebar{{inset:0 0 0 auto;border-right:0;border-left:1px solid var(--line)}}.brand{{display:flex;gap:11px;align-items:center;padding:8px 8px 22px;border-bottom:1px solid #1a3048;margin-bottom:14px}}.brand-icon{{width:43px;height:43px;border-radius:13px;display:grid;place-items:center;background:linear-gradient(145deg,#376ddd,#17396f);font-size:21px}}.brand strong{{display:block;font-size:15px}}.brand small{{display:block;color:var(--muted);font-size:10px;margin-top:4px}}.section-label{{color:#5f7690;font-size:10px;font-weight:800;padding:11px 11px 5px}}.nav-item{{display:flex;align-items:center;gap:10px;padding:11px 12px;border-radius:11px;color:#aebed1;font-size:12px;margin:2px 0;transition:.18s}}.nav-item span{{width:25px;text-align:center;font-size:16px;color:#7891ad}}.nav-item:hover{{background:#10243c;color:white}}.nav-item.active{{background:linear-gradient(90deg,#1a3d6b,#123052);color:white;box-shadow:inset 3px 0 #5c8eff}}.nav-item.active span{{color:#79a0ff}}.main{{width:calc(100% - 258px);margin-right:258px;min-width:0}}[dir="rtl"] .main{{margin-right:0;margin-left:258px}}.topbar{{height:70px;position:sticky;top:0;z-index:20;display:flex;align-items:center;justify-content:space-between;padding:0 28px;background:rgba(6,15,27,.84);border-bottom:1px solid var(--line);backdrop-filter:blur(18px)}}.top-title{{font-size:14px;font-weight:800}}.top-sub{{font-size:10px;color:var(--muted);margin-top:4px}}.logout{{padding:9px 13px;border-radius:10px;background:#172b42;border:1px solid #29425e;color:#d5e1ee;font-size:12px;font-weight:700}}.mobile-menu{{display:none;border:0;background:#142940;color:white;width:39px;height:39px;border-radius:10px;font-size:18px}}.content{{max-width:1500px;margin:auto;padding:28px}}h1{{font-size:25px;margin:0 0 6px;letter-spacing:-.4px}}h2{{font-size:16px;margin:0 0 17px}}p{{line-height:1.8}}.muted{{color:var(--muted);font-size:12px}}.grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:20px 0}}.card{{background:linear-gradient(145deg,rgba(15,32,52,.97),rgba(9,22,37,.97));border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:0 15px 40px #0003;margin-bottom:16px}}.stat-card{{position:relative;overflow:hidden;min-height:118px}}.stat-card:after{{content:"";position:absolute;width:80px;height:80px;border-radius:50%;background:#4f83ff12;left:-20px;bottom:-25px}}.label{{font-size:11px;color:var(--muted)}}.stat{{font-size:25px;font-weight:900;margin-top:12px;letter-spacing:-.5px}}.good{{color:var(--good)}}.warn{{color:var(--warn)}}.bad{{color:var(--bad)}}.two{{display:grid;grid-template-columns:1.55fr 1fr;gap:16px}}.toolbar{{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin-bottom:14px}}input,select,textarea{{background:#081523;border:1px solid #29415d;color:var(--text);border-radius:11px;padding:10px 12px;outline:0}}input:focus,select:focus,textarea:focus{{border-color:#5c8eff;box-shadow:0 0 0 3px #5c8eff18}}input.search{{min-width:250px}}button,.btn{{display:inline-flex;align-items:center;justify-content:center;gap:6px;border:0;border-radius:10px;padding:10px 14px;background:var(--brand);color:white;font-size:12px;font-weight:800;cursor:pointer}}.btn.secondary,button.secondary{{background:#1b3048}}.btn.good,button.good{{background:#16734e}}.btn.danger,button.danger{{background:#922f42}}.tablewrap{{overflow:auto;border:1px solid #1d334c;border-radius:13px}}table{{width:100%;border-collapse:collapse;min-width:720px}}th,td{{padding:12px 11px;border-bottom:1px solid #1b3047;text-align:right;font-size:11px;white-space:nowrap}}th{{color:#8fa5bd;background:#0a1929;font-weight:800;position:sticky;top:0}}tr:last-child td{{border-bottom:0}}tr:hover td{{background:#10243a}}.badge{{display:inline-flex;align-items:center;padding:5px 8px;border-radius:999px;background:#17304a;color:#c9d8e8;font-size:10px;font-weight:700}}.badge.good{{background:#0d3b2b;color:#6ce0ad}}.badge.warn{{background:#463619;color:#ffd477}}.badge.bad{{background:#411d27;color:#ff9cac}}.actions{{display:flex;gap:6px;flex-wrap:wrap}}.metricline{{display:flex;justify-content:space-between;gap:15px;padding:11px 0;border-bottom:1px solid #1b3047;font-size:11px}}.empty{{padding:35px 15px;text-align:center;color:var(--muted);font-size:12px}}.flash{{background:#103d2d;border:1px solid #1d7655;padding:11px;border-radius:11px;margin-bottom:15px;font-size:12px}}
@media(max-width:1100px){{.sidebar{{width:225px;flex-basis:225px}}.main{{width:calc(100% - 225px)}}[dir="rtl"] .main{{margin-left:225px}}.grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}.two{{grid-template-columns:1fr}}}}
@media(max-width:760px){{body{{background:#07111f}}.sidebar{{transform:translateX(110%);transition:transform .22s ease;box-shadow:-20px 0 60px #0008;width:min(86vw,300px)}}[dir="rtl"] .sidebar{{transform:translateX(110%)}}.sidebar.open{{transform:translateX(0)}}.main,[dir="rtl"] .main{{width:100%;margin:0}}.topbar{{height:62px;padding:0 13px}}.mobile-menu{{display:block}}.content{{padding:16px 13px}}h1{{font-size:20px}}.grid{{grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin:15px 0}}.card{{border-radius:15px;padding:14px;margin-bottom:12px}}.stat-card{{min-height:98px}}.stat{{font-size:20px;margin-top:9px}}.label{{font-size:10px}}.top-title{{font-size:12px}}.top-sub{{display:none}}.logout{{padding:8px 10px;font-size:10px}}.toolbar{{display:grid;grid-template-columns:1fr;gap:8px}}.toolbar>*{{width:100%!important;min-width:0!important}}.tablewrap{{border:0;overflow:visible}}table,thead,tbody,tr,th,td{{display:block}}thead{{display:none}}tr{{background:#0d1d30;border:1px solid #20364f;border-radius:14px;margin-bottom:9px;padding:7px 10px}}td{{display:flex;justify-content:space-between;align-items:center;gap:12px;border:0;padding:8px 3px;white-space:normal;text-align:left;font-size:11px}}td:before{{content:attr(data-label);color:#7890a9;font-weight:700;text-align:right}}.actions{{width:100%;display:grid;grid-template-columns:1fr 1fr}}.actions .btn{{width:100%}}}}
@media(max-width:420px){{.grid{{grid-template-columns:1fr 1fr}}.stat{{font-size:18px}.card{{padding:12px}}.content{{padding:13px 10px}}}}
</style></head>
<body><div class="app"><aside class="sidebar" id="sidebar"><div class="brand"><div class="brand-icon">🛡️</div><div><strong>PasarguardBot</strong><small>مرکز مدیریت نمایندگان</small></div></div><div class="section-label">مدیریت سیستم</div>{links}<div class="section-label">حساب کاربری</div><a class="nav-item" href="/logout"><span>↪</span><b>خروج از حساب</b></a></aside>
<main class="main"><header class="topbar"><div style="display:flex;align-items:center;gap:10px"><button class="mobile-menu" onclick="document.getElementById('sidebar').classList.toggle('open')">☰</button><div><div class="top-title">{_esc(active)}</div><div class="top-sub">پنل مدیریت مرکزی PasarguardBot</div></div></div><a class="logout" href="/logout">خروج</a></header><section class="content">{body}</section></main></div>
<script>document.querySelectorAll('.sidebar a').forEach(a=>a.addEventListener('click',()=>document.getElementById('sidebar').classList.remove('open')));</script>
</body></html>'''


def apply(module):
    module._page = _page
    module._login_page = _login_page
