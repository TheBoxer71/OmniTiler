"""Disposable uinput keyboard for opt-in desktop checks; needs existing user access.

Uses Linux uinput's public ABI. No permissions, services, or physical devices
are modified. Every modifier is released before the virtual device is removed.
"""
import fcntl
import os
import struct
import time


def press(key, shift=True, alt=False):
    codes = {"Left": 105, "Right": 106, **{str(n): n + 1 for n in range(1, 10)}}
    held = [125] + ([42] if shift else []) + ([56] if alt else []) + [codes[key]]
    fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
    created = False

    def event(code, value):
        os.write(fd, struct.pack("llHHi", 0, 0, 1, code, value))
        os.write(fd, struct.pack("llHHi", 0, 0, 0, 0, 0))
        time.sleep(0.03)

    try:
        fcntl.ioctl(fd, 0x40045564, 1)  # UI_SET_EVBIT(EV_KEY)
        for code in set(held):
            fcntl.ioctl(fd, 0x40045565, code)  # UI_SET_KEYBIT
        setup = struct.pack("HHHH80sI", 3, 1, 1, 1, b"OmniTiler test keyboard", 0)
        fcntl.ioctl(fd, 0x405c5503, setup)  # UI_DEV_SETUP
        fcntl.ioctl(fd, 0x5501)  # UI_DEV_CREATE
        created = True
        time.sleep(0.4)
        for code in held:
            event(code, 1)
    finally:
        if created:
            for code in reversed(held):
                event(code, 0)
            fcntl.ioctl(fd, 0x5502)  # UI_DEV_DESTROY
        os.close(fd)
