"""Small shared helpers for the Keypad Person Router integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_REARM_BUTTON, REARM_BUTTON_HINTS


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
