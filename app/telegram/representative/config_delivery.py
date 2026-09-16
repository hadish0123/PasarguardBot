from __future__ import annotations

import httpx


async def deliver(event, service, details=None) -> None:
    subscription_url = (details.subscription_url if details else None) or service.subscription_url
    if not subscription_url:
        await event.respond(
            "⚠️ لینک اشتراک این سرویس هنوز آماده نیست. ابتدا سرویس را بروزرسانی کنید.",
            parse_mode=None,
        )
        return

    xray_url = subscription_url.rstrip("/") + "/xray"
    timeout = httpx.Timeout(20.0, connect=8.0)

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(xray_url)
            if response.status_code != 200:
                await event.respond(
                    f"❌ دریافت کانفیگ خام Xray ناموفق بود.\nHTTP {response.status_code}",
                    parse_mode=None,
                )
                return
            body = response.content.decode("utf-8", errors="replace").strip()
    except httpx.HTTPError as exc:
        await event.respond(
            f"❌ ارتباط با لینک Xray برقرار نشد.\n{type(exc).__name__}",
            parse_mode=None,
        )
        return

    if not body:
        await event.respond("❌ کانفیگ خام Xray خالی است.", parse_mode=None)
        return

    # Send the provider response as plain text, without Markdown/HTML and
    # without converting it to a subscription URL. This keeps vless://,
    # vmess://, trojan:// and other raw Xray entries copyable as-is.
    chunks: list[str] = []
    remaining = body
    while len(remaining) > 3800:
        cut = remaining.rfind("\n", 0, 3800)
        if cut <= 0:
            cut = 3800
        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip("\n")
    if remaining:
        chunks.append(remaining)

    await event.respond(
        f"🦋 کانفیگ خام Xray سرویس #{service.id}\n\n"
        "کانفیگ‌ها را دقیقاً به همان شکل دریافتی از پاسارگارد ارسال می‌کنم.",
        parse_mode=None,
    )
    for chunk in chunks:
        await event.respond(chunk, parse_mode=None)

    await event.respond(
        f"✅ {len(chunks)} بخش از کانفیگ خام Xray ارسال شد.",
        parse_mode=None,
    )
