"""Virtual GameCube pad via uinput/evdev (master spec Candidate B).

Creates a gamepad-class evdev device that SDL (and therefore Dolphin)
enumerates as a physical controller, giving deterministic, focus-free,
traceable input with no synthetic-event popups. Requires write access to
/dev/uinput; on this host the owner is in the `input` group, so it works
unprivileged.
"""
from __future__ import annotations
import time
from evdev import UInput, ecodes as e

# Standard linux gamepad mapping (SDL reads these as a controller).
GC_BUTTONS = [
    e.BTN_SOUTH,   # A
    e.BTN_EAST,    # B
    e.BTN_NORTH,   # X
    e.BTN_WEST,    # Y
    e.BTN_TL,      # L (digital)
    e.BTN_TR,      # R (digital)
    e.BTN_SELECT,  # Select
    e.BTN_START,   # Start
    e.BTN_MODE,    # Z (unused default, repurposed)
    e.BTN_DPAD_UP, e.BTN_DPAD_DOWN, e.BTN_DPAD_LEFT, e.BTN_DPAD_RIGHT,
]
GC_AXES = {
    e.ABS_X:  (-32767, 32767, 128, 0),   # main stick x
    e.ABS_Y:  (-32767, 32767, 128, 0),   # main stick y
    e.ABS_RX: (-32767, 32767, 128, 0),   # c-stick x
    e.ABS_RY: (-32767, 32767, 128, 0),   # c-stick y
    e.ABS_Z:  (0, 255, 0, 0),            # analog L
    e.ABS_RZ: (0, 255, 0, 0),            # analog R
}
NAME = "pikminlab-virtual-pad"


class VirtualPad:
    """Holds a uinput gamepad. Press/release/hold are level-based so the
    state is always re-issuable (idempotent) per the spec's input rules."""

    def __init__(self, name: str = NAME):
        caps = {e.EV_KEY: GC_BUTTONS, e.EV_ABS: {k: v for k, v in GC_AXES.items()}}
        self.ui = UInput(caps, name=name)
        self.name = name

    # -- level control -------------------------------------------------
    def button(self, btn: int, down: bool) -> None:
        self.ui.write(e.EV_KEY, btn, 1 if down else 0)
        self.ui.syn()

    def tap(self, btn: int, frames: float = 0.05) -> None:
        self.button(btn, True); time.sleep(frames); self.button(btn, False)

    def stick(self, xaxis: int, yaxis: int, x: int, y: int) -> None:
        self.ui.write(e.EV_ABS, xaxis, x)
        self.ui.write(e.EV_ABS, yaxis, y)
        self.ui.syn()

    def neutral(self) -> None:
        for b in GC_BUTTONS:
            self.ui.write(e.EV_KEY, b, 0)
        self.stick(e.ABS_X, e.ABS_Y, 0, 0)
        self.stick(e.ABS_RX, e.ABS_RY, 0, 0)
        self.ui.write(e.EV_ABS, e.ABS_Z, 0); self.ui.write(e.EV_ABS, e.ABS_RZ, 0)
        self.ui.syn()

    def close(self) -> None:
        self.neutral(); self.ui.close()

    def __enter__(self): return self
    def __exit__(self, *exc): self.close()
