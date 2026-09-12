"""Select entities: per-person lock/action/automation, and the
method+slot -> person credential grid. Everything lives on the device
page; there is no separate settings dialog for any of this.
"""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_CREDENTIALS,
    CONF_PERSON_AUTOMATION,
    CONF_PERSON_LOCK_ACTION,
    CONF_PERSON_LOCK_ENTITY,
    CONF_PERSON_NAME,
    CONF_PERSONS,
    DOMAIN,
    INTEGRATION_TITLE,
    LOCK_ACTIONS,
    LOCK_ACTION_LABELS,
    METHODS,
    METHOD_LABELS,
    NONE_OPTION,
    PERSON_KEYS,
    SLOT_KEYS,
    UNASSIGNED_OPTION,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entities: list[SelectEntity] = []
    for person_key in PERSON_KEYS:
        entities.append(PersonLockSelect(hass, entry, person_key))
        entities.append(PersonActionSelect(hass, entry, person_key))
        entities.append(PersonAutomationSelect(hass, entry, person_key))
    for method in METHODS:
        for slot in SLOT_KEYS:
            entities.append(CredentialPersonSelect(hass, entry, method, slot))
    async_add_entities(entities)


def _person_label(entry: ConfigEntry, key: str) -> str:
    name = entry.options.get(CONF_PERSONS, {}).get(key, {}).get(CONF_PERSON_NAME, "").strip()
    return name if name else f"Person {key}"


class _BasePersonSelect(SelectEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, person_key: str) -> None:
        self.hass = hass
        self._entry = entry
        self._person_key = person_key

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)}, name=INTEGRATION_TITLE
        )

    def _person(self) -> dict:
        return dict(self._entry.options.get(CONF_PERSONS, {}).get(self._person_key, {}))

    def _save_person(self, person: dict) -> None:
        persons = dict(self._entry.options.get(CONF_PERSONS, {}))
        persons[self._person_key] = person
        new_options = dict(self._entry.options)
        new_options[CONF_PERSONS] = persons
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        self.async_write_ha_state()


class PersonLockSelect(_BasePersonSelect):
    """Which lock this person's unlock action targets."""

    _attr_icon = "mdi:lock"

    def __init__(self, hass, entry, person_key) -> None:
        super().__init__(hass, entry, person_key)
        self._attr_unique_id = f"{entry.entry_id}_person_{person_key}_lock_select"

    @property
    def name(self) -> str:
        return f"{_person_label(self._entry, self._person_key)} Schloss"

    @property
    def options(self) -> list[str]:
        locks = sorted(self.hass.states.async_entity_ids("lock"))
        return [NONE_OPTION, *locks]

    @property
    def current_option(self) -> str | None:
        return self._person().get(CONF_PERSON_LOCK_ENTITY) or NONE_OPTION

    async def async_select_option(self, option: str) -> None:
        person = self._person()
        person[CONF_PERSON_LOCK_ENTITY] = None if option == NONE_OPTION else option
        self._save_person(person)


class PersonActionSelect(_BasePersonSelect):
    """Which lock action (open/unlock/lock) this person triggers."""

    _attr_icon = "mdi:lock-open-variant"

    def __init__(self, hass, entry, person_key) -> None:
        super().__init__(hass, entry, person_key)
        self._attr_unique_id = f"{entry.entry_id}_person_{person_key}_action_select"
        self._attr_options = [LOCK_ACTION_LABELS[a] for a in LOCK_ACTIONS]

    @property
    def name(self) -> str:
        return f"{_person_label(self._entry, self._person_key)} Aktion"

    @property
    def current_option(self) -> str | None:
        action = self._person().get(CONF_PERSON_LOCK_ACTION, "open")
        return LOCK_ACTION_LABELS.get(action, LOCK_ACTION_LABELS["open"])

    async def async_select_option(self, option: str) -> None:
        reverse = {v: k for k, v in LOCK_ACTION_LABELS.items()}
        person = self._person()
        person[CONF_PERSON_LOCK_ACTION] = reverse.get(option, "open")
        self._save_person(person)


class PersonAutomationSelect(_BasePersonSelect):
    """An optional extra automation to trigger for this person."""

    _attr_icon = "mdi:robot"

    def __init__(self, hass, entry, person_key) -> None:
        super().__init__(hass, entry, person_key)
        self._attr_unique_id = f"{entry.entry_id}_person_{person_key}_automation_select"

    @property
    def name(self) -> str:
        return f"{_person_label(self._entry, self._person_key)} Automation"

    @property
    def options(self) -> list[str]:
        automations = sorted(self.hass.states.async_entity_ids("automation"))
        return [NONE_OPTION, *automations]

    @property
    def current_option(self) -> str | None:
        return self._person().get(CONF_PERSON_AUTOMATION) or NONE_OPTION

    async def async_select_option(self, option: str) -> None:
        person = self._person()
        person[CONF_PERSON_AUTOMATION] = None if option == NONE_OPTION else option
        self._save_person(person)


class CredentialPersonSelect(SelectEntity, RestoreEntity):
    """Which person a given (method, slot) credential belongs to."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:account-key"

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, method: str, slot: str
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._method = method
        self._slot = slot
        self._attr_unique_id = f"{entry.entry_id}_cred_{method}_{slot}"

    @property
    def name(self) -> str:
        return f"{METHOD_LABELS[self._method]} Slot {self._slot}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)}, name=INTEGRATION_TITLE
        )

    @property
    def options(self) -> list[str]:
        return [UNASSIGNED_OPTION] + [
            f"{key}: {_person_label(self._entry, key)}" for key in PERSON_KEYS
        ]

    @property
    def current_option(self) -> str | None:
        credentials = self._entry.options.get(CONF_CREDENTIALS, {})
        person_key = credentials.get(self._method, {}).get(self._slot)
        if not person_key:
            return UNASSIGNED_OPTION
        return f"{person_key}: {_person_label(self._entry, person_key)}"

    async def async_select_option(self, option: str) -> None:
        credentials = {
            method: dict(slots)
            for method, slots in self._entry.options.get(CONF_CREDENTIALS, {}).items()
        }
        method_map = dict(credentials.get(self._method, {}))
        if option == UNASSIGNED_OPTION:
            method_map.pop(self._slot, None)
        else:
            person_key = option.split(":", 1)[0].strip()
            method_map[self._slot] = person_key
        credentials[self._method] = method_map
        new_options = dict(self._entry.options)
        new_options[CONF_CREDENTIALS] = credentials
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        self.async_write_ha_state()
