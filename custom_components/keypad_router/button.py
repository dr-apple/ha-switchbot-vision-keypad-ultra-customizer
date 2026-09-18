"""Per-keypad virtual doorbell button."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, KEYPAD_KEYS
from .util import keypad_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    router = hass.data[DOMAIN][entry.entry_id]["router"]
    async_add_entities(
        KeypadDoorbellButton(hass, entry, router, key) for key in KEYPAD_KEYS
    )


class KeypadDoorbellButton(ButtonEntity):
    """Fires the same log/notify as a real doorbell press at this keypad.

    Useful for testing the notification/automation from the dashboard
    without walking to the physical keypad -- goes through the same
    `_fire_doorbell` path as a genuine `on_doorbell` event, so it's
    indistinguishable in the Logbook/push from the real thing.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:bell-ring-outline"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, router, keypad_key: str) -> None:
        self.hass = hass
        self._entry = entry
        self._router = router
        self._keypad_key = keypad_key
        self._attr_unique_id = f"{entry.entry_id}_keypad_{keypad_key}_doorbell_button"

    @property
    def name(self) -> str:
        return f"Keypad {self._keypad_key} Klingel"

    @property
    def device_info(self) -> DeviceInfo:
        return keypad_device_info(self._entry, self._keypad_key)

    async def async_press(self) -> None:
        await self._router.trigger_doorbell(self._keypad_key)
