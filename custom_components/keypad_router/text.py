"""Per-person name text entities."""
from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_PERSON_NAME, CONF_PERSONS, DOMAIN, INTEGRATION_TITLE, PERSON_KEYS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(PersonNameText(hass, entry, key) for key in PERSON_KEYS)


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
