"""Small shared helpers for the Keypad Person Router integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    CONF_KEYPAD_SOURCE_ID,
    CONF_KEYPADS,
    CONF_REARM_BUTTON,
    DOMAIN,
    INTEGRATION_TITLE,
    REARM_BUTTON_HINTS,
)


def resolve_rearm_button(hass: HomeAssistant, entry: ConfigEntry) -> str | None:
    """The configured re-arm button, or an auto-detected one.

    Works out of the box for switchbot-keypad-bridge-style setups (a
    button entity literally named "re-arm"/"scharf schalten") without
    requiring you to go find and assign it yourself. Still overridable
    via the Re-Arm Button select if auto-detection picks the wrong one,
    or explicitly turned off by selecting "— keine —" there (stored as
    "", distinct from never having been touched at all).
    """
    if CONF_REARM_BUTTON in entry.options:
        return entry.options[CONF_REARM_BUTTON] or None
    for entity_id in hass.states.async_entity_ids("button"):
        lowered = entity_id.lower()
        if any(hint in lowered for hint in REARM_BUTTON_HINTS):
            return entity_id
    return None


def main_device_info(entry: ConfigEntry) -> DeviceInfo:
    """The integration's main device -- shared/global entities live here.

    Persons, the credential grid, the re-arm/notify selects: anything that
    applies across every keypad, not scoped to one.
    """
    return DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name=INTEGRATION_TITLE)


def keypad_device_info(entry: ConfigEntry, keypad_key: str) -> DeviceInfo:
    """A per-keypad sub-device, so each keypad's entities get their own
    device page instead of piling everything (persons x locks x 2 keypads)
    onto one. Linked back to the main device via `via_device` -- shows up
    nested under it rather than as an unrelated device.

    The name includes the configured Quelle-ID (e.g. "tor"), once set, so
    the device list itself confirms which physical bridge is which without
    opening it.
    """
    source_id = (
        entry.options.get(CONF_KEYPADS, {}).get(keypad_key, {}).get(CONF_KEYPAD_SOURCE_ID)
    )
    name = f"Keypad {keypad_key}" + (f" ({source_id})" if source_id else "")
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_keypad_{keypad_key}")},
        name=name,
        via_device=(DOMAIN, entry.entry_id),
    )
