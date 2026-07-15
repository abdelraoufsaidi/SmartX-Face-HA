"""Reverse-proxy HTTP/WebSocket pour exposer smartx-face-service sur la même origine que HA.

Pourquoi : les panels iframe (Enrôlement / Interphone) chargeaient jusqu'ici le
container smartx-face-service directement en http://host:port. Quand Home
Assistant est servi en https (ex: tunnel Cloudflare), le navigateur bloque ces
iframes en tant que "mixed content", indépendamment du certificat utilisé.

En faisant transiter ces requêtes par Home Assistant (même origine que la page
parente), elles héritent automatiquement du https de HA et le blocage
disparaît. Ce module fournit :
- SmartXFaceProxyView : proxy HTTP générique (GET/POST/DELETE), en streaming
  (nécessaire pour le flux MJPEG /stream, qui est une réponse infinie).
- async_register_talk_ws : pont WebSocket bidirectionnel pour /talk/ws
  (audio talkback), car un WebSocket ne peut pas être proxifié comme une
  requête HTTP classique.
"""

import asyncio
import contextlib
import logging

import aiohttp
from aiohttp import web

from homeassistant.core import HomeAssistant
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

# En-têtes qui ne doivent jamais être transmis tels quels d'un côté à l'autre du proxy.
_HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
}


class SmartXFaceProxyView(HomeAssistantView):
    """Proxifie GET/POST/DELETE vers smartx-face-service, en streaming.

    requires_auth=False : un panel de type "iframe" HA charge son URL via une
    simple navigation <iframe src="...">, sans jamais y attacher le jeton
    Bearer de HA (pas de cookie de session classique côté HA). Avec
    requires_auth=True, HA rejette donc systématiquement la requête, même
    pour un utilisateur connecté. On revient au même niveau de protection
    qu'avant cette modification (service accessible sans authentification),
    l'entry_id (ULID long et non devinable) dans le chemin jouant le rôle de
    jeton d'accès minimal.
    """

    requires_auth = False

    def __init__(self, entry_id: str, host: str, port: int):
        self._host = host
        self._port = port
        self.url = f"/api/smartx_face/{entry_id}/{{tail:.*}}"
        self.name = f"api:smartx_face:{entry_id}"

    async def _proxy(self, request: web.Request) -> web.StreamResponse:
        hass: HomeAssistant = request.app["hass"]
        session = async_get_clientsession(hass)
        tail = request.match_info.get("tail", "")
        target = f"http://{self._host}:{self._port}/{tail}"

        body = await request.read()
        fwd_headers = {
            k: v for k, v in request.headers.items() if k.lower() not in _HOP_BY_HOP
        }

        try:
            async with session.request(
                request.method,
                target,
                params=request.query,
                data=body or None,
                headers=fwd_headers,
                timeout=aiohttp.ClientTimeout(total=None, sock_connect=10),
            ) as upstream:
                resp = web.StreamResponse(
                    status=upstream.status,
                    headers={
                        k: v
                        for k, v in upstream.headers.items()
                        if k.lower() not in _HOP_BY_HOP
                    },
                )
                await resp.prepare(request)
                async for chunk in upstream.content.iter_any():
                    await resp.write(chunk)
                await resp.write_eof()
                return resp
        except Exception as e:
            _LOGGER.error("Erreur proxy SMARTX Face (%s): %s", tail, e)
            return web.Response(status=502, text=f"Erreur proxy smartx_face: {e}")

    async def get(self, request: web.Request, **kwargs) -> web.StreamResponse:
        return await self._proxy(request)

    async def post(self, request: web.Request, **kwargs) -> web.StreamResponse:
        return await self._proxy(request)

    async def delete(self, request: web.Request, **kwargs) -> web.StreamResponse:
        return await self._proxy(request)


async def _ws_bridge(
    ws_browser: web.WebSocketResponse, ws_backend: aiohttp.ClientWebSocketResponse
) -> None:
    """Relaie les frames audio dans les deux sens jusqu'à ce qu'un des deux côtés ferme."""

    async def browser_to_backend():
        async for msg in ws_browser:
            if msg.type == aiohttp.WSMsgType.BINARY:
                await ws_backend.send_bytes(msg.data)
            elif msg.type == aiohttp.WSMsgType.TEXT:
                await ws_backend.send_str(msg.data)
            else:
                break

    async def backend_to_browser():
        async for msg in ws_backend:
            if msg.type == aiohttp.WSMsgType.BINARY:
                await ws_browser.send_bytes(msg.data)
            elif msg.type == aiohttp.WSMsgType.TEXT:
                await ws_browser.send_str(msg.data)
            else:
                break

    tasks = [asyncio.create_task(browser_to_backend()), asyncio.create_task(backend_to_browser())]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for t in pending:
        t.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await t


def _register_route(router, method: str, path: str, handler) -> None:
    """Enregistre une route en ignorant l'erreur si elle existe déjà (rechargement d'intégration)."""
    try:
        router.add_route(method, path, handler)
    except RuntimeError:
        _LOGGER.debug("Route %s %s déjà enregistrée, on garde l'existante", method, path)


def async_register_proxy(hass: HomeAssistant, entry_id: str, host: str, port: int) -> None:
    """Enregistre le proxy HTTP générique + le pont WebSocket /talk/ws pour cette entrée."""

    view = SmartXFaceProxyView(entry_id, host, port)
    try:
        hass.http.register_view(view)
    except RuntimeError:
        _LOGGER.debug("Vue proxy smartx_face déjà enregistrée pour %s", entry_id)

    ws_path = f"/api/smartx_face/{entry_id}/talk/ws"

    async def ws_handler(request: web.Request) -> web.WebSocketResponse:
        ws_browser = web.WebSocketResponse()
        await ws_browser.prepare(request)

        session = async_get_clientsession(hass)
        backend_url = f"http://{host}:{port}/talk/ws"
        try:
            async with session.ws_connect(backend_url, timeout=10) as ws_backend:
                await _ws_bridge(ws_browser, ws_backend)
        except Exception as e:
            _LOGGER.error("Erreur pont WebSocket SMARTX Face talk: %s", e)
        finally:
            if not ws_browser.closed:
                await ws_browser.close()
        return ws_browser

    _register_route(hass.http.app.router, "GET", ws_path, ws_handler)
