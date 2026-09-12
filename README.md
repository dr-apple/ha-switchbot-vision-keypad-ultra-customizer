# SwitchBot Vision Keypad Ultra Customizer

A small Home Assistant integration that sits between a keypad bridge (e.g.
[switchbot-keypad-bridge](https://github.com/pierluigizagaria/switchbot-keypad-bridge))
and your locks/scripts, and answers one question cleanly: **who used the
keypad, and what should happen because of it?**

Despite the name, it isn't SwitchBot-specific — any integration that fires an
event with a `method` and a credential `index` on unlock works.

## Why

Bridges like switchbot-keypad-bridge fire an event per unlock with a
`method` (`pin` / `nfc` / `fingerprint` / `face`) and a credential `index`.
That index is **per method** — face slot `0` and fingerprint slot `0` are two
different physical credentials that happen to share a number. Mapping that
directly to "who unlocked" with a flat list of helpers gets confusing fast.

This integration fixes that with two small, fixed tables — both fully live
on the device page, nothing hidden behind a settings dialog:

- **6 persons.** Each with a name, up to 3 target locks, one action applied
  to all of them (open / unlock / lock), an optional script to also run,
  and a dashboard-visible on/off switch.
- **A credential grid.** For every (method, slot) pair — 4 methods × 6 slots
  — a dropdown picks which of the 6 persons it belongs to.

On every unlock/lock/doorbell event the integration resolves the person,
logs the access to the Logbook, sends a push notification (if configured),
and — if that person's switch is on — runs their configured lock action on
each of their configured locks and their optional script. Everything is
logged regardless of the switch, so turning someone off (a cleaner between
visits, a kid grounded from the garden gate) never loses access history.

**Deliberately not dynamic.** Six persons, four methods, six slots, three
locks each — fixed. No "add another person" flow to maintain. If you need
more, raise the constants in `const.py` and it scales the same way.

**Naming is static** ("Person 1 Schloss 1", "Person 1 Aktion", ...) rather
than following the person's current name — the one field that lets you
*set* the name would otherwise be the only one that never updates its own
label, which makes it hard to find. The name you enter shows up as that
entity's *value*, not baked into every other entity's label.

## Installation

### HACS (custom repository)

1. HACS → Integrations → ⋮ → Custom repositories.
2. Add `https://github.com/dr-apple/ha-keypad-router`, category
   "Integration".
3. Install "SwitchBot Vision Keypad Ultra Customizer", restart Home
   Assistant.

### Manual

Copy `custom_components/keypad_router` into your `config/custom_components/`
folder and restart Home Assistant.

## Setup

1. **Settings → Devices & Services → Add Integration → "SwitchBot Vision
   Keypad Ultra Customizer"**.
2. Enter the three event types your bridge fires (defaults match
   switchbot-keypad-bridge: `esphome.switchbot_keypad_unlock`,
   `esphome.switchbot_keypad_lock`, `esphome.switchbot_keypad_doorbell`),
   and optionally a notify target for push notifications.
3. Open the device page. Everything else is configured right there, as
   regular entities, per person:
   - **Person N Name** (text) — who this is.
   - **Person N Schloss 1/2/3** (select) — up to three locks this person's
     credential should act on.
   - **Person N Aktion** (select) — Öffnen / Entriegeln / Verriegeln,
     applied to every lock configured above.
   - **Person N Skript** (select) — an optional script to also run.
   - **Person N aktiv** (switch) — suspend this person's actions without
     touching their configuration; access is still logged either way.
   - **\<Methode> Slot \<N>** (select, one set for the whole device, not
     per person) — picks which person a given method+slot credential
     belongs to.

No YAML, no options flow — just fill in the entities.

## Example dashboard

The device page already shows everything, but a dedicated dashboard view
groups it better for daily use — one block per person, and the credential
grid split into one block per method (mirrors how the slots are physically
organized on the keypad):

```yaml
type: sections
title: Schließsystem
path: schliesssystem
icon: mdi:door-closed-lock
max_columns: 3
sections:
  - type: grid
    cards:
      - type: heading
        heading: Danny
        icon: mdi:account-key
      - type: entities
        title: Danny
        show_header_toggle: false
        entities:
          - entity: switch.keypad_person_router_person_1_aktiv
            name: Aktiv
          - entity: select.switchbot_vision_keypad_ultra_customizer_person_1_schloss_1
            name: Schloss 1
          - entity: select.switchbot_vision_keypad_ultra_customizer_person_1_schloss_2
            name: Schloss 2
          - entity: select.switchbot_vision_keypad_ultra_customizer_danny_aktion
            name: Aktion
          - entity: select.switchbot_vision_keypad_ultra_customizer_person_1_skript
            name: Skript
  - type: grid
    cards:
      - type: heading
        heading: Gesicht
        icon: mdi:face-recognition
      - type: entities
        title: Gesicht
        show_header_toggle: false
        entities:
          - entity: select.switchbot_vision_keypad_ultra_customizer_gesicht_slot_0
            name: Slot 0
          - entity: select.switchbot_vision_keypad_ultra_customizer_gesicht_slot_1
            name: Slot 1
  - type: grid
    cards:
      - type: heading
        heading: Fingerabdruck
        icon: mdi:fingerprint
      - type: entities
        title: Fingerabdruck
        show_header_toggle: false
        entities:
          - entity: select.switchbot_vision_keypad_ultra_customizer_fingerabdruck_slot_0
            name: Slot 0
  - type: grid
    column_span: 3
    cards:
      - type: heading
        heading: Zugriffsprotokoll
        icon: mdi:history
      - type: logbook
        title: Wer hat es benutzt
        entities:
          - lock.tor_tor_lock_ultra
        hours_to_show: 168
        grid_options:
          columns: full
          rows: 6
```

Duplicate the "Gesicht"/"Fingerabdruck" blocks for PIN and NFC, and the
"Danny" block per person, to match how many you've actually configured.

## Notes

- All entities persist across restarts (`RestoreEntity`); a person switch
  never touched defaults to on.
- Lock and script selects list every `lock.*` / `script.*` entity in your
  system live, so newly added ones show up without a reload.
- Editing any entity (name, lock, action, script, credential slot) updates
  the config entry's options and reloads it, so other display names refresh
  immediately.
- Entity IDs are generated once from the initial (often empty) name and
  don't rename themselves later — only the friendly name/value does. That's
  normal Home Assistant behavior, not a bug.
- Logging uses the `logbook.log` service against the first configured lock
  entity, so entries group under a real device instead of collapsing under
  the integration itself.

## License

MIT — see [LICENSE](LICENSE).
