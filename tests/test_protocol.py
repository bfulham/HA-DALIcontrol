"""Tests for the DCBM frame builders, using the examples from TS000264."""

import importlib.util
import pathlib
import sys
import unittest

# Load protocol.py directly so the tests do not need Home Assistant installed.
_path = (
    pathlib.Path(__file__).parent.parent
    / "custom_components"
    / "dalicontrol"
    / "protocol.py"
)
_spec = importlib.util.spec_from_file_location("dali_protocol", _path)
p = importlib.util.module_from_spec(_spec)
sys.modules["dali_protocol"] = p
_spec.loader.exec_module(p)


class ProtocolTests(unittest.TestCase):
    def test_dali_example_1(self):
        # Group 5, line A, MAX, controller 011
        frame = p.dali_command(
            11, p.Line.A, p.AddressType.GROUP, 5, direct=False, action=p.DaliAction.MAX
        )
        self.assertEqual(frame, "$011014010010051000500*")

    def test_dali_example_2(self):
        # Address 15, lines A+B, direct arc 120, controller 023 (address type 2)
        frame = p.dali_command(
            23, p.Line.BOTH, p.AddressType.BALLAST, 15, direct=True, action=120
        )
        self.assertEqual(frame, "$023014010000152112000*")

    def test_dali_broadcast_zeroes_address(self):
        frame = p.dali_command(
            1, p.Line.BOTH, p.AddressType.BROADCAST, 33, direct=False, action=0
        )
        self.assertEqual(frame, "$001014010000000000000*")

    def test_dali_scene(self):
        frame = p.dali_scene(1, p.Line.A, p.AddressType.GROUP, 2, 3)
        self.assertEqual(frame, "$001014010010021001900*")

    def test_group_example_1(self):
        frame = p.group_command(11, 5, p.GroupActionType.DALI, p.DaliAction.MAX)
        self.assertEqual(frame, "$011015007005800500*")

    def test_group_example_2(self):
        # Group B30 (94), sequence 6 step 1, controller 052
        frame = p.group_command(
            52, 94, p.GroupActionType.SEQUENCE, p.sequence_action(6, 1)
        )
        self.assertEqual(frame, "$052015007094820500*")

    def test_sequence_action(self):
        self.assertEqual(p.sequence_action(1, 1), 0x00)
        self.assertEqual(p.sequence_action(32, 1), 0x1F)
        self.assertEqual(p.sequence_action(1, 2), 0x20)
        self.assertEqual(p.sequence_action(32, 8), 0xFF)

    def test_list_actions(self):
        self.assertEqual(p.list_start_action(1), 0x01)
        self.assertEqual(p.list_stop_action(), 0x80)
        self.assertEqual(p.list_stop_action(1), 0x81)

    def test_validation(self):
        bad = [
            lambda: p.group_command(255, 1, p.GroupActionType.DALI, 0),
            lambda: p.group_command(1, 0, p.GroupActionType.DALI, 0),
            lambda: p.group_command(1, 129, p.GroupActionType.DALI, 0),
            lambda: p.dali_command(
                1, p.Line.A, p.AddressType.BALLAST, 64, direct=True, action=0
            ),
            lambda: p.dali_command(
                1, p.Line.A, p.AddressType.GROUP, 16, direct=True, action=0
            ),
            lambda: p.dali_command(
                1, p.Line.A, p.AddressType.GROUP, 1, direct=True, action=256
            ),
            lambda: p.dali_scene(1, p.Line.A, p.AddressType.GROUP, 1, 16),
        ]
        for call in bad:
            with self.assertRaises(ValueError):
                call()


if __name__ == "__main__":
    unittest.main()
