from __future__ import annotations

import base64
import httpx


async def _fetch_text(client: httpx.AsyncClient, url: str) -> str:
    response = await client.get(url)
    response.raise_for_status()
    return response.content.decode("utf-8", errors="replace").strip()


def _decode_subscription_body(body: str) -> str:
    """Return newline-separated raw share links from a PasarGuard subscription body."""
    if not body:
        return ""

    # PasarGuard's /links endpoint is the canonical endpoint for raw share
    # links. Depending on the panel/template, the response may be plain text
    # or base64 encoded. Decode base64 only when the decoded payload actually
    # looks like share links; never turn an arbitrary text response into junk.
    if any(scheme in body for scheme in ("vless://", "vmess://", "trojan://", "ss://", "hysteria://", "hysteria2://")):
        return body

    compact = "".join(body.split())
    try:
        decoded = base64.b64decode(compact + "=" * (-len(compact) % 4), validate=False).decode("utf-8", errors="replace").strip()
    except Exception:
        return body

    if any(scheme in decoded for scheme in ("vless://", "vmess://", "trojan://", "ss://", "hysteria://", "hysteria2://")):
        return decoded
    return body


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
            f"❌ دریافت کانفیگ‌های واقعی Xray ناموفق بود.\nHTTP {status}",
            parse_mode=None,
        )
        return
    except httpx.HTTPError as exc:
        await event.respond(
            f"❌ ارتباط با سابسکریپشن پاسارگارد برقرار نشد.\n{type(exc).__name__}",
            parse_mode=None,
        )
        return

    if not body:
        await event.respond("❌ سابسکریپشن هیچ کانفیگ Xray قابل استفاده‌ای برنگرداند.", parse_mode=None)
        return

    # /links is what we need here: the actual share URIs contained in the
    # subscription (vless://, vmess://, trojan://, ss://, ...), not the full
    # Xray client JSON returned by /xray.
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    share_lines = [
        line for line in lines
        if line.startswith(("vless://", "vmess://", "trojan://", "ss://", "hysteria://", "hysteria2://"))
    ]

    if not share_lines:
        # Some panels return a single long body without clean line breaks.
        # Still send it so the user can inspect/copy the exact subscription
        # payload instead of receiving the unrelated Xray JSON profile.
        share_lines = [body]

    await event.respond(
        f"🦋 کانفیگ‌های واقعی Xray سرویس #{service.id}\n\n"
        f"✅ {len(share_lines)} کانفیگ از داخل سابسکریپشن دریافت شد.\n"
        "هر خط یک کانفیگ قابل کپی است:",
        parse_mode=None,
    )

    # Keep each link intact. Telegram message limit is ~4096 chars, so split
    # only between complete links whenever possible.
    current = ""
    chunks: list[str] = []
    for line in share_lines:
        if current and len(current) + len(line) + 1 > 3900:
            chunks.append(current)
            current = ""
        current = line if not current else f"{current}\n{line}"
    if current:
        chunks.append(current)

    for chunk in chunks:
        await event.respond(chunk, parse_mode=None)

    await event.respond(
        f"✅ ارسال شد: {len(share_lines)} کانفیگ واقعی از سابسکریپشن.",
        parse_mode=None,
    )
