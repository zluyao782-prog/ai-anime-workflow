# Shot-Level Regeneration And UI Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-phase optimization that supports shot-level image regeneration while preparing the frontend for future component splits.

**Architecture:** Keep JSON storage and the existing launcher API. Add a focused episode-runner helper for one-shot image generation, expose it through a launcher endpoint, and wire it into the storyboard review UI so users can revise a single shot without rerunning the whole episode.

**Tech Stack:** Python 3.11+ standard library, React + TypeScript + Vite, existing `unittest` test suite.

---

### Task 1: Shot-Level Image Generation Backend

**Files:**
- Modify: `anime_workflow/story/episode_runner.py`
- Modify: `anime_workflow/launcher/server.py`
- Test: `tests/test_episode_production.py`
- Test: `tests/test_launcher_server.py`

- [x] Add a `generate_shot_image()` helper that updates only one shot in a storyboard and preserves all other shots.
- [x] Add `/api/storyboard/shot/image` POST endpoint accepting `project_id`, `episode_id`, `shot_id`, `provider`, and `confirm_openai`.
- [x] Ensure OpenAI still requires confirmation and configured API key.
- [x] Add focused tests for the helper and endpoint behavior.

### Task 2: Frontend API And Review Workbench Wiring

**Files:**
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/App.tsx`

- [x] Add a TypeScript API method for the new endpoint.
- [x] Add a shot-level regenerate button in the storyboard review tab.
- [x] Update review state with the returned storyboard so the UI reflects only the regenerated shot.
- [x] Keep existing review/save/rewrite flows intact.

### Task 3: First Frontend Split

**Files:**
- Create: `frontend/src/navigation.ts`
- Modify: `frontend/src/App.tsx`

- [x] Move tab navigation metadata out of `App.tsx`.
- [x] Keep labels, icons, and tab values unchanged.
- [x] Preserve TypeScript inference for `TabValue`.

### Task 4: Verification

**Files:**
- No production file edits unless verification exposes a small regression.

- [x] Run focused Python tests for episode production and storyboard review/server endpoint coverage.
- [x] Install frontend dependencies if missing, then run `npm --prefix frontend run build`.
- [x] Report known baseline failures separately from new verification results.
