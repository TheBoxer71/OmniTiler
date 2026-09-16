"""Safe, content-free terminal window used by the opt-in desktop smoke test."""
import os
import signal
import sys
import time

n = int(sys.argv[1])
slot = (n - 1) % 3
title = ["CENTER STAGE", "ROOM FOR CONTEXT", "TOOLS WITHIN REACH"][slot]
percent = ["40%", "30%", "30%"][slot]
description = ["Your main app, exactly where you need it.",
               "References and conversations, side by side.",
               "Keep the essentials close."][slot]


def draw(*_):
    size = os.get_terminal_size()
    lines = ["O M N I T I L E R", "", "────────────────────────────", "", title,
             "", percent, "", description, "", "────────────────────────────", "",
             "30 LEFT   ·   40 CENTER   ·   30 RIGHT", "", "Made for ultrawide. Built for Omarchy."]
    sys.stdout.write("\x1b[?25l\x1b[2J\x1b[H" + "\n" * max(0, (size.lines - len(lines)) // 2))
    for i, line in enumerate(lines):
        text = line.center(size.columns - 1)
        sys.stdout.write(("\x1b[1;36m" if i in (0, 4, 6) else "\x1b[0m") + text + "\n")
    sys.stdout.flush()


signal.signal(signal.SIGWINCH, draw)
draw()
while True:
    time.sleep(30)
