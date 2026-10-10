# ADR-0014: Headless video backend measured — OpenGL/llvmpipe under Xvfb works, Vulkan gets no window

**Date:** 2026-10-10
**Status:** accepted

Answers handoff issue #1 §3 ("UNTESTED — determine this first") on the headless
Arch host, after the owner's `pacman -Syu` fixed the broken Dolphin binaries
(ADR-0013 blocker 1).

## Measured, same ISO, same isolated profile, one variable at a time

| `-v` | result | evidence |
| --- | --- | --- |
| `OpenGL` | **PASS** — render window 2 s, lit 640x480 frame by 30 s, `0x80000000 == b"GPVE01"`, zero stray PIDs after SIGKILL | `reports/runs/2026-10-10T050107Z-headless-smoke/result.json` |
| `Vulkan` | **FAIL** — no render window at all within 40 s (this box has no Vulkan ICD; `vulkan-intel` was not installed), clean teardown anyway | `reports/runs/2026-10-10T050219Z-headless-smoke/result.json` |

The exact working invocation (also `scripts/headless_smoke.py`, which emits the
JSON record itself):

```bash
PIKMINLAB_VIDEO_BACKEND=OpenGL \
  xvfb-run -a -s "-screen 0 1280x960x24" \
  uv run python scripts/headless_smoke.py pikmin2.iso
```

`DISPLAY` is exported by `xvfb-run` (got `:99`) and inherited by the child —
that is the plumbing added in ADR-0013; with the old hardcoded `:0` this could
not have worked at all.

## Software rendering, and that is visible in the timings

Dolphin's own stderr under Xvfb:

```
MESA-EGL: warning: DRI3 error: Could not get DRI3 device
MESA-EGL: warning: Ensure your X server supports DRI3 to get accelerated rendering
```

Xvfb has no DRI3/GLAMOR, so Mesa serves llvmpipe (CPU) even though `/dev/dri
/renderD128` exists and is world-writable. Observed wall-clock progression with
no input at all (full series + the Dolphin stderr quote are preserved in
`reports/headless-boot-timings.txt`, along with the Vulkan negative control):

| seconds after exec | frame statistics |
| --- | --- |
| 20–70 | mean 0.066–0.075, 256 colours, max 1.0 — dark screen with bright text (the HEALTH/HARM warning), bright-content bbox `545x294+48+64` |
| 100–160 | mean 0.275–0.285, ~116k colours — full-colour attract/title content |

Consequences for every future headless session: budget **~100 s**, not the
laptop's ~17 s, before the title is comparable, and never assert on a frame
before it is *lit*. Software rendering also means low FPS, so keep sessions
short and batch assertions (handoff §9's ≤60 s guidance becomes ~2–3 min here).

## Numeric scene oracle (this session's model cannot see images)

`PI_MODEL=qwen3-8-flash-next` on this host rejects image input, so the skill's
"screenshot → LOOK → act" loop cannot be executed by eye from the agent. Until
that changes, gates here assert on pixel *statistics* instead of visual reading:

- `lit` = `mean >= 0.02` **and** distinct colours `>= 32` (black/idle framebuffer
  is `mean 0, colors 1`).
- freshness = two captures 6 s apart with different sha256 **and** both `lit`
  (a hash-only check is too weak: a black frame differs from a lit one, which is
  how the first 45-second settle produced a bogus "PASS" — recorded here as a
  failed experiment, not erased).
- scene change = `magick compare -metric RMSE` after `-resize 320x240!`, with
  the skill's ~1–2 % UI-pulse noise floor as the "nothing happened" band.

`scripts/headless_smoke.py` implements all three and is the reusable headless
gate probe. Screenshots stay on disk for the owner to eyeball, and any future
vision-capable reviewer should re-check at least one image per gate rather than
trusting the numbers alone.

## Gate effect — honest version

- **G0 headless boot: 1/1 cold boot observed** (window + lit frame + disc-ID
  read + clean teardown). The handoff's §3 validation is answered. This is *not*
  10/10 and repeats were waived (ADR-0006); one boot is what was run.
- **G1 state reads: re-proven on this host** — DME hooking works from the parent
  Python process under `ptrace_scope=1`.
- **G1 input: still NOT proven on this host.** `/dev/uinput` is `0600 root:root`
  and the new `99-uinput.rules` has not been applied to the live device node
  (needs `udevadm control --reload` + trigger, or a reboot). The smoke test
  deliberately ran `pad=False`; `pikminlab serve` still hard-requires the pad, so
  the daemon path is unusable until that lands.

## Next measurement owed

Install `vulkan-intel` (owner) and retry `-v Vulkan` under Xvfb: ANV might reach
the iGPU through the render node where llvmpipe cannot, which would buy real
frame rates for G3 loops. If it still fails, record it and stay on OpenGL — do
not chase GPU acceleration inside a software X server.
