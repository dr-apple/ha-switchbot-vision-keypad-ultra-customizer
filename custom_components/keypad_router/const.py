"""Constants for the Keypad Person Router integration."""

DOMAIN = "keypad_router"
INTEGRATION_TITLE = "SwitchBot Vision Keypad Ultra Customizer"

METHODS = ["pin", "nfc", "fingerprint", "face"]
METHOD_LABELS = {
    "pin": "PIN",
    "nfc": "NFC",
    "fingerprint": "Fingerabdruck",
    "face": "Gesicht",
}

NUM_PERSONS = 6
SLOTS_PER_METHOD = 6
PERSON_KEYS = [str(i) for i in range(1, NUM_PERSONS + 1)]
SLOT_KEYS = [str(i) for i in range(SLOTS_PER_METHOD)]

LOCK_ACTIONS = ["open", "unlock", "lock"]
LOCK_ACTION_LABELS = {
    "open": "Öffnen",
    "unlock": "Entriegeln",
    "lock": "Verriegeln",
}

CONF_UNLOCK_EVENT = "unlock_event"
CONF_LOCK_EVENT = "lock_event"
CONF_DOORBELL_EVENT = "doorbell_event"
CONF_NOTIFY_TARGET = "notify_target"
CONF_LOGBOOK_ENTITY = "logbook_entity"
CONF_LOGBOOK_NAME = "logbook_name"

DEFAULT_UNLOCK_EVENT = "esphome.switchbot_keypad_unlock"
DEFAULT_LOCK_EVENT = "esphome.switchbot_keypad_lock"
DEFAULT_DOORBELL_EVENT = "esphome.switchbot_keypad_doorbell"
DEFAULT_LOGBOOK_NAME = "Schließsystem"

CONF_PERSONS = "persons"
CONF_CREDENTIALS = "credentials"
CONF_REARM_BUTTON = "rearm_button"
REARM_DELAY_SECONDS = 3
# Auto-detect a re-arm button by entity_id substring so this works out of
# the box for switchbot-keypad-bridge-style setups without manual setup.
REARM_BUTTON_HINTS = ["scharf_schalten", "rearm"]

# Per-person option keys (nested under CONF_PERSONS[<person_key>])
CONF_PERSON_NAME = "name"
CONF_PERSON_LOCK_ACTION = "lock_action"
CONF_PERSON_SCRIPT = "script_entity"

LOCK_SLOTS_PER_PERSON = 3
LOCK_SLOT_KEYS = [str(i) for i in range(1, LOCK_SLOTS_PER_PERSON + 1)]
CONF_PERSON_LOCK_PREFIX = "lock_"  # + LOCK_SLOT_KEYS -> "lock_1", "lock_2", "lock_3"

# Fixed keypad (bridge) slots. Which locks/action apply to a given person is
# configured per keypad -- not per person -- since the same person can be
# recognized at more than one physical keypad and each keypad may need to
# trigger something different (e.g. the Tor keypad opens Tor+Haustuer, the
# Haustuer keypad only opens Haustuer). Person identity, the credential
# grid, the enabled switch and the access log all stay shared/global.
NUM_KEYPADS = 2
KEYPAD_KEYS = [str(i) for i in range(1, NUM_KEYPADS + 1)]

CONF_KEYPADS = "keypads"
# Per-keypad option keys (nested under CONF_KEYPADS[<keypad_key>])
CONF_KEYPAD_SOURCE_ID = "source_id"  # must match the incoming event's "source_id" field
CONF_KEYPAD_PERSONS = "persons"  # nested: [person_key] -> {lock_1/2/3, lock_action}
# (re-uses LOCK_SLOT_KEYS / CONF_PERSON_LOCK_PREFIX / CONF_PERSON_LOCK_ACTION
# for the keys *inside* that nested per-person dict)

UNKNOWN_PERSON_LABEL = "Unbekannt"

NONE_OPTION = "— keine —"
UNASSIGNED_OPTION = "— frei —"
