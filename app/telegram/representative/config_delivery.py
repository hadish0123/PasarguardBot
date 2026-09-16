from __future__ import annotations

import httpx


CONFIG_ROUTES = (
    ("xray", "Xray", "xray.txt"),
    ("clash_meta", "Clash Meta", "clash-meta.yaml"),
    ("clash", "Clash", "clash.yaml"),
    ("sing_box", "Sing-box", "sing-box.json"),
    ("wireguard", "WireGuard", "wireguard.conf"),
    ("outline", "Outline", "outline.txt"),
    ("links", "لینک‌ها", "links.txt"),
    ("links_base64", "لینک‌های Base64", "links-base64.txt"),
)


async def deliver(event, service, details=None) -> None:
    subscription_url = (details.subscription_url if details else None) or service.subscription_url
    if not subscription_url:
        await event.respond(
            "⚠️ لینک اشتراک این سرویس هنوز در دسترس نیست. ابتدا سرویس را بروزرسانی کنید.",
            parse_mode=None,
        )
        return

    base = subscription_url.rstrip("/")
    timeout = httpx.Timeout(20.0, connect=8.0)
    results: list[tuple[str, str, bytes]] = []
    failures: list[str] = []

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for route, label, filename in CONFIG_ROUTES:
            try:
                response = await client.get(f"{base}/{route}")
                if response.status_code != 200:
                    failures.append(f"{label}: HTTP {response.status_code}")
                    continue
                body = response.content
                if not body.strip():
                    failures.append(f"{label}: پاسخ خالی")
                    continue
                results.append((label, filename, body))
            except httpx.HTTPError as exc:
                failures.append(f"{label}: {type(exc).__name__}")

    if not results:
        await event.respond(
            "❌ هیچ کانفیگی از سابسکریپشن دریافت نشد.\n\n"
            "ممکن است سرویس هنوز آماده نباشد یا لینک اشتراک از پنل پاسخ ندهد.",
            parse_mode=None,
        )
        return

    await event.respond(
        f"📥 کانفیگ‌های سرویس #{service.id} آماده شد\n\n"
        f"✅ {len(results)} نوع کانفیگ از پاسارگارد دریافت شد.\n"
        "فایل‌های زیر را می‌توانید مستقیم در کلاینت مربوطه وارد کنید.",
        parse_mode=None,
    )

    for label, filename, body in results:
        try:
            await event.client.send_document(
                event.chat_id,
                body,
                filename=filename,
                caption=f"📄 {label} | سرویس #{service.id}",
            )
        except Exception as exc:
            failures.append(f"ارسال {label}: {type(exc).__name__}")

    if failures:
        await event.respond(
            "⚠️ بعضی فایل‌ها ارسال نشدند:\n" + "\n".join(f"• {item}" for item in failures),
            parse_mode=None,
        )
    else:
        await event.respond(
            f"✅ هر {len(results)} فایل کانفیگ با موفقیت برای شما ارسال شد.",
            parse_mode=None,
        )
