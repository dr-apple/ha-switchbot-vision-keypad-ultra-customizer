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
from datetime import timedelta

from homeassistant.components.lock import LockEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CREDENTIALS,
    CONF_DOORBELL_EVENT,
    CONF_KEYPAD_NAME,
    CONF_KEYPAD_PERSONS,
    CONF_KEYPAD_SOURCE_ID,
    CONF_KEYPADS,
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
    DOOR_STABLE_SECONDS,
    KEYPAD_KEYS,
    LOCK_SLOT_KEYS,
    METHOD_LABELS,
    REARM_DELAY_SECONDS,
    UNKNOWN_PERSON_LABEL,
)
from .util import resolve_rearm_button

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch", "select", "text", "button"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Router (and its hass.data entry) must exist before platform setup --
    # button.py looks it up there to wire the doorbell buttons to it.
    router = KeypadRouter(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"router": router}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

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

    hass.data[DOMAIN][entry.entry_id]["unsub"] = [
        unsub_unlock,
        unsub_lock,
        unsub_doorbell,
        unsub_options,
    ]
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
        keypads = self.entry.options.get(CONF_KEYPADS, {})
        for keypad in keypads.values():
            for person_lock_config in keypad.get(CONF_KEYPAD_PERSONS, {}).values():
                for slot in LOCK_SLOT_KEYS:
                    if lock_entity := person_lock_config.get(f"{CONF_PERSON_LOCK_PREFIX}{slot}"):
                        return lock_entity
        return None

    def _keypad_display_name(self, keypad_key: str | None) -> str:
        """Human-readable label for a keypad, for push/Logbook text.

        Uses the "Keypad N Name" text if set, else falls back to the
        source_id, else "Keypad N" -- always something rather than nothing,
        even for a keypad that hasn't been named yet.
        """
        if keypad_key is None:
            return "Unbekanntes Keypad"
        keypad = self.entry.options.get(CONF_KEYPADS, {}).get(keypad_key, {})
        name = keypad.get(CONF_KEYPAD_NAME, "").strip()
        if name:
            return name
        source_id = keypad.get(CONF_KEYPAD_SOURCE_ID, "").strip()
        return source_id or f"Keypad {keypad_key}"

    def _keypad_key_for_source(self, source_id: str | None) -> str | None:
        """Which configured keypad slot a "source_id" event field belongs to.

        A missing `source_id` (a bridge running firmware from before this
        field existed) resolves to keypad slot 1 -- the same slot a
        single-keypad setup was implicitly using -- so updating this
        integration alone never breaks an existing bridge that hasn't been
        reflashed yet.
        """
        keypads = self.entry.options.get(CONF_KEYPADS, {})
        if not source_id:
            return KEYPAD_KEYS[0] if KEYPAD_KEYS else None
        for keypad_key, keypad in keypads.items():
            if keypad.get(CONF_KEYPAD_SOURCE_ID) == source_id:
                return keypad_key
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

        Some of these BLE door sensors flap between open/closed for a
        second or two at a time (bad magnet alignment, RF noise) even while
        the door is genuinely in one state. A bare `state.state != "on"`
        read is a coin flip if it happens to land mid-flap, so this also
        requires the "closed" reading to have held for DOOR_STABLE_SECONDS
        -- filters that noise without meaningfully delaying a real unlock,
        since normal closed periods last far longer than the flaps do.
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
        if state is None:
            return True
        if state.state == "on":
            return False
        stable_for = dt_util.utcnow() - state.last_changed
        return stable_for >= timedelta(seconds=DOOR_STABLE_SECONDS)

    async def handle_unlock(self, event: Event) -> None:
        method = event.data.get("method", "unknown")
        index = event.data.get("index")
        source_id = event.data.get("source_id")
        method_label = METHOD_LABELS.get(method, method)
        name, person_key, person = self._resolve_person(method, index)
        display_name = name or f"{UNKNOWN_PERSON_LABEL} ({method_label} Slot {index})"
        keypad_key = self._keypad_key_for_source(source_id)
        keypad_label = self._keypad_display_name(keypad_key)

        await self._log(f"{display_name} hat an {keypad_label} per {method_label} aufgeschlossen")
        await self._notify(f"{keypad_label} entriegelt", f"{display_name} · {method_label}")
        self.hass.async_create_task(self._rearm_after_delay())

        if person_key is None:
            return  # nothing configured for this credential -- log only

        if not self._person_enabled(person_key):
            _LOGGER.info("Keypad Router: %s is disabled, skipping action", display_name)
            return

        if keypad_key is None:
            _LOGGER.warning(
                "Keypad Router: event source_id %r matches no configured keypad, "
                "no lock action taken (set a matching Quelle-ID text entity)",
                source_id,
            )
        else:
            keypad = self.entry.options.get(CONF_KEYPADS, {}).get(keypad_key, {})
            lock_config = keypad.get(CONF_KEYPAD_PERSONS, {}).get(person_key, {})
            lock_action = lock_config.get(CONF_PERSON_LOCK_ACTION, "open")
            for slot in LOCK_SLOT_KEYS:
                lock_entity = lock_config.get(f"{CONF_PERSON_LOCK_PREFIX}{slot}")
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
        keypad_key = self._keypad_key_for_source(event.data.get("source_id"))
        keypad_label = self._keypad_display_name(keypad_key)
        await self._log(f"{keypad_label} wurde verriegelt")

    async def handle_doorbell(self, event: Event) -> None:
        keypad_key = self._keypad_key_for_source(event.data.get("source_id"))
        await self._fire_doorbell(keypad_key)

    async def trigger_doorbell(self, keypad_key: str) -> None:
        """Manually fire the doorbell log/notify for one keypad.

        Used by the "Keypad N Klingel" button so pressing it in HA behaves
        exactly like a real doorbell press at that physical keypad --
        useful for testing the notification/automation without walking to
        the door.
        """
        await self._fire_doorbell(keypad_key)

    async def _fire_doorbell(self, keypad_key: str | None) -> None:
        keypad_label = self._keypad_display_name(keypad_key)
        await self._log(f"Es hat an {keypad_label} geklingelt (Keypad Vision)")
        await self._notify(f"Klingel {keypad_label}", f"Jemand steht an {keypad_label} (Keypad Vision)")
