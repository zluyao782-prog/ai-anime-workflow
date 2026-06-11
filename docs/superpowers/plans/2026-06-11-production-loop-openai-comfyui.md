# OpenAI ComfyUI Production Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a cost-aware real production loop that routes storyboard shots through ComfyUI and OpenAI image generation, records reproducible metadata, and exports a usable episode video.

**Architecture:** Keep the existing local JSON store and launcher API. Treat ComfyUI as the preferred production route and OpenAI as the default real image provider behind that route, with mock remaining as the safe test fallback. Add readiness checks, richer workflow templates, explicit OpenAI confirmation for direct and indirect usage, workflow-template-aware jobs, better export failure handling, and a guarded smoke script for end-to-end verification.

**Tech Stack:** Python 3.11+ standard library, React + TypeScript + Vite, ComfyUI HTTP API, OpenAI-compatible image endpoint, FFmpeg, existing `unittest` suite.

---

## Scope

This plan focuses on a real creator workflow:

1. Configure OpenAI-compatible image API and local or remote ComfyUI.
2. Create or select a project and episode.
3. Generate a storyboard.
4. Bind continuity references during review.
5. Generate single-shot or whole-episode images through `comfyui_external_anime`.
6. Preserve prompt, provider, workflow template, references, cache, and output metadata.
7. Export an episode video from generated frames.
8. Verify the chain with a guarded smoke script.

This plan does not tune image quality prompts deeply, add full AI video generation, automate platform publishing, or replace the JSON storage model.

## File Structure

- `anime_workflow/services/production_readiness.py`: new readiness checks for OpenAI, ComfyUI, FFmpeg, output paths, and workflow templates.
- `anime_workflow/services/workflow_templates.py`: enrich built-in templates with route, cost, and confirmation metadata.
- `anime_workflow/services/anime_api_adapter.py`: add workflow and cost metadata to image generation records.
- `anime_workflow/story/episode_runner.py`: pass workflow template and reference bindings into metadata/rerun history for shot and episode generation.
- `anime_workflow/jobs/models.py`: store `workflow_template` on production jobs.
- `anime_workflow/jobs/runner.py`: route ComfyUI jobs through the job's selected workflow template.
- `anime_workflow/launcher/server.py`: add readiness endpoint, cost-safe provider routing, and workflow-template-aware job/image handlers.
- `frontend/src/api.ts`: add readiness and job workflow template types.
- `frontend/src/App.tsx`: expose production readiness, workflow selection, real-provider confirmations, and clearer export results.
- `scripts/smoke_production_loop.py`: guarded local smoke script for one project, one episode, and two or three shots.
- `tests/test_production_readiness.py`: new backend readiness tests.
- Existing tests to extend: `tests/test_anime_api_adapter.py`, `tests/test_episode_production.py`, `tests/test_job_queue.py`, `tests/test_launcher_server.py`, `tests/test_launcher_services.py`.

---

### Task 1: Production Readiness Backend

**Files:**
- Create: `anime_workflow/services/production_readiness.py`
- Modify: `anime_workflow/launcher/server.py`
- Test: `tests/test_production_readiness.py`
- Test: `tests/test_launcher_server.py`

- [ ] **Step 1: Write failing readiness unit tests**

Create `tests/test_production_readiness.py`:

```python
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from anime_workflow.services.production_readiness import production_readiness


class ProductionReadinessTest(unittest.TestCase):
    def test_reports_openai_comfyui_ffmpeg_and_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "exports"
            config = {
                "openai_api_key": "sk-test",
                "openai_base_url": "https://example.test",
                "openai_image_model": "gpt-image-2",
                "comfyui_mode": "remote",
                "comfyui_remote_base_url": "http://10.0.0.2:8188",
                "output_dir": str(output_dir),
            }

            with patch("anime_workflow.services.production_readiness.check_http_json") as check, patch(
                "anime_workflow.services.production_readiness.shutil.which", return_value="ffmpeg"
            ):
                check.return_value = {"ok": True, "detail": "{\"system\":\"ok\"}"}
                readiness = production_readiness(config, Path(tmp))

            self.assertTrue(readiness["ok"])
            self.assertTrue(readiness["checks"]["openai"]["ok"])
            self.assertEqual(readiness["checks"]["openai"]["model"], "gpt-image-2")
            self.assertTrue(readiness["checks"]["comfyui"]["ok"])
            self.assertEqual(readiness["checks"]["comfyui"]["base_url"], "http://10.0.0.2:8188")
            self.assertTrue(readiness["checks"]["ffmpeg"]["ok"])
            self.assertEqual(readiness["checks"]["output_dir"]["path"], str(output_dir))

    def test_missing_openai_key_marks_real_route_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "openai_api_key": "",
                "openai_base_url": "https://example.test",
                "openai_image_model": "gpt-image-2",
                "comfyui_mode": "remote",
                "comfyui_remote_base_url": "http://10.0.0.2:8188",
                "output_dir": "data/exports",
            }

            with patch("anime_workflow.services.production_readiness.check_http_json") as check, patch(
                "anime_workflow.services.production_readiness.shutil.which", return_value=None
            ):
                check.return_value = {"ok": False, "detail": "connection refused"}
                readiness = production_readiness(config, Path(tmp))

            self.assertFalse(readiness["ok"])
            self.assertFalse(readiness["checks"]["openai"]["ok"])
            self.assertEqual(readiness["checks"]["openai"]["detail"], "OpenAI API Key is not configured")
            self.assertFalse(readiness["checks"]["comfyui"]["ok"])
            self.assertFalse(readiness["checks"]["ffmpeg"]["ok"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run readiness tests and verify failure**

Run:

```bash
python -m unittest tests.test_production_readiness -v
```

Expected: fail with `ModuleNotFoundError` for `anime_workflow.services.production_readiness`.

- [ ] **Step 3: Implement readiness service**

Create `anime_workflow/services/production_readiness.py`:

```python
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from anime_workflow.launcher.config import effective_comfyui_base_url
from anime_workflow.launcher.services import check_http_json
from anime_workflow.services.workflow_templates import list_workflow_templates


def configured_output_dir(config: dict[str, Any], project_root: Path) -> Path:
    path = Path(str(config.get("output_dir") or "data/exports"))
    if path.is_absolute():
        return path
    return Path(project_root) / path


def production_readiness(config: dict[str, Any], project_root: Path) -> dict[str, Any]:
    output_dir = configured_output_dir(config, project_root)
    comfyui_base_url = effective_comfyui_base_url(config)
    comfyui = check_http_json(f"{comfyui_base_url.rstrip('/')}/system_stats")
    ffmpeg_path = shutil.which("ffmpeg") or ""
    api_key = str(config.get("openai_api_key") or "")
    openai_ok = bool(api_key)

    checks = {
        "openai": {
            "ok": openai_ok,
            "base_url": str(config.get("openai_base_url") or ""),
            "model": str(config.get("openai_image_model") or "gpt-image-2"),
            "detail": "configured" if openai_ok else "OpenAI API Key is not configured",
        },
        "comfyui": {
            "ok": bool(comfyui["ok"]),
            "mode": str(config.get("comfyui_mode") or "local"),
            "base_url": comfyui_base_url,
            "detail": str(comfyui["detail"]),
        },
        "ffmpeg": {
            "ok": bool(ffmpeg_path),
            "path": ffmpeg_path,
            "detail": "configured" if ffmpeg_path else "ffmpeg is not available on PATH",
        },
        "output_dir": {
            "ok": True,
            "path": str(output_dir),
            "detail": "directory will be created during export",
        },
        "workflow_templates": {
            "ok": any(template["template_id"] == "comfyui_external_anime" for template in list_workflow_templates()),
            "templates": list_workflow_templates(),
        },
    }
    return {"ok": all(item["ok"] for item in checks.values()), "checks": checks, "project_root": str(Path(project_root))}
```

- [ ] **Step 4: Add launcher endpoint test**

Append to `tests/test_launcher_server.py`:

```python
    def test_production_readiness_api_reports_checks(self):
        self.handler.config_store.save(
            {
                "openai_api_key": "sk-test",
                "openai_base_url": "https://example.test",
                "openai_image_model": "gpt-image-2",
                "comfyui_mode": "remote",
                "comfyui_remote_base_url": "http://10.0.0.2:8188",
            }
        )
        with patch("anime_workflow.launcher.server.production_readiness") as readiness:
            readiness.return_value = {"ok": True, "checks": {"openai": {"ok": True}}}
            response = self.get_json("/api/production/readiness")

        self.assertTrue(response["ok"])
        self.assertTrue(response["readiness"]["ok"])
```

- [ ] **Step 5: Wire `GET /api/production/readiness`**

In `anime_workflow/launcher/server.py`, import the service:

```python
from anime_workflow.services.production_readiness import production_readiness
```

In `do_GET`, before `/api/workflow-templates`:

```python
        if parsed.path == "/api/production/readiness":
            self._json({"ok": True, "readiness": production_readiness(self.config_store.load(), PROJECT_ROOT)})
            return
```

- [ ] **Step 6: Run tests**

Run:

```bash
python -m unittest tests.test_production_readiness tests.test_launcher_server.LauncherServerTest.test_production_readiness_api_reports_checks -v
```

Expected: pass.

---

### Task 2: Enrich Workflow Template Registry

**Files:**
- Modify: `anime_workflow/services/workflow_templates.py`
- Modify: `frontend/src/api.ts`
- Test: `tests/test_launcher_server.py`

- [ ] **Step 1: Add failing template shape test**

Append to `tests/test_launcher_server.py`:

```python
    def test_workflow_templates_include_cost_and_route_metadata(self):
        response = self.get_json("/api/workflow-templates")
        templates = {template["template_id"]: template for template in response["templates"]}

        comfyui = templates["comfyui_external_anime"]
        self.assertEqual(comfyui["provider"], "comfyui")
        self.assertEqual(comfyui["external_provider"], "openai")
        self.assertTrue(comfyui["consumes_api"])
        self.assertTrue(comfyui["requires_openai_confirmation"])
        self.assertEqual(comfyui["route"], "comfyui_openai_image")
        self.assertIn("ComfyUI", comfyui["route_summary"])
```

- [ ] **Step 2: Run template test and verify failure**

Run:

```bash
python -m unittest tests.test_launcher_server.LauncherServerTest.test_workflow_templates_include_cost_and_route_metadata -v
```

Expected: fail because metadata fields are missing.

- [ ] **Step 3: Extend built-in templates**

In `anime_workflow/services/workflow_templates.py`, update each template to include explicit metadata:

```python
{
    "template_id": "mock_image",
    "name": "Mock Image",
    "provider": "mock",
    "external_provider": "mock",
    "route": "local_mock_image",
    "route_summary": "Local mock copy route for fast validation without API cost.",
    "consumes_api": False,
    "requires_openai_confirmation": False,
    "description": "Use the local mock provider for fast review without API cost.",
},
{
    "template_id": "openai_image",
    "name": "OpenAI Image",
    "provider": "openai",
    "external_provider": "openai",
    "route": "direct_openai_image",
    "route_summary": "Direct OpenAI-compatible image edit route.",
    "consumes_api": True,
    "requires_openai_confirmation": True,
    "description": "Route the shot through the configured OpenAI-compatible image endpoint.",
},
{
    "template_id": "comfyui_external_anime",
    "name": "ComfyUI External Anime",
    "provider": "comfyui",
    "external_provider": "openai",
    "route": "comfyui_openai_image",
    "route_summary": "ComfyUI ExternalAnimeStylize node calls the configured OpenAI-compatible image endpoint.",
    "consumes_api": True,
    "requires_openai_confirmation": True,
    "description": "Route the shot through the configured local or remote ComfyUI ExternalAnimeStylize workflow.",
    "comfyui": {
        "node_id": "1",
        "class_type": "ExternalAnimeStylize",
        "return_image_base64": True,
        "inputs": {
            "source_image_path": "",
            "source_image_base64": "{{source_image_base64}}",
            "reference_image_base64": "{{reference_image_base64}}",
            "output_path": "{{remote_output_path}}",
            "style_preset": "{{style_preset}}",
            "prompt": "{{prompt}}",
            "api_endpoint": "{{api_endpoint}}",
            "api_key": "{{api_key}}",
            "provider_name": "{{provider_name}}",
            "model_version": "{{model_version}}",
            "return_image_base64": "{{return_image_base64}}",
        },
    },
}
```

- [ ] **Step 4: Update TypeScript template type**

In `frontend/src/api.ts`, replace `WorkflowTemplate` with:

```typescript
export type WorkflowRoute = "local_mock_image" | "direct_openai_image" | "comfyui_openai_image";

export type WorkflowTemplate = {
  template_id: string;
  name: string;
  provider: JobProvider;
  external_provider: "mock" | "openai";
  route: WorkflowRoute;
  route_summary: string;
  consumes_api: boolean;
  requires_openai_confirmation: boolean;
  description: string;
};
```

- [ ] **Step 5: Run template and frontend type checks**

Run:

```bash
python -m unittest tests.test_launcher_server.LauncherServerTest.test_workflow_templates_include_cost_and_route_metadata -v
npm --prefix frontend run build
```

Expected: both pass.

---

### Task 3: Cost-Safe Provider Routing

**Files:**
- Modify: `anime_workflow/launcher/server.py`
- Modify: `anime_workflow/jobs/runner.py`
- Test: `tests/test_launcher_server.py`
- Test: `tests/test_job_queue.py`

- [ ] **Step 1: Add failing launcher tests for indirect OpenAI confirmation**

Append to `tests/test_launcher_server.py`:

```python
    def test_comfyui_route_with_openai_key_requires_confirmation(self):
        self.handler.config_store.save({"openai_api_key": "sk-test"})
        project = self.project_store.save_project({"project_id": "demo", "name": "Demo"})
        episode = self.project_store.save_episode(project["project_id"], {"episode_id": "episode_001", "title": "E1"})
        storyboard = generate_storyboard(
            {
                "project_id": project["project_id"],
                "episode_id": episode["episode_id"],
                "premise": "rain alley clue",
                "shot_count": 1,
                "duration_seconds": 3,
            }
        )
        save_storyboard(storyboard, self.storyboard_dir)

        response = self.post_json(
            "/api/storyboard/shot/image",
            {
                "project_id": "demo",
                "episode_id": "episode_001",
                "shot_id": "shot_001",
                "provider": "comfyui",
                "workflow_template": "comfyui_external_anime",
            },
            expected_status=400,
        )

        self.assertEqual(response["error"], "comfyui openai route requires confirmation")
```

- [ ] **Step 2: Add failing runner test for ComfyUI job confirmation**

Append to `tests/test_job_queue.py`:

```python
    def test_comfyui_job_with_openai_key_requires_confirmation(self):
        project = self.project_store.save_project({"project_id": "demo", "name": "Demo"})
        episode = self.project_store.save_episode(project["project_id"], {"episode_id": "episode_001", "title": "E1"})
        job = self.job_store.create_job(
            {
                "project_id": project["project_id"],
                "episode_ids": [episode["episode_id"]],
                "steps": ["images"],
                "provider": "comfyui",
                "workflow_template": "comfyui_external_anime",
            }
        )
        runner = JobRunner(
            job_store=self.job_store,
            project_store=self.project_store,
            storyboard_dir=self.storyboard_dir,
            source_dir=self.source_dir,
            image_dir=self.image_dir,
            metadata_dir=self.metadata_dir,
            output_dir=self.output_dir,
            config_loader=lambda: {"openai_api_key": "sk-test"},
        )

        result = runner.run_next()

        self.assertEqual(result["status"], "failed")
        self.assertIn("comfyui openai route requires confirmation", result["error"])
```

- [ ] **Step 3: Run new confirmation tests and verify failure**

Run:

```bash
python -m unittest tests.test_launcher_server.LauncherServerTest.test_comfyui_route_with_openai_key_requires_confirmation tests.test_job_queue.JobRunnerTest.test_comfyui_job_with_openai_key_requires_confirmation -v
```

Expected: fail because ComfyUI currently uses OpenAI when a key exists without requiring `confirm_openai`.

- [ ] **Step 4: Update launcher provider routing**

In `anime_workflow/launcher/server.py`, change `_image_provider_from_body` and `_comfyui_image_provider`:

```python
    def _image_provider_from_body(self, body: dict[str, Any]):
        config = self.config_store.load()
        provider_name = str(body.get("provider") or "mock").lower()
        if provider_name == "comfyui":
            template = workflow_template_by_id(str(body.get("workflow_template") or "comfyui_external_anime"))
            return self._comfyui_image_provider(config, template, confirm_openai=body.get("confirm_openai") is True)
        if provider_name == "openai":
            if body.get("confirm_openai") is not True:
                raise ValueError("openai provider requires confirmation")
            api_key = config.get("openai_api_key", "")
            if not api_key:
                raise ValueError("OpenAI API Key is not configured")
            return OpenAIImageProvider(
                api_key=api_key,
                model=config.get("openai_image_model", "gpt-image-2"),
                endpoint=config.get("openai_base_url", "https://aigate.zhixingjidian.cn"),
            )
        return MockAnimeProvider()

    def _comfyui_image_provider(self, config: dict[str, Any], template: dict[str, Any], confirm_openai: bool = False) -> ComfyUIAnimeProvider:
        api_key = str(config.get("openai_api_key") or "")
        external_provider = "openai" if api_key else "mock"
        if external_provider == "openai" and confirm_openai is not True:
            raise ValueError("comfyui openai route requires confirmation")
        endpoint = str(config.get("openai_base_url") or "mock")
        if external_provider == "openai" and not endpoint.rstrip("/").endswith("/images/edits"):
            endpoint = f"{endpoint.rstrip('/')}/v1/images/edits"
        return ComfyUIAnimeProvider(
            base_url=effective_comfyui_base_url(config),
            api_endpoint=endpoint if external_provider == "openai" else "mock",
            api_key=api_key,
            provider_name=external_provider,
            model_version=str(config.get("openai_image_model") or "gpt-image-2"),
            workflow_template=template,
        )
```

- [ ] **Step 5: Update runner provider routing**

In `anime_workflow/jobs/runner.py`, make ComfyUI jobs require stored confirmation when OpenAI is configured:

```python
    def _provider(self, provider_name: str, workflow_template: str = "comfyui_external_anime", confirm_openai: bool = False):
        if provider_name == "comfyui":
            config = self.config_loader()
            api_key = str(config.get("openai_api_key") or "")
            external_provider = "openai" if api_key else "mock"
            if external_provider == "openai" and confirm_openai is not True:
                raise ValueError("comfyui openai route requires confirmation")
            endpoint = str(config.get("openai_base_url") or "mock")
            if external_provider == "openai" and not endpoint.rstrip("/").endswith("/images/edits"):
                endpoint = f"{endpoint.rstrip('/')}/v1/images/edits"
            return ComfyUIAnimeProvider(
                base_url=effective_comfyui_base_url(config),
                api_endpoint=endpoint if external_provider == "openai" else "mock",
                api_key=api_key,
                provider_name=external_provider,
                model_version=str(config.get("openai_image_model") or "gpt-image-2"),
                workflow_template=workflow_template_by_id(workflow_template),
            )
```

Update the images branch in `_run_step`:

```python
            provider = self._provider(
                job["provider"],
                workflow_template=str(job.get("workflow_template") or "comfyui_external_anime"),
                confirm_openai=job.get("confirm_openai") is True,
            )
```

- [ ] **Step 6: Run confirmation tests**

Run:

```bash
python -m unittest tests.test_launcher_server.LauncherServerTest.test_comfyui_route_with_openai_key_requires_confirmation tests.test_job_queue.JobRunnerTest.test_comfyui_job_with_openai_key_requires_confirmation -v
```

Expected: pass.

---

### Task 4: Workflow-Template-Aware Jobs

**Files:**
- Modify: `anime_workflow/jobs/models.py`
- Modify: `anime_workflow/jobs/store.py`
- Modify: `anime_workflow/jobs/runner.py`
- Modify: `anime_workflow/launcher/server.py`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/App.tsx`
- Test: `tests/test_job_queue.py`
- Test: `tests/test_launcher_server.py`

- [ ] **Step 1: Write failing job model tests**

Append to `tests/test_job_queue.py`:

```python
    def test_create_job_preserves_workflow_template_and_confirmation(self):
        job = self.job_store.create_job(
            {
                "project_id": "demo",
                "episode_ids": ["episode_001"],
                "steps": ["images"],
                "provider": "comfyui",
                "workflow_template": "comfyui_external_anime",
                "confirm_openai": True,
            }
        )

        self.assertEqual(job["workflow_template"], "comfyui_external_anime")
        self.assertTrue(job["confirm_openai"])
```

- [ ] **Step 2: Run job model test and verify failure**

Run:

```bash
python -m unittest tests.test_job_queue.JobQueueStoreTest.test_create_job_preserves_workflow_template_and_confirmation -v
```

Expected: fail because `workflow_template` and `confirm_openai` are not persisted on jobs.

- [ ] **Step 3: Extend job model**

In `anime_workflow/jobs/models.py`, import `workflow_template_by_id`:

```python
from anime_workflow.services.workflow_templates import workflow_template_by_id
```

In `job_from`, after provider validation:

```python
    workflow_template = str(values.get("workflow_template") or existing.get("workflow_template") or "").strip()
    if not workflow_template:
        workflow_template = "comfyui_external_anime" if provider == "comfyui" else f"{provider}_image"
    workflow_template_by_id(workflow_template)
    confirm_openai = bool(values.get("confirm_openai", existing.get("confirm_openai", False)))
```

Add to the returned dict:

```python
        "workflow_template": workflow_template,
        "confirm_openai": confirm_openai,
```

- [ ] **Step 4: Extend frontend job payload**

In `frontend/src/api.ts`, extend `CreateJobRequest`:

```typescript
export type CreateJobRequest = {
  project_id: string;
  episode_ids: string[];
  steps: Array<JobStep | "full">;
  provider: JobProvider;
  workflow_template?: string;
  confirm_openai?: boolean;
};
```

Extend `Job`:

```typescript
  workflow_template: string;
  confirm_openai: boolean;
```

- [ ] **Step 5: Pass selected template from UI job creation**

In `frontend/src/App.tsx`, add state near the existing job provider state:

```typescript
const [jobWorkflowTemplate, setJobWorkflowTemplate] = useState("comfyui_external_anime");
```

When calling `api.createJob`, include:

```typescript
workflow_template: jobWorkflowTemplate,
confirm_openai: jobProvider === "openai" || jobProvider === "comfyui",
```

Add a workflow template select near the batch job provider selector:

```tsx
<Field label="工作流模板">
  <select
    className="input"
    value={jobWorkflowTemplate}
    onChange={(event) => setJobWorkflowTemplate(event.target.value)}
  >
    {workflowTemplates
      .filter((template) => template.provider === jobProvider)
      .map((template) => (
        <option key={template.template_id} value={template.template_id}>
          {template.name}
        </option>
      ))}
  </select>
</Field>
```

- [ ] **Step 6: Run job and frontend checks**

Run:

```bash
python -m unittest tests.test_job_queue -v
npm --prefix frontend run build
```

Expected: pass.

---

### Task 5: Metadata And Rerun Records For Real Production

**Files:**
- Modify: `anime_workflow/services/anime_api_adapter.py`
- Modify: `anime_workflow/story/episode_runner.py`
- Test: `tests/test_anime_api_adapter.py`
- Test: `tests/test_episode_production.py`

- [ ] **Step 1: Add failing metadata test**

Append to `tests/test_anime_api_adapter.py`:

```python
    def test_metadata_includes_workflow_route_and_cost_fields(self):
        source = self.tmp / "source.png"
        source.write_bytes(self.png_bytes)
        provider = MockAnimeProvider()
        adapter = AnimeApiAdapter(provider=provider, output_dir=self.tmp / "out", metadata_dir=self.tmp / "meta")

        result = adapter.stylize(
            AnimeApiRequest(
                project_id="demo",
                episode_id="episode_001",
                shot_id="shot_001",
                source_image=source,
                style_preset="clean_anime",
                prompt="rain alley",
                reference_images=(source,),
                workflow_template="comfyui_external_anime",
                reference_bindings=("rain_alley",),
            )
        )

        metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata["workflow_template"], "comfyui_external_anime")
        self.assertEqual(metadata["reference_bindings"], ["rain_alley"])
        self.assertEqual(metadata["estimated_cost"]["amount"], 0)
        self.assertEqual(metadata["estimated_cost"]["currency"], "USD")
```

- [ ] **Step 2: Extend request dataclass**

In `anime_workflow/services/anime_api_adapter.py`, add fields to `AnimeApiRequest`:

```python
    workflow_template: str = "mock_image"
    reference_bindings: tuple[str, ...] = ()
```

- [ ] **Step 3: Extend cache key and metadata**

In `_cache_key`, include:

```python
            "workflow_template": request.workflow_template,
            "reference_bindings": list(request.reference_bindings),
```

In `_write_metadata`, include:

```python
            "workflow_template": request.workflow_template,
            "reference_bindings": list(request.reference_bindings),
            "estimated_cost": {"amount": 0, "currency": "USD", "source": "not_tracked"},
```

Replace the existing scalar `"estimated_cost": 0` entry with the structured object above.

- [ ] **Step 4: Pass workflow and bindings from episode runner**

In `anime_workflow/story/episode_runner.py`, when creating `AnimeApiRequest`, include:

```python
        workflow_template=workflow_template,
        reference_bindings=tuple(str(item) for item in shot.get("reference_bindings", []) if str(item).strip()),
```

Ensure `append_rerun_history` records the same fields:

```python
        "workflow_template": workflow_template,
        "reference_bindings": list(shot.get("reference_bindings", [])),
```

- [ ] **Step 5: Run metadata tests**

Run:

```bash
python -m unittest tests.test_anime_api_adapter tests.test_episode_production -v
```

Expected: pass.

---

### Task 6: Video Export Error Surfacing

**Files:**
- Modify: `anime_workflow/story/episode_runner.py`
- Modify: `anime_workflow/launcher/server.py`
- Modify: `frontend/src/App.tsx`
- Test: `tests/test_episode_production.py`
- Test: `tests/test_launcher_server.py`

- [ ] **Step 1: Add failing export failure tests**

Append to `tests/test_launcher_server.py`:

```python
    def test_project_episode_video_failure_marks_episode_failed(self):
        project = self.project_store.save_project({"project_id": "demo", "name": "Demo"})
        episode = self.project_store.save_episode(project["project_id"], {"episode_id": "episode_001", "title": "E1"})
        storyboard = generate_storyboard(
            {
                "project_id": "demo",
                "episode_id": "episode_001",
                "premise": "missing frames",
                "shot_count": 1,
                "duration_seconds": 3,
            }
        )
        save_storyboard(storyboard, self.storyboard_dir)

        response = self.post_json(
            "/api/projects/demo/episodes/episode_001/video",
            {},
            expected_status=500,
        )

        self.assertFalse(response["ok"])
        updated = self.project_store.get_episode("demo", "episode_001")
        self.assertEqual(updated["status"], "failed")
        self.assertIn("missing", updated["error"].lower())
```

- [ ] **Step 2: Run export failure test and verify failure**

Run:

```bash
python -m unittest tests.test_launcher_server.LauncherServerTest.test_project_episode_video_failure_marks_episode_failed -v
```

Expected: fail if the current endpoint returns 400 or does not mark the episode with a clear export failure.

- [ ] **Step 3: Normalize export errors**

In `anime_workflow/launcher/server.py`, wrap `_handle_project_episode_video` body:

```python
    def _handle_project_episode_video(self, project_id: str, episode_id: str) -> None:
        try:
            storyboard = load_storyboard(storyboard_path(STORYBOARD_DIR, project_id, episode_id))
            video = export_episode_video(storyboard, configured_output_dir(self.config_store.load()))
            storyboard["video_path"] = str(video)
            save_storyboard(storyboard, STORYBOARD_DIR)
            episode = self.project_store.update_episode(
                project_id,
                episode_id,
                {"status": "exported", "video_path": str(video), "error": ""},
            )
            self._json({"ok": True, "video_path": str(video), "storyboard": storyboard, "episode": episode})
        except Exception as exc:
            self.project_store.update_episode(project_id, episode_id, {"status": "failed", "error": str(exc)})
            self._json_error(exc, HTTPStatus.INTERNAL_SERVER_ERROR)
```

- [ ] **Step 4: Improve UI export result copy**

In `frontend/src/App.tsx`, after `exportProjectEpisodeVideo`, set a precise notice:

```typescript
setNotice(`视频已导出：${result.video_path}`);
await refreshProjectLibrary(currentProjectId);
```

In the generic `runBusy` catch path, keep server error text visible:

```typescript
const message = error instanceof Error ? error.message : String(error);
setNotice(message);
```

- [ ] **Step 5: Run export tests and frontend build**

Run:

```bash
python -m unittest tests.test_launcher_server.LauncherServerTest.test_project_episode_video_failure_marks_episode_failed tests.test_episode_production -v
npm --prefix frontend run build
```

Expected: pass.

---

### Task 7: Guarded Production Smoke Script

**Files:**
- Create: `scripts/smoke_production_loop.py`
- Test: `tests/test_launcher_server.py`

- [ ] **Step 1: Create script with safe defaults**

Create `scripts/smoke_production_loop.py`:

```python
from __future__ import annotations

import argparse
import json
from urllib import request


BASE_URL = "http://127.0.0.1:7860"


def post_json(path: str, payload: dict) -> dict:
    req = request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def get_json(path: str) -> dict:
    with request.urlopen(f"{BASE_URL}{path}", timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the local AI anime production loop.")
    parser.add_argument("--provider", choices=["mock", "openai", "comfyui"], default="mock")
    parser.add_argument("--workflow-template", default="mock_image")
    parser.add_argument("--confirm-openai", action="store_true")
    parser.add_argument("--project-id", default="smoke_production")
    parser.add_argument("--episode-id", default="episode_001")
    args = parser.parse_args()

    if args.provider in {"openai", "comfyui"} and not args.confirm_openai:
        raise SystemExit("--confirm-openai is required for openai or comfyui smoke runs")

    readiness = get_json("/api/production/readiness")
    print(json.dumps(readiness, ensure_ascii=False, indent=2))

    post_json(
        "/api/projects",
        {
            "project_id": args.project_id,
            "name": "Smoke Production",
            "genre": "悬疑",
            "platform": "douyin",
            "premise": "雨夜侦探收到匿名线索",
            "default_duration_seconds": 9,
            "default_shot_count": 3,
            "default_style_id": "clean_anime_drama",
        },
    )
    post_json(
        f"/api/projects/{args.project_id}/episodes/batch",
        {"count": 1, "direction": "每个镜头推进一个线索"},
    )
    storyboard = post_json(f"/api/projects/{args.project_id}/episodes/{args.episode_id}/storyboard", {})
    print(f"storyboard: {storyboard.get('storyboard_path')}")

    images = post_json(
        f"/api/projects/{args.project_id}/episodes/{args.episode_id}/images",
        {
            "provider": args.provider,
            "workflow_template": args.workflow_template,
            "confirm_openai": args.confirm_openai,
        },
    )
    print(f"images provider: {images.get('provider')}")

    video = post_json(f"/api/projects/{args.project_id}/episodes/{args.episode_id}/video", {})
    print(f"video: {video.get('video_path')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Add docs comment to README local running section**

In `README.md`, add:

````markdown
真实生产链路 smoke test：

```bash
python scripts/smoke_production_loop.py --provider comfyui --workflow-template comfyui_external_anime --confirm-openai
```

该命令会消耗真实图片 API 配额；不加 `--confirm-openai` 时不会运行真实 provider。
````

- [ ] **Step 3: Run script help**

Run:

```bash
python scripts/smoke_production_loop.py --help
```

Expected: prints CLI help and exits 0.

- [ ] **Step 4: Run safe mock smoke against launcher**

Start launcher in a separate terminal:

```bash
python scripts/start_launcher.py
```

Run:

```bash
python scripts/smoke_production_loop.py --provider mock --workflow-template mock_image
```

Expected: creates `smoke_production`, generates 3 mock images, and attempts video export. If FFmpeg is missing, the script fails at video export with the server's clear FFmpeg error and the episode status becomes `failed`.

---

### Task 8: Frontend Production Readiness And Real Route UX

**Files:**
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add readiness types and API method**

In `frontend/src/api.ts`, add:

```typescript
export type ProductionReadiness = {
  ok: boolean;
  checks: Record<
    string,
    {
      ok: boolean;
      detail?: string;
      path?: string;
      base_url?: string;
      model?: string;
      templates?: WorkflowTemplate[];
    }
  >;
  project_root: string;
};
```

Add API method:

```typescript
productionReadiness: () => request<{ ok: boolean; readiness: ProductionReadiness }>("/api/production/readiness"),
```

- [ ] **Step 2: Add readiness state**

In `frontend/src/App.tsx`, import the type and add state:

```typescript
const [productionReadiness, setProductionReadiness] = useState<ProductionReadiness | null>(null);
```

Add loader:

```typescript
const refreshProductionReadiness = async () => {
  const data = await api.productionReadiness();
  setProductionReadiness(data.readiness);
};
```

Include it in initial loading:

```typescript
Promise.all([refreshStatus(), refreshProjectLibrary(), refreshJobs(), refreshProductionReadiness()])
```

- [ ] **Step 3: Render readiness in overview**

Add a compact production readiness panel to the overview tab:

```tsx
<Panel title="生产链路" icon={Clapperboard}>
  <div className="grid gap-3 md:grid-cols-2">
    {productionReadiness &&
      Object.entries(productionReadiness.checks).map(([key, check]) => (
        <StatusMetric
          key={key}
          label={key}
          value={`${check.ok ? "可用" : "待处理"}${check.detail ? ` / ${check.detail}` : ""}`}
        />
      ))}
  </div>
</Panel>
```

- [ ] **Step 4: Add confirmation text for ComfyUI real route**

Before ComfyUI generation in single-shot and batch flows, use:

```typescript
const template = workflowTemplates.find((item) => item.template_id === reviewWorkflowTemplate);
if (template?.requires_openai_confirmation) {
  const confirmed = window.confirm(`${template.name} 会通过 ${template.route_summary} 消耗真实图片 API 配额，是否继续？`);
  if (!confirmed) {
    setNotice("已取消真实图片生成。");
    return;
  }
}
```

Send `confirm_openai: true` only when confirmed.

- [ ] **Step 5: Run frontend build**

Run:

```bash
npm --prefix frontend run build
```

Expected: pass.

---

### Task 9: Full Verification

**Files:**
- No production file edits unless verification exposes a small regression.

- [ ] **Step 1: Run backend tests**

Run:

```bash
python -m unittest discover -s tests -v
```

Expected: all tests pass; video export integration may skip if FFmpeg is unavailable.

- [ ] **Step 2: Run frontend build**

Run:

```bash
npm --prefix frontend run build
```

Expected: TypeScript and Vite build pass, writing fresh assets under `web/launcher`.

- [ ] **Step 3: Run readiness smoke**

Start launcher:

```bash
python scripts/start_launcher.py
```

Call readiness:

```bash
python - <<'PY'
from urllib.request import urlopen
print(urlopen("http://127.0.0.1:7860/api/production/readiness").read().decode("utf-8"))
PY
```

Expected: JSON includes `openai`, `comfyui`, `ffmpeg`, `output_dir`, and `workflow_templates`.

- [ ] **Step 4: Run safe mock smoke**

Run:

```bash
python scripts/smoke_production_loop.py --provider mock --workflow-template mock_image
```

Expected: the script reaches image generation. If FFmpeg is installed, it also exports a video. If FFmpeg is missing, the export error is clear and the episode is marked `failed`.

- [ ] **Step 5: Run guarded real route smoke when ready**

Only run when OpenAI key and ComfyUI are configured:

```bash
python scripts/smoke_production_loop.py --provider comfyui --workflow-template comfyui_external_anime --confirm-openai
```

Expected: ComfyUI receives the workflow, the custom node calls the OpenAI-compatible image endpoint, generated images and metadata are saved under `data/assets`, and video export either succeeds or reports the exact FFmpeg/input-frame issue.

- [ ] **Step 6: Commit**

```bash
git status --short
git add anime_workflow frontend scripts tests README.md web/launcher docs/superpowers/plans/2026-06-11-production-loop-openai-comfyui.md
git commit -m "Add OpenAI ComfyUI production loop"
```

Expected: commit contains readiness checks, cost-safe routing, workflow-template-aware jobs, metadata improvements, UI updates, smoke script, tests, and rebuilt launcher assets.

---

## Self-Review

- Spec coverage: the plan covers readiness, explicit OpenAI confirmation for direct and ComfyUI routes, template metadata, job routing, image metadata, video export errors, UI visibility, and smoke verification.
- Placeholder scan: no task uses unfinished placeholders or vague handling language; each task names files, code, commands, and expected results.
- Type consistency: `workflow_template`, `confirm_openai`, `requires_openai_confirmation`, `route_summary`, and `ProductionReadiness` are named consistently across Python and TypeScript tasks.
- Scope check: the plan stays inside the production loop and does not include publishing automation, advanced prompt tuning, or AI video generation.
