from __future__ import annotations

import base64

import httpx


async def _fetch_text(client: httpx.AsyncClient, url: str) -> str:
    response = await client.get(url)
    response.raise_for_status()
    return response.content.decode("utf-8", errors="replace").strip()


def _decode_subscription_body(body: str) -> str:
    if not body:
        return ""
    schemes = ("vless://", "vmess://", "trojan://", "ss://", "hysteria://", "hysteria2://")
    if any(scheme in body for scheme in schemes):
        return body
    compact = "".join(body.split())
    try:
        decoded = base64.b64decode(compact + "=" * (-len(compact) % 4), validate=False).decode("utf-8", errors="replace").strip()
    except Exception:
        return body
    return decoded if any(scheme in decoded for scheme in schemes) else body


def _extract_configs(body: str) -> list[str]:
    schemes = ("vless://", "vmess://", "trojan://", "ss://", "hysteria://", "hysteria2://")
    result: list[str] = []
    seen: set[str] = set()
    for line in body.splitlines():
        line = line.strip()
        if not line or not line.startswith(schemes) or line in seen:
            continue
        seen.add(line)
        result.append(line)
    return result


def _message_chunks(text: str, limit: int = 3900) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        cut = remaining.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip("\r\n")
    if remaining:
        chunks.append(remaining)
    return chunks


async def deliver(event, service, details=None) -> None:
    subscription_url = (details.subscription_url if details else None) or service.subscription_url
    if not subscription_url:
        await event.respond(
            "⚠️ لینک اشتراک این سرویس هنوز آماده نیست. ابتدا سرویس را بروزرسانی کنید.",
            parse_mode=None,
        )
        return

    base = subscription_url.rstrip("/")
    links_url = f"{base}/links"
    timeout = httpx.Timeout(20.0, connect=8.0)

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            body = _decode_subscription_body(await _fetch_text(client, links_url))
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        await event.respond(
            f"❌ دریافت کانفیگ واقعی Xray ناموفق بود.\nHTTP {status}",
            parse_mode=None,
        )
        return
    except httpx.HTTPError:
        await event.respond(
            "❌ ارتباط با سابسکریپشن پاسارگارد برقرار نشد.\nلطفاً چند لحظه بعد دوباره تلاش کنید.",
            parse_mode=None,
        )
        return

    configs = _extract_configs(body)
    if not configs:
        await event.respond(
            "❌ داخل سابسکریپشن هیچ کانفیگ واقعی Xray پیدا نشد.\n\n"
            "پاسارگارد باید لینک‌هایی مثل vless:// یا vmess:// برگرداند.",
            parse_mode=None,
        )
        return

    # Put the subscription URL and the actual raw Xray links in the same
    # ordered Telegram message. For normal services this is a single message;
    # Telegram's 4096-character limit is respected for unusually large lists.
    lines = [
        f"📦 کانفیگ سرویس #{service.id}",
        "",
        "🔗 سابسکریپشن:",
        base,
        "",
        f"🦋 کانفیگ‌های واقعی Xray ({len(configs)} عدد):",
        "",
    ]
    for index, config in enumerate(configs, start=1):
        lines.append(f"{index}️⃣ {config}")
        lines.append("")
    lines.extend(
        [
            "━━━━━━━━━━━━━━━━",
            "✅ هر خط یک کانفیگ واقعی و قابل کپی است.",
            "💡 برای افزودن چند کانفیگ، می‌توانید خطوط را مستقیماً کپی کنید.",
        ]
    )
    message = "\n".join(lines).strip()

    chunks = _message_chunks(message)
    for index, chunk in enumerate(chunks, start=1):
        if len(chunks) > 1:
            chunk = f"📄 بخش {index}/{len(chunks)}\n\n{chunk}"
        await event.respond(chunk, parse_mode=None)

    # When the complete payload fits Telegram's limit, the user receives
    # exactly one clean message containing both the subscription and configs.
    if len(chunks) == 1:
        return

    await event.respond(
        "⚠️ تعداد کانفیگ‌ها زیاد بود و به چند پیام تقسیم شد؛ محتوای کانفیگ‌ها بدون تغییر ارسال شده است.",
        parse_mode=None,
    )
