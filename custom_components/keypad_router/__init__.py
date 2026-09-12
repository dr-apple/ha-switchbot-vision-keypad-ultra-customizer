"""Keypad Person Router.

Listens for the events a switchbot-keypad-bridge (or similar) ESPHome
device fires on unlock/lock/doorbell, resolves (method, credential index)
to one of a fixed set of persons, and -- if that person is enabled --
runs their configured lock action and/or automation. Every event is
logged to the Logbook and (optionally) pushed to a notify target,
regardless of the enabled switch, so access history stays complete even
while someone's actions are temporarily suspended.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import entity_registry as er

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
    METHOD_LABELS,
    UNKNOWN_PERSON_LABEL,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    router = KeypadRouter(hass, entry)
    unsub_unlock = hass.bus.async_listen(
        entry.data.get(CONF_UNLOCK_EVENT, DEFAULT_UNLOCK_EVENT), router.handle_unlock
    )
    unsub_lock = hass.bus.async_listen(
        entry.data.get(CONF_LOCK_EVENT, DEFAULT_LOCK_EVENT), router.handle_lock
    )
    unsub_doorbell = hass.bus.async_listen(
        entry.data.get(CONF_DOORBELL_EVENT, DEFAULT_DOORBELL_EVENT),
        router.handle_doorbell,
    )

    unsub_options = entry.add_update_listener(_async_options_updated)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "unsub": [unsub_unlock, unsub_lock, unsub_doorbell, unsub_options],
    }
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        for unsub in data["unsub"]:
            unsub()
    return unload_ok


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Persons/credentials changed -- switch entity names may need a refresh."""
    await hass.config_entries.async_reload(entry.entry_id)


class KeypadRouter:
    """Resolves keypad events to a person and runs their configured action."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

    def _logbook_target(self) -> dict:
        name = self.entry.data.get(CONF_LOGBOOK_NAME, DEFAULT_LOGBOOK_NAME)
        persons = self.entry.options.get(CONF_PERSONS, {})
        # Log against the first configured lock so entries group under a
        # real device entity instead of collapsing under this integration.
        for person in persons.values():
            if person.get(CONF_PERSON_LOCK_ENTITY):
                return {"name": name, "entity_id": person[CONF_PERSON_LOCK_ENTITY]}
        return {"name": name}

    async def _log(self, message: str) -> None:
        await self.hass.services.async_call(
            "logbook",
            "log",
            {**self._logbook_target(), "message": message},
            blocking=False,
        )

    async def _notify(self, title: str, message: str) -> None:
        target = self.entry.data.get(CONF_NOTIFY_TARGET)
        if not target:
            return
        await self.hass.services.async_call(
            "notify",
            "send_message",
            {"entity_id": target, "title": title, "message": message},
            blocking=False,
        )

    def _resolve_person(self, method: str, index) -> tuple[str | None, dict]:
        """Return (display_name_or_None, person_config_dict)."""
        if index is None:
            return None, {}
        credentials = self.entry.options.get(CONF_CREDENTIALS, {})
        person_key = credentials.get(method, {}).get(str(index))
        if not person_key:
            return None, {}
        persons = self.entry.options.get(CONF_PERSONS, {})
        person = persons.get(person_key, {})
        name = person.get(CONF_PERSON_NAME, "").strip()
        return (name or None), person

    def _person_enabled(self, person_key_name: str | None) -> bool:
        if person_key_name is None:
            return False
        entity_id = self._switch_entity_id_for_name(person_key_name)
        if entity_id is None:
            return True  # no switch resolvable yet -- fail open on logging-only
        state = self.hass.states.get(entity_id)
        return state is None or state.state != "off"

    def _switch_entity_id_for_name(self, name: str) -> str | None:
        persons = self.entry.options.get(CONF_PERSONS, {})
        for key, person in persons.items():
            if person.get(CONF_PERSON_NAME, "").strip() == name:
                registry = er.async_get(self.hass)
                unique_id = f"{self.entry.entry_id}_person_{key}_enabled"
                return registry.async_get_entity_id("switch", DOMAIN, unique_id)
        return None

    async def handle_unlock(self, event: Event) -> None:
        method = event.data.get("method", "unknown")
        index = event.data.get("index")
        method_label = METHOD_LABELS.get(method, method)
        name, person = self._resolve_person(method, index)
        display_name = name or f"{UNKNOWN_PERSON_LABEL} ({method_label} Slot {index})"

        await self._log(f"{display_name} hat per {method_label} aufgeschlossen")
        await self._notify("Tor entriegelt", f"{display_name} · {method_label}")

        if name is None:
            return  # nothing configured for this credential -- log only

        if not self._person_enabled(name):
            _LOGGER.info("Keypad Router: %s is disabled, skipping action", name)
            return

        lock_entity = person.get(CONF_PERSON_LOCK_ENTITY)
        lock_action = person.get(CONF_PERSON_LOCK_ACTION, "open")
        if lock_entity:
            await self.hass.services.async_call(
                "lock", lock_action, {"entity_id": lock_entity}, blocking=False
            )

        automation_entity = person.get(CONF_PERSON_AUTOMATION)
        if automation_entity:
            await self.hass.services.async_call(
                "automation",
                "trigger",
                {"entity_id": automation_entity},
                blocking=False,
            )

    async def handle_lock(self, event: Event) -> None:
        await self._log("Tor wurde verriegelt")

    async def handle_doorbell(self, event: Event) -> None:
        await self._log("Es hat am Tor geklingelt (Keypad Vision)")
        await self._notify("Klingel Tor", "Jemand steht am Tor (Keypad Vision)")
