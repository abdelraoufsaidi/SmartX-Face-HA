"""Caméra SMARTX — proxie le flux MJPEG live du service face-service dans Home Assistant.

Permet de voir qui sonne à la porte directement depuis un dashboard HA
(carte caméra native), sans quitter l'interface.
"""

import logging
import aiohttp
from aiohttp import web

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, CONF_SERVICE_HOST, CONF_SERVICE_PORT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    async_add_entities([SmartXDoorCamera(hass, entry)])


class SmartXDoorCamera(Camera):
    _attr_name = "SMARTX Caméra porte"
    _attr_icon = "mdi:cctv"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        super().__init__()
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_door_camera"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="SMARTX Face Recognition",
            manufacturer="SMARTX",
            model="Face Recognition + VTO Door Control",
        )

    @property
    def _base_url(self) -> str:
        host = self._entry.data[CONF_SERVICE_HOST]
        port = self._entry.data[CONF_SERVICE_PORT]
        return f"http://{host}:{port}"

    async def async_camera_image(self, width=None, height=None):
        """Image fixe (utilisée pour les vignettes, notifications, historique)."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                f"{self._base_url}/snapshot", timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    return await resp.read()
        except Exception as e:
            _LOGGER.warning(f"Impossible de récupérer le snapshot : {e}")
        return None

    async def handle_async_mjpeg_stream(self, request):
        """Flux live continu : proxie directement /stream du service vers le dashboard HA."""
        session = async_get_clientsession(self.hass)
        try:
            source_resp = await session.get(f"{self._base_url}/stream")
        except Exception as e:
            _LOGGER.warning(f"Impossible de joindre le flux MJPEG : {e}")
            return None

        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": source_resp.headers.get(
                    "Content-Type", "multipart/x-mixed-replace; boundary=frame"
                )
            },
        )
        await response.prepare(request)
        try:
            async for chunk in source_resp.content.iter_any():
                await response.write(chunk)
        except (ConnectionResetError, aiohttp.ClientConnectionError):
            pass
        finally:
            source_resp.close()
        return response
