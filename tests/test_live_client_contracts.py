"""No-game-required regression checks for the live-client contract."""
import math
import unittest

from workbench.runtime.live_client import DevelopmentAction, Position, validate_action


class LiveClientContractsTest(unittest.TestCase):
    def test_finite_coordinates(self):
        self.assertEqual(Position(44, 1, 2, 3).zone_id, 44)
        for bad in (math.nan, math.inf, -math.inf):
            with self.assertRaises(ValueError):
                Position(44, bad, 0, 0)

    def test_zone_range(self):
        with self.assertRaises(ValueError):
            Position(-1, 0, 0, 0)

    def test_writes_default_denied(self):
        for action in (DevelopmentAction.NUDGE, DevelopmentAction.WARP_ENTITY,
                       DevelopmentAction.SET_SPEED, DevelopmentAction.SET_VISIBILITY):
            with self.assertRaises(PermissionError):
                validate_action(action, authorized_dev_session=False,
                                adapter_supports_writes=False, version_verified=False)

    def test_read_only_actions_allowed(self):
        validate_action(DevelopmentAction.VALIDATE_NAVMESH, authorized_dev_session=False,
                        adapter_supports_writes=False, version_verified=False)


if __name__ == "__main__":
    unittest.main()
