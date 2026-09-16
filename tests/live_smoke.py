"""Opt-in REAL desktop integration test; always closes only its own demo windows."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import Hyprland


def ipc(command):
    result = subprocess.run(["omarchy-shell", "omnitiler", command], capture_output=True,
                            text=True, check=True, timeout=10).stdout.strip()
    return json.loads(result) if command == "status" else result


def wait_for(predicate, message, timeout=12):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        result = predicate()
        if result:
            return result
        time.sleep(0.15)
    raise AssertionError(message + "\n" + json.dumps(ipc("status")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", required=True)
    args = parser.parse_args()
    h = Hyprland()
    before = h.query("activewindow")
    workspace = h.query("activeworkspace")["id"]
    monitor = next(m for m in h.query("monitors") if m["focused"])
    used = {w["id"] for w in h.query("workspaces")}
    start = 4
    while any(n in used for n in range(start, start + 5)):
        start += 5
    children = []
    checks = []

    def demos():
        return [c for c in h.query("clients") if c["class"].startswith("omnitiler.demo.")]

    def launch(n):
        p = subprocess.Popen(["foot", "--app-id=omnitiler.demo." + str(n),
                              "--title=OmniTiler · Demo " + str(n), "--font=monospace:size=13",
                              "python3", str(ROOT / "tests/demo_window.py"), str(n)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        children.append(p)
        return wait_for(lambda: next((c for c in demos() if c["class"] == "omnitiler.demo." + str(n)), None),
                        "Demo did not open")

    def settle(count):
        wait_for(lambda: sum(sum(bool(v) for v in slots.values())
                            for slots in ipc("status")["occupancy"].values()) == count,
                 "Unexpected managed window count")
        time.sleep(1.1)
        assert not ipc("status")["error"], ipc("status")

    try:
        assert not ipc("status")["active"], "Turn OmniTiler off before running smoke tests"
        h.dispatch('hl.dispatch(hl.dsp.focus({workspace=' + str(start) + ', on_current_monitor=true}))')
        ipc("activate")
        wait_for(lambda: ipc("status")["active"], "Activation failed")
        for n in range(1, 8):
            launch(n)
            settle(n)
            current = h.query("activewindow")
            expected_ws = start + (n - 1) // 3
            assert current["workspace"]["id"] == expected_ws, current
            assert current["class"] == "omnitiler.demo." + str(n), current
            g = h.dimensions(monitor)
            for c in demos():
                number = int(c["class"].rsplit(".", 1)[1])
                rect = g[("center", "left", "right")[(number - 1) % 3]]
                assert all(abs(a - b) <= 1 for a, b in zip(c["at"] + c["size"], rect)), c
            checks.append(f"{n} windows: geometry, occupancy and focus correct")
            if n == 3:
                subprocess.run(["grim", "-o", monitor["name"], str(ROOT / "docs/preview.png")], check=True)
        # Close left, refill it, keeping the other two fixed.
        children[1].terminate()
        children[1].wait(timeout=5)
        settle(6)
        h.dispatch('hl.dispatch(hl.dsp.focus({workspace=' + str(start) + '}))')
        c = launch(8)
        settle(7)
        c = next(c for c in demos() if c["class"] == "omnitiler.demo.8")
        assert tuple(c["at"] + c["size"]) == h.dimensions(monitor)["left"]
        checks.append("Closing and reopening a window refills the left slot")
        h.dispatch('hl.dispatch(hl.dsp.window.fullscreen({window=w, action="set"}))', c)
        time.sleep(1)
        assert next(w for w in demos() if w["address"] == c["address"])["fullscreen"]
        h.dispatch('hl.dispatch(hl.dsp.window.fullscreen({window=w, action="unset"}))', c)
        time.sleep(1.5)
        c = next(w for w in demos() if w["address"] == c["address"])
        assert tuple(c["at"] + c["size"]) == h.dimensions(monitor)["left"]
        checks.append("Fullscreen exits back into the assigned slot")
        h.move(c, start + 4, monitor["name"])
        settle(6)
        assert not next(w for w in demos() if w["address"] == c["address"])["floating"]
        checks.append("Manual move to unmanaged workspace releases normal tiling")
        for _ in range(2):
            ipc("deactivate")
            wait_for(lambda: not any(c["floating"] for c in demos()), "Disable did not restore tiling")
            ipc("activate")
            wait_for(lambda: ipc("status")["active"], "Reactivation failed")
        ipc("deactivate")
        wait_for(lambda: not any(c["floating"] for c in demos()), "Final cleanup failed")
        checks.append("Repeated toggles restore all managed windows")
        (ROOT / "test-results").mkdir(exist_ok=True)
        (ROOT / "test-results/live-smoke.json").write_text(json.dumps(checks, indent=2) + "\n")
        print("\n".join(checks))
    finally:
        ipc("deactivate")
        time.sleep(0.3)
        for p in children:
            if p.poll() is None:
                p.terminate()
                p.wait(timeout=5)
        h.dispatch('hl.dispatch(hl.dsp.focus({workspace=' + str(workspace) + '}))')
        if before.get("address"):
            h.focus(before)


if __name__ == "__main__":
    main()
