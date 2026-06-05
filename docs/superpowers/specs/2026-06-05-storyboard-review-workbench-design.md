# Storyboard Review Workbench Design

## Goal

Add a practical storyboard review workbench so the user can inspect imported or generated episodes before spending image-generation credits. The first version focuses on manual editing, saving, and local single-shot rewrite.

## Non-Goals

- No collaborative review.
- No visual timeline editor.
- No image prompt scoring.
- No automatic image regeneration after saving a storyboard.
- No paid OpenAI shot rewrite in the first implementation, except preserving the same backend confirmation pattern for future expansion.

## User Flow

In a new `分镜审稿` tab:

1. Select a project.
2. Select an episode with a generated storyboard.
3. Load the storyboard.
4. Edit episode-level fields:
   - title
   - premise
   - protagonist
   - style preset
5. Edit each shot:
   - duration
   - scene
   - dialogue
   - image prompt
   - camera
   - emotion
6. Save the storyboard.
7. Rewrite one selected shot locally with a short instruction.
8. Continue to `剧集生产` to generate images and video.

## Backend API

### `POST /api/storyboard/save`

Accepts:

```json
{
  "project_id": "demo",
  "episode_id": "episode_001",
  "storyboard": {}
}
```

Behavior:

- validates the storyboard shape
- forces `project_id` and `episode_id` from the request path/body
- saves `data/storyboards/{project_id}/{episode_id}/storyboard.json`
- updates the project episode `status="storyboarded"` and `storyboard_path`

### `POST /api/storyboard/shot/update`

Accepts:

```json
{
  "project_id": "demo",
  "episode_id": "episode_001",
  "shot_id": "shot_001",
  "updates": {
    "scene": "new scene",
    "dialogue": "new dialogue",
    "image_prompt": "new prompt"
  }
}
```

Behavior:

- loads the existing storyboard
- updates only allowed shot fields
- saves the storyboard
- returns the updated storyboard

Allowed shot fields:

- `duration`
- `scene`
- `dialogue`
- `image_prompt`
- `camera`
- `emotion`

### `POST /api/storyboard/shot/rewrite`

Accepts:

```json
{
  "project_id": "demo",
  "episode_id": "episode_001",
  "shot_id": "shot_001",
  "instruction": "更悬疑，结尾留钩子",
  "provider": "local"
}
```

First implementation:

- `provider="local"` rewrites the shot deterministically using the instruction.
- `provider="openai"` returns `400` unless `confirm_openai: true`; once confirmed, it returns `501` for this first version with `openai shot rewrite is not implemented yet`.

This gives the UI and safety contract now while keeping paid shot rewrite for a later focused task.

## Backend Component

Add `anime_workflow/story/review.py`:

- validate storyboard shape
- update one shot
- local rewrite one shot
- keep existing image paths unless the user explicitly updates them

## Frontend

Add a `分镜审稿` tab:

- project selector
- episode selector
- load button
- editable episode fields
- repeated shot editors
- save storyboard button
- instruction box per selected shot
- local rewrite button

The page should be dense and workbench-like. It should not be a marketing or tutorial page.

## Error Handling

- Missing storyboard: `storyboard not found`
- Missing shot: `shot not found`
- Invalid storyboard: `storyboard API returned invalid storyboard`
- OpenAI unconfirmed: `openai storyboard provider requires confirmation`
- OpenAI confirmed first-version stub: `openai shot rewrite is not implemented yet`

## Testing

Backend tests:

- saving a storyboard writes JSON and updates episode status
- shot update changes only selected shot fields
- shot rewrite local updates scene/dialogue/image prompt and preserves shot id
- missing shot returns 404 through launcher
- openai shot rewrite without confirmation returns 400

Frontend verification:

- TypeScript build passes
- tab renders
- project and episode selectors render
- editable storyboard form renders when storyboard is loaded

## Acceptance Criteria

- User can load a generated storyboard from the UI.
- User can edit storyboard text fields and save them.
- User can rewrite one shot locally with an instruction.
- Existing image and video generation flows still work after editing.
