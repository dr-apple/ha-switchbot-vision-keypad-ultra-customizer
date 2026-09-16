"""SwitchBot Vision Keypad Ultra Customizer.

Listens for the events a switchbot-keypad-bridge (or similar) ESPHome
device fires on unlock/lock/doorbell, resolves (method, credential index)
to one of a fixed set of persons, and -- if that person is enabled --
runs their configured lock action on each of their configured locks and/or
their configured script. Every event is logged to the Logbook and
(optionally) pushed to a notify target, regardless of the enabled switch,
so access history stays complete even while someone's actions are
temporarily suspended.
"""
from __future__ import annotations

import asyncio
import logging

from homeassistant.components.lock import LockEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_CREDENTIALS,
    CONF_DOORBELL_EVENT,
    CONF_LOCK_EVENT,
    CONF_LOGBOOK_NAME,
    CONF_NOTIFY_TARGET,
    CONF_PERSON_LOCK_ACTION,
    CONF_PERSON_LOCK_PREFIX,
    CONF_PERSON_NAME,
    CONF_PERSON_SCRIPT,
    CONF_PERSONS,
    CONF_REARM_BUTTON,
    CONF_UNLOCK_EVENT,
    DEFAULT_DOORBELL_EVENT,
    DEFAULT_LOCK_EVENT,
    DEFAULT_LOGBOOK_NAME,
    DEFAULT_UNLOCK_EVENT,
    DOMAIN,
    LOCK_SLOT_KEYS,
    METHOD_LABELS,
    REARM_DELAY_SECONDS,
    UNKNOWN_PERSON_LABEL,
)
from .util import resolve_rearm_button

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch", "select", "text"]


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
    """Persons/credentials changed -- entity display names may need a refresh."""
    await hass.config_entries.async_reload(entry.entry_id)


class KeypadRouter:
    """Resolves keypad events to a person and runs their configured action."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

    def _first_lock_entity(self) -> str | None:
        """Any configured lock, just to group Logbook entries under a real device."""
        persons = self.entry.options.get(CONF_PERSONS, {})
        for person in persons.values():
            for slot in LOCK_SLOT_KEYS:
                if lock_entity := person.get(f"{CONF_PERSON_LOCK_PREFIX}{slot}"):
                    return lock_entity
        return None

    def _logbook_target(self) -> dict:
        name = self.entry.data.get(CONF_LOGBOOK_NAME, DEFAULT_LOGBOOK_NAME)
        if lock_entity := self._first_lock_entity():
            return {"name": name, "entity_id": lock_entity}
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

    async def _rearm_after_delay(self) -> None:
        """Press the (auto-detected or configured) re-arm button, if any.

        Runs as its own task so a slow/absent button never delays the
        logging, notification, or lock actions above.
        """
        button_entity = resolve_rearm_button(self.hass, self.entry)
        if not button_entity:
            return
        await asyncio.sleep(REARM_DELAY_SECONDS)
        await self.hass.services.async_call(
            "button", "press", {"entity_id": button_entity}, blocking=False
        )

    def _resolve_person(self, method: str, index) -> tuple[str | None, str | None, dict]:
        """Return (display_name_or_None, person_key_or_None, person_config_dict)."""
        if index is None:
            return None, None, {}
        credentials = self.entry.options.get(CONF_CREDENTIALS, {})
        person_key = credentials.get(method, {}).get(str(index))
        if not person_key:
            return None, None, {}
        persons = self.entry.options.get(CONF_PERSONS, {})
        person = persons.get(person_key, {})
        name = person.get(CONF_PERSON_NAME, "").strip()
        return (name or None), person_key, person

    def _lock_action_for(self, lock_entity: str, requested_action: str) -> str:
        """Fall back to `unlock` where `open` isn't supported.

        A person's action applies to every lock they're assigned, but not
        every lock supports "open" -- e.g. a switch-as-x buzzer wired up as
        a lock only ever supports lock/unlock. Rather than making the user
        pick a different action per lock (the whole point of one action for
        all of a person's locks), degrade to unlock automatically so
        "Öffnen" still does the closest working thing everywhere.
        """
        if requested_action != "open":
            return requested_action
        state = self.hass.states.get(lock_entity)
        supported = state.attributes.get("supported_features", 0) if state else 0
        if supported & LockEntityFeature.OPEN:
            return "open"
        return "unlock"

    def _person_enabled(self, person_key: str) -> bool:
        registry = er.async_get(self.hass)
        unique_id = f"{self.entry.entry_id}_person_{person_key}_enabled"
        entity_id = registry.async_get_entity_id("switch", DOMAIN, unique_id)
        if entity_id is None:
            return True  # entity not resolvable yet -- fail open on logging-only
        state = self.hass.states.get(entity_id)
        return state is None or state.state != "off"

    def _door_closed_for_lock(self, lock_entity: str) -> bool:
        """Whether the door/gate belonging to `lock_entity` is closed.

        Many SwitchBot locks (Lock Ultra, Lock Pro) expose their own
        integrated door-contact sensor as a sibling `binary_sensor` on the
        same HA device. Unlocking while that door is already open is
        pointless (nothing to open) and can leave the lock's bolt in a
        confused position, so this is used to skip the action rather than
        run it. Fails open (True) when the lock has no device link or no
        `device_class: door` sibling -- e.g. locks without a built-in
        sensor -- so those keep working exactly as before.
        """
        registry = er.async_get(self.hass)
        lock_reg_entry = registry.async_get(lock_entity)
        if lock_reg_entry is None or lock_reg_entry.device_id is None:
            return True
        door_entry = next(
            (
                e
                for e in er.async_entries_for_device(
                    registry, lock_reg_entry.device_id
                )
                if e.domain == "binary_sensor"
                and (e.device_class or e.original_device_class) == "door"
            ),
            None,
        )
        if door_entry is None:
            return True
        state = self.hass.states.get(door_entry.entity_id)
        return state is None or state.state != "on"

    async def handle_unlock(self, event: Event) -> None:
        method = event.data.get("method", "unknown")
        index = event.data.get("index")
        method_label = METHOD_LABELS.get(method, method)
        name, person_key, person = self._resolve_person(method, index)
        display_name = name or f"{UNKNOWN_PERSON_LABEL} ({method_label} Slot {index})"

        await self._log(f"{display_name} hat per {method_label} aufgeschlossen")
        await self._notify("Tor entriegelt", f"{display_name} · {method_label}")
        self.hass.async_create_task(self._rearm_after_delay())

        if person_key is None:
            return  # nothing configured for this credential -- log only

        if not self._person_enabled(person_key):
            _LOGGER.info("Keypad Router: %s is disabled, skipping action", display_name)
            return

        lock_action = person.get(CONF_PERSON_LOCK_ACTION, "open")
        for slot in LOCK_SLOT_KEYS:
            lock_entity = person.get(f"{CONF_PERSON_LOCK_PREFIX}{slot}")
            if lock_entity:
                if not self._door_closed_for_lock(lock_entity):
                    _LOGGER.info(
                        "Keypad Router: door open for %s, skipping unlock action",
                        lock_entity,
                    )
                    await self._log(
                        f"{display_name}: Tür an {lock_entity} war offen -- nicht entriegelt"
                    )
                    continue
                action = self._lock_action_for(lock_entity, lock_action)
                try:
                    await self.hass.services.async_call(
                        "lock", action, {"entity_id": lock_entity}, blocking=True
                    )
                except Exception:
                    _LOGGER.exception(
                        "Keypad Router: %s on %s failed", action, lock_entity
                    )

        if script_entity := person.get(CONF_PERSON_SCRIPT):
            await self.hass.services.async_call(
                "script", "turn_on", {"entity_id": script_entity}, blocking=False
            )

    async def handle_lock(self, event: Event) -> None:
        await self._log("Tor wurde verriegelt")

    async def handle_doorbell(self, event: Event) -> None:
        await self._log("Es hat am Tor geklingelt (Keypad Vision)")
        await self._notify("Klingel Tor", "Jemand steht am Tor (Keypad Vision)")
