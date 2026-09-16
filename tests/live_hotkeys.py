"""Opt-in tests of real Omarchy key combinations using a disposable uinput device."""
import json
import subprocess
import sys
import time
from live_smoke import ROOT, Hyprland, ipc, wait_for
from keyboard import press


def main():
    if sys.argv[1:] != ["--run"]:
        raise SystemExit("Pass --run to exercise the real desktop")
    h = Hyprland()
    original = h.query("activewindow")
    original_ws = h.query("activeworkspace")["id"]
    monitor = next(m for m in h.query("monitors") if m["focused"])
    used = {w["id"] for w in h.query("workspaces")}
    ws = next(n for n in range(4, 8) if n not in used and n+1 not in used)
    children = []
    results = []

    def binds():
        return [{k: v for k, v in b.items() if k != "arg"} for b in h.query("binds")
                if b["modmask"] == 65 and b["key"].upper() in ("LEFT", "RIGHT")]

    baseline = binds()

    def clients():
        return {int(c["class"].rsplit(".", 1)[1]): c for c in h.query("clients")
                if c["class"].startswith("omnitiler.keys.")}

    def slot(n, name):
        c = clients().get(n)
        rect = h.dimensions(monitor)[name]
        return c and tuple(c["at"] + c["size"]) == rect and c["floating"]

    def focus(n):
        h.focus(clients()[n])
        wait_for(lambda: h.query("activewindow").get("address") == clients()[n]["address"], "Focus failed")
        time.sleep(0.15)

    try:
        assert not ipc("status")["active"]
        h.dispatch('hl.dispatch(hl.dsp.focus({workspace=' + str(ws) + ', on_current_monitor=true}))')
        ipc("activate")
        wait_for(lambda: ipc("status")["active"], "Activation failed")
        for n in (1, 2, 3):
            children.append(subprocess.Popen(["foot", "--app-id=omnitiler.keys." + str(n),
                "--title=OmniTiler · Keyboard demo", "python3", str(ROOT / "tests/demo_window.py"), str(n)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            wait_for(lambda: slot(n, ("center", "left", "right")[n-1]), "Initial placement failed")
        focus(1)
        press("Left")
        wait_for(lambda: slot(1, "left") and slot(2, "center"), "Super+Shift+Left did not swap")
        time.sleep(1.5)
        assert slot(1, "left") and slot(2, "center"), "Reconciliation undid swap"
        press("Right")
        wait_for(lambda: slot(1, "center") and slot(2, "left"), "Super+Shift+Right did not swap")
        wait_for(lambda: h.query("activewindow").get("address") == clients()[1]["address"],
                 "Swap did not preserve focused window")
        time.sleep(0.5)
        results.append("Real Super+Shift+Left/Right swap windows and their widths without snapping back")
        press("Right", shift=False)
        wait_for(lambda: h.query("activewindow").get("address") == clients()[3]["address"], "Super+Right focus failed")
        results.append("Native Super+Arrow focus remains functional")
        children[1].terminate()
        children[1].wait(timeout=5)
        wait_for(lambda: 2 not in clients(), "Closed window still visible")
        focus(1)
        press("Left")
        wait_for(lambda: slot(1, "left"), "Move into empty left column failed")
        press("Left")
        time.sleep(0.8)
        assert slot(1, "left")
        results.append("Empty adjacent columns accept moves; outer edges do not wrap")
        press(str(ws + 1))
        wait_for(lambda: clients()[1]["workspace"]["id"] == ws + 1 and not clients()[1]["floating"],
                 "Workspace shortcut did not release window")
        focus(1)
        press(str(ws))
        wait_for(lambda: slot(1, "center"), "Moving back into a managed workspace did not adopt a slot")
        results.append("Super+Shift+Number moves out of and back into managed workspaces")
        focus(1)
        press(str(ws + 1), alt=True)
        wait_for(lambda: clients()[1]["workspace"]["id"] == ws + 1 and not clients()[1]["floating"],
                 "Silent workspace move failed")
        assert h.query("activeworkspace")["id"] == ws
        results.append("Super+Shift+Alt+Number preserves silent workspace movement")
        focus(3)
        subprocess.run(["hyprctl", "reload"], check=True, capture_output=True)
        time.sleep(1.5)
        assert not h.request("/configerrors").strip()
        press("Left")
        wait_for(lambda: slot(3, "center"), "Bindings were not restored after config reload")
        results.append("Hyprland reload keeps movement working with no configuration errors")
        ipc("deactivate")
        wait_for(lambda: not any(c["floating"] for c in clients().values()), "Cleanup failed")
        assert binds() == baseline, "Native bindings were not restored"
        results.append("Disabling OmniTiler restores the original binding definitions")
        ipc("activate")
        wait_for(lambda: clients()[3]["floating"], "Reactivation failed")
        subprocess.run(["omarchy", "plugin", "disable", "fredrick.omnitiler"], check=True, capture_output=True)
        until = time.monotonic() + 8
        while clients()[3]["floating"] and time.monotonic() < until:
            time.sleep(0.1)
        assert not clients()[3]["floating"] and binds() == baseline, "Unload did not restore tiling and shortcuts"
        results.append("Plugin unload restores native shortcuts through the recovery watcher")
        subprocess.run(["omarchy", "plugin", "enable", "fredrick.omnitiler", "--section", "center",
                        "--after", "omarchy.clock"], check=True, capture_output=True)
        time.sleep(0.8)
        (ROOT / "test-results/hotkeys.json").write_text(json.dumps(results, indent=2) + "\n")
        print("\n".join(results))
    finally:
        try:
            ipc("deactivate")
        except Exception:
            subprocess.run(["omarchy", "plugin", "enable", "fredrick.omnitiler", "--section", "center",
                            "--after", "omarchy.clock"], check=True, capture_output=True)
        time.sleep(0.3)
        for p in children:
            if p.poll() is None:
                p.terminate()
                p.wait(timeout=5)
        h.dispatch('hl.dispatch(hl.dsp.focus({workspace=' + str(original_ws) + '}))')
        if original.get("address"):
            h.focus(original)


if __name__ == "__main__":
    main()
