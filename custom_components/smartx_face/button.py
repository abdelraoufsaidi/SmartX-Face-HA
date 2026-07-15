"""Bouton 'Ouvrir la porte' — appelle POST /door/open sur le container face-service."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from . import async_open_door
from .const import DOMAIN, CONF_SERVICE_HOST, CONF_SERVICE_PORT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    async_add_entities([SmartXOpenDoorButton(hass, entry)])


class SmartXOpenDoorButton(ButtonEntity):
    _attr_name = "SMARTX Ouvrir la porte"
    _attr_icon = "mdi:door-open"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_open_door"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="SMARTX Face Recognition",
            manufacturer="SMARTX",
            model="Face Recognition + VTO Door Control",
        )

    async def async_press(self) -> None:
        host = self._entry.data[CONF_SERVICE_HOST]
        port = self._entry.data[CONF_SERVICE_PORT]
        await async_open_door(self.hass, host, port)
