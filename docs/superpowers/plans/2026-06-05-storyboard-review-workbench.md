# Storyboard Review Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a storyboard review workbench for loading, editing, saving, and locally rewriting storyboard shots before image generation.

**Architecture:** Add focused storyboard review helpers under `anime_workflow/story/review.py`, expose save/update/rewrite endpoints from the launcher server, then add a dense React tab that edits the current storyboard JSON through those APIs.

**Tech Stack:** Python standard library, `unittest`, JSON storyboard files, React, TypeScript, Vite.

---

## File Structure

Create:

- `anime_workflow/story/review.py` - storyboard validation, shot update, local shot rewrite.
- `tests/test_storyboard_review.py` - unit tests for review helpers.

Modify:

- `anime_workflow/launcher/server.py` - add save/update/rewrite storyboard endpoints.
- `tests/test_launcher_server.py` - cover new endpoints.
- `frontend/src/api.ts` - add storyboard review API helpers.
- `frontend/src/App.tsx` - add `分镜审稿` tab and editor UI.

## Task 1: Storyboard Review Helpers

- [x] Add tests in `tests/test_storyboard_review.py` for:
  - `validate_storyboard_for_review` accepts a valid storyboard.
  - invalid storyboard raises `ValueError("storyboard API returned invalid storyboard")`.
  - `update_storyboard_shot` changes allowed fields only.
  - missing shot raises `FileNotFoundError("shot not found")`.
  - `rewrite_storyboard_shot_local` preserves `shot_id` and updates scene/dialogue/image_prompt with instruction.
- [x] Run `.venv/bin/python -m unittest tests.test_storyboard_review -v` and confirm failures.
- [x] Implement `anime_workflow/story/review.py`.
- [x] Re-run the review helper tests and confirm pass.

## Task 2: Launcher Storyboard Review APIs

- [x] Add tests in `tests/test_launcher_server.py` for:
  - `POST /api/storyboard/save` writes the storyboard and updates episode status.
  - `POST /api/storyboard/shot/update` updates one shot.
  - `POST /api/storyboard/shot/rewrite` local provider rewrites one shot.
  - rewrite missing shot returns 404.
  - unconfirmed openai shot rewrite returns 400.
- [x] Run `.venv/bin/python -m unittest tests.test_launcher_server.LauncherServerTest -v` and confirm failures.
- [x] Add endpoint handlers to `anime_workflow/launcher/server.py`.
- [x] Re-run launcher server tests and confirm pass.

## Task 3: Frontend API And Review Tab

- [x] Add `saveStoryboard`, `updateStoryboardShot`, and `rewriteStoryboardShot` to `frontend/src/api.ts`.
- [x] Add `分镜审稿` nav item in `frontend/src/App.tsx`.
- [x] Add state for selected project, selected episode, loaded storyboard, selected shot id, rewrite instruction, and review log.
- [x] Add UI:
  - project selector
  - episode selector
  - load storyboard button
  - episode field editors
  - shot field editors
  - save button
  - local shot rewrite button
- [x] Run `cd frontend && npm run build` and confirm pass.

## Task 4: Full Verification

- [x] Run `.venv/bin/python -m unittest discover -s tests -v`.
- [x] Run `cd frontend && npm run build`.
- [x] Restart launcher on `127.0.0.1:7860`.
- [x] Smoke load root page and confirm `分镜审稿` tab appears.
- [x] Smoke `POST /api/storyboard/shot/rewrite` against an existing storyboard.
- [x] Commit and push.
