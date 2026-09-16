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


def _chunks(lines: list[str], limit: int = 3900) -> list[str]:
    """Split raw links without ever creating a Telegram-over-limit message."""
    result: list[str] = []
    current = ""
    for line in lines:
        if len(line) <= limit:
            if current and len(current) + len(line) + 1 > limit:
                result.append(current)
                current = line
            else:
                current = line if not current else f"{current}\n{line}"
            continue
        if current:
            result.append(current)
            current = ""
        for start in range(0, len(line), limit):
            result.append(line[start : start + limit])
    if current:
        result.append(current)
    return result


async def deliver(event, service, details=None) -> None:
    subscription_url = (details.subscription_url if details else None) or service.subscription_url
    if not subscription_url:
        await event.respond("⚠️ لینک اشتراک این سرویس هنوز آماده نیست. ابتدا سرویس را بروزرسانی کنید.", parse_mode=None)
        return

    base = subscription_url.rstrip("/")
    links_url = f"{base}/links"
    timeout = httpx.Timeout(20.0, connect=8.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            body = _decode_subscription_body(await _fetch_text(client, links_url))
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        await event.respond(f"❌ دریافت کانفیگ‌های واقعی Xray ناموفق بود.\nHTTP {status}", parse_mode=None)
        return
    except httpx.HTTPError:
        await event.respond("❌ ارتباط با سابسکریپشن پاسارگارد برقرار نشد.\nلطفاً چند لحظه بعد دوباره تلاش کنید.", parse_mode=None)
        return

    if not body:
        await event.respond("❌ سابسکریپشن هیچ کانفیگ Xray قابل استفاده‌ای برنگرداند.", parse_mode=None)
        return

    schemes = ("vless://", "vmess://", "trojan://", "ss://", "hysteria://", "hysteria2://")
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    share_lines = [line for line in lines if line.startswith(schemes)]
    if not share_lines:
        share_lines = [body]

    chunks = _chunks(share_lines)
    await event.respond(
        f"🦋 کانفیگ‌های واقعی Xray سرویس #{service.id}\n\n"
        f"✅ {len(share_lines)} کانفیگ از داخل سابسکریپشن دریافت شد.\n"
        "هر خط یک کانفیگ قابل کپی است:",
        parse_mode=None,
    )

    sent = 0
    for chunk in chunks:
        try:
            await event.respond(chunk, parse_mode=None)
            sent += 1
        except Exception:
            # A single malformed/oversized Telegram message must not bubble
            # into user_services' generic error screen. Try the same payload
            # as a plain text document so the raw Xray data is still delivered.
            try:
                await event.client.send_document(
                    event.chat_id,
                    chunk.encode("utf-8"),
                    filename=f"service-{service.id}-xray-{sent + 1}.txt",
                    caption="🦋 کانفیگ خام Xray",
                )
                sent += 1
            except Exception:
                continue

    if sent:
        await event.respond(
            f"✅ {len(share_lines)} کانفیگ واقعی Xray ارسال شد.",
            parse_mode=None,
        )
    else:
        await event.respond("❌ ارسال کانفیگ به تلگرام ناموفق بود. لطفاً دوباره تلاش کنید.", parse_mode=None)
