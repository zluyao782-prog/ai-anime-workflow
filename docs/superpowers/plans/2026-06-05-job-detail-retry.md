# Job Detail And Retry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-episode, per-step job detail and targeted retry for the existing local JSON job queue.

**Architecture:** Extend the existing `anime_workflow.jobs` JSON model with derived `items`, update the runner to mark each episode-step item, add launcher retry endpoints, then render a compact React detail panel under the current queue. Retry creates new jobs and keeps the original job as history.

**Tech Stack:** Python standard library, `unittest`, local JSON files, `ThreadingHTTPServer`, React, TypeScript, Vite.

---

## File Structure

Modify:

- `anime_workflow/jobs/models.py` - add item defaults, step dependency expansion, item normalization.
- `anime_workflow/jobs/store.py` - add item update helpers and retry-job creation helpers.
- `anime_workflow/jobs/runner.py` - mark item running/completed/failed/cancelled while executing.
- `anime_workflow/launcher/server.py` - add job detail and targeted retry endpoints.
- `tests/test_job_queue.py` - cover item creation, runner item updates, and retry job scoping.
- `tests/test_launcher_server.py` - cover job detail and retry endpoints.
- `frontend/src/api.ts` - add `JobItem` and retry API helpers.
- `frontend/src/App.tsx` - add job detail state, detail button, detail panel, and retry actions.

Keep:

- Existing `/api/jobs`, `/api/jobs/{job_id}/cancel`, `/api/jobs/{job_id}/retry`.
- Existing openai safety rule: real API actions must pass `confirm_openai: true`.
- Existing JSON storage, no database.

## Tasks

### Task 1: Job Items In Store And Model

- [x] Add tests in `tests/test_job_queue.py` proving `create_job` adds `items` for every episode-step pair and legacy job JSON without `items` is normalized on read.
- [x] Run `.venv/bin/python -m unittest tests.test_job_queue.JobQueueStoreTest -v` and confirm the new tests fail because `items` does not exist.
- [x] Add item constants and helpers in `anime_workflow/jobs/models.py`: `VALID_ITEM_STATUSES`, `step_sequence_from`, `default_job_items`, `normalize_items`, and include `items` in `job_from`.
- [x] Update `anime_workflow/jobs/store.py` so `get_job` and `list_jobs` return normalized jobs with `items`.
- [x] Re-run `tests.test_job_queue.JobQueueStoreTest` and confirm it passes.

### Task 2: Runner Item Status Updates

- [x] Add tests in `tests/test_job_queue.py` proving successful full mock jobs mark all items completed with output paths and failures mark the active item failed with an error.
- [x] Run the specific runner tests and confirm failure.
- [x] Add `set_item_running`, `set_item_completed`, `set_item_failed`, and `cancel_pending_items` helpers in `JobStore`.
- [x] Update `JobRunner._run_job` and `_run_step` so each step returns its output path and item state is written before/after execution.
- [x] Re-run runner tests and confirm they pass.

### Task 3: Backend Detail And Retry APIs

- [x] Add tests in `tests/test_launcher_server.py` for `GET /api/jobs/{job_id}`, `POST /api/jobs/{job_id}/retry-failed`, episode retry, step retry, and unconfirmed openai rejection.
- [x] Run `tests.test_launcher_server.LauncherServerTest -v` and confirm the new tests fail.
- [x] Add retry helpers in `JobStore`: `failed_retry_payload`, `episode_retry_payload`, `episode_step_retry_payload`, and `create_retry_job`.
- [x] Add path parsing and handlers in `anime_workflow/launcher/server.py`.
- [x] Re-run launcher server tests and confirm they pass.

### Task 4: Frontend Detail Panel

- [x] Add `JobItem` and API helpers to `frontend/src/api.ts`.
- [x] Add `selectedJobId`, `selectedJobDetail`, `loadJobDetail`, retry action handlers, and selected-job polling in `frontend/src/App.tsx`.
- [x] Add `详情` button to `JobRow`.
- [x] Add `JobDetailPanel` with a compact episode-step table and retry buttons.
- [x] Run `cd frontend && npm run build` and confirm TypeScript passes.

### Task 5: Full Verification

- [x] Run `.venv/bin/python -m unittest discover -s tests -v`.
- [x] Run `cd frontend && npm run build`.
- [x] Restart launcher on `127.0.0.1:7860`.
- [x] Smoke `GET /api/jobs/{existing_job_id}`.
- [x] Smoke unconfirmed openai retry request and confirm it returns `openai provider requires confirmation`.
- [x] Confirm the browser UI can open the `剧集生产` tab and show job detail.
