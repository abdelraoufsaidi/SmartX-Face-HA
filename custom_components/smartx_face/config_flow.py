"""Config flow SMARTX Face Recognition : service -> features -> source caméra -> (caméra) -> VTO."""

import logging
import voluptuous as vol
import requests

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_SERVICE_HOST,
    CONF_SERVICE_PORT,
    CONF_AUTO_OPEN_DOOR,
    CONF_CAMERA_SOURCE,
    CAMERA_SOURCE_VTO,
    CAMERA_SOURCE_SEPARATE,
    CONF_CAM_IP,
    CONF_CAM_USERNAME,
    CONF_CAM_PASSWORD,
    CONF_CAM_CHANNEL,
    CONF_CAM_SUBTYPE,
    CONF_VTO_IP,
    CONF_VTO_USERNAME,
    CONF_VTO_PASSWORD,
    CONF_VTO_CHANNEL,
    CONF_VTO_SUBTYPE,
    CONF_ENABLE_TALK,
    CONF_TALK_LOCAL_IP,
    CONF_TALK_EXTENSION,
    CONF_TALK_PASSWORD,
    CONF_TALK_VTO_EXTENSION,
    DEFAULT_SERVICE_PORT,
)

_LOGGER = logging.getLogger(__name__)


def _check_service_reachable(host: str, port: int) -> bool:
    try:
        resp = requests.get(f"http://{host}:{port}/health", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def _build_payload(data: dict) -> dict:
    """Construit le payload /config à partir des données du flow, quel que soit le mode."""
    if data.get(CONF_CAMERA_SOURCE) == CAMERA_SOURCE_SEPARATE:
        camera_cfg = {
            "ip": data[CONF_CAM_IP],
            "username": data[CONF_CAM_USERNAME],
            "password": data[CONF_CAM_PASSWORD],
            "channel": data[CONF_CAM_CHANNEL],
            "subtype": data[CONF_CAM_SUBTYPE],
        }
    else:
        # Caméra du VTO : mêmes identifiants pour le flux et pour la porte
        camera_cfg = {
            "ip": data[CONF_VTO_IP],
            "username": data[CONF_VTO_USERNAME],
            "password": data[CONF_VTO_PASSWORD],
            "channel": data.get(CONF_VTO_CHANNEL, "1"),
            "subtype": data.get(CONF_VTO_SUBTYPE, "1"),
        }

    vto_cfg = {
        "ip": data[CONF_VTO_IP],
        "username": data[CONF_VTO_USERNAME],
        "password": data[CONF_VTO_PASSWORD],
    }

    payload = {"camera": camera_cfg, "vto": vto_cfg}

    if data.get(CONF_ENABLE_TALK):
        payload["talk"] = {
            "local_ip": data.get(CONF_TALK_LOCAL_IP, ""),
            "extension": data.get(CONF_TALK_EXTENSION, ""),
            "password": data.get(CONF_TALK_PASSWORD, ""),
            "vto_extension": data.get(CONF_TALK_VTO_EXTENSION, "8001"),
        }

    return payload


def _push_config_to_service(host: str, port: int, payload: dict) -> bool:
    try:
        resp = requests.post(f"http://{host}:{port}/config", json=payload, timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


class SmartXFaceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Assistant de configuration : service -> features -> source caméra -> (caméra) -> VTO."""

    VERSION = 1

    def __init__(self):
        self._data: dict = {}

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Étape 1 : adresse du container smartx_face_service."""
        errors = {}

        if user_input is not None:
            reachable = await self.hass.async_add_executor_job(
                _check_service_reachable,
                user_input[CONF_SERVICE_HOST],
                user_input[CONF_SERVICE_PORT],
            )
            if not reachable:
                errors["base"] = "cannot_connect"
            else:
                self._data.update(user_input)
                return await self.async_step_features()

        schema = vol.Schema({
            vol.Required(CONF_SERVICE_HOST): str,
            vol.Required(CONF_SERVICE_PORT, default=DEFAULT_SERVICE_PORT): int,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_features(self, user_input=None) -> FlowResult:
        """Étape 2 : ouverture automatique de la porte sur reconnaissance."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_camera_source()

        schema = vol.Schema({
            vol.Required(CONF_AUTO_OPEN_DOOR, default=False): bool,
        })
        return self.async_show_form(step_id="features", data_schema=schema)

    async def async_step_camera_source(self, user_input=None) -> FlowResult:
        """Étape 3 : la reconnaissance se fait-elle via la caméra du VTO, ou une caméra IP séparée ?"""
        if user_input is not None:
            self._data.update(user_input)
            if user_input[CONF_CAMERA_SOURCE] == CAMERA_SOURCE_SEPARATE:
                return await self.async_step_camera()
            return await self.async_step_vto()

        schema = vol.Schema({
            vol.Required(CONF_CAMERA_SOURCE, default=CAMERA_SOURCE_VTO): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": CAMERA_SOURCE_VTO, "label": "Caméra du VTO (reconnaissance + porte, même appareil)"},
                        {"value": CAMERA_SOURCE_SEPARATE, "label": "Caméra IP séparée (reconnaissance) + VTO (porte uniquement)"},
                    ],
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
        })
        return self.async_show_form(step_id="camera_source", data_schema=schema)

    async def async_step_camera(self, user_input=None) -> FlowResult:
        """Étape 4 (si caméra séparée) : identifiants de la caméra IP dédiée à la reconnaissance."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_vto()

        schema = vol.Schema({
            vol.Required(CONF_CAM_IP): str,
            vol.Required(CONF_CAM_USERNAME, default="admin"): str,
            vol.Required(CONF_CAM_PASSWORD): str,
            vol.Required(CONF_CAM_CHANNEL, default="1"): str,
            vol.Required(CONF_CAM_SUBTYPE, default="1"): str,
        })
        return self.async_show_form(step_id="camera", data_schema=schema)

    async def async_step_vto(self, user_input=None) -> FlowResult:
        """Dernière étape : identifiants du VTO Dahua (porte, + flux caméra si mode VTO)."""
        errors = {}
        is_separate = self._data.get(CONF_CAMERA_SOURCE) == CAMERA_SOURCE_SEPARATE

        if user_input is not None:
            self._data.update(user_input)

            if user_input.get(CONF_ENABLE_TALK):
                return await self.async_step_talk()

            payload = _build_payload(self._data)
            pushed = await self.hass.async_add_executor_job(
                _push_config_to_service,
                self._data[CONF_SERVICE_HOST],
                self._data[CONF_SERVICE_PORT],
                payload,
            )
            if not pushed:
                errors["base"] = "cannot_push_config"
            else:
                return self.async_create_entry(title="SMARTX Face Recognition", data=self._data)

        if is_separate:
            # Pas besoin de channel/subtype : le VTO ne sert qu'à ouvrir la porte ici
            schema = vol.Schema({
                vol.Required(CONF_VTO_IP): str,
                vol.Required(CONF_VTO_USERNAME, default="admin"): str,
                vol.Required(CONF_VTO_PASSWORD): str,
                vol.Required(CONF_ENABLE_TALK, default=False): bool,
            })
        else:
            schema = vol.Schema({
                vol.Required(CONF_VTO_IP): str,
                vol.Required(CONF_VTO_USERNAME, default="admin"): str,
                vol.Required(CONF_VTO_PASSWORD): str,
                vol.Required(CONF_VTO_CHANNEL, default="1"): str,
                vol.Required(CONF_VTO_SUBTYPE, default="1"): str,
                vol.Required(CONF_ENABLE_TALK, default=False): bool,
            })
        return self.async_show_form(step_id="vto", data_schema=schema, errors=errors)

    async def async_step_talk(self, user_input=None) -> FlowResult:
        """Étape optionnelle : identifiants SIP de l'interphone (entrée VTS créée manuellement sur le VTO)."""
        errors = {}
        if user_input is not None:
            self._data.update(user_input)
            payload = _build_payload(self._data)
            pushed = await self.hass.async_add_executor_job(
                _push_config_to_service,
                self._data[CONF_SERVICE_HOST],
                self._data[CONF_SERVICE_PORT],
                payload,
            )
            if not pushed:
                errors["base"] = "cannot_push_config"
            else:
                return self.async_create_entry(title="SMARTX Face Recognition", data=self._data)

        schema = vol.Schema({
            vol.Required(CONF_TALK_LOCAL_IP): str,
            vol.Required(CONF_TALK_EXTENSION, default="9904"): str,
            vol.Required(CONF_TALK_PASSWORD): str,
            vol.Required(CONF_TALK_VTO_EXTENSION, default="8001"): str,
        })
        return self.async_show_form(step_id="talk", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry):
        return SmartXFaceOptionsFlow()


class SmartXFaceOptionsFlow(config_entries.OptionsFlow):
    """Permet de tout modifier après coup, sans réinstaller."""

    async def async_step_init(self, user_input=None) -> FlowResult:
        errors = {}
        current = {**self.config_entry.data}
        is_separate = current.get(CONF_CAMERA_SOURCE) == CAMERA_SOURCE_SEPARATE

        if user_input is not None:
            payload = _build_payload(user_input)
            pushed = await self.hass.async_add_executor_job(
                _push_config_to_service,
                current[CONF_SERVICE_HOST],
                current[CONF_SERVICE_PORT],
                payload,
            )
            if not pushed:
                errors["base"] = "cannot_push_config"
            else:
                new_data = {**current, **user_input}
                self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
                return self.async_create_entry(title="", data={})

        fields = {
            vol.Required(CONF_AUTO_OPEN_DOOR, default=current.get(CONF_AUTO_OPEN_DOOR, False)): bool,
            vol.Required(
                CONF_CAMERA_SOURCE, default=current.get(CONF_CAMERA_SOURCE, CAMERA_SOURCE_VTO)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": CAMERA_SOURCE_VTO, "label": "Caméra du VTO (reconnaissance + porte)"},
                        {"value": CAMERA_SOURCE_SEPARATE, "label": "Caméra IP séparée + VTO (porte uniquement)"},
                    ],
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Required(CONF_ENABLE_TALK, default=current.get(CONF_ENABLE_TALK, False)): bool,
        }

        if is_separate:
            fields.update({
                vol.Required(CONF_CAM_IP, default=current.get(CONF_CAM_IP, "")): str,
                vol.Required(CONF_CAM_USERNAME, default=current.get(CONF_CAM_USERNAME, "admin")): str,
                vol.Required(CONF_CAM_PASSWORD, default=current.get(CONF_CAM_PASSWORD, "")): str,
                vol.Required(CONF_CAM_CHANNEL, default=current.get(CONF_CAM_CHANNEL, "1")): str,
                vol.Required(CONF_CAM_SUBTYPE, default=current.get(CONF_CAM_SUBTYPE, "1")): str,
                vol.Required(CONF_VTO_IP, default=current.get(CONF_VTO_IP, "")): str,
                vol.Required(CONF_VTO_USERNAME, default=current.get(CONF_VTO_USERNAME, "admin")): str,
                vol.Required(CONF_VTO_PASSWORD, default=current.get(CONF_VTO_PASSWORD, "")): str,
            })
        else:
            fields.update({
                vol.Required(CONF_VTO_IP, default=current.get(CONF_VTO_IP, "")): str,
                vol.Required(CONF_VTO_USERNAME, default=current.get(CONF_VTO_USERNAME, "admin")): str,
                vol.Required(CONF_VTO_PASSWORD, default=current.get(CONF_VTO_PASSWORD, "")): str,
                vol.Required(CONF_VTO_CHANNEL, default=current.get(CONF_VTO_CHANNEL, "1")): str,
                vol.Required(CONF_VTO_SUBTYPE, default=current.get(CONF_VTO_SUBTYPE, "1")): str,
            })

        if current.get(CONF_ENABLE_TALK):
            fields.update({
                vol.Required(CONF_TALK_LOCAL_IP, default=current.get(CONF_TALK_LOCAL_IP, "")): str,
                vol.Required(CONF_TALK_EXTENSION, default=current.get(CONF_TALK_EXTENSION, "9904")): str,
                vol.Required(CONF_TALK_PASSWORD, default=current.get(CONF_TALK_PASSWORD, "")): str,
                vol.Required(CONF_TALK_VTO_EXTENSION, default=current.get(CONF_TALK_VTO_EXTENSION, "8001")): str,
            })

        schema = vol.Schema(fields)
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
