"""Light platform: DALI groups, ballasts and broadcast as lights.

The DCBM's Ethernet interface is write only, so state is assumed.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.const import CONF_NAME, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import DaliControlConfigEntry
from .client import DaliControlError
from .const import (
    CONF_ADDRESS,
    CONF_CONTROLLER_ID,
    CONF_KIND,
    CONF_LIGHTS,
    CONF_LINE,
    DOMAIN,
    KIND_BALLAST,
    KIND_BROADCAST,
    KIND_GROUP,
    LINE_A,
    LINE_B,
)
from .protocol import AddressType, DaliAction, Line, dali_command, dali_scene

_LOGGER = logging.getLogger(__name__)

_LINES = {LINE_A: Line.A, LINE_B: Line.B}
_KINDS = {
    KIND_GROUP: AddressType.GROUP,
    KIND_BALLAST: AddressType.BALLAST,
    KIND_BROADCAST: AddressType.BROADCAST,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaliControlConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        DaliLight(entry, cfg) for cfg in entry.options.get(CONF_LIGHTS, [])
    )
    entity_platform.async_get_current_platform().async_register_entity_service(
        "recall_scene",
        {vol.Required("scene"): vol.All(vol.Coerce(int), vol.Range(min=0, max=15))},
        "async_recall_scene",
    )


class DaliLight(LightEntity, RestoreEntity):
    """A DALI group, ballast or broadcast address."""

    _attr_has_entity_name = True
    _attr_assumed_state = True
    _attr_should_poll = False
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(self, entry: DaliControlConfigEntry, cfg: dict[str, Any]) -> None:
        self._client = entry.runtime_data
        self._controller = entry.data[CONF_CONTROLLER_ID]
        self._line = _LINES.get(cfg[CONF_LINE], Line.BOTH)
        self._type = _KINDS[cfg[CONF_KIND]]
        self._address = cfg[CONF_ADDRESS]
        self._attr_name = cfg[CONF_NAME]
        self._attr_unique_id = f"{entry.entry_id}_{cfg[CONF_KIND]}_{cfg[CONF_LINE]}_{self._address}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Clipsal / Schneider Electric",
            model="DCBM line controller",
        )
        self._attr_is_on = False
        self._attr_brightness = 254

    async def async_added_to_hass(self) -> None:
        if (last := await self.async_get_last_state()) is not None:
            self._attr_is_on = last.state == STATE_ON
            if (b := last.attributes.get(ATTR_BRIGHTNESS)) is not None:
                self._attr_brightness = int(b)

    async def _send(self, frame: str) -> None:
        try:
            await self._client.async_send(frame)
        except DaliControlError as err:
            raise HomeAssistantError(str(err)) from err

    def _cmd(self, *, direct: bool, action: int) -> str:
        return dali_command(
            self._controller, self._line, self._type, self._address, direct=direct, action=action
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._attr_brightness or 254)
        # HA brightness is 1-255; DALI arc levels 1-254 (255 is the mask value).
        arc = max(1, min(254, round(brightness * 254 / 255)))
        await self._send(self._cmd(direct=True, action=arc))
        self._attr_is_on = True
        self._attr_brightness = brightness
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._send(self._cmd(direct=False, action=DaliAction.OFF))
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_recall_scene(self, scene: int) -> None:
        await self._send(
            dali_scene(self._controller, self._line, self._type, self._address, scene)
        )
        self._attr_is_on = True
        self.async_write_ha_state()
