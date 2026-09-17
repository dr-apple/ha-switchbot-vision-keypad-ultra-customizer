"""Per-person name text entities."""
from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_KEYPAD_SOURCE_ID,
    CONF_KEYPADS,
    CONF_PERSON_NAME,
    CONF_PERSONS,
    DOMAIN,
    INTEGRATION_TITLE,
    KEYPAD_KEYS,
    PERSON_KEYS,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entities = [PersonNameText(hass, entry, key) for key in PERSON_KEYS]
    entities += [KeypadSourceIdText(hass, entry, key) for key in KEYPAD_KEYS]
    async_add_entities(entities)


class PersonNameText(TextEntity, RestoreEntity):
    """The display name for one of the 6 fixed person slots."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:rename-box"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, person_key: str) -> None:
        self.hass = hass
        self._entry = entry
        self._person_key = person_key
        self._attr_unique_id = f"{entry.entry_id}_person_{person_key}_name"
        self._attr_native_value = ""

    @property
    def name(self) -> str:
        return f"Person {self._person_key} Name"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)}, name=INTEGRATION_TITLE
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        persons = self._entry.options.get(CONF_PERSONS, {})
        stored = persons.get(self._person_key, {}).get(CONF_PERSON_NAME, "")
        if stored:
            self._attr_native_value = stored
        elif (last_state := await self.async_get_last_state()) is not None:
            self._attr_native_value = last_state.state

    async def async_set_value(self, value: str) -> None:
        self._attr_native_value = value
        persons = dict(self._entry.options.get(CONF_PERSONS, {}))
        person = dict(persons.get(self._person_key, {}))
        person[CONF_PERSON_NAME] = value.strip()
        persons[self._person_key] = person
        new_options = dict(self._entry.options)
        new_options[CONF_PERSONS] = persons
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        self.async_write_ha_state()


class KeypadSourceIdText(TextEntity, RestoreEntity):
    """The source_id this keypad's bridge tags its events with.

    Must match the "source_id" field the ESPHome device puts in its
    on_unlock/on_lock/on_doorbell event data (see the example YAML) --
    that's how the router tells two physical keypads apart when both feed
    the same event type.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:identifier"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, keypad_key: str) -> None:
        self.hass = hass
        self._entry = entry
        self._keypad_key = keypad_key
        self._attr_unique_id = f"{entry.entry_id}_keypad_{keypad_key}_source_id"
        self._attr_native_value = ""

    @property
    def name(self) -> str:
        return f"Keypad {self._keypad_key} Quelle-ID"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)}, name=INTEGRATION_TITLE
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        keypads = self._entry.options.get(CONF_KEYPADS, {})
        stored = keypads.get(self._keypad_key, {}).get(CONF_KEYPAD_SOURCE_ID, "")
        if stored:
            self._attr_native_value = stored
        elif (last_state := await self.async_get_last_state()) is not None:
            self._attr_native_value = last_state.state

    async def async_set_value(self, value: str) -> None:
        self._attr_native_value = value
        keypads = {k: dict(v) for k, v in self._entry.options.get(CONF_KEYPADS, {}).items()}
        keypad = dict(keypads.get(self._keypad_key, {}))
        keypad[CONF_KEYPAD_SOURCE_ID] = value.strip()
        keypads[self._keypad_key] = keypad
        new_options = dict(self._entry.options)
        new_options[CONF_KEYPADS] = keypads
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        self.async_write_ha_state()
