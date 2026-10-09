# Pikmin 2 AI Lab — Start Here

**Updated:** 2026-10-09 | **Project scope:** local Arch Linux + Dolphin. No physical GameCube hardware required.

This packet contains:

- `Pikmin2_AI_Lab_Master_Spec.md` — authoritative product/technical requirements, A/B driver benchmarks, asset pipeline, CLI design, test oracles and acceptance gates.
- `AGENTS.md` — copy into the root of your coding agent's project; step-by-step implementation instructions and safety policy.
- `Pikmin2_AI_Lab_AGENT_WORK_ORDERS.md` — identical to `AGENTS.md`, for convenience.
- `Pikmin2_AI_Lab_Physical_Hardware_Options.md` — **entirely separate**, optional console-mod / network / USB / ODE research paths. Not part of the software mission.

## Minimum owner input for local agent

You have already provided the distro (Arch Linux), autonomy model (trusted-setup) and the fact that an ISO exists. The only missing input needed to begin is the **absolute filesystem path to that ISO** and approval when system package installation or privilege changes are proposed.

## Suggested starter prompt to your coding agent

> Read `AGENTS.md` and `Pikmin2_AI_Lab_Master_Spec.md`. You are on my Arch Linux laptop. My Pikmin 2 ISO is at `/ABSOLUTE/PATH/TO/PIKMIN2.ISO`. Begin at P0: inspect the environment without changing system settings, verify my game image, create a protected workspace and isolated Dolphin profile, then prove a baseline boot and the first controller+state+screenshot automation. Continue through the acceptance gates while working independently within the trusted-setup permission rules. Do not touch my normal Dolphin saves, modify the original ISO, or do hardware/GameCube work. Treat documented capabilities as hypotheses until locally tested. Report exact commands, hashes, evidence and blockers.

## What the documents do and do not mean

They are **instructions and a researched architecture**, not a claim that code has been built, the game modified, or Dolphin controlled on your laptop. The agent must empirically prove each gate before considering the overall loop finished. Do not distribute copyrighted disc data; generated game images stay private unless you separately authorize a legally appropriate sharing format.
