from __future__ import annotations

from io import BytesIO

import httpx


CONFIG_ROUTES = (
    ("xray", "Xray", "xray", "xray.txt"),
    ("clash_meta", "Clash Meta", "clash_meta", "clash-meta.yaml"),
    ("clash", "Clash", "clash", "clash.yaml"),
    ("sing_box", "Sing-box", "sing_box", "sing-box.json"),
    ("wireguard", "WireGuard", "wireguard", "wireguard.conf"),
    ("outline", "Outline", "outline", "outline.txt"),
    ("links", "لینک‌ها", "links", "links.txt"),
    ("links_base64", "لینک‌های Base64", "links_base64", "links-base64.txt"),
)


async def deliver(event, service, details=None) -> None:
    subscription_url = (details.subscription_url if details else None) or service.subscription_url
    if not subscription_url:
        await event.respond("⚠️ لینک اشتراک این سرویس هنوز در دسترس نیست. ابتدا سرویس را بروزرسانی کنید.")
        return

    base = subscription_url.rstrip("/")
    timeout = httpx.Timeout(20.0, connect=8.0)
    results: list[tuple[str, str, bytes]] = []
    failures: list[str] = []

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for _, label, route, filename in CONFIG_ROUTES:
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
            "ممکن است سرویس هنوز آماده نباشد یا لینک اشتراک از پنل پاسخ ندهد."
        )
        return

    await event.respond(
        f"📥 **کانفیگ‌های سرویس #{service.id} آماده شد**\n\n"
        f"✅ {len(results)} نوع کانفیگ از پاسارگارد دریافت شد.\n"
        "فایل‌های زیر را می‌توانید مستقیم در کلاینت مربوطه وارد کنید."
    )

    for label, filename, body in results:
        # Telegram supports document uploads well beyond the message text limit.
        # Keep the raw provider response byte-for-byte so JSON/YAML/base64/URI
        # formats are not corrupted by text encoding or Markdown escaping.
        await event.respond(
            file=BytesIO(body),
            force_document=True,
            attributes=[],
            message=f"📄 {label} — `{filename}`",
        )

    if failures:
        await event.respond("⚠️ بعضی فرمت‌ها دریافت نشدند:\n" + "\n".join(f"• {item}" for item in failures))
