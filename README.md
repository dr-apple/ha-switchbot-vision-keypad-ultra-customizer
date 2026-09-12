# SwitchBot Vision Keypad Ultra Customizer

A small Home Assistant integration that sits between a keypad bridge (e.g.
[switchbot-keypad-bridge](https://github.com/pierluigizagaria/switchbot-keypad-bridge))
and your locks/automations, and answers one question cleanly: **who used the
keypad, and what should happen because of it?**

Despite the name, it isn't SwitchBot-specific — any integration that fires an
event with a `method` and a credential `index` on unlock works.

## Why

Bridges like switchbot-keypad-bridge fire an event per unlock with a
`method` (`pin` / `nfc` / `fingerprint` / `face`) and a credential `index`.
That index is **per method** — face slot `0` and fingerprint slot `0` are two
different physical credentials that happen to share a number. Mapping that
directly to "who unlocked" with a flat list of helpers gets confusing fast,
and wiring "also open the front door for family" into the same automation
means editing one big blob of YAML every time something changes.

This integration fixes that with two small, fixed tables — both fully live
on the device page, nothing hidden behind a settings dialog:

- **6 persons.** Each with a name, a target lock, an action
  (open / unlock / lock), an optional automation to also trigger, and a
  dashboard-visible on/off switch.
- **A credential grid.** For every (method, slot) pair — 4 methods × 6 slots
  — a dropdown picks which of the 6 persons it belongs to.

On every unlock/lock/doorbell event the integration resolves the person,
logs the access to the Logbook, sends a push notification (if configured),
and — if that person's switch is on — runs their configured lock action and
automation. Everything is logged regardless of the switch, so turning
someone off (a cleaner between visits, a kid grounded from the garden gate)
never loses access history.

**Deliberately not dynamic.** Six persons, four methods, six slots — fixed.
No "add another person" flow to maintain. If you need more, raise the
constants in `const.py` and it scales the same way.

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
   regular entities:
   - **Person N Name** (text), **Person N Schloss** / **Aktion** /
     **Automation** (selects), **Person N aktiv** (switch) — one set of four
     per person, for the persons you actually use.
   - **\<Methode> Slot \<N>** (select) — one per method/slot your keypad has
     enrolled, picks which person that credential belongs to.

No YAML, no options flow — just fill in the entities.

## Example dashboard

The device page already shows everything, but a dedicated dashboard view
groups it better for daily use. Example for one person ("Danny") plus the
credential grid for two enrolled face slots and one fingerprint slot —
duplicate the person block and add rows to the grid as you configure more:

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
          - entity: select.switchbot_vision_keypad_ultra_customizer_danny_schloss
            name: Schloss
          - entity: select.switchbot_vision_keypad_ultra_customizer_danny_aktion
            name: Aktion
          - entity: select.switchbot_vision_keypad_ultra_customizer_danny_automation
            name: Zusatz-Automation
  - type: grid
    cards:
      - type: heading
        heading: Codes/Gesichter → Person
        icon: mdi:account-key
      - type: entities
        title: Zuordnung
        show_header_toggle: false
        entities:
          - entity: select.switchbot_vision_keypad_ultra_customizer_gesicht_slot_0
            name: Gesicht 0
          - entity: select.switchbot_vision_keypad_ultra_customizer_gesicht_slot_1
            name: Gesicht 1
          - entity: select.switchbot_vision_keypad_ultra_customizer_fingerabdruck_slot_0
            name: Fingerabdruck 0
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

## Notes

- All entities persist across restarts (`RestoreEntity`); a person switch
  never touched defaults to on.
- Lock and automation selects list every `lock.*` / `automation.*` entity in
  your system live, so newly added locks/automations show up without a
  reload.
- Editing any entity (name, lock, action, automation, credential slot)
  updates the config entry's options and reloads it, so display names
  (e.g. a switch's label) update immediately everywhere.
- Logging uses the `logbook.log` service against the first configured lock
  entity, so entries group under a real device instead of collapsing under
  the integration itself.

## License

MIT — see [LICENSE](LICENSE).
