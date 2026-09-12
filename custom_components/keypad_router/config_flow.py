"""Config flow for Keypad Person Router.

Deliberately static: a fixed number of persons (NUM_PERSONS) and a fixed
credential grid (METHODS x SLOTS_PER_METHOD). Nothing here is added or
removed at runtime -- only the values in those fixed slots are edited.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_CREDENTIALS,
    CONF_DOORBELL_EVENT,
    CONF_LOCK_EVENT,
    CONF_LOGBOOK_NAME,
    CONF_NOTIFY_TARGET,
    CONF_PERSON_AUTOMATION,
    CONF_PERSON_LOCK_ACTION,
    CONF_PERSON_LOCK_ENTITY,
    CONF_PERSON_NAME,
    CONF_PERSONS,
    CONF_UNLOCK_EVENT,
    DEFAULT_DOORBELL_EVENT,
    DEFAULT_LOCK_EVENT,
    DEFAULT_LOGBOOK_NAME,
    DEFAULT_UNLOCK_EVENT,
    DOMAIN,
    LOCK_ACTIONS,
    LOCK_ACTION_LABELS,
    METHODS,
    METHOD_LABELS,
    NUM_PERSONS,
    PERSON_KEYS,
    SLOT_KEYS,
)


class KeypadRouterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up the single Keypad Person Router entry."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="Keypad Person Router", data=user_input)

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

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> KeypadRouterOptionsFlow:
        return KeypadRouterOptionsFlow()


class KeypadRouterOptionsFlow(config_entries.OptionsFlow):
    """Edit the fixed persons table and the fixed credential grid."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=["persons", "credentials"],
        )

    # ------------------------------------------------------------------
    # Persons: 6 fixed rows, each with name / lock / action / automation.
    # ------------------------------------------------------------------
    async def async_step_persons(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        current = dict(self.config_entry.options.get(CONF_PERSONS, {}))

        if user_input is not None:
            persons: dict[str, dict[str, Any]] = {}
            for key in PERSON_KEYS:
                persons[key] = {
                    CONF_PERSON_NAME: user_input.get(f"p{key}_name", "").strip(),
                    CONF_PERSON_LOCK_ENTITY: user_input.get(f"p{key}_lock_entity"),
                    CONF_PERSON_LOCK_ACTION: user_input.get(
                        f"p{key}_lock_action", "open"
                    ),
                    CONF_PERSON_AUTOMATION: user_input.get(f"p{key}_automation"),
                }
            new_options = dict(self.config_entry.options)
            new_options[CONF_PERSONS] = persons
            return self.async_create_entry(title="", data=new_options)

        fields: dict[Any, Any] = {}
        for key in PERSON_KEYS:
            defaults = current.get(key, {})
            fields[
                vol.Optional(f"p{key}_name", default=defaults.get(CONF_PERSON_NAME, ""))
            ] = str
            fields[
                vol.Optional(
                    f"p{key}_lock_entity",
                    description={
                        "suggested_value": defaults.get(CONF_PERSON_LOCK_ENTITY)
                    },
                )
            ] = selector.EntitySelector(selector.EntitySelectorConfig(domain="lock"))
            fields[
                vol.Optional(
                    f"p{key}_lock_action",
                    default=defaults.get(CONF_PERSON_LOCK_ACTION, "open"),
                )
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=a, label=LOCK_ACTION_LABELS[a])
                        for a in LOCK_ACTIONS
                    ]
                )
            )
            fields[
                vol.Optional(
                    f"p{key}_automation",
                    description={
                        "suggested_value": defaults.get(CONF_PERSON_AUTOMATION)
                    },
                )
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="automation")
            )

        return self.async_show_form(step_id="persons", data_schema=vol.Schema(fields))

    # ------------------------------------------------------------------
    # Credentials: for every (method, slot) pick one of the 6 persons.
    # ------------------------------------------------------------------
    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        persons = self.config_entry.options.get(CONF_PERSONS, {})
        current = dict(self.config_entry.options.get(CONF_CREDENTIALS, {}))

        person_options = [selector.SelectOptionDict(value="", label="— frei —")]
        for key in PERSON_KEYS:
            name = persons.get(key, {}).get(CONF_PERSON_NAME, "").strip()
            label = name if name else f"Person {key} (kein Name gesetzt)"
            person_options.append(selector.SelectOptionDict(value=key, label=label))

        if user_input is not None:
            credentials: dict[str, dict[str, str]] = {}
            for method in METHODS:
                credentials[method] = {}
                for slot in SLOT_KEYS:
                    value = user_input.get(f"{method}_{slot}", "")
                    if value:
                        credentials[method][slot] = value
            new_options = dict(self.config_entry.options)
            new_options[CONF_CREDENTIALS] = credentials
            return self.async_create_entry(title="", data=new_options)

        fields: dict[Any, Any] = {}
        for method in METHODS:
            for slot in SLOT_KEYS:
                default_value = current.get(method, {}).get(slot, "")
                fields[
                    vol.Optional(
                        f"{method}_{slot}",
                        default=default_value,
                        description={
                            "suggested_value": default_value,
                            "name": f"{METHOD_LABELS[method]} – Slot {slot}",
                        },
                    )
                ] = selector.SelectSelector(
                    selector.SelectSelectorConfig(options=person_options)
                )

        return self.async_show_form(
            step_id="credentials", data_schema=vol.Schema(fields)
        )
