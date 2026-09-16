#!/usr/bin/env python3
"""OmniTiler's session-local, serial Hyprland controller. No third-party deps."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import signal
import socket
import subprocess
import sys
import threading
import time

SLOTS = ("center", "left", "right")
SPATIAL_SLOTS = ("left", "center", "right")


def identity(client):
    return (client["address"], str(client["stableId"]), client["pid"])


def eligible(c):
    return (c.get("mapped", False) and not c.get("hidden", False)
            and c.get("acceptsInput", True) and c["workspace"]["id"] > 0
            and not any(c.get(k) for k in ("floating", "pinned", "grouped")))


def css_gaps(value):
    """Hyprland uses CSS order: top right bottom left."""
    n = [max(0, round(float(x))) for x in str(value).split()]
    if len(n) == 1:
        return n * 4
    if len(n) == 2:
        return n * 2
    if len(n) == 3:
        return [n[0], n[1], n[2], n[1]]
    if len(n) != 4:
        raise ValueError("Invalid compositor gap value")
    return n


def geometry(monitor, outer, inner, border):
    """Return content rectangles; borders and pairwise inner gaps are external."""
    w, h = monitor["width"], monitor["height"]
    if monitor.get("transform", 0) % 2:
        w, h = h, w
    scale = monitor["scale"]
    w, h = round(w / scale), round(h / scale)
    left, top, right, bottom = monitor.get("reserved", [0, 0, 0, 0])
    ot, ore, ob, ol = outer
    _, ir, _, il = inner
    gap = il + ir
    usable = w - left - right - ol - ore - 6 * border - 2 * gap
    height = h - top - bottom - ot - ob - 2 * border
    if usable < 30 or height < 30:
        raise ValueError("Monitor work area is too small for three columns")
    side = round(usable * 0.3)
    widths = (side, usable - 2 * side, side)
    x = round(monitor["x"] + left + ol + border)
    y = round(monitor["y"] + top + ot + border)
    result = {}
    for name, width in zip(("left", "center", "right"), widths):
        result[name] = (x, y, width, round(height))
        x += width + 2 * border + gap
    return result


class Hyprland:
    def __init__(self):
        signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
        runtime = os.environ.get("XDG_RUNTIME_DIR", "")
        if not signature or not runtime:
            raise RuntimeError("OmniTiler needs a running Hyprland session")
        self.directory = Path(runtime) / "hypr" / signature
        self.hotkey_map = None

    def enable_hotkeys(self):
        # Do not silently replace a user's customized key combination.
        bindings = self.query("binds")
        for key, description in (("LEFT", "Swap window to the left"),
                                 ("RIGHT", "Swap window to the right")):
            matches = [b for b in bindings if b["modmask"] == 65
                       and b["key"].upper() == key and not b["submap"]]
            if (len(matches) != 1 or matches[0]["description"] != description
                    or any(matches[0].get(k) for k in ("release", "mouse", "locked", "longPress",
                        "repeat", "non_consuming", "auto_consuming", "allow_input_capture", "catch_all"))):
                raise RuntimeError(f"Super+Shift+{key.title()} is customized; restore its Omarchy swap binding to use OmniTiler")
        self.dispatch(Path(__file__).with_name("hotkeys.lua").read_text())
        self.hotkey_map = None

    def sync_hotkeys(self, records):
        mapping = sorted((int(r["identity"][1], 16), r["workspace"]) for r in records)
        if mapping != self.hotkey_map:
            values = ",".join(f"[{stable}]={workspace}" for stable, workspace in mapping)
            self.dispatch("if _G.__omnitiler_hotkeys then "
                          "_G.__omnitiler_hotkeys.windows={" + values + "} end")
            self.hotkey_map = mapping

    def clear_hotkeys(self):
        self.dispatch("if _G.__omnitiler_hotkeys then _G.__omnitiler_hotkeys.restore() end")
        self.hotkey_map = None

    def request(self, command):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            s.connect(str(self.directory / ".socket.sock"))
            s.sendall(command.encode())
            data = bytearray()
            while True:
                part = s.recv(65536)
                if not part:
                    break
                data.extend(part)
        return data.decode()

    def query(self, command):
        return json.loads(self.request("j/" + command))

    def snapshot(self):
        return {k: self.query(k) for k in ("clients", "monitors", "workspaces")}

    def dimensions(self, monitor):
        outer = css_gaps(self.query("getoption general:gaps_out")["css"])
        inner = css_gaps(self.query("getoption general:gaps_in")["css"])
        border = max(0, self.query("getoption general:border_size")["int"])
        return geometry(monitor, outer, inner, border)

    def dispatch(self, code, client=None):
        # Guard within the compositor, not just in the earlier JSON snapshot.
        # stableId is hexadecimal in Hyprland JSON; Lua stable_id is numeric.
        if client:
            addr, stable, pid = identity(client)
            if not re.fullmatch(r"0x[0-9a-fA-F]+", addr) or not re.fullmatch(r"[0-9a-fA-F]+", stable):
                raise ValueError("Invalid Hyprland window identity")
            code = (f'local w = hl.get_window("address:{addr}"); '
                    f'if w and w.stable_id == tonumber("{stable}", 16) and w.pid == {int(pid)} '
                    f'then {code} end')
        result = self.request("/eval " + code).strip()
        if result != "ok":
            raise RuntimeError(result[:250] or "Empty compositor response")

    def float(self, c, enabled):
        action = "on" if enabled else "off"
        self.dispatch(f'hl.dispatch(hl.dsp.window.float({{window=w, action="{action}"}}))', c)

    def place(self, c, rect):
        x, y, width, height = rect
        self.dispatch(
            'hl.dispatch(hl.dsp.window.float({window=w, action="on"})); '
            f'hl.dispatch(hl.dsp.window.resize({{window=w, x={width}, y={height}, relative=false}})); '
            f'hl.dispatch(hl.dsp.window.move({{window=w, x={x}, y={y}, relative=false}}))', c)

    def move(self, c, workspace, monitor):
        # on_current_monitor is used only for new/empty targets; callers exclude
        # workspaces assigned to other monitors, including configured bindings.
        self.dispatch(f'hl.dispatch(hl.dsp.window.move({{window=w, workspace={int(workspace)}, follow=false}}))', c)
        self.dispatch('hl.dispatch(hl.dsp.workspace.move({workspace=' + str(int(workspace))
                      + ', monitor=' + json.dumps(monitor) + '}))')

    def focus(self, c):
        self.dispatch('hl.dispatch(hl.dsp.focus({window=w}))', c)

    def rules(self):
        return self.query("workspacerules")


class Journal:
    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        try:
            data = json.loads(self.path.read_text())
            if not isinstance(data, list):
                raise ValueError("Invalid recovery journal")
            return data
        except FileNotFoundError:
            return []

    def save(self, records):
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w") as f:
            json.dump(list(records), f)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(self.path)


class Controller:
    def __init__(self, backend, journal, clock=time.monotonic):
        self.hypr, self.journal, self.clock = backend, journal, clock
        self.active = False
        self.monitor = None
        self.workspaces = set()
        self.records = {}
        self.seen = set()
        self.locations = {}
        self.error = ""
        self.rectangles = {}
        self.pending_opens = []
        self.restore_journal()

    def persist(self):
        self.journal.save(self.records.values())
        if self.active:
            self.hypr.sync_hotkeys(self.records.values())

    def restore_journal(self):
        self.hypr.clear_hotkeys()
        records = self.journal.load()
        if not records:
            return
        clients = {identity(c): c for c in self.hypr.query("clients")}
        remaining = []
        for record in records:
            c = clients.get(tuple(record["identity"]))
            if c:
                try:
                    self.hypr.float(c, False)
                except Exception:
                    remaining.append(record)
        self.journal.save(remaining)
        if remaining:
            raise RuntimeError("Could not restore interrupted tiling; retry when Hyprland is available")

    def status(self):
        occupancy = {str(w): {s: None for s in SLOTS} for w in sorted(self.workspaces)}
        for record in self.records.values():
            ws = str(record["workspace"])
            if ws in occupancy:
                occupancy[ws][record["slot"]] = record["identity"][0]
        return {"active": self.active, "monitor": self.monitor,
                "workspaces": sorted(self.workspaces), "occupancy": occupancy,
                "error": self.error}

    def activate(self):
        if self.active:
            return
        if self.records:
            self.deactivate()
            if self.records:
                raise RuntimeError("Restore pending windows before activating again")
        snap = self.hypr.snapshot()
        monitor = next((m for m in snap["monitors"] if m.get("focused")), None)
        if not monitor or monitor.get("specialWorkspace", {}).get("id", 0):
            raise ValueError("Switch to a normal numbered workspace first")
        ws = monitor["activeWorkspace"]["id"]
        if ws <= 0 or monitor["activeWorkspace"].get("name", str(ws)) != str(ws):
            raise ValueError("Activate on a numbered workspace")
        self.monitor = monitor["name"]
        self.rectangles = self.hypr.dimensions(monitor)
        self.hypr.enable_hotkeys()
        self.workspaces = {ws}
        self.seen = {identity(c) for c in snap["clients"]}
        self.locations = {identity(c): (c["monitor"], c["workspace"]["id"])
                          for c in snap["clients"]}
        self.active, self.error = True, ""
        candidates = sorted((c for c in snap["clients"] if eligible(c)
                             and c["workspace"]["id"] == ws and c["monitor"] == monitor["id"]),
                            key=lambda c: (c.get("focusHistoryID", 999999) < 0,
                                           c.get("focusHistoryID", 999999), c["address"]))
        target = ws
        for c in candidates:
            target = self.admit(c, target, follow=False)
        if candidates:
            self.hypr.focus(candidates[0])

    def move_slot(self, direction, address, stable):
        """Honor a keypress for its captured window, even if focus changes later."""
        if not self.active or direction not in ("l", "r"):
            return
        self.reconcile()
        clients = {identity(c): c for c in self.hypr.query("clients")}
        key = next((k for k in self.records if k[:2] == (address, stable)), None)
        if key is None or key not in clients:
            return
        c, record = clients[key], self.records[key]
        if c.get("fullscreen"):
            return
        index = SPATIAL_SLOTS.index(record["slot"]) + (-1 if direction == "l" else 1)
        if not 0 <= index < len(SPATIAL_SLOTS):
            return
        target = SPATIAL_SLOTS[index]
        neighbor = next((k for k, r in self.records.items()
                         if r["workspace"] == record["workspace"] and r["slot"] == target), None)
        if neighbor and clients[neighbor].get("fullscreen"):
            return
        was_focused = self.hypr.query("activewindow").get("address") == address
        previous = record["slot"]
        record.update(slot=target, attempts=0)
        if neighbor:
            self.records[neighbor].update(slot=previous, attempts=0)
        self.persist()
        if neighbor:
            self.place(clients[neighbor], self.records[neighbor])
        self.place(c, record)
        # Moving a neighbor under the pointer can change focus mid-dispatch.
        # Preserve the keypress window's focus as captured before placement.
        if was_focused:
            self.hypr.focus(c)

    def vacant(self, workspace):
        occupied = {r["slot"] for r in self.records.values() if r["workspace"] == workspace}
        return next((s for s in SLOTS if s not in occupied), None)

    def next_empty(self, workspace):
        snap = self.hypr.snapshot()
        occupied = {c["workspace"]["id"] for c in snap["clients"] if c.get("mapped")}
        other = {w["id"] for w in snap["workspaces"] if w["monitor"] != self.monitor}
        # Respect concrete numeric workspace-to-monitor rules, even when empty.
        for rule in self.hypr.rules():
            name = str(rule.get("workspaceString", ""))
            if name.isdigit() and rule.get("monitor") not in (None, "", self.monitor):
                other.add(int(name))
        target = workspace + 1
        while target in occupied or target in other or any(
                r["workspace"] == target for r in self.records.values()):
            target += 1
        if target > 2147483647:
            raise ValueError("No higher numbered workspace available")
        return target

    def admit(self, c, workspace, follow=True):
        if identity(c) in self.records:
            return workspace
        slot = self.vacant(workspace)
        if slot is None:
            workspace, slot = self.next_empty(workspace), "center"
        record = {"identity": list(identity(c)), "workspace": workspace,
                  "slot": slot, "last_place": 0, "attempts": 0}
        self.records[identity(c)] = record
        self.workspaces.add(workspace)
        # Journal BEFORE mutating any window: crash recovery also covers partial work.
        self.persist()
        try:
            moved = c["workspace"]["id"] != workspace
            if moved:
                self.hypr.move(c, workspace, self.monitor)
            if not c.get("fullscreen"):
                self.place(c, record)
            if moved and follow:
                self.hypr.focus(c)
        except Exception as e:
            self.error = "Placement failed: " + str(e)
            self.release(c)
        return workspace

    def place(self, c, record):
        record["last_place"] = self.clock()
        record["attempts"] += 1
        self.hypr.place(c, self.rectangles[record["slot"]])

    def release(self, c):
        key = identity(c)
        try:
            if key in self.records:
                self.hypr.float(c, False)
                del self.records[key]
                self.persist()
        except Exception as e:
            self.error = "Could not restore a window: " + str(e)

    def deactivate(self):
        self.active = False
        self.error = ""
        self.hypr.clear_hotkeys()
        clients = {identity(c): c for c in self.hypr.query("clients")}
        for key in list(self.records):
            if key in clients:
                self.release(clients[key])
            else:
                del self.records[key]
        self.persist()
        self.workspaces.clear()
        self.monitor = None
        self.pending_opens.clear()

    def reconcile(self):
        if not self.active:
            return
        snap = self.hypr.snapshot()
        monitor = next((m for m in snap["monitors"] if m["name"] == self.monitor), None)
        if not monitor:
            self.deactivate()
            self.error = "Monitor disconnected; normal tiling restored"
            return
        rectangles = self.hypr.dimensions(monitor)
        geometry_changed = rectangles != self.rectangles
        self.rectangles = rectangles
        clients = {identity(c): c for c in snap["clients"]}
        # Workspaces deliberately moved off this monitor leave the managed set.
        departed = {w["id"] for w in snap["workspaces"] if w["monitor"] != self.monitor}
        self.workspaces.difference_update(departed)
        for key, record in list(self.records.items()):
            c = clients.get(key)
            if not c:
                del self.records[key]
                self.persist()
                continue
            ws = c["workspace"]["id"]
            if (ws not in self.workspaces or c["monitor"] != monitor["id"]
                    or c.get("pinned") or c.get("grouped")):
                self.release(c)
                continue
            if ws != record["workspace"]:
                slot = self.vacant(ws)
                if slot is None:
                    self.release(c)
                    self.error = "Destination is full; moved window released to normal tiling"
                    continue
                record.update(workspace=ws, slot=slot, attempts=0)
                self.persist()
            if c.get("fullscreen"):
                record["attempts"] = 0
                continue
            desired = self.rectangles[record["slot"]]
            actual = tuple(c["at"] + c["size"])
            matches = c["floating"] and all(abs(a - b) <= 1 for a, b in zip(actual, desired))
            if matches:
                record["attempts"] = 0
                continue
            if geometry_changed:
                record["attempts"] = 0
            if self.clock() - record["last_place"] < 0.8:
                continue  # Let compositor animations / client configure acks settle.
            if record["attempts"] >= 2:
                self.release(c)
                self.error = "A window could not fit its slot and was released to normal tiling"
                continue
            try:
                self.place(c, record)
            except Exception as e:
                self.error = "Placement failed: " + str(e)
                self.release(c)
        # Socket arrival order, with snapshot ordering as a reconnect fallback.
        order = {address: i for i, address in enumerate(self.pending_opens)}
        new = [c for k, c in clients.items() if k not in self.seen or
               (k not in self.records and self.locations.get(k) !=
                (c["monitor"], c["workspace"]["id"]))]
        new.sort(key=lambda c: (order.get(c["address"], len(order)), int(str(c["stableId"]), 16)))
        self.pending_opens.clear()
        destinations = {}
        for c in new:
            if (eligible(c) and c["workspace"]["id"] in self.workspaces
                    and c["monitor"] == monitor["id"]):
                source = c["workspace"]["id"]
                follow = (identity(c) not in self.seen or
                          self.hypr.query("activewindow").get("address") == c["address"])
                destinations[source] = self.admit(c, destinations.get(source, source), follow=follow)
        self.seen = set(clients)
        self.locations = {k: (c["monitor"], c["workspace"]["id"]) for k, c in clients.items()}


def event_reader(backend, incoming, stop):
    while not stop.is_set():
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                s.connect(str(backend.directory / ".socket2.sock"))
                buffer = b""
                while not stop.is_set():
                    try:
                        data = s.recv(65536)
                    except socket.timeout:
                        continue
                    if not data:
                        break
                    buffer += data
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        name, _, payload = line.decode(errors="replace").partition(">>")
                        if name == "openwindow":
                            incoming.put(("open", "0x" + payload.split(",", 1)[0].removeprefix("0x")))
                        elif name == "custom" and payload.startswith("omnitiler:move,"):
                            parts = payload.split(",")
                            if len(parts) == 4:
                                incoming.put(("move", parts[1:]))
                        elif name in {"closewindow", "movewindowv2", "fullscreen", "configreloaded",
                                      "monitorremoved", "monitoradded", "moveworkspacev2",
                                      "changefloatingmode", "togglegroup", "pin"}:
                            incoming.put(("event", name))
        except OSError:
            pass
        stop.wait(1)


def state_directory(backend):
    digest = hashlib.sha256(str(backend.directory).encode()).hexdigest()[:16]
    state = Path(os.environ["XDG_RUNTIME_DIR"]) / ("omnitiler-" + digest)
    state.mkdir(mode=0o700, exist_ok=True)
    return state


def guardian(read_fd):
    """Qt may kill a Process during component destruction, before it can clean up.

    This independent child holds only the read end of a lifetime pipe. EOF means
    its controller exited (including SIGKILL). The lock prevents any concurrent
    controller/recovery writes. A replacement controller also recovers on start.
    """
    with os.fdopen(read_fd, "rb") as lifetime:
        while lifetime.read(1):
            pass
    backend = Hyprland()
    state = state_directory(backend)
    with (state / "lock").open("w") as lock:
        for _ in range(30):
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(0.1)
        else:
            return  # Replacement controller owns recovery and the session now.
        Controller(backend, Journal(state / "windows.json"))


def main():
    backend = Hyprland()
    state = state_directory(backend)
    # A process from an old QML instance can be finishing cleanup during reload.
    lock = (state / "lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX)
    controller = Controller(backend, Journal(state / "windows.json"))
    read_fd, lifetime_fd = os.pipe()
    watcher = subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()),
                                "--guardian", str(read_fd)], pass_fds=(read_fd,),
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, start_new_session=True)
    os.close(read_fd)
    incoming = queue.Queue()
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: incoming.put(("command", "shutdown")))
    signal.signal(signal.SIGINT, lambda *_: incoming.put(("command", "shutdown")))

    def read_commands():
        for line in sys.stdin:
            try:
                command = json.loads(line).get("command")
                incoming.put(("command", command))
            except (ValueError, AttributeError):
                incoming.put(("invalid", "Invalid JSON command"))
        incoming.put(("command", "shutdown"))

    threading.Thread(target=read_commands, daemon=True).start()
    threading.Thread(target=event_reader, args=(backend, incoming, stop), daemon=True).start()
    last_output = None

    def emit(force=False):
        nonlocal last_output
        value = json.dumps(controller.status(), sort_keys=True)
        if force or value != last_output:
            print(value, flush=True)
            last_output = value

    emit()
    next_tick = time.monotonic() + 1
    try:
        while True:
            try:
                kind, payload = incoming.get(timeout=max(0.001, next_tick - time.monotonic()))
            except queue.Empty:
                kind, payload = "tick", None
            try:
                if kind == "command":
                    if payload == "shutdown":
                        break
                    if payload == "toggle":
                        payload = "deactivate" if controller.active else "activate"
                    if payload in {"activate", "deactivate"}:
                        getattr(controller, payload)()
                    elif payload != "status":
                        raise ValueError("Unknown command")
                elif kind == "invalid":
                    raise ValueError(payload)
                elif kind == "open" and controller.active:
                    controller.pending_opens.append(payload)
                elif kind == "move":
                    controller.move_slot(*payload)
                elif kind == "event" and payload == "configreloaded" and controller.active:
                    backend.enable_hotkeys()
                    backend.sync_hotkeys(controller.records.values())
                if kind in {"open", "event"}:
                    next_tick = min(next_tick, time.monotonic() + 0.12)
                if time.monotonic() >= next_tick or kind == "tick":
                    controller.reconcile()
                    next_tick = time.monotonic() + 1
            except Exception as e:
                controller.error = str(e)
                next_tick = time.monotonic() + 1
            emit(force=kind == "command")
    finally:
        stop.set()
        try:
            controller.deactivate()
        finally:
            os.close(lifetime_fd)
            fcntl.flock(lock, fcntl.LOCK_UN)
            watcher.wait(timeout=8)


if __name__ == "__main__":
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "--guardian":
            guardian(int(sys.argv[2]))
        else:
            main()
    except Exception as error:
        print("OmniTiler: " + str(error), file=sys.stderr)
        sys.exit(1)
