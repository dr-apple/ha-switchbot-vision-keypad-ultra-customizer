"""Constants for the Keypad Person Router integration."""

DOMAIN = "keypad_router"

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

# Per-person option keys (nested under CONF_PERSONS[<person_key>])
CONF_PERSON_NAME = "name"
CONF_PERSON_LOCK_ENTITY = "lock_entity"
CONF_PERSON_LOCK_ACTION = "lock_action"
CONF_PERSON_AUTOMATION = "automation_entity"

UNKNOWN_PERSON_LABEL = "Unbekannt"
