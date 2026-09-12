"""Per-person enable/disable switches for Keypad Person Router."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_PERSON_NAME, CONF_PERSONS, DOMAIN, PERSON_KEYS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one switch per fixed person slot."""
    async_add_entities(
        PersonEnabledSwitch(entry, person_key) for person_key in PERSON_KEYS
    )


class PersonEnabledSwitch(SwitchEntity, RestoreEntity):
    """Whether this person's configured action fires on a keypad match.

    A person always gets logged and notified regardless of this switch --
    it only gates whether the configured lock/automation action actually
    runs, so you can temporarily suspend someone's access (e.g. a cleaner
    between visits) without touching their configuration.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, person_key: str) -> None:
        self._entry = entry
        self._person_key = person_key
        self._attr_unique_id = f"{entry.entry_id}_person_{person_key}_enabled"
        self._attr_is_on = True

    @property
    def name(self) -> str:
        persons = self._entry.options.get(CONF_PERSONS, {})
        person_name = persons.get(self._person_key, {}).get(CONF_PERSON_NAME, "").strip()
        label = person_name if person_name else f"Person {self._person_key}"
        return f"{label} aktiv"

    @property
    def icon(self) -> str:
        return "mdi:account-check" if self.is_on else "mdi:account-off"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Keypad Person Router",
            manufacturer="dr-apple",
            model="keypad_router",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_is_on = last_state.state == "on"

    async def async_turn_on(self, **kwargs) -> None:
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self._attr_is_on = False
        self.async_write_ha_state()
