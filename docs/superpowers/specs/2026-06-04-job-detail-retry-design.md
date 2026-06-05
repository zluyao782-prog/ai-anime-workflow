# Job Detail And Retry Design

## Goal

Add a practical task-detail view and targeted retry flow for the local AI anime workbench. The user should be able to inspect a batch job, see which episode and production step failed, and retry only the failed or selected part without recreating the whole batch by hand.

This is an A1 extension of the current JSON-backed job queue. It keeps the app local-first, single-user, and lightweight.

## Non-Goals

- No SQLite or external database in this phase.
- No multi-worker scheduling.
- No automatic Douyin or Bilibili publishing.
- No automatic retry loop that could repeatedly spend real API credits.
- No interruption of an in-flight image API call; cancellation and retry boundaries remain step-based.

## User Flow

In the `剧集生产` tab:

1. The user sees jobs in the existing `任务队列` panel.
2. The user clicks `详情` on one job.
3. A compact detail panel opens under the queue.
4. The detail panel shows each episode in that job and the status of:
   - `storyboard`
   - `images`
   - `video`
5. If a step fails, the row shows the error message and the current output path if one exists.
6. The user can:
   - retry all failed steps in the job
   - retry one episode with the original job steps
   - retry one episode starting from a selected step
7. If the original provider is `openai`, every retry action requires a fresh UI confirmation and the backend requires `confirm_openai: true`.

## Data Model

Extend each job JSON with an `items` list. One item represents one episode-step pair.

```json
{
  "job_id": "job_20260604_171530_ab12cd",
  "project_id": "demo_drama",
  "episode_ids": ["episode_001"],
  "steps": ["storyboard", "images", "video"],
  "provider": "mock",
  "status": "running",
  "items": [
    {
      "episode_id": "episode_001",
      "step": "storyboard",
      "status": "completed",
      "error": "",
      "output_path": "/path/to/storyboard.json",
      "started_at": "2026-06-04T09:00:00+00:00",
      "finished_at": "2026-06-04T09:00:01+00:00"
    },
    {
      "episode_id": "episode_001",
      "step": "images",
      "status": "failed",
      "error": "OpenAI API Key is not configured",
      "output_path": "",
      "started_at": "2026-06-04T09:00:01+00:00",
      "finished_at": "2026-06-04T09:00:02+00:00"
    }
  ]
}
```

Valid item statuses:

- `pending`
- `running`
- `completed`
- `failed`
- `cancelled`
- `skipped`

Existing job fields stay compatible. When old job JSON files do not have `items`, the backend derives a default item list from `episode_ids` and `steps` when the job is read or updated.

## Backend Behavior

### Job Store

`JobStore` adds helpers for item-level updates:

- build default items from `episode_ids` and `steps`
- set an item `running`
- set an item `completed` with `output_path`
- set an item `failed` with `error`
- list failed items
- create retry jobs from selected episode and step ranges

JSON writes continue to use the existing atomic temp-file replace behavior.

### Job Runner

The runner updates the matching item before and after every step:

1. Mark item `running`.
2. Execute the production step.
3. Mark item `completed` and record the most useful output path:
   - storyboard path for `storyboard`
   - storyboard path after generated images for `images`
   - video path for `video`
4. If a step raises, mark item `failed`, mark the job `failed`, and preserve completed previous items.
5. If cancellation is requested between steps, mark remaining pending items `cancelled` where appropriate.

The runner does not automatically continue after a failed step. A retry creates a new job, preserving the original failed job as history.

## Backend API

Add endpoints:

### `GET /api/jobs/{job_id}`

Returns the full job with `items`.

### `POST /api/jobs/{job_id}/retry-failed`

Creates a new job from failed items only. The new job groups failed items by episode and uses the minimal step sequence needed for those failures.

For example:

- failed `images` creates a retry job with `steps=["images", "video"]` for that episode, because video depends on images
- failed `video` creates `steps=["video"]`
- failed `storyboard` creates `steps=["storyboard", "images", "video"]`

### `POST /api/jobs/{job_id}/episodes/{episode_id}/retry`

Creates a new job for one episode using the original job's steps.

### `POST /api/jobs/{job_id}/episodes/{episode_id}/steps/{step}/retry`

Creates a new job for one episode starting from the selected step:

- `storyboard` means `storyboard + images + video`
- `images` means `images + video`
- `video` means `video`

All retry endpoints preserve the original provider. If provider is `openai`, the request must include:

```json
{
  "confirm_openai": true
}
```

Otherwise the backend returns a `400` error and no new job is created.

## Frontend Design

Extend `frontend/src/api.ts` with:

- `JobItem`
- `getJob(jobId)`
- `retryFailedJob(jobId, confirmOpenai)`
- `retryJobEpisode(jobId, episodeId, confirmOpenai)`
- `retryJobEpisodeFromStep(jobId, episodeId, step, confirmOpenai)`

Extend `frontend/src/App.tsx`:

- Add `selectedJobId` and `selectedJobDetail` state.
- Add `详情` button to each `JobRow`.
- Render a `JobDetailPanel` under `任务队列`.
- Show a compact table with columns:
  - episode
  - storyboard
  - images
  - video
  - error
  - actions
- Add actions:
  - `重跑失败`
  - `重跑本集`
  - `从分镜重跑`
  - `从图片重跑`
  - `只重跑视频`

The detail panel polls while the selected job is queued or running and refreshes once after completion or failure.

## Error Handling

- Missing job returns `404`.
- Missing episode in retry request returns `404`.
- Invalid step returns `400`.
- Retry from `images` or `video` may fail if required prior artifacts are missing. The error is recorded on the new retry job rather than hidden.
- Corrupt legacy job JSON files remain isolated by the existing list behavior.
- Unconfirmed `openai` retry returns `400` before any provider construction.

## Testing

Backend tests:

- job creation includes derived `items`
- runner marks item running and completed
- runner marks item failed with error
- `GET /api/jobs/{job_id}` returns detail
- retry failed creates the expected scoped job
- retry episode creates a one-episode job
- retry from step expands dependencies correctly
- openai retry without `confirm_openai` is rejected

Frontend build:

- TypeScript compiles with new job item types and API helpers.

Manual smoke:

- Open `http://127.0.0.1:7860`.
- Create a mock full-flow job.
- Open job detail.
- Confirm all steps show completed.
- Trigger an unconfirmed openai retry request by API and confirm backend rejects it.

## Acceptance Criteria

- A user can inspect a job and see per-episode, per-step status.
- A failed job can be retried without manually recreating all selected episodes.
- Retrying a single episode does not rerun unrelated episodes.
- Retrying from `images` does not rerun `storyboard`.
- Real `gpt-image-2` retry cannot happen without explicit UI confirmation and backend `confirm_openai: true`.
- Existing job JSON files without `items` still load.
