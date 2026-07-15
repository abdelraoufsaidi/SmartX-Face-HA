"""SMARTX Face Recognition — intégration Home Assistant."""

import logging
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, Event, callback
from homeassistant.components import frontend

from .const import DOMAIN, CONF_SERVICE_HOST, CONF_SERVICE_PORT, CONF_AUTO_OPEN_DOOR, CONF_ENABLE_TALK
from .http import async_register_proxy

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["button", "camera"]


def _call_open_door(host: str, port: int) -> dict:
    resp = requests.post(f"http://{host}:{port}/door/open", timeout=5)
    return resp.json()


async def async_open_door(hass: HomeAssistant, host: str, port: int) -> None:
    """Fonction partagée : appelée par le bouton manuel ET par l'ouverture automatique."""
    try:
        data = await hass.async_add_executor_job(_call_open_door, host, port)
        if data.get("opened"):
            _LOGGER.info("Porte ouverte avec succès")
        else:
            _LOGGER.warning(f"Échec ouverture porte : {data}")
    except Exception as e:
        _LOGGER.error(f"Erreur appel ouverture porte : {e}")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    host = entry.data[CONF_SERVICE_HOST]
    port = entry.data[CONF_SERVICE_PORT]

    # Proxy HTTP/WebSocket : fait passer les panels par Home Assistant (même
    # origine que la page HA) au lieu d'appeler http://host:port directement.
    # Nécessaire pour que les iframes fonctionnent quand HA est servi en
    # https (ex: tunnel Cloudflare) -> évite le blocage "mixed content".
    async_register_proxy(hass, entry.entry_id, host, port)
    proxy_base = f"/api/smartx_face/{entry.entry_id}"

    enroll_url = f"{proxy_base}/enroll_ui"

    # Panel latéral "SMARTX Enrôlement" -> iframe pointant vers le proxy HA (même origine).
    frontend.async_register_built_in_panel(
        hass,
        component_name="iframe",
        sidebar_title="SMARTX Enrôlement",
        sidebar_icon="mdi:face-recognition",
        frontend_url_path=f"smartx_face_enroll_{entry.entry_id}",
        config={"url": enroll_url},
        require_admin=True,
    )

    # Panel latéral "SMARTX Interphone" -> vidéo live + appel SIP + ouverture de porte.
    if entry.data.get(CONF_ENABLE_TALK, False):
        talk_url = f"{proxy_base}/talk_ui"
        frontend.async_register_built_in_panel(
            hass,
            component_name="iframe",
            sidebar_title="SMARTX Interphone",
            sidebar_icon="mdi:phone-in-talk",
            frontend_url_path=f"smartx_face_talk_{entry.entry_id}",
            config={"url": talk_url},
            require_admin=False,
        )

    # ── Ouverture automatique de la porte sur reconnaissance faciale ──
    # Activable/désactivable par le client final dans la config de l'intégration,
    # sans avoir à écrire d'automatisation YAML.
    unsub = None
    if entry.data.get(CONF_AUTO_OPEN_DOOR, False):

        @callback
        def _handle_presence_change(event: Event) -> None:
            entity_id = event.data.get("entity_id", "")
            if not entity_id.startswith("binary_sensor.presence_"):
                return
            new_state = event.data.get("new_state")
            if new_state is None or new_state.state != "on":
                return
            _LOGGER.info(f"Reconnaissance détectée ({entity_id}) -> ouverture automatique")
            hass.async_create_task(async_open_door(hass, host, port))

        unsub = hass.bus.async_listen("state_changed", _handle_presence_change)
        _LOGGER.info("Ouverture automatique de la porte activée")

    hass.data[DOMAIN][f"{entry.entry_id}_unsub"] = unsub

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        unsub = hass.data[DOMAIN].pop(f"{entry.entry_id}_unsub", None)
        if unsub:
            unsub()
        hass.data[DOMAIN].pop(entry.entry_id, None)
        frontend.async_remove_panel(hass, f"smartx_face_enroll_{entry.entry_id}")
        if entry.data.get(CONF_ENABLE_TALK, False):
            frontend.async_remove_panel(hass, f"smartx_face_talk_{entry.entry_id}")
    return unload_ok
