#!/usr/bin/env python3
"""Local developer installation. Marketplace installs use `omarchy plugin add`."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ID = "fredrick.omnitiler"
SOURCE = Path(__file__).resolve().parent
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "omarchy"
TARGET = CONFIG / "plugins" / ID


def run(*args, check=True):
    return subprocess.run(args, check=check, text=True, capture_output=True, timeout=20)


def stop():
    result = run("omarchy-shell", "omnitiler", "deactivate", check=False)
    if result.returncode:
        return
    for _ in range(40):
        status = run("omarchy-shell", "omnitiler", "status", check=False)
        try:
            state = json.loads(status.stdout)
            if not state["active"]:
                if state.get("error"):
                    raise RuntimeError(state["error"])
                return
        except json.JSONDecodeError:
            pass
        time.sleep(0.1)
    raise RuntimeError("OmniTiler did not stop; refusing to remove its recovery code")


def backup():
    config = CONFIG / "shell.json"
    if config.exists():
        directory = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "omnitiler/backups"
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / ("shell-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".json")
        shutil.copy2(config, target)
        print("Shell configuration backup:", target)


def owned_target():
    if TARGET.is_symlink():
        raise RuntimeError("Refusing to replace a symlink installation")
    if TARGET.exists() and json.loads((TARGET / "manifest.json").read_text())["id"] != ID:
        raise RuntimeError("Installation path belongs to another plugin")


def install():
    if SOURCE == TARGET:
        raise RuntimeError("Run the installer from the source repository")
    run("omarchy", "plugin", "validate", str(SOURCE))
    owned_target()
    backup()
    if TARGET.exists():
        stop()
        run("omarchy", "plugin", "disable", ID)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="omnitiler-install-", dir=CONFIG) as directory:
        staged = Path(directory) / ID
        shutil.copytree(SOURCE, staged, ignore=shutil.ignore_patterns(
            ".git", "__pycache__", "*.pyc", "test-results", ".pytest_cache"))
        run("omarchy", "plugin", "validate", str(staged))
        if TARGET.exists():
            TARGET.rename(Path(directory) / "previous")
        staged.rename(TARGET)
    run("omarchy-shell", "shell", "rescanPlugins")
    # CLI performs a targeted, persisted layout change; clock anchor is untouched.
    config = json.loads((CONFIG / "shell.json").read_text())
    center = config.get("bar", {}).get("layout", {}).get("center", [])
    args = ["omarchy", "plugin", "enable", ID, "--section", "center"]
    if any(e.get("id") == "omarchy.clock" for e in center):
        args += ["--after", "omarchy.clock"]
    run(*args)
    print("Installed OmniTiler beside the clock. Tiling starts off.")


def remove():
    owned_target()
    if not TARGET.exists():
        print("OmniTiler is not installed")
        return
    backup()
    stop()
    run("omarchy", "plugin", "disable", ID)
    shutil.rmtree(TARGET)
    run("omarchy-shell", "shell", "rescanPlugins")
    print("Removed OmniTiler. Other plugins and settings were preserved.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "remove"])
    args = parser.parse_args()
    {"install": install, "remove": remove}[args.action]()
