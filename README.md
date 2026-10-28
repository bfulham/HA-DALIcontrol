# HA-DALIcontrol

Home Assistant custom integration for Clipsal / Schneider Electric **DALIcontrol DCBM** line controllers (DCBM1-1608, DCBM2-1608), using the Ethernet 3rd party interface described in application note TS000264.

> **Status: early release, untested against real hardware.** The frame formats are implemented from the application note and checked against its examples, but nobody has run this on a DCBM yet. Please report what you find.

## Features

- One config entry per DCBM line controller (host, controller ID, UDP or TCP).
- Lights for DALI **groups** (0-15), **controller groups** (GA1-64 / GB1-64, as named in DCBM Manager), **ballasts** or **broadcast**, with brightness (direct arc level).
- Services: `dalicontrol.recall_scene` (on a light), `run_sequence`, `run_list`, `stop_list` and `send_raw`.

## Limitations

- **State is assumed.** The Ethernet interface is write only: the controller has no documented way to report levels or faults, so Home Assistant remembers what it last sent. Changes made from wall switches or other software are not seen.
- A controller only allows **4 TCP sockets** (port 1001), and this integration opens one per command and closes it again. UDP (port 1235) is preferred.
- UDP is connectionless, so setup cannot tell whether the controller is really there.
- No authentication exists on the interface. Keep controllers on their own VLAN.

## Install

### HACS

1. HACS > three-dot menu > **Custom repositories**.
2. Add `https://github.com/bfulham/HA-DALIcontrol` as an **Integration**.
3. Install **DALIcontrol** and restart Home Assistant.

### Manual

Copy `custom_components/dalicontrol` into your Home Assistant `config/custom_components/` and restart.

## Setup

1. **Settings > Devices & services > Add integration > DALIcontrol**.
2. Enter the controller's IP, its **controller ID** (000-254, as programmed in DCBM Manager) and the protocol. Leave the port blank for the default (UDP 1235, TCP 1001).
3. Open the entry's **Configure** menu and add lights: a name, type (DALI group 0-15, controller group, ballast 0-63, broadcast), line and address. For GA20 choose **Controller group**, line **A**, address **20**.

For UDP the host may be the VLAN broadcast address, but every controller on the VLAN then receives the frame. Controllers ignore frames with a different controller ID.

## Protocol summary

Frames are ASCII, start with `$`, end with `*`, with fixed width zero padded fields.

| Command | Frame | Reply |
|---|---|---|
| DALI type (014) | `$` ID(3) `014` `010` line(2) addr(3) addrtype(1) action-type(1) action(3) `00` `*` | none |
| Group type (015) | `$` ID(3) `015` `007` group(3) action-type(2 hex) action(2 hex) `00` `*` | `$0000150000300000*` |

Example: group 5, line A, MAX on controller 011 is `$011014010010051000500*`.

Notes on the source document:

- Its second DALI example is labelled "group 12" but encodes address 015 with address type 2 (ballast). This integration follows the field table, not the label.
- The document lists list numbers as "01-20" but the hex ranges (0x01-0x1A, 0x81-0x9A) allow 26, so `run_list` accepts 1-26.

Source: Clipsal DALIcontrol Application Note TS000264, "3rd Party Interface - Ethernet", Rev 1.2 (not redistributed here).

## Development

```
python -m unittest discover -s tests -v
```

The protocol and transport tests do not need Home Assistant installed.

## License

MIT
