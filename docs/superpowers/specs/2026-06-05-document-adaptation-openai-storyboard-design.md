# Document Adaptation And OpenAI-Compatible Storyboard Design

## Goal

Add a practical document-adaptation workflow for the local anime workbench. The user can import a `txt`, `markdown`, or text-based `pdf` source, split it into short-video episodes, generate episode drafts, and create storyboards through either the existing local rule engine or an OpenAI-compatible text API.

This joins two related needs:

- Long text import and automatic short-video pacing.
- External API support for AI storyboard generation.

## Non-Goals

- No OCR for scanned PDFs in this phase.
- No web crawler or automatic resource scraping in this phase.
- No automatic real API spending without explicit confirmation.
- No database migration; keep JSON files.
- No fully automatic publish flow.
- No long-drama timeline editor.

## User Flow

In a new `文档改编` tab:

1. The user uploads or pastes a source document.
2. The app extracts readable text.
3. The user chooses:
   - project id and project name
   - genre
   - platform: `douyin` or `bilibili`
   - target episode duration: 30, 60, 90, or 180 seconds
   - shots per episode: 6, 8, or 12
   - maximum episode count for this import batch
   - storyboard provider: `local` or `openai`
4. The app cleans the text and splits it using short-video pacing.
5. The app creates or updates a project and writes episode drafts.
6. If `local` storyboard provider is selected, storyboards are generated with the current deterministic engine.
7. If `openai` storyboard provider is selected, the UI asks for confirmation and the backend requires `confirm_openai: true`.
8. The generated episodes appear in the existing `剧集生产` project episode list and can use the current batch queue for images and video.

## Short-Video Splitting Behavior

The default segmentation mode is `short_video`.

The splitter should prioritize watchability over original chapter boundaries. Each episode draft should have:

- a strong opening hook
- one clear conflict or discovery
- one emotional or suspense beat
- a closing hook for the next episode

For the first version, the splitter can be deterministic and local:

- normalize whitespace
- remove common markdown headings, repeated blank lines, and obvious boilerplate markers
- split into paragraphs
- group paragraphs into episode chunks by approximate character budget
- produce `episode_001`, `episode_002`, etc.

Approximate Chinese text budget:

- 30 seconds: 400-700 chars
- 60 seconds: 800-1200 chars
- 90 seconds: 1200-1800 chars
- 180 seconds: 2400-3600 chars

Each generated episode draft stores:

- `episode_no`
- `title`
- `premise`
- `duration_seconds`
- `shot_count`
- `source_excerpt`
- `status="draft"`

The first version may generate simple titles like `第1集：<opening phrase>`. Later, OpenAI-compatible text generation can improve titles and summaries.

## Imported Source Model

Add a JSON-backed imported source record under:

```text
data/imports/{import_id}.json
```

Shape:

```json
{
  "import_id": "import_20260605_150000_ab12cd",
  "project_id": "rain_detective",
  "filename": "novel.txt",
  "content_type": "text/plain",
  "text_length": 125000,
  "cleaned_text_path": "data/imports/import_...txt",
  "episode_ids": ["episode_001", "episode_002"],
  "settings": {
    "platform": "douyin",
    "duration_seconds": 60,
    "shot_count": 8,
    "max_episodes": 10,
    "segmentation_mode": "short_video",
    "storyboard_provider": "local"
  },
  "created_at": "2026-06-05T00:00:00+00:00"
}
```

## Backend Components

### `anime_workflow/imports/document_reader.py`

Responsibilities:

- extract text from `.txt`
- extract text from `.md`
- extract text from text-based `.pdf`
- reject unsupported file names
- reject empty extracted text

PDF support should be best-effort. If text extraction fails or the PDF is likely scanned, return a clear error: `PDF text could not be extracted; scanned PDFs need OCR and are not supported yet`.

### `anime_workflow/imports/adaptation.py`

Responsibilities:

- clean document text
- split into short-video episode chunks
- produce episode draft payloads compatible with `ProjectStore.save_episode`
- create import metadata records

### `anime_workflow/story/providers.py`

Responsibilities:

- define a local storyboard provider that wraps existing `generate_storyboard`
- define an OpenAI-compatible text storyboard provider
- validate the storyboard JSON returned by the provider
- fall back only when explicitly requested; do not silently replace failed API calls with local output

OpenAI-compatible provider should support:

- `/v1/chat/completions` for first implementation
- `/v1/responses` as a config mode after chat completions is stable

The provider prompt must require a JSON object matching current storyboard shape:

- `title`
- `genre`
- `premise`
- `protagonist`
- `style_preset`
- `platform`
- `duration_seconds`
- `shot_count`
- `shots`

Each shot must include:

- `shot_id`
- `duration`
- `scene`
- `dialogue`
- `image_prompt`
- `camera`
- `emotion`
- `source_image`
- `anime_image`

The backend must normalize and validate the response before saving.

### Config

Extend `LauncherConfigStore`:

```json
{
  "openai_text_model": "gpt-4.1-mini",
  "openai_text_endpoint_mode": "chat_completions"
}
```

Reuse:

- `openai_base_url`
- `openai_api_key`

The public config can show the text model and endpoint mode, but must keep masking the API key.

## Backend API

### `POST /api/imports/adapt`

Accepts JSON in the first version:

```json
{
  "filename": "story.txt",
  "content_base64": "...",
  "project_id": "rain_detective",
  "project_name": "雨夜侦探",
  "genre": "悬疑",
  "platform": "douyin",
  "duration_seconds": 60,
  "shot_count": 8,
  "max_episodes": 10,
  "storyboard_provider": "local",
  "confirm_openai": false
}
```

Returns:

```json
{
  "ok": true,
  "import": {},
  "project": {},
  "episodes": []
}
```

Behavior:

- creates or updates the project
- writes generated episode drafts
- generates storyboards when `storyboard_provider` is `local` or confirmed `openai`
- updates episode `storyboard_path` and status when storyboard generation succeeds
- if one storyboard fails, the API should return `400` with the error and preserve already-created draft episodes

### `POST /api/storyboard/generate`

Optional utility endpoint for regenerating one episode storyboard with a selected provider:

```json
{
  "project_id": "rain_detective",
  "episode_id": "episode_001",
  "provider": "openai",
  "confirm_openai": true
}
```

This endpoint should share provider logic with the import workflow and the existing project episode storyboard route.

## Frontend Design

Add a `文档改编` tab.

The UI should be a workbench, not a landing page:

- file picker for `.txt`, `.md`, `.pdf`
- optional paste textarea for quick tests
- project settings form
- episode settings controls
- storyboard provider selector
- preview of extracted text length and generated episode count
- result panel listing generated episode ids and storyboard status

OpenAI-compatible storyboard generation must show confirmation text before sending:

```text
将调用外部文本 API 生成分镜，可能消耗额度。是否继续？
```

The request must include `confirm_openai: true`; frontend confirmation alone is not enough.

## Error Handling

- Empty document: `document text is empty`
- Unsupported extension: `unsupported document type`
- PDF extraction failure: `PDF text could not be extracted; scanned PDFs need OCR and are not supported yet`
- Missing API key for OpenAI storyboard: `OpenAI API Key is not configured`
- Unconfirmed OpenAI storyboard: `openai storyboard provider requires confirmation`
- Invalid API JSON: `storyboard API returned invalid JSON`
- Invalid storyboard shape: `storyboard API returned invalid storyboard`

## Testing

Backend tests:

- txt and markdown extraction
- text cleaning and short-video segmentation
- import adaptation creates project and episode drafts
- local storyboard provider produces current storyboard shape
- OpenAI-compatible provider posts chat completions payload and parses JSON
- OpenAI storyboard rejects missing confirmation
- OpenAI storyboard rejects missing API key
- launcher API creates import and storyboards

Frontend verification:

- TypeScript build passes
- `文档改编` tab renders
- selecting a text file loads preview metadata
- local adaptation request creates episodes
- OpenAI provider asks for confirmation before request

Manual smoke:

- import a short `.txt`
- generate 2-3 episodes
- open `剧集生产`
- verify imported episodes appear
- run mock image/video queue for one imported episode

## Acceptance Criteria

- User can import or paste a text source and generate short-video episode drafts.
- Imported episodes show in the existing project episode list.
- User can generate storyboards from imported episodes using local rules.
- User can generate storyboards through an OpenAI-compatible text API when confirmed.
- Backend blocks unconfirmed OpenAI-compatible storyboard calls.
- Existing image generation, video export, job detail, and retry workflows continue to work.
