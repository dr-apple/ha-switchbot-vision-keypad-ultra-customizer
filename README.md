# Keypad Person Router

A small Home Assistant integration that sits between a keypad bridge (e.g.
[switchbot-keypad-bridge](https://github.com/pierluigizagaria/switchbot-keypad-bridge))
and your locks/automations, and answers one question cleanly: **who used the
keypad, and what should happen because of it?**

## Why

Bridges like switchbot-keypad-bridge fire an event per unlock with a
`method` (`pin` / `nfc` / `fingerprint` / `face`) and a credential `index`.
That index is **per method** — face slot `0` and fingerprint slot `0` are two
different physical credentials that happen to share a number. Mapping that
directly to "who unlocked" with a flat list of helpers gets confusing fast,
and wiring "also open the front door for family" into the same automation
means editing one big blob of YAML every time something changes.

This integration fixes that by giving you two small, fixed tables instead:

- **6 persons.** Each with a name, a target lock, an action
  (open / unlock / lock), an optional automation to also trigger, and a
  dashboard-visible on/off switch.
- **A credential grid.** For every (method, slot) pair — 4 methods × 6 slots
  — pick which of the 6 persons it belongs to.

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
3. Install "Keypad Person Router", restart Home Assistant.

### Manual

Copy `custom_components/keypad_router` into your `config/custom_components/`
folder and restart Home Assistant.

## Setup

1. **Settings → Devices & Services → Add Integration → "Keypad Person
   Router"**.
2. Enter the three event types your bridge fires (defaults match
   switchbot-keypad-bridge: `esphome.switchbot_keypad_unlock`,
   `esphome.switchbot_keypad_lock`, `esphome.switchbot_keypad_doorbell`),
   and optionally a notify target for push notifications.
3. Open the integration's **Configure** button:
   - **Personen** — fill in name, lock, action, and optional automation for
     each of the 6 rows you actually use.
   - **Zuordnung Slots → Personen** — for every method/slot your keypad
     actually has enrolled, pick the matching person from the dropdown.

That's it — no dashboard entities are required to configure it, only to
*use* it (see below).

## Example dashboard

The integration itself only creates one thing you'd put on a dashboard: a
switch per person. Everything else (name, lock, action, automation) lives in
the integration's own settings page. A minimal "Schließsystem" view:

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
        heading: Personen
        icon: mdi:account-key
      - type: entities
        title: Zugriff aktiv/inaktiv
        show_header_toggle: false
        entities:
          - entity: switch.keypad_person_router_person_1_aktiv
          - entity: switch.keypad_person_router_person_2_aktiv
          - entity: switch.keypad_person_router_person_3_aktiv
          - entity: switch.keypad_person_router_person_4_aktiv
          - entity: switch.keypad_person_router_person_5_aktiv
          - entity: switch.keypad_person_router_person_6_aktiv
  - type: grid
    cards:
      - type: heading
        heading: Schlösser
        icon: mdi:lock
      - type: tile
        entity: lock.tor_tor_lock_ultra
        grid_options:
          columns: 12
          rows: 2
        tap_action:
          action: none
        icon_tap_action:
          action: none
        features:
          - type: lock-commands
          - type: lock-open-door
        features_position: bottom
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

Rename/duplicate the switch rows and the lock tile to match how many
persons and locks you've actually configured.

## Notes

- The person switches persist their on/off state across restarts
  (`RestoreEntity`), defaulting to on for a switch that's never been touched.
- Editing "Personen" or "Zuordnung" via Configure reloads the integration
  entry, so a switch's display name updates immediately.
- Logging uses the `logbook.log` service against the first configured lock
  entity, so entries group under a real device instead of collapsing under
  the integration itself.

## License

MIT — see [LICENSE](LICENSE).
