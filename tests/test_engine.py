import copy
import json
from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Controller, Journal, css_gaps, geometry, identity


MONITOR = {"id": 0, "name": "DP-2", "width": 3440, "height": 1440, "scale": 1,
           "x": 0, "y": 0, "reserved": [0, 26, 0, 0], "focused": True,
           "activeWorkspace": {"id": 1, "name": "1"}}


def window(n, workspace=1, **kwargs):
    return dict(address=hex(n), stableId=format(n + 1000, "x"), pid=n,
                mapped=True, hidden=False, acceptsInput=True, floating=False,
                pinned=False, grouped=[], fullscreen=0, monitor=0,
                workspace={"id": workspace, "name": str(workspace)},
                at=[0, 0], size=[100, 100], focusHistoryID=n, **kwargs)


class FakeHypr:
    def __init__(self, windows=()):
        self.clients = list(windows)
        self.monitors = [copy.deepcopy(MONITOR)]
        self.extra_workspaces = []
        self.calls = []
        self.fail = False
        self.stubborn = False
        self.workspace_rules = []

    def query(self, name):
        if name == "clients":
            return copy.deepcopy(self.clients)
        if name == "activewindow":
            return copy.deepcopy(self.clients[0]) if self.clients else {}
        raise ValueError(name)

    def enable_hotkeys(self):
        self.hotkeys = True

    def sync_hotkeys(self, records):
        self.hotkey_windows = [r["identity"] for r in records]

    def clear_hotkeys(self):
        self.hotkeys = False

    def snapshot(self):
        workspaces = [{"id": n, "monitor": "DP-2"} for n in
                      {c["workspace"]["id"] for c in self.clients}]
        return copy.deepcopy(dict(clients=self.clients, monitors=self.monitors,
                                  workspaces=workspaces + self.extra_workspaces))

    def rules(self):
        return self.workspace_rules

    def dimensions(self, m):
        return geometry(m, [10]*4, [5]*4, 1)

    def live(self, c):
        return next((w for w in self.clients if identity(c) == identity(w)), None)

    def float(self, c, enabled):
        self.calls.append(("float", c["address"], enabled))
        if self.fail:
            raise RuntimeError("compositor unavailable")
        if self.live(c):
            self.live(c)["floating"] = enabled

    def place(self, c, rect):
        self.float(c, True)
        if not self.stubborn and self.live(c):
            self.live(c).update(at=list(rect[:2]), size=list(rect[2:]))

    def move(self, c, ws, monitor):
        if self.live(c):
            self.live(c)["workspace"] = {"id": ws, "name": str(ws)}
        self.calls.append(("move", c["address"], ws))

    def focus(self, c):
        self.calls.append(("focus", c["address"]))


class GeometryTests(unittest.TestCase):
    def test_current_monitor(self):
        g = geometry(MONITOR, [10]*4, [5]*4, 1)
        self.assertEqual(g["left"], (11, 37, 1018, 1392))
        self.assertEqual(g["center"], (1041, 37, 1358, 1392))
        self.assertEqual(g["right"], (2411, 37, 1018, 1392))
        self.assertEqual(g["center"][0] + g["center"][2] / 2, 1720)

    def test_fractional_offset_and_reservations(self):
        m = dict(MONITOR, scale=1.25, x=-2752, reserved=[12, 32, 18, 48])
        g = geometry(m, [8, 9, 10, 11], [2, 3, 4, 5], 2)
        self.assertEqual(g["left"][0], -2727)
        self.assertEqual(g["left"][1], 42)
        self.assertEqual(g["left"][2], g["right"][2])
        self.assertEqual(g["right"][0] + g["right"][2] + 2 + 9 + 18, 0)

    def test_rotated_monitor(self):
        g = geometry(dict(MONITOR, transform=1), [0]*4, [0]*4, 0)
        self.assertEqual(sum(r[2] for r in g.values()), 1440)
        self.assertEqual(g["left"][3], 3414)

    def test_css(self):
        self.assertEqual(css_gaps("3"), [3]*4)
        self.assertEqual(css_gaps("3 7"), [3, 7, 3, 7])
        self.assertEqual(css_gaps("3 7 9"), [3, 7, 9, 7])


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.journal = Journal(Path(self.temp.name) / "windows.json")
        self.hypr = FakeHypr()
        self.now = 10
        self.c = Controller(self.hypr, self.journal, lambda: self.now)

    def tick(self):
        self.now += 2
        self.c.reconcile()

    def test_focus_first_and_initial_overflow(self):
        self.hypr.clients = [window(n) for n in range(1, 8)]
        self.hypr.clients[4]["focusHistoryID"] = 0
        self.c.activate()
        records = self.c.records
        self.assertEqual(records[identity(self.hypr.clients[4])]["slot"], "center")
        self.assertEqual([sum(r["workspace"] == n for r in records.values())
                          for n in (1, 2, 3)], [3, 3, 1])
        self.assertEqual(self.hypr.calls[-1], ("focus", "0x5"))

    def test_open_order_and_vacancy(self):
        self.c.activate()
        for n in (1, 2, 3):
            self.hypr.clients.append(window(n))
            self.tick()
        self.assertEqual([r["slot"] for r in self.c.records.values()], ["center", "left", "right"])
        self.hypr.clients.pop(1)
        self.tick()
        self.hypr.clients.append(window(4))
        self.tick()
        self.assertEqual(self.c.records[identity(self.hypr.clients[-1])]["slot"], "left")
        self.assertEqual(self.c.records[identity(self.hypr.clients[1])]["slot"], "right")

    def test_burst_and_skip_occupied_or_other_monitor(self):
        self.hypr.clients = [window(99, 2)]
        self.hypr.extra_workspaces = [{"id": 3, "monitor": "HDMI-A-1"}]
        self.hypr.workspace_rules = [{"workspaceString": "4", "monitor": "HDMI-A-1"}]
        self.c.activate()
        self.hypr.clients += [window(n) for n in range(1, 8)]
        self.c.pending_opens = [hex(n) for n in range(7, 0, -1)]
        self.tick()
        self.assertEqual(sorted(self.c.workspaces), [1, 5, 6])
        self.assertEqual(self.c.records[identity(self.hypr.clients[-1])]["slot"], "center")
        self.assertFalse(self.hypr.clients[0]["floating"])

    def test_exclusions_and_unmanaged_workspace(self):
        self.hypr.clients = [window(n) for n in range(1, 6)]
        for c, prop in zip(self.hypr.clients, ("floating", "pinned", "grouped", "hidden")):
            c[prop] = True
        self.hypr.clients[-1]["workspace"]["id"] = -99
        self.c.activate()
        self.hypr.clients += [window(6, 2), dict(window(7), monitor=1)]
        self.tick()
        self.assertEqual(self.c.records, {})

    def test_fullscreen_and_deliberate_move(self):
        self.hypr.clients = [window(1)]
        self.c.activate()
        c = self.hypr.clients[0]
        c.update(fullscreen=2, size=[3440, 1440], at=[0, 0])
        self.tick()
        self.assertEqual(c["size"], [3440, 1440])
        c["fullscreen"] = 0
        self.tick()
        self.assertEqual(c["size"], [1358, 1392])
        c["workspace"]["id"] = 9
        self.tick()
        self.assertFalse(c["floating"])
        self.assertFalse(self.c.records)

    def test_geometry_change_and_disconnect(self):
        self.hypr.clients = [window(1)]
        self.c.activate()
        self.hypr.monitors[0]["scale"] = 1.25
        self.tick()
        self.assertEqual(self.hypr.clients[0]["size"][0], self.c.rectangles["center"][2])
        self.hypr.monitors.clear()
        self.tick()
        self.assertFalse(self.c.active)
        self.assertFalse(self.hypr.clients[0]["floating"])

    def test_failure_preserves_journal_for_retry(self):
        self.hypr.clients = [window(1)]
        self.c.activate()
        self.hypr.fail = True
        self.c.deactivate()
        self.assertTrue(self.journal.load())
        self.hypr.fail = False
        self.c.deactivate()
        self.assertEqual(self.journal.load(), [])
        self.assertFalse(self.hypr.clients[0]["floating"])

    def test_stubborn_window_released_without_loop(self):
        self.hypr.clients = [window(1)]
        self.hypr.stubborn = True
        self.c.activate()
        self.tick()
        self.tick()
        count = len(self.hypr.calls)
        for _ in range(5):
            self.tick()
        self.assertEqual(len(self.hypr.calls), count)
        self.assertFalse(self.hypr.clients[0]["floating"])
        self.assertIn("could not fit", self.c.error)

    def test_recovery_and_address_reuse(self):
        self.hypr.clients = [window(1), window(2)]
        self.c.activate()
        self.hypr.clients[1]["stableId"] = "badbeef"
        self.hypr.clients[1]["floating"] = False
        self.hypr.calls.clear()
        restored = Controller(self.hypr, self.journal)
        self.assertFalse(restored.active)
        self.assertEqual(self.hypr.calls, [("float", "0x1", False)])
        self.assertEqual(self.journal.load(), [])

    def test_closed_before_reconcile_and_repeated_toggle(self):
        for _ in range(3):
            self.hypr.clients = [window(1)]
            self.c.activate()
            self.hypr.clients.clear()
            self.tick()
            self.c.deactivate()
        self.assertEqual(self.journal.load(), [])

    def test_hotkeys_swap_sizes_and_stay_swapped(self):
        self.hypr.clients = [window(n) for n in (1, 2, 3)]
        self.c.activate()
        center, left, right = self.hypr.clients
        self.c.move_slot("l", center["address"], center["stableId"])
        self.assertEqual(center["size"][0], 1018)
        self.assertEqual(left["size"][0], 1358)
        self.tick()
        self.tick()
        self.assertEqual(self.c.records[identity(center)]["slot"], "left")
        self.assertEqual(self.c.records[identity(left)]["slot"], "center")
        self.assertEqual(self.c.records[identity(right)]["slot"], "right")
        self.c.move_slot("r", center["address"], center["stableId"])
        self.assertEqual(center["size"][0], 1358)

    def test_hotkey_empty_slot_edges_and_stale_window(self):
        self.hypr.clients = [window(1)]
        self.c.activate()
        c = self.hypr.clients[0]
        self.c.move_slot("r", c["address"], c["stableId"])
        self.assertEqual(self.c.records[identity(c)]["slot"], "right")
        self.c.move_slot("r", c["address"], c["stableId"])
        self.assertEqual(self.c.records[identity(c)]["slot"], "right")
        self.c.move_slot("l", c["address"], "deadbeef")
        self.assertEqual(self.c.records[identity(c)]["slot"], "right")
        c["fullscreen"] = 2
        self.c.move_slot("l", c["address"], c["stableId"])
        self.assertEqual(self.c.records[identity(c)]["slot"], "right")
        self.c.deactivate()
        self.assertFalse(self.hypr.hotkeys)

    def test_move_existing_window_into_managed_workspace(self):
        self.hypr.clients = [window(1), window(2, 9)]
        self.c.activate()
        self.hypr.clients[1]["workspace"]["id"] = 1
        self.tick()
        self.assertEqual(self.c.records[identity(self.hypr.clients[1])]["slot"], "left")
        self.assertTrue(self.hypr.clients[1]["floating"])

    def test_hotkey_does_not_move_unmanaged_window(self):
        self.hypr.clients = [window(1), window(2, 9)]
        self.c.activate()
        c = self.hypr.clients[1]
        self.c.move_slot("l", c["address"], c["stableId"])
        self.assertFalse(c["floating"])
        self.assertEqual(c["workspace"]["id"], 9)
        self.assertNotIn(identity(c), self.c.records)


if __name__ == "__main__":
    unittest.main()
