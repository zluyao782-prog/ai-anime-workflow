# Document Adaptation And OpenAI Storyboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a local document-adaptation workflow that imports txt/markdown/text-PDF sources, splits them by short-video rhythm, creates project episodes, and generates storyboards with local or OpenAI-compatible text providers.

**Architecture:** Add focused import helpers under `anime_workflow/imports`, providerized storyboard generation under `anime_workflow/story/providers.py`, and launcher endpoints that reuse `ProjectStore` plus existing storyboard persistence. Add a `文档改编` React tab that sends base64 document content to the launcher and shows generated episode results.

**Tech Stack:** Python standard library, `unittest`, JSON storage, `ThreadingHTTPServer`, React, TypeScript, Vite.

---

## File Structure

Create:

- `anime_workflow/imports/__init__.py` - package marker.
- `anime_workflow/imports/document_reader.py` - txt/md/pdf text extraction.
- `anime_workflow/imports/adaptation.py` - text cleaning, short-video splitting, import metadata.
- `anime_workflow/story/providers.py` - local and OpenAI-compatible storyboard providers.
- `tests/test_document_adaptation.py` - unit tests for extraction, splitting, and provider parsing.

Modify:

- `anime_workflow/launcher/config.py` - add text model and endpoint mode config keys.
- `anime_workflow/launcher/server.py` - add import/storyboard endpoints and route project storyboard generation through providers.
- `anime_workflow/jobs/runner.py` - route queued storyboard generation through local provider wrapper while preserving current behavior.
- `frontend/src/api.ts` - add import request/response types and config fields.
- `frontend/src/App.tsx` - add `文档改编` tab and UI workflow.
- `tests/test_launcher_config.py` - cover new public config fields.
- `tests/test_launcher_server.py` - cover import adaptation and openai confirmation.

## Task 1: Document Text Extraction

- [x] Add failing tests in `tests/test_document_adaptation.py`:
  - `extract_document_text("story.txt", b"...")` returns decoded text.
  - `extract_document_text("story.md", b"# title\nbody")` keeps useful text.
  - `extract_document_text("story.pdf", synthetic_pdf_bytes)` extracts literal text.
  - unsupported extension raises `ValueError("unsupported document type")`.
  - empty text raises `ValueError("document text is empty")`.
- [x] Run `.venv/bin/python -m unittest tests.test_document_adaptation.DocumentReaderTest -v` and confirm failures.
- [x] Implement `anime_workflow/imports/document_reader.py` with:
  - UTF-8 first decode for txt/md, fallback to GB18030.
  - best-effort PDF text extraction from literal strings used by text-based PDFs.
  - clear scanned-PDF error when no text is found.
- [x] Re-run the document reader tests and confirm pass.

## Task 2: Short-Video Adaptation

- [x] Add failing tests in `tests/test_document_adaptation.py`:
  - `clean_source_text` removes markdown heading markers and collapses whitespace.
  - `split_short_video_episodes` chunks text using duration budget and max episode count.
  - `build_episode_drafts` creates `episode_001` style ids, titles, premises, duration, shot count, and `source_excerpt`.
  - `build_import_record` returns stable metadata with import id, settings, text length, and episode ids.
- [x] Run `.venv/bin/python -m unittest tests.test_document_adaptation.AdaptationTest -v` and confirm failures.
- [x] Implement `anime_workflow/imports/adaptation.py` with deterministic cleaning and chunking.
- [x] Re-run adaptation tests and confirm pass.

## Task 3: Storyboard Providers

- [x] Add failing tests in `tests/test_document_adaptation.py`:
  - local provider returns the same storyboard shape as current `generate_storyboard`.
  - OpenAI chat-completions provider posts to `{base_url}/v1/chat/completions` and parses JSON from `choices[0].message.content`.
  - OpenAI responses provider posts to `{base_url}/v1/responses` and parses `output_text`.
  - invalid returned JSON raises `ValueError("storyboard API returned invalid JSON")`.
  - invalid storyboard shape raises `ValueError("storyboard API returned invalid storyboard")`.
- [x] Run `.venv/bin/python -m unittest tests.test_document_adaptation.StoryboardProviderTest -v` and confirm failures.
- [x] Implement `anime_workflow/story/providers.py`.
- [x] Re-run provider tests and confirm pass.

## Task 4: Config And Launcher Import API

- [x] Add failing tests:
  - `tests/test_launcher_config.py` verifies `openai_text_model` and `openai_text_endpoint_mode` are public config fields.
  - `tests/test_launcher_server.py` verifies `POST /api/imports/adapt` creates project episodes from text.
  - `tests/test_launcher_server.py` verifies openai storyboard import rejects missing `confirm_openai`.
  - `tests/test_launcher_server.py` verifies openai storyboard import rejects missing API key.
- [x] Run `.venv/bin/python -m unittest tests.test_launcher_config tests.test_launcher_server.LauncherServerTest -v` and confirm failures.
- [x] Extend `LauncherConfigStore.DEFAULT_CONFIG`.
- [x] Add `IMPORTS_DIR = PROJECT_ROOT / "data/imports"` in `server.py`.
- [x] Implement `POST /api/imports/adapt`:
  - decode `content_base64` or use `text`.
  - extract and clean text.
  - save/update project.
  - save episode drafts.
  - write import metadata and cleaned text.
  - generate storyboards with selected provider.
- [x] Add `POST /api/storyboard/generate` for one-episode regeneration.
- [x] Update existing project episode storyboard endpoint to use provider selection.
- [x] Re-run launcher/config tests and confirm pass.

## Task 5: Queue Storyboard Provider Compatibility

- [x] Add or update runner tests proving full mock jobs still complete storyboard/images/video after provider refactor.
- [x] Run `.venv/bin/python -m unittest tests.test_job_queue.JobRunnerTest -v`.
- [x] Update `JobRunner` only if needed to call local provider wrapper.
- [x] Re-run runner tests and confirm pass.

## Task 6: Frontend Import Workbench

- [x] Add `DocumentAdaptRequest`, `DocumentAdaptResponse`, and `adaptDocument` to `frontend/src/api.ts`.
- [x] Add config fields `openai_text_model` and `openai_text_endpoint_mode` to frontend config types and form.
- [x] Add `文档改编` nav item in `frontend/src/App.tsx`.
- [x] Add a compact workbench with:
  - file input for `.txt,.md,.pdf`
  - paste textarea
  - project id/name, genre, platform
  - duration, shot count, max episodes
  - storyboard provider and endpoint mode display
  - result list
- [x] Ensure OpenAI provider calls `window.confirm` and sends `confirm_openai: true`.
- [x] Run `cd frontend && npm run build` and confirm TypeScript passes.

## Task 7: Full Verification

- [x] Run `.venv/bin/python -m unittest discover -s tests -v`.
- [x] Run `cd frontend && npm run build`.
- [x] Restart launcher on `127.0.0.1:7860`.
- [x] Smoke `POST /api/imports/adapt` with a small text and local provider.
- [x] Smoke unconfirmed openai import and confirm `openai storyboard provider requires confirmation`.
- [x] Open the UI and confirm `文档改编` tab renders.
- [x] Commit and push:

```bash
git add anime_workflow tests frontend web docs
git commit -m "Add document adaptation and OpenAI storyboard provider"
git push
```
