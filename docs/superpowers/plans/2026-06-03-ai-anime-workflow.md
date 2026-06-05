# AI Anime Short Drama Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a personal local-first AI anime short drama workbench for Douyin and Bilibili content production.

**Architecture:** Start with a local workflow that can turn a legally usable story source into scripts, storyboard prompts, voiceover text, subtitles, and edited video packages. Use ComfyUI as the local workflow orchestrator, but call an external anime-stylization API for image transformation when local GPU generation is not practical. Wrap the workflow in a lightweight app only after the pipeline works manually. Keep publishing as assisted export first, then add browser/API automation later.

**Tech Stack:** Python, FastAPI, SQLite, local file storage, Ollama or cloud LLM API, ComfyUI, external anime-stylization API, FFmpeg, optional TTS engine, optional Playwright/Chrome automation for future publishing assistance.

---

## Scope

This plan targets a personal side-project tool, not a public SaaS product. The first working version should help one creator produce AI anime short drama videos for Douyin and Bilibili with lower manual effort.

The MVP does not need account billing, team permissions, cloud rendering, full automatic platform posting, or public user onboarding.

## Product Principles

- Local-first: source material, scripts, generated assets, and exports are stored locally.
- Human-in-the-loop: AI generates drafts; the creator approves scripts, storyboards, and final videos.
- Rights-aware: every imported story keeps source, author, license, and risk notes.
- Dual-platform: one story can produce a short Douyin version and a longer Bilibili version.
- Repeatable: every episode has a reproducible production package, not just one-off chat output.

## Local AI Workflow

### 1. Source Discovery And Import

Purpose: collect story material that can be adapted safely.

Supported source types for v1:

- Public-domain stories.
- Folk tales and historical anecdotes with low rights risk.
- Creative Commons or explicitly licensed works.
- Manual paste/import from your own writing.
- Trend references from Douyin/Bilibili, limited to topics, tags, titles, and audience signals, not copied story text.

Each imported source stores:

- Title.
- Author or original source.
- Source URL.
- License or rights note.
- Whether commercial adaptation is allowed.
- Whether attribution is required.
- Risk level: low, medium, high, blocked.
- Raw text.
- Summary.
- Tags.

### 2. Story Adaptation

Purpose: turn a source into an original anime short drama plan.

The adaptation output contains:

- Core premise.
- Main conflict.
- Character list.
- World rules.
- Episode arc.
- Douyin episode breakdown.
- Bilibili episode or collection breakdown.
- Rights note explaining how the adaptation differs from the source.

### 3. IP And Style Bible

Purpose: keep visual style, character identity, and storytelling tone consistent.

The style bible contains:

- Main character design prompts.
- Supporting character prompts.
- Fixed clothing and color notes.
- Voice style.
- Narration tone.
- Visual style.
- Forbidden elements.
- Douyin rhythm rules.
- Bilibili rhythm rules.

### 4. Episode Package Generation

Purpose: generate everything needed to make one episode.

Each episode package contains:

- Platform: Douyin or Bilibili.
- Runtime target.
- Title options.
- Hook.
- Beat outline.
- Full script.
- Voiceover text.
- Dialogue.
- Storyboard table.
- Image/video prompts.
- Subtitle file draft.
- Cover text.
- Publishing description.
- Tags.

### 5. ComfyUI External Anime-Stylization Workflow

Purpose: use ComfyUI as the repeatable local workflow layer while outsourcing anime-stylization to an external API.

Recommended direction:

- Use ComfyUI for workflow orchestration, input/output management, preview, batching, and future video workflows.
- Add an external API node or custom node that sends source images and style parameters to the anime-stylization service.
- Keep API provider details outside prompt templates by using an adapter layer in the backend.
- Keep generated images organized by project, episode, scene, and shot.
- Use fixed character references, style bible settings, and shot IDs where possible for consistency.
- Generate first as still-image storyboards or anime-stylized keyframes before attempting heavy video generation.
- Cache API results by source image hash, style preset, project ID, and shot ID to avoid paying twice for the same request.
- Store the original source image, API request metadata, anime-stylized result, and failure reason if the call fails.

v1 output can be:

- Static anime panels with camera movement.
- Anime-stylized versions of sketches, rough frames, reference images, or generated base images.
- Generated voiceover.
- Subtitles.
- Background music and effects.
- Edited vertical Douyin video.
- Edited Bilibili version or collection video.

### 6. Editing And Export

Purpose: generate publishable video files.

Use FFmpeg or a lightweight editing script to assemble:

- Images or video clips.
- Voiceover.
- Background music.
- Subtitles.
- Transitions.
- Cover frame.

Export presets:

- Douyin: vertical 9:16, 30-90 seconds, large subtitles.
- Bilibili: 16:9 or 9:16 depending on series style, 2-5 minutes for early tests, richer intro and continuity.

### 7. Publishing Assistant

Purpose: prepare posts without risky full automation at first.

v1 generates:

- Douyin title.
- Douyin hashtags.
- Douyin cover text.
- Bilibili title.
- Bilibili description.
- Bilibili tags.
- Suggested publish time.

v2 can add:

- Browser-assisted upload.
- Draft creation.
- Publish checklist.
- Manual confirmation before final posting.

### 8. Performance Review

Purpose: learn what works.

v1 uses manual data entry:

- Views.
- Likes.
- Comments.
- Shares.
- Favorites.
- Completion rate if available.
- Publish time.

Later versions can add automated collection where platform rules and account safety allow it.

## Recommended Software Modules

### Backend

- `app/main.py`: FastAPI entrypoint.
- `app/db.py`: SQLite connection and migrations.
- `app/models.py`: data models for source, project, character, episode, asset, export, platform post.
- `app/services/source_importer.py`: manual import and crawler-safe import logic.
- `app/services/rights_checker.py`: license and risk classification.
- `app/services/adaptation.py`: source-to-drama adaptation prompts.
- `app/services/style_bible.py`: project/IP consistency rules.
- `app/services/episode_generator.py`: script, storyboard, subtitle, and prompt generation.
- `app/services/anime_api_adapter.py`: external anime-stylization API calls, retries, metadata capture, and provider isolation.
- `app/services/asset_registry.py`: local asset path tracking.
- `app/services/exporter.py`: FFmpeg export orchestration.
- `app/services/publish_assistant.py`: Douyin/Bilibili post copy generation.
- `app/services/metrics.py`: manual performance recording.

### Frontend

- `web/src/pages/SourceLibrary.tsx`: material library and rights notes.
- `web/src/pages/ProjectBible.tsx`: IP, character, and style settings.
- `web/src/pages/AdaptationWorkbench.tsx`: source-to-series adaptation.
- `web/src/pages/EpisodeWorkbench.tsx`: episode package editor.
- `web/src/pages/AssetBoard.tsx`: generated image/video/audio asset tracking.
- `web/src/pages/ExportQueue.tsx`: render jobs and output files.
- `web/src/pages/PublishAssistant.tsx`: Douyin/Bilibili publishing copy.
- `web/src/pages/MetricsReview.tsx`: manual data review.

### Local Folders

- `data/app.db`: SQLite database.
- `data/sources/`: imported source texts.
- `data/projects/`: project and style bible files.
- `data/assets/`: generated images, audio, and clips.
- `data/assets/source_frames/`: original frames or rough source images before anime-stylization.
- `data/assets/anime_frames/`: external API anime-stylized images.
- `data/assets/api_metadata/`: request and response metadata for traceability.
- `data/exports/`: finished videos and platform packages.
- `workflows/comfyui/`: ComfyUI workflow JSON files.
- `prompts/`: reusable prompt templates.

## MVP Phases

### Phase 0: Local Tool Baseline

- [ ] Install Python environment.
- [ ] Install FFmpeg.
- [ ] Install and run ComfyUI.
- [ ] Install Ollama or configure an LLM API key.
- [ ] Confirm one text generation request works.
- [ ] Confirm one image generation workflow works.
- [ ] Confirm one FFmpeg video assembly command works.

Success criteria:

- One local text prompt produces a script.
- One local image workflow produces an anime image.
- One local FFmpeg command produces a short video from images and audio.

### Phase 1: Manual Pipeline Prototype

- [ ] Select one low-risk source story.
- [ ] Write a project style bible.
- [ ] Generate a 5-episode Douyin outline.
- [ ] Generate a 1-episode Bilibili collection outline.
- [ ] Generate one Douyin episode script.
- [ ] Generate storyboard prompts for that episode.
- [ ] Generate still images for 5-8 shots.
- [ ] Generate or record voiceover.
- [ ] Assemble one 30-60 second vertical video.
- [ ] Generate Douyin and Bilibili publishing copy.

Success criteria:

- One episode can be produced end-to-end by following a repeatable checklist.
- The output package includes source note, script, prompts, assets, video, and publishing copy.

### Phase 2: Backend Data Model

- [ ] Create tables for sources, projects, characters, episodes, scenes, shots, assets, exports, and platform posts.
- [ ] Add CRUD APIs for source library.
- [ ] Add CRUD APIs for project bible.
- [ ] Add episode package APIs.
- [ ] Add export package records.

Success criteria:

- A source can be imported and linked to a project.
- A project can contain characters and style rules.
- An episode can contain script, storyboard, prompts, and export state.

### Phase 3: Prompt Template System

- [ ] Create prompt templates for rights summary.
- [ ] Create prompt templates for source adaptation.
- [ ] Create prompt templates for Douyin short drama script.
- [ ] Create prompt templates for Bilibili collection script.
- [ ] Create prompt templates for storyboard shots.
- [ ] Create prompt templates for image prompts.
- [ ] Create prompt templates for publishing copy.

Success criteria:

- The same source and style bible can generate structured episode packages repeatedly.
- Output format is JSON or markdown with stable sections.

### Phase 4: Simple Web Workbench

- [ ] Build source library page.
- [ ] Build project bible page.
- [ ] Build adaptation page.
- [ ] Build episode editor.
- [ ] Build asset board.
- [ ] Build export queue.
- [ ] Build publishing assistant page.

Success criteria:

- You can manage one complete short drama project from a browser UI.
- You can review and edit AI output before asset generation and export.

### Phase 5: ComfyUI And External Anime API Integrations

- [ ] Add LLM adapter for Ollama or cloud LLM API.
- [ ] Add ComfyUI workflow trigger through its queue API or file handoff.
- [ ] Add anime API adapter that accepts input image path, style preset, character reference path, and output path.
- [ ] Add request metadata capture for provider name, model/version, source hash, prompt, style preset, cost estimate, and response status.
- [ ] Add retry policy for transient API failures.
- [ ] Add cache lookup before every external anime API call.
- [ ] Add a ComfyUI workflow JSON for source frame to anime frame.
- [ ] Add TTS adapter.
- [ ] Add FFmpeg export job runner.
- [ ] Add output package generation per platform.

Success criteria:

- The workbench can generate text packages.
- The workbench can submit a frame through ComfyUI and receive an anime-stylized result from the external API.
- The workbench can register original frames, anime frames, and API metadata.
- The workbench can assemble at least one video export from tracked assets.

### Phase 6: Douyin And Bilibili Publishing Assistant

- [ ] Generate platform-specific titles.
- [ ] Generate cover text.
- [ ] Generate hashtags/tags.
- [ ] Generate description.
- [ ] Create a publish checklist.
- [ ] Track published URL and publish time manually.

Success criteria:

- Each exported video has a ready-to-use Douyin package and Bilibili package.
- Manual publishing takes copy/paste instead of fresh writing.

### Phase 7: Data Feedback Loop

- [ ] Add manual metrics entry.
- [ ] Compare episodes by source, hook type, runtime, and platform.
- [ ] Generate weekly recommendations.
- [ ] Mark high-performing styles and story beats.

Success criteria:

- The tool can explain which episode patterns performed better.
- Future episode generation can use successful patterns as context.

## First 14-Day Execution Schedule

### Days 1-2: Environment And Workflow Baseline

- Install and verify Python, FFmpeg, ComfyUI, and LLM access.
- Produce one test image.
- Produce one test voiceover.
- Produce one FFmpeg test video.

### Days 3-4: Source And IP Setup

- Choose the first story type: public-domain folk tale or zhiguai-style story.
- Create one project bible.
- Create 3 fixed character designs.
- Define Douyin and Bilibili format rules.

### Days 5-7: First Episode Prototype

- Generate one 5-episode outline.
- Generate episode 1 script and storyboard.
- Generate 5-8 images.
- Generate voiceover and subtitles.
- Export one Douyin vertical video.

### Days 8-10: Repeatability

- Produce episode 2 and episode 3 using the same style bible.
- Record what changed manually.
- Turn repeated steps into prompt templates and checklist files.

### Days 11-12: Minimal App Skeleton

- Create local database schema.
- Create backend APIs for source, project, and episode.
- Create a simple UI for viewing and editing episode packages.

### Days 13-14: Publishing Package And Review

- Generate Douyin/Bilibili titles and descriptions.
- Publish manually.
- Enter early metrics manually.
- Decide whether to improve generation quality or build more UI next.

## Risk Controls

### Copyright

- Block high-risk copyrighted novels unless explicit adaptation and commercial rights are documented.
- Store source URL and rights note for every imported item.
- Prefer public-domain and original transformations for first experiments.

### Platform Account Safety

- Do not start with fully automated posting.
- Use publishing assistant mode first.
- Add manual confirmation before any future browser automation.

### Cost

- Start with still images plus camera movement instead of full video generation.
- Generate short episodes before long videos.
- Reuse characters, backgrounds, voices, and templates.

### Quality

- Keep fixed project bible.
- Review each script before generating assets.
- Generate storyboards before images.
- Track character consistency problems per shot.

## First Concrete Build Target

Build a local MVP that can handle one project:

- Source: one legally usable folk/zhiguai-style story.
- Output: 3 Douyin vertical episodes and 1 Bilibili collection script.
- Media: still-image anime panels, voiceover, subtitles, simple transitions.
- Publishing: platform-specific copy and manual publishing checklist.
- Review: manual metrics table.

When this target works, expand to crawler discovery, more IPs, and semi-automated upload.

## Open Decisions

- Whether to prioritize fully local LLM generation or use a cloud LLM API for better script quality.
- Whether first videos should use still-image animation or AI video generation.
- Whether Bilibili should use vertical reposts or horizontal collection edits.
- Which TTS tool should be used for the first working voice style.
