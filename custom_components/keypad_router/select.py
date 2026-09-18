"""Select entities: per-person locks/action/script, and the
method+slot -> person credential grid. Everything lives on the device
page; there is no separate settings dialog for any of this.

Naming is deliberately static ("Person 1 ...") rather than following the
person's current name -- otherwise the one field that lets you *set* the
name is the only one that never updates, which makes it hard to find.
"""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_added_domain,
    async_track_state_removed_domain,
)
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_CREDENTIALS,
    CONF_KEYPAD_PERSONS,
    CONF_KEYPADS,
    CONF_NOTIFY_TARGET,
    CONF_PERSON_LOCK_ACTION,
    CONF_PERSON_LOCK_PREFIX,
    CONF_PERSON_NAME,
    CONF_PERSON_SCRIPT,
    CONF_PERSONS,
    CONF_REARM_BUTTON,
    KEYPAD_KEYS,
    LOCK_ACTIONS,
    LOCK_ACTION_LABELS,
    LOCK_SLOT_KEYS,
    METHODS,
    METHOD_LABELS,
    NONE_OPTION,
    PERSON_KEYS,
    SLOT_KEYS,
    UNASSIGNED_OPTION,
)
from .util import keypad_device_info, main_device_info, resolve_rearm_button


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entities: list[SelectEntity] = []
    for person_key in PERSON_KEYS:
        entities.append(PersonScriptSelect(hass, entry, person_key))
    for keypad_key in KEYPAD_KEYS:
        for person_key in PERSON_KEYS:
            for lock_slot in LOCK_SLOT_KEYS:
                entities.append(
                    KeypadPersonLockSelect(hass, entry, keypad_key, person_key, lock_slot)
                )
            entities.append(KeypadPersonActionSelect(hass, entry, keypad_key, person_key))
    for method in METHODS:
        for slot in SLOT_KEYS:
            entities.append(CredentialPersonSelect(hass, entry, method, slot))
    entities.append(RearmButtonSelect(hass, entry))
    entities.append(NotifyTargetSelect(hass, entry))
    async_add_entities(entities)


def _person_display(entry: ConfigEntry, key: str) -> str:
    name = entry.options.get(CONF_PERSONS, {}).get(key, {}).get(CONF_PERSON_NAME, "").strip()
    return name if name else f"Person {key}"


class _DomainOptionsRefreshMixin:
    """Keep `options` live when it lists every entity of a given domain.

    Without this, a select whose options come from
    `hass.states.async_entity_ids(...)` only ever reports the list as it
    looked the moment it last wrote its state (setup, or the last time
    someone picked an option). On startup, integrations that own locks
    (Tesla, SwitchBot Cloud, KeyMagic, ...) can finish loading well after
    this one does, so the very first snapshot is incomplete and, with
    nothing to prompt another write, stays that way -- shown as the
    picked value going "unknown" because it's no longer in that frozen
    list, even though the entity itself still exists.
    """

    _tracked_domains: tuple[str, ...] = ()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if not self._tracked_domains:
            return

        @callback
        def _refresh(_event) -> None:
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_added_domain(self.hass, self._tracked_domains, _refresh)
        )
        self.async_on_remove(
            async_track_state_removed_domain(self.hass, self._tracked_domains, _refresh)
        )


class _BasePersonSelect(_DomainOptionsRefreshMixin, SelectEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, person_key: str) -> None:
        self.hass = hass
        self._entry = entry
        self._person_key = person_key

    @property
    def device_info(self) -> DeviceInfo:
        return main_device_info(self._entry)

    def _person(self) -> dict:
        return dict(self._entry.options.get(CONF_PERSONS, {}).get(self._person_key, {}))

    def _save_person(self, person: dict) -> None:
        persons = dict(self._entry.options.get(CONF_PERSONS, {}))
        persons[self._person_key] = person
        new_options = dict(self._entry.options)
        new_options[CONF_PERSONS] = persons
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        self.async_write_ha_state()


class _BaseKeypadPersonSelect(_DomainOptionsRefreshMixin, SelectEntity, RestoreEntity):
    """Base for the per-(keypad, person) lock/action selects.

    Which locks/action fire for a person depends on which physical keypad
    recognized them -- so this data lives under
    CONF_KEYPADS[keypad_key][CONF_KEYPAD_PERSONS][person_key], not under the
    person itself. Person identity, the credential grid and the enabled
    switch stay per-person/global; only "what happens on this keypad" is
    split out here.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, keypad_key: str, person_key: str
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._keypad_key = keypad_key
        self._person_key = person_key

    @property
    def device_info(self) -> DeviceInfo:
        return keypad_device_info(self._entry, self._keypad_key)

    def _keypad_person(self) -> dict:
        keypad = self._entry.options.get(CONF_KEYPADS, {}).get(self._keypad_key, {})
        return dict(keypad.get(CONF_KEYPAD_PERSONS, {}).get(self._person_key, {}))

    def _save_keypad_person(self, person_lock_config: dict) -> None:
        keypads = {k: dict(v) for k, v in self._entry.options.get(CONF_KEYPADS, {}).items()}
        keypad = dict(keypads.get(self._keypad_key, {}))
        persons = dict(keypad.get(CONF_KEYPAD_PERSONS, {}))
        persons[self._person_key] = person_lock_config
        keypad[CONF_KEYPAD_PERSONS] = persons
        keypads[self._keypad_key] = keypad
        new_options = dict(self._entry.options)
        new_options[CONF_KEYPADS] = keypads
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        self.async_write_ha_state()


class KeypadPersonLockSelect(_BaseKeypadPersonSelect):
    """One of up to LOCK_SLOTS_PER_PERSON locks this keypad triggers for this person."""

    _attr_icon = "mdi:lock"
    _tracked_domains = ("lock",)

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        keypad_key: str,
        person_key: str,
        lock_slot: str,
    ) -> None:
        super().__init__(hass, entry, keypad_key, person_key)
        self._lock_slot = lock_slot
        self._conf_key = f"{CONF_PERSON_LOCK_PREFIX}{lock_slot}"
        self._attr_unique_id = (
            f"{entry.entry_id}_keypad_{keypad_key}_person_{person_key}_lock_{lock_slot}"
        )

    @property
    def name(self) -> str:
        return f"Keypad {self._keypad_key} Person {self._person_key} Schloss {self._lock_slot}"

    @property
    def options(self) -> list[str]:
        locks = sorted(self.hass.states.async_entity_ids("lock"))
        return [NONE_OPTION, *locks]

    @property
    def current_option(self) -> str | None:
        return self._keypad_person().get(self._conf_key) or NONE_OPTION

    async def async_select_option(self, option: str) -> None:
        person_lock_config = self._keypad_person()
        person_lock_config[self._conf_key] = None if option == NONE_OPTION else option
        self._save_keypad_person(person_lock_config)


class KeypadPersonActionSelect(_BaseKeypadPersonSelect):
    """Which lock action (open/unlock/lock) this keypad applies for this person."""

    _attr_icon = "mdi:lock-open-variant"

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, keypad_key: str, person_key: str
    ) -> None:
        super().__init__(hass, entry, keypad_key, person_key)
        self._attr_unique_id = (
            f"{entry.entry_id}_keypad_{keypad_key}_person_{person_key}_action_select"
        )
        self._attr_options = [LOCK_ACTION_LABELS[a] for a in LOCK_ACTIONS]

    @property
    def name(self) -> str:
        return f"Keypad {self._keypad_key} Person {self._person_key} Aktion"

    @property
    def current_option(self) -> str | None:
        action = self._keypad_person().get(CONF_PERSON_LOCK_ACTION, "open")
        return LOCK_ACTION_LABELS.get(action, LOCK_ACTION_LABELS["open"])

    async def async_select_option(self, option: str) -> None:
        reverse = {v: k for k, v in LOCK_ACTION_LABELS.items()}
        person_lock_config = self._keypad_person()
        person_lock_config[CONF_PERSON_LOCK_ACTION] = reverse.get(option, "open")
        self._save_keypad_person(person_lock_config)


class PersonScriptSelect(_BasePersonSelect):
    """An optional script to run for this person, instead of/alongside locks."""

    _attr_icon = "mdi:script-text-outline"
    _tracked_domains = ("script",)

    def __init__(self, hass, entry, person_key) -> None:
        super().__init__(hass, entry, person_key)
        self._attr_unique_id = f"{entry.entry_id}_person_{person_key}_script_select"

    @property
    def name(self) -> str:
        return f"Person {self._person_key} Skript"

    @property
    def options(self) -> list[str]:
        scripts = sorted(self.hass.states.async_entity_ids("script"))
        return [NONE_OPTION, *scripts]

    @property
    def current_option(self) -> str | None:
        return self._person().get(CONF_PERSON_SCRIPT) or NONE_OPTION

    async def async_select_option(self, option: str) -> None:
        person = self._person()
        person[CONF_PERSON_SCRIPT] = None if option == NONE_OPTION else option
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
        return main_device_info(self._entry)

    @property
    def options(self) -> list[str]:
        return [UNASSIGNED_OPTION] + [
            f"{key}: {_person_display(self._entry, key)}" for key in PERSON_KEYS
        ]

    @property
    def current_option(self) -> str | None:
        credentials = self._entry.options.get(CONF_CREDENTIALS, {})
        person_key = credentials.get(self._method, {}).get(self._slot)
        if not person_key:
            return UNASSIGNED_OPTION
        return f"{person_key}: {_person_display(self._entry, person_key)}"

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


class RearmButtonSelect(_DomainOptionsRefreshMixin, SelectEntity, RestoreEntity):
    """Keypad re-arm button, pressed a few seconds after every unlock.

    Some keypads (e.g. Keypad Vision on switchbot-keypad-bridge) only
    re-enable their face/fingerprint scan after seeing the paired lock
    report LOCKED, which never happens on its own if the physical lock is
    a separate device. Pressing a dedicated re-arm button fakes that.

    Auto-detected by entity_id (see REARM_BUTTON_HINTS) so this works
    out of the box without assigning anything -- this select just shows
    what was picked and lets you override it if needed.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:lock-reset"
    _tracked_domains = ("button",)

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_rearm_button_select"

    @property
    def name(self) -> str:
        return "Re-Arm Button"

    @property
    def device_info(self) -> DeviceInfo:
        return main_device_info(self._entry)

    @property
    def options(self) -> list[str]:
        buttons = sorted(self.hass.states.async_entity_ids("button"))
        return [NONE_OPTION, *buttons]

    @property
    def current_option(self) -> str | None:
        return resolve_rearm_button(self.hass, self._entry) or NONE_OPTION

    async def async_select_option(self, option: str) -> None:
        new_options = dict(self._entry.options)
        # An explicit "— keine —" here means "don't even auto-detect one" --
        # store an empty string (falsy but present) rather than deleting the
        # key, so it's distinguishable from "never configured".
        new_options[CONF_REARM_BUTTON] = "" if option == NONE_OPTION else option
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        self.async_write_ha_state()


class NotifyTargetSelect(_DomainOptionsRefreshMixin, SelectEntity, RestoreEntity):
    """Push-notification target for unlock/doorbell events.

    Was only settable once, at initial setup, in entry.data -- with no
    way to fix it if the target entity later disappeared (phone re-paired,
    companion app reinstalled) other than editing storage by hand. Making
    it a live select, like everything else here, means a dead reference
    is visible and fixable from the device page instead of silently
    swallowed by the fire-and-forget notify call.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:bell-outline"
    _tracked_domains = ("notify",)

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_notify_target_select"

    @property
    def name(self) -> str:
        return "Notify Ziel"

    @property
    def device_info(self) -> DeviceInfo:
        return main_device_info(self._entry)

    @property
    def options(self) -> list[str]:
        targets = sorted(self.hass.states.async_entity_ids("notify"))
        return [NONE_OPTION, *targets]

    @property
    def current_option(self) -> str | None:
        return self._entry.data.get(CONF_NOTIFY_TARGET) or NONE_OPTION

    async def async_select_option(self, option: str) -> None:
        new_data = dict(self._entry.data)
        if option == NONE_OPTION:
            new_data.pop(CONF_NOTIFY_TARGET, None)
        else:
            new_data[CONF_NOTIFY_TARGET] = option
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)
        self.async_write_ha_state()
