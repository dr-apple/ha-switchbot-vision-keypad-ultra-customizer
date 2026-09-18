"""Per-keypad "last access" sensor, for automations/scripts that need to
react to *who* unlocked *how* -- not just that a lock changed state.
"""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, KEYPAD_KEYS
from .util import keypad_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    router = hass.data[DOMAIN][entry.entry_id]["router"]
    entities = [LastAccessSensor(hass, entry, key) for key in KEYPAD_KEYS]
    async_add_entities(entities)
    router.register_last_access_sensors({e.keypad_key: e for e in entities})


class LastAccessSensor(RestoreEntity, SensorEntity):
    """Who last unlocked this keypad and how.

    State is the resolved person's display name (or "Unbekannt (<Methode>
    Slot <N>)" for a credential nobody's assigned to -- the same fallback
    used in the Logbook/push text). The method, its raw name, the
    credential slot and the resolved person key ride along as attributes,
    since a single state string can't carry all of that and an
    automation/script triggering on "this keypad had a new access" only
    needs one entity to watch.

    Updated by KeypadRouter.handle_unlock for every unlock event this
    keypad reports, including unresolved credentials -- restricting it to
    only known/enabled persons would hide exactly the "someone tried an
    unknown code here" case an automation might most want to react to.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:account-clock-outline"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, keypad_key: str) -> None:
        self.hass = hass
        self._entry = entry
        self.keypad_key = keypad_key
        self._attr_unique_id = f"{entry.entry_id}_keypad_{keypad_key}_last_access"
        self._attr_native_value: str | None = None
        self._attr_extra_state_attributes: dict = {}

    @property
    def name(self) -> str:
        return f"Keypad {self.keypad_key} Letzter Zugriff"

    @property
    def device_info(self) -> DeviceInfo:
        return keypad_device_info(self._entry, self.keypad_key)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in ("unknown", "unavailable"):
                self._attr_native_value = last_state.state
            self._attr_extra_state_attributes = {
                k: v for k, v in last_state.attributes.items() if k in ATTR_KEYS
            }

    def record_access(
        self,
        *,
        display_name: str,
        method: str | None,
        method_label: str,
        credential_index: str | None,
        person_key: str | None,
    ) -> None:
        self._attr_native_value = display_name
        self._attr_extra_state_attributes = {
            "method": method,
            "method_label": method_label,
            "credential_index": credential_index,
            "person_key": person_key,
        }
        self.async_write_ha_state()


ATTR_KEYS = {"method", "method_label", "credential_index", "person_key"}
