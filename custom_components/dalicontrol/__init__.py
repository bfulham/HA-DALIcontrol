"""The DALIcontrol integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .client import DaliControlClient, DaliControlError
from .const import CONF_CONTROLLER_ID, CONF_PROTOCOL, DOMAIN
from .protocol import (
    GroupActionType,
    group_command,
    list_start_action,
    list_stop_action,
    sequence_action,
)

PLATFORMS = [Platform.LIGHT]

type DaliControlConfigEntry = ConfigEntry[DaliControlClient]

ATTR_ENTRY = "config_entry_id"

_BASE = {vol.Required(ATTR_ENTRY): cv.string}
_GROUP = {**_BASE, vol.Required("group"): vol.All(vol.Coerce(int), vol.Range(min=1, max=128))}

SERVICE_SCHEMAS = {
    "run_sequence": vol.Schema(
        {
            **_GROUP,
            vol.Required("sequence"): vol.All(vol.Coerce(int), vol.Range(min=1, max=32)),
            vol.Optional("step", default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=8)),
        }
    ),
    "run_list": vol.Schema(
        {**_GROUP, vol.Required("list"): vol.All(vol.Coerce(int), vol.Range(min=1, max=26))}
    ),
    "stop_list": vol.Schema(
        {**_GROUP, vol.Optional("list"): vol.All(vol.Coerce(int), vol.Range(min=1, max=26))}
    ),
    "send_raw": vol.Schema({**_BASE, vol.Required("frame"): cv.string}),
}


def _entry_for(hass: HomeAssistant, entry_id: str) -> DaliControlConfigEntry:
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN or not hasattr(entry, "runtime_data"):
        raise ServiceValidationError(f"No loaded DALIcontrol entry {entry_id}")
    return entry


async def _handle(hass: HomeAssistant, call: ServiceCall) -> None:
    entry = _entry_for(hass, call.data[ATTR_ENTRY])
    controller = entry.data[CONF_CONTROLLER_ID]
    data = call.data
    if call.service == "run_sequence":
        frame = group_command(
            controller,
            data["group"],
            GroupActionType.SEQUENCE,
            sequence_action(data["sequence"], data["step"]),
        )
    elif call.service == "run_list":
        frame = group_command(
            controller, data["group"], GroupActionType.LIST, list_start_action(data["list"])
        )
    elif call.service == "stop_list":
        frame = group_command(
            controller, data["group"], GroupActionType.LIST, list_stop_action(data.get("list"))
        )
    else:
        frame = data["frame"].strip()
        if not (frame.startswith("$") and frame.endswith("*")):
            raise ServiceValidationError("Frame must start with $ and end with *")
    try:
        await entry.runtime_data.async_send(frame)
    except DaliControlError as err:
        raise HomeAssistantError(str(err)) from err


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register domain services."""

    def _make(name: str):
        async def _service(call: ServiceCall) -> None:
            await _handle(hass, call)

        return _service

    for name, schema in SERVICE_SCHEMAS.items():
        hass.services.async_register(DOMAIN, name, _make(name), schema=schema)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: DaliControlConfigEntry) -> bool:
    """Set up a DCBM controller from a config entry."""
    entry.runtime_data = DaliControlClient(
        entry.data[CONF_HOST], entry.data[CONF_PORT], entry.data[CONF_PROTOCOL]
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


async def _reload(hass: HomeAssistant, entry: DaliControlConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: DaliControlConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
