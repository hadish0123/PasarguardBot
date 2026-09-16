from __future__ import annotations

import base64
import json
from urllib.parse import quote, urlencode

import httpx


_SHARE_SCHEMES = ("vless://", "vmess://", "trojan://", "ss://", "hysteria://", "hysteria2://")


async def _fetch_text(client: httpx.AsyncClient, url: str) -> str:
    response = await client.get(url)
    response.raise_for_status()
    return response.content.decode("utf-8", errors="replace").strip()


def _looks_like_share_links(value: str) -> bool:
    return any(scheme in value for scheme in _SHARE_SCHEMES)


def _json_documents(body: str) -> list[dict]:
    decoder = json.JSONDecoder()
    documents: list[dict] = []
    position = 0
    while position < len(body):
        while position < len(body) and body[position].isspace():
            position += 1
        if position >= len(body):
            break
        try:
            value, end = decoder.raw_decode(body, position)
        except json.JSONDecodeError:
            return []
        if isinstance(value, dict):
            documents.append(value)
        position = end
    return documents


def _vless_from_xray(document: dict) -> list[str]:
    links: list[str] = []
    for outbound in document.get("outbounds") or []:
        if not isinstance(outbound, dict) or outbound.get("protocol") != "vless":
            continue
        settings = outbound.get("settings") or {}
        stream = outbound.get("streamSettings") or {}
        vnext = settings.get("vnext") or []
        if not isinstance(vnext, list):
            continue

        for server in vnext:
            if not isinstance(server, dict):
                continue
            address = server.get("address")
            port = server.get("port")
            users = server.get("users") or []
            if not address or not port or not isinstance(users, list):
                continue

            network = str(stream.get("network") or "tcp")
            security = str(stream.get("security") or "")
            tcp = stream.get("tcpSettings") or {}
            ws = stream.get("wsSettings") or {}
            grpc = stream.get("grpcSettings") or {}
            reality = stream.get("realitySettings") or {}
            tls = stream.get("tlsSettings") or {}

            for user in users:
                if not isinstance(user, dict) or not user.get("id"):
                    continue
                query: list[tuple[str, str]] = [("security", security)]
                encryption = str(user.get("encryption") or "")
                if encryption:
                    query.append(("encryption", encryption))

                if network == "tcp":
                    header = tcp.get("header") or {}
                    header_type = header.get("type")
                    if header_type:
                        query.append(("headerType", str(header_type)))
                    query.append(("type", "tcp"))
                elif network == "ws":
                    query.append(("type", "ws"))
                    if ws.get("path"):
                        query.append(("path", str(ws["path"])))
                    headers = ws.get("headers") or {}
                    if headers.get("Host"):
                        query.append(("host", str(headers["Host"])))
                elif network == "grpc":
                    query.append(("type", "grpc"))
                    if grpc.get("serviceName"):
                        query.append(("serviceName", str(grpc["serviceName"])))
                else:
                    query.append(("type", network))

                if security == "tls" and tls.get("serverName"):
                    query.append(("sni", str(tls["serverName"])))
                elif security == "reality":
                    if reality.get("serverName"):
                        query.append(("sni", str(reality["serverName"])))
                    if reality.get("publicKey"):
                        query.append(("pbk", str(reality["publicKey"])))
                    if reality.get("shortId"):
                        query.append(("sid", str(reality["shortId"])))
                    if reality.get("spiderX"):
                        query.append(("spx", str(reality["spiderX"])))

                encoded_query = urlencode(query, quote_via=quote, safe="-._~")
                remark = str(outbound.get("tag") or document.get("remarks") or "Xray")
                links.append(
                    f"vless://{user['id']}@{address}:{port}?{encoded_query}#{quote(remark, safe='-._~')}"
                )
    return links


def _decode_subscription_body(body: str) -> str:
    if not body:
        return ""
    if _looks_like_share_links(body):
        return body

    documents = _json_documents(body)
    converted: list[str] = []
    for document in documents:
        converted.extend(_vless_from_xray(document))
    if converted:
        return "\n".join(dict.fromkeys(converted))

    compact = "".join(body.split())
    try:
        decoded = base64.b64decode(compact + "=" * (-len(compact) % 4), validate=False).decode("utf-8", errors="replace").strip()
    except Exception:
        return body
    if _looks_like_share_links(decoded):
        return decoded

    documents = _json_documents(decoded)
    converted = []
    for document in documents:
        converted.extend(_vless_from_xray(document))
    if converted:
        return "\n".join(dict.fromkeys(converted))
    return body


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
    except httpx.HTTPError as exc:
        await event.respond(f"❌ ارتباط با سابسکریپشن پاسارگارد برقرار نشد.\n{type(exc).__name__}", parse_mode=None)
        return

    if not body:
        await event.respond("❌ سابسکریپشن هیچ کانفیگ Xray قابل استفاده‌ای برنگرداند.", parse_mode=None)
        return

    lines = [line.strip() for line in body.splitlines() if line.strip()]
    share_lines = [line for line in lines if line.startswith(_SHARE_SCHEMES)]
    if not share_lines:
        share_lines = [body]

    await event.respond(
        f"🦋 کانفیگ‌های Xray سرویس #{service.id}\n\n"
        f"✅ {len(share_lines)} کانفیگ آماده شد.\n"
        "هر خط یک کانفیگ کامل و قابل کپی است:",
        parse_mode=None,
    )

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
        f"✅ ارسال شد: {len(share_lines)} کانفیگ Xray.\n\nهر خط را می‌توانید مستقیماً کپی و داخل کلاینت وارد کنید.",
        parse_mode=None,
    )
