"""Frame builders for the DALIcontrol DCBM Ethernet 3rd party interface.

Implements the string formats from Clipsal application note TS000264
("3rd Party Interface - Ethernet", Rev 1.2). Frames are ASCII, start with
``$``, end with ``*`` and use fixed width, zero padded fields. This module has
no Home Assistant dependency so it can be unit tested on its own.
"""

from __future__ import annotations

from enum import IntEnum

CMD_DALI = 14
CMD_GROUP = 15

MAX_CONTROLLER_ID = 254

# Successful reply to a Group Type command (command 015).
GROUP_ACK = "$0000150000300000*"


class Line(IntEnum):
    """DALI line selection."""

    BOTH = 0
    A = 1
    B = 2


class AddressType(IntEnum):
    """DALI address type."""

    BROADCAST = 0
    GROUP = 1
    BALLAST = 2


class DaliAction(IntEnum):
    """Indirect DALI commands (action type 0 / 0x80)."""

    OFF = 0
    UP = 1
    DOWN = 2
    STEP_UP = 3
    STEP_DOWN = 4
    MAX = 5
    MIN = 6


class GroupActionType(IntEnum):
    """Action type byte of a Group Type command."""

    DALI = 0x80
    ARC_LEVEL = 0x81
    SEQUENCE = 0x82
    LIST = 0x85


# Scenes 0-15 are action 16-31 (0x10-0x1F) in both command types.
SCENE_BASE = 16


def _check(name: str, value: int, low: int, high: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise ValueError(f"{name} must be an integer {low}-{high}, got {value!r}")
    return value


def _frame(controller_id: int, command: int, data: str) -> str:
    _check("controller_id", controller_id, 0, MAX_CONTROLLER_ID)
    return f"${controller_id:03d}{command:03d}{len(data) - 2:03d}{data}*"


def dali_command(
    controller_id: int,
    line: Line,
    address_type: AddressType,
    address: int,
    *,
    direct: bool,
    action: int,
) -> str:
    """Build a DALI Type command (014).

    ``direct`` selects a direct arc level (action 0-255); otherwise ``action``
    is an indirect DALI command (a :class:`DaliAction` or ``SCENE_BASE + n``).
    The controller sends no reply to this command.
    """
    line = Line(line)
    address_type = AddressType(address_type)
    if address_type is AddressType.BROADCAST:
        address = 0
    elif address_type is AddressType.GROUP:
        _check("address", address, 0, 15)
    else:
        _check("address", address, 0, 63)
    if direct:
        _check("arc level", action, 0, 255)
    else:
        _check("action", action, 0, 31)
    # The data length field (010) counts line..action, not the trailing "00".
    return _frame(
        controller_id,
        CMD_DALI,
        f"{line:02d}{address:03d}{address_type:d}{int(direct):d}{action:03d}00",
    )


def dali_scene(
    controller_id: int, line: Line, address_type: AddressType, address: int, scene: int
) -> str:
    """Recall scene 0-15 on a DALI address."""
    _check("scene", scene, 0, 15)
    return dali_command(
        controller_id, line, address_type, address, direct=False, action=SCENE_BASE + scene
    )


def group_command(
    controller_id: int, group: int, action_type: GroupActionType, action: int
) -> str:
    """Build a Group Type command (015).

    ``group`` is 1-64 for Group A and 65-128 for Group B. ``action`` is the
    single byte sent as two hex digits. A successful command is acknowledged
    with :data:`GROUP_ACK`.
    """
    _check("group", group, 1, 128)
    action_type = GroupActionType(action_type)
    _check("action", action, 0, 255)
    return _frame(
        controller_id, CMD_GROUP, f"{group:03d}{action_type:02X}{action:02X}00"
    )


def sequence_action(sequence: int, step: int = 1) -> int:
    """Action byte for sequence 1-32 at step 1-8."""
    _check("sequence", sequence, 1, 32)
    _check("step", step, 1, 8)
    return (step - 1) * 0x20 + (sequence - 1)


def list_start_action(list_number: int) -> int:
    """Action byte to start list 1-26 (0x01-0x1A)."""
    return _check("list", list_number, 1, 26)


def list_stop_action(list_number: int | None = None) -> int:
    """Action byte to stop list 1-26 (0x81-0x9A), or 0x80 to stop the running list."""
    if list_number is None:
        return 0x80
    return 0x80 + _check("list", list_number, 1, 26)
