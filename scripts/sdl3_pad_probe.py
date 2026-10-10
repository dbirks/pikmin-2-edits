"""SDL3 gamepad mapping probe (no window): register our pad via
SDL_GAMECONTROLLERCONFIG and check whether SDL3 accepts it as a gamepad."""
import ctypes, os
from evdev import UInput, ecodes as e

GC_BUTTONS = [e.BTN_SOUTH, e.BTN_EAST, e.BTN_NORTH, e.BTN_WEST, e.BTN_TL,
              e.BTN_TR, e.BTN_SELECT, e.BTN_START, e.BTN_MODE,
              e.BTN_DPAD_UP, e.BTN_DPAD_DOWN, e.BTN_DPAD_LEFT, e.BTN_DPAD_RIGHT]
ABS = {code: (-32767, 32767, 128, 0) for code in (e.ABS_X, e.ABS_Y, e.ABS_RX, e.ABS_RY)}
ABS.update({e.ABS_Z: (0, 255, 0, 0), e.ABS_RZ: (0, 255, 0, 0)})

MAP = ("pikminlab-virtual-pad,platform:Linux,xinput,"
       "a:b0,b:b1,x:b2,y:b3,back:b6,start:b7,guide:b8,"
       "leftshoulder:b4,rightshoulder:b5,"
       "dpup:b9,dpdown:b10,dpleft:b11,dpright:b12,"
       "leftx:a0,lefty:a1,rightx:a2,righty:a3,"
       "lefttrigger:a4,righttrigger:a5")

ui = UInput({e.EV_KEY: GC_BUTTONS, e.EV_ABS: ABS}, name="pikminlab-virtual-pad")
os.environ["SDL_GAMECONTROLLERCONFIG"] = MAP + "\n"

sdl = ctypes.CDLL("libSDL3.so.0")
if sdl.SDL_Init(0x2000) == 0:  # SDL_INIT_GAMEPAD
    print("SDL_Init FAIL:", sdl.SDL_GetError().decode())
    raise SystemExit(1)
sdl.SDL_GetJoysticks.restype = ctypes.POINTER(ctypes.c_int)
sdl.SDL_GetJoysticks.argtypes = [ctypes.POINTER(ctypes.c_int)]
sdl.SDL_GetGamepadNameForID.restype = ctypes.c_char_p
cnt = ctypes.c_int(0)
ids = sdl.SDL_GetJoysticks(ctypes.byref(cnt))
for i in range(cnt.value):
    jid = ids[i]
    is_gp = bool(sdl.SDL_IsGamepad(jid))
    nm = sdl.SDL_GetGamepadNameForID(jid) if is_gp else None
    print(f"joy id={jid} is_gamepad={is_gp} gamepad_name={nm!r}")
sdl.SDL_Quit()
ui.close()
