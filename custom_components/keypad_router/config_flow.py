"""Config flow for SwitchBot Vision Keypad Ultra Customizer.

Only the one-time connection settings (event types, notify target) are
asked here. Persons, their lock/action/automation, and the credential
grid are all live entities on the device page -- see select.py/text.py.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_DOORBELL_EVENT,
    CONF_LOCK_EVENT,
    CONF_LOGBOOK_NAME,
    CONF_NOTIFY_TARGET,
    CONF_UNLOCK_EVENT,
    DEFAULT_DOORBELL_EVENT,
    DEFAULT_LOCK_EVENT,
    DEFAULT_LOGBOOK_NAME,
    DEFAULT_UNLOCK_EVENT,
    DOMAIN,
    INTEGRATION_TITLE,
)


class KeypadRouterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up the single Customizer entry."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title=INTEGRATION_TITLE, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_UNLOCK_EVENT, default=DEFAULT_UNLOCK_EVENT): str,
                vol.Required(CONF_LOCK_EVENT, default=DEFAULT_LOCK_EVENT): str,
                vol.Required(CONF_DOORBELL_EVENT, default=DEFAULT_DOORBELL_EVENT): str,
                vol.Optional(CONF_NOTIFY_TARGET): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="notify")
                ),
                vol.Optional(CONF_LOGBOOK_NAME, default=DEFAULT_LOGBOOK_NAME): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)
