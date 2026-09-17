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

This integration fixes that with a few small, fixed tables — all fully live
on the device page, nothing hidden behind a settings dialog:

- **6 persons.** Each with a name, an optional script to also run, and a
  dashboard-visible on/off switch. Person identity is shared across every
  keypad — the same person table and the same access log apply no matter
  which physical keypad recognized them.
- **Up to 2 keypads.** Each with a **Quelle-ID** (source id) that must match
  the `source_id` field the bridge puts in its event data — that's how two
  keypads sharing the same event type get told apart. For every keypad ×
  person pair, up to 3 target locks and one action (open / unlock / lock)
  applied to all of them: what a given person's credential does is a
  property of *which keypad* recognized them, not of the person alone (e.g.
  the gate keypad can open gate+front door together, while the front-door
  keypad only opens the front door).
- **A credential grid.** For every (method, slot) pair — 4 methods × 6 slots
  — a dropdown picks which of the 6 persons it belongs to. Shared across
  keypads too, so enrolling the same person in the same slot number on a
  second keypad needs no extra configuration here.

On every unlock/lock/doorbell event the integration resolves the person,
logs the access to the Logbook, sends a push notification (if configured),
and — if that person's switch is on — runs the lock action configured for
*that person on the keypad the event came from*, plus the person's optional
script. Everything is logged regardless of the switch, so turning someone
off (a cleaner between visits, a kid grounded from the garden gate) never
loses access history. An event whose `source_id` matches no configured
keypad is still logged and notified, just with no lock action taken.

**Deliberately not dynamic.** Six persons, two keypads, four methods, six
slots, three locks each — fixed. No "add another person/keypad" flow to
maintain. If you need more, raise the constants in `const.py` and it scales
the same way.

**Naming is static** ("Person 1 Name", "Keypad 1 Person 1 Schloss 1", ...)
rather than following the person's/keypad's current name — the one field
that lets you *set* the name would otherwise be the only one that never
updates its own label, which makes it hard to find. The name you enter
shows up as that entity's *value*, not baked into every other entity's
label.

## Installation

### HACS (custom repository)

1. HACS → Integrations → ⋮ → Custom repositories.
2. Add `https://github.com/dr-apple/ha-switchbot-vision-keypad-ultra-customizer`, category
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
   - **Person N Name** (text) — who this is. Shared across every keypad.
   - **Person N Skript** (select) — an optional script to also run. Shared.
   - **Person N aktiv** (switch) — suspend this person's actions everywhere
     without touching their configuration; access is still logged either
     way. Shared.
   - **\<Methode> Slot \<N>** (select, one set for the whole device) —
     picks which person a given method+slot credential belongs to. Shared.
   - **Keypad N Quelle-ID** (text) — set this to a short id (e.g. `tor`,
     `haustuer`) and put the same string in that bridge's YAML as the
     `source_id` field on its `on_unlock`/`on_lock`/`on_doorbell` events
     (see the example below). This is how the router tells two keypads
     apart when both fire the same event type.
   - **Keypad N Person M Schloss 1/2/3** (select) — up to three locks that
     *this keypad* triggers when it recognizes person M.
   - **Keypad N Person M Aktion** (select) — Öffnen / Entriegeln /
     Verriegeln, applied to every lock configured above for that
     keypad+person pair.

No YAML-based configuration, no options flow — just fill in the entities.
The only YAML involved is the bridge's own ESPHome config, which needs a
`source_id` in its event data to distinguish keypads:

```yaml
switchbot_keypad_bridge:
  on_unlock:
    - homeassistant.event:
        event: esphome.switchbot_keypad_unlock  # same event name on every bridge
        data:
          method: !lambda 'return method;'
          index: !lambda 'return to_string(index);'
          source_id: "haustuer"  # matches this bridge's "Keypad N Quelle-ID"
  on_lock:
    - homeassistant.event:
        event: esphome.switchbot_keypad_lock
        data:
          source_id: "haustuer"
  on_doorbell:
    - homeassistant.event:
        event: esphome.switchbot_keypad_doorbell
        data:
          source_id: "haustuer"
```

All bridges use the **same** event names (so they share one person table
and one access log) but each bridge's own fixed `source_id` string.

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
          - entity: select.switchbot_vision_keypad_ultra_customizer_person_1_skript
            name: Skript
          - entity: text.switchbot_vision_keypad_ultra_customizer_keypad_1_quelle_id
            name: "Keypad 1 (Quelle-ID)"
          - entity: select.switchbot_vision_keypad_ultra_customizer_keypad_1_person_1_schloss_1
            name: "Keypad 1 → Schloss 1"
          - entity: select.switchbot_vision_keypad_ultra_customizer_keypad_1_person_1_schloss_2
            name: "Keypad 1 → Schloss 2"
          - entity: select.switchbot_vision_keypad_ultra_customizer_keypad_1_person_1_aktion
            name: "Keypad 1 → Aktion"
          - entity: text.switchbot_vision_keypad_ultra_customizer_keypad_2_quelle_id
            name: "Keypad 2 (Quelle-ID)"
          - entity: select.switchbot_vision_keypad_ultra_customizer_keypad_2_person_1_schloss_1
            name: "Keypad 2 → Schloss 1"
          - entity: select.switchbot_vision_keypad_ultra_customizer_keypad_2_person_1_aktion
            name: "Keypad 2 → Aktion"
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
