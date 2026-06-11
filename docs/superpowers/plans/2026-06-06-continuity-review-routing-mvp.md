# Continuity Review Routing MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a ComfyDirector-inspired MVP for continuity references, shot review bindings, rerun history, and ComfyUI template routing.

**Architecture:** Keep the current local JSON project store and launcher API. Add project-scoped continuity references, allow storyboard shots to bind references and workflow templates, enrich image prompts from bindings, and persist shot rerun records in the storyboard.

**Tech Stack:** Python 3.11+ standard library, React + TypeScript + Vite, existing `unittest` suite.

---

### Task 1: Project Continuity References

**Files:**
- Modify: `anime_workflow/projects/models.py`
- Modify: `anime_workflow/projects/store.py`
- Modify: `anime_workflow/launcher/server.py`
- Test: `tests/test_project_library.py`
- Test: `tests/test_launcher_server.py`

- [x] Add a `reference_from()` normalizer for `character`, `prop`, `location`, `style`, and `action` continuity references.
- [x] Store references under `data/projects/<project>/references/*.json`.
- [x] Add `GET/POST /api/projects/<project_id>/references`.

### Task 2: Shot Bindings And Rerun Records

**Files:**
- Modify: `anime_workflow/story/storyboard.py`
- Modify: `anime_workflow/story/review.py`
- Modify: `anime_workflow/story/episode_runner.py`
- Test: `tests/test_storyboard_review.py`
- Test: `tests/test_episode_production.py`

- [x] Add default `reference_bindings`, `workflow_template`, and `rerun_history` fields to generated shots.
- [x] Allow review updates to edit those fields.
- [x] Enrich image prompts from bound reference prompt fragments.
- [x] Append a rerun record whenever a single-shot image is regenerated.

### Task 3: Workflow Template Registry

**Files:**
- Create: `anime_workflow/services/workflow_templates.py`
- Modify: `anime_workflow/launcher/server.py`
- Test: `tests/test_launcher_server.py`

- [x] Add built-in templates: `mock_image`, `openai_image`, `comfyui_external_anime`.
- [x] Add `GET /api/workflow-templates`.
- [x] Save selected template into shot rerun history.

### Task 4: Frontend Review Workbench

**Files:**
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/App.tsx`

- [x] Add API types and methods for references and workflow templates.
- [x] Load references/templates when a project is selected.
- [x] Add reference binding, template selection, and rerun history display to the storyboard review tab.

### Task 5: Verification

**Files:**
- No production file edits unless verification exposes a small regression.

- [x] Run Python unit tests.
- [x] Run `npm --prefix frontend run build`.
- [x] Keep the launcher running so the updated UI is available locally.
