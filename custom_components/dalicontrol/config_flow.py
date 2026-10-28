"""Config and options flow for DALIcontrol."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import selector

from .client import DaliControlError, async_test_connection
from .const import (
    CONF_ADDRESS,
    CONF_CONTROLLER_ID,
    CONF_KIND,
    CONF_LIGHTS,
    CONF_LINE,
    CONF_PROTOCOL,
    DEFAULT_PORT,
    DOMAIN,
    KIND_BALLAST,
    KIND_BROADCAST,
    KIND_CONTROLLER_GROUP,
    KIND_GROUP,
    LINE_A,
    LINE_B,
    LINE_BOTH,
    PROTOCOL_TCP,
    PROTOCOL_UDP,
)


def _select(options: list[str], key: str) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options,
            translation_key=key,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


class DaliControlConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a DCBM line controller."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            protocol = user_input[CONF_PROTOCOL]
            port = int(user_input.get(CONF_PORT) or DEFAULT_PORT[protocol])
            controller_id = int(user_input[CONF_CONTROLLER_ID])
            host = user_input[CONF_HOST].strip()
            await self.async_set_unique_id(f"{host}:{port}:{controller_id}")
            self._abort_if_unique_id_configured()
            try:
                await async_test_connection(host, port, protocol)
            except DaliControlError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME) or f"DCBM {controller_id:03d} ({host})",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_PROTOCOL: protocol,
                        CONF_CONTROLLER_ID: controller_id,
                    },
                    options={CONF_LIGHTS: []},
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_CONTROLLER_ID, default=0): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=254)
                ),
                vol.Required(CONF_PROTOCOL, default=PROTOCOL_UDP): _select(
                    [PROTOCOL_UDP, PROTOCOL_TCP], "protocol"
                ),
                vol.Optional(CONF_PORT): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
                vol.Optional(CONF_NAME): str,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return DaliControlOptionsFlow()


class DaliControlOptionsFlow(OptionsFlow):
    """Add and remove the lights exposed for a controller."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(step_id="init", menu_options=["add_light", "remove_light"])

    def _lights(self) -> list[dict[str, Any]]:
        return list(self.config_entry.options.get(CONF_LIGHTS, []))

    async def async_step_add_light(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            kind = user_input[CONF_KIND]
            address = int(user_input.get(CONF_ADDRESS, 0))
            if kind == KIND_GROUP and not 0 <= address <= 15:
                errors[CONF_ADDRESS] = "invalid_group"
            elif kind == KIND_BALLAST and not 0 <= address <= 63:
                errors[CONF_ADDRESS] = "invalid_ballast"
            elif kind == KIND_CONTROLLER_GROUP and not 1 <= address <= 64:
                errors[CONF_ADDRESS] = "invalid_controller_group"
            elif kind == KIND_CONTROLLER_GROUP and user_input[CONF_LINE] == LINE_BOTH:
                errors[CONF_LINE] = "controller_group_line"
            else:
                if kind == KIND_BROADCAST:
                    address = 0
                light = {
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_KIND: kind,
                    CONF_LINE: user_input[CONF_LINE],
                    CONF_ADDRESS: address,
                }
                lights = self._lights()
                key = (kind, light[CONF_LINE], address)
                if any((x[CONF_KIND], x[CONF_LINE], x[CONF_ADDRESS]) == key for x in lights):
                    errors["base"] = "already_added"
                else:
                    lights.append(light)
                    return self.async_create_entry(data={CONF_LIGHTS: lights})

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_KIND, default=KIND_GROUP): _select(
                    [KIND_GROUP, KIND_CONTROLLER_GROUP, KIND_BALLAST, KIND_BROADCAST], "kind"
                ),
                vol.Required(CONF_LINE, default=LINE_A): _select(
                    [LINE_A, LINE_B, LINE_BOTH], "line"
                ),
                vol.Optional(CONF_ADDRESS, default=0): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=63)
                ),
            }
        )
        return self.async_show_form(
            step_id="add_light",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def async_step_remove_light(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        lights = self._lights()
        if user_input is not None:
            remove = set(user_input.get("remove", []))
            kept = [x for x in lights if x[CONF_NAME] not in remove]
            return self.async_create_entry(data={CONF_LIGHTS: kept})
        if not lights:
            return self.async_abort(reason="no_lights")
        return self.async_show_form(
            step_id="remove_light",
            data_schema=vol.Schema(
                {
                    vol.Required("remove", default=[]): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[x[CONF_NAME] for x in lights],
                            multiple=True,
                        )
                    )
                }
            ),
        )
