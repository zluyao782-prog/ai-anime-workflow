# Batch Job Queue Design

## Goal

Add a practical local task queue for the AI anime workbench so the user can select multiple episodes in the current project and run batch production without blocking the browser or accidentally spending real image API credits.

The first version targets a single-user local workflow:

- Jobs are persisted as JSON files under `data/jobs/`.
- One worker runs one job at a time inside the launcher process.
- The queue supports selected episodes from the current project, not full-project one-click production.
- Image generation defaults to `mock`.
- `gpt-image-2`/OpenAI image generation requires an explicit second confirmation in the UI before a job is created.

## Non-Goals

- No cloud job service.
- No account system or multi-user scheduling.
- No concurrent image generation in the first version.
- No automatic posting to Douyin or Bilibili in this phase.
- No database migration; JSON stays consistent with the current project library.
- No real image API call from tests.

## User Flow

In the `剧集生产` tab:

1. The user creates or loads episodes for the current project.
2. The user selects one or more episodes with checkboxes.
3. The user chooses production steps:
   - `storyboard`
   - `images`
   - `video`
   - or `full`, which expands to all three steps in order.
4. The image provider defaults to `mock`.
5. If the user chooses `openai`, the UI shows a confirmation dialog with:
   - selected episode count
   - estimated image count
   - provider name
   - a clear warning that real API credits may be consumed
6. The user submits the job.
7. The `任务队列` area shows queued, running, completed, failed, and cancelled jobs.
8. Failed jobs can be retried. Cancelled jobs do not resume automatically.

## Backend Architecture

Create a new package:

- `anime_workflow/jobs/__init__.py`
- `anime_workflow/jobs/models.py`
- `anime_workflow/jobs/store.py`
- `anime_workflow/jobs/runner.py`

The launcher server will own a singleton queue runner per process. The runner stores job state on disk and executes jobs in a background thread.

### Job Storage

Jobs are stored under:

```text
data/jobs/{job_id}.json
```

`job_id` uses a stable timestamp plus short random suffix:

```text
job_20260604_171530_ab12cd
```

Each job JSON contains:

```json
{
  "job_id": "job_20260604_171530_ab12cd",
  "project_id": "demo_drama",
  "episode_ids": ["episode_001", "episode_002"],
  "steps": ["storyboard", "images", "video"],
  "provider": "mock",
  "status": "queued",
  "current_episode_id": "",
  "current_step": "",
  "total_steps": 6,
  "completed_steps": 0,
  "progress": 0,
  "error": "",
  "created_at": "2026-06-04T09:15:30+00:00",
  "started_at": "",
  "finished_at": "",
  "cancel_requested": false
}
```

Valid statuses:

- `queued`
- `running`
- `completed`
- `failed`
- `cancelled`

Valid steps:

- `storyboard`
- `images`
- `video`

`full` is accepted by the API as a convenience but stored as `["storyboard", "images", "video"]`.

### Store Responsibilities

`JobStore` handles:

- create job
- get job
- list jobs, newest first
- update status and progress
- mark cancel requested
- retry failed/cancelled job by creating a new queued job with the same payload

The store must validate JSON object shape and reject non-object job files with `ValueError`, matching existing project store behavior.

### Runner Responsibilities

`JobRunner` handles:

- ensuring only one worker loop runs
- picking the oldest queued job
- marking it running
- executing selected episodes in order
- updating `current_episode_id`, `current_step`, `completed_steps`, and `progress`
- marking `completed`, `failed`, or `cancelled`

The runner reuses existing production functions:

- `ProjectStore.build_storyboard_values`
- `generate_storyboard`
- `save_storyboard`
- `generate_episode_images`
- `export_episode_video`
- `ProjectStore.update_episode`

Provider behavior:

- `mock` always uses `MockAnimeProvider`.
- `openai` checks `openai_api_key`; missing key fails the job with a clear error before provider construction.
- Tests use mock providers or monkeypatches only.

Cancellation behavior:

- If a job is queued and cancelled, it becomes `cancelled`.
- If a job is running and cancellation is requested, the runner checks between steps and before each episode. It does not interrupt a single in-flight image API call.

Failure behavior:

- On production failure, the job becomes `failed`.
- The current episode is updated to `status=failed` and `error=str(exc)` when possible.
- Completed previous episodes are not rolled back.
- Retry creates a new job, preserving the original failed job for history.

## Backend API

Add endpoints to the existing launcher server:

### `GET /api/jobs`

Returns:

```json
{
  "ok": true,
  "jobs": []
}
```

### `POST /api/jobs`

Request:

```json
{
  "project_id": "demo_drama",
  "episode_ids": ["episode_001", "episode_002"],
  "steps": ["storyboard", "images", "video"],
  "provider": "mock"
}
```

Response:

```json
{
  "ok": true,
  "job": {}
}
```

Validation:

- `project_id` is required and must be a valid project slug.
- `episode_ids` must be a non-empty list of valid episode slugs.
- `provider` must be `mock` or `openai`.
- `steps` must contain only valid steps or `full`.
- Every episode must exist in the project.

### `POST /api/jobs/{job_id}/cancel`

Marks cancellation requested and returns the updated job.

### `POST /api/jobs/{job_id}/retry`

Creates a new queued job from a failed or cancelled job and returns it.

## Frontend Design

Extend `frontend/src/api.ts` with:

- `Job`
- `JobStatus`
- `CreateJobRequest`
- `listJobs`
- `createJob`
- `cancelJob`
- `retryJob`

Extend `frontend/src/App.tsx`:

- Add checkbox state for selected project episodes.
- Add batch controls in `剧集生产`:
  - select all / clear selection
  - step selection
  - provider selection, default `mock`
  - estimated image count
  - create job button
- Add a `任务队列` panel in `剧集生产`, or a dedicated `任务队列` tab if the panel becomes crowded.

The first implementation should prefer a panel in `剧集生产` to keep the workflow in one place. A separate tab can be added later if the queue UI grows.

### Confirmation Rule

If provider is `openai`, the UI must show a blocking browser confirmation before `POST /api/jobs`:

```text
将使用 gpt-image-2 为 N 集生成约 M 张图片，可能消耗真实 API 额度。确认加入任务队列？
```

If the user cancels, no job is created.

### Polling

The frontend polls `GET /api/jobs` every 2 seconds while there is any queued or running job. It can stop polling when all visible jobs are terminal.

After a job changes to `completed`, `failed`, or `cancelled`, refresh:

- project episodes
- outputs
- current storyboard preview if it belongs to the affected episode

## Data Flow

```text
UI selection
  -> POST /api/jobs
  -> JobStore writes data/jobs/{job_id}.json
  -> JobRunner starts background worker if idle
  -> runner updates job JSON and project episode JSON
  -> UI polls GET /api/jobs
  -> UI refreshes project episodes and outputs
```

## Error Handling

- Bad request payload returns HTTP 400 with `{ok:false,error}`.
- Missing project, episode, or job returns HTTP 404.
- Unexpected runner errors are stored on the job as `failed`.
- The API should not expose API keys in any job JSON or UI text.
- If a malformed job JSON file exists, listing jobs should skip that one only if the filename is unrelated to the current API operation. Directly reading that job should return an error. The first version may choose stricter behavior and fail listing; tests should document the chosen behavior.

The recommended first-version behavior is strict listing failure for malformed job JSON, matching the project store style.

## Testing

Backend tests:

- create job writes JSON and lists it
- invalid provider is rejected
- invalid empty episode list is rejected
- `full` expands to `storyboard/images/video`
- runner completes a mock full-flow job and updates episode status to `exported`
- runner fails OpenAI job without API key before constructing provider
- cancel queued job marks cancelled
- retry failed job creates a new queued job
- `/api/jobs` endpoints return expected JSON

Frontend verification:

- `npm run build`
- create selected-episode mock job from UI
- queue panel shows queued/running/completed
- OpenAI provider path shows browser confirmation before creating a job
- completed job refreshes episode status and outputs

## Rollout Plan

1. Implement job models and store with unit tests.
2. Implement runner with mocked production functions.
3. Wire launcher APIs and tests.
4. Extend frontend API types and functions.
5. Add UI controls and queue panel.
6. Run backend tests, frontend build, and Playwright manual flow.

## Future Extensions

- Configurable concurrency, default still 1.
- Pause/resume queue.
- Per-shot retry.
- Cost accounting by provider and image count.
- Prompt editing before job creation.
- Auto-generate Douyin/Bilibili titles, descriptions, tags, and publishing checklist.
