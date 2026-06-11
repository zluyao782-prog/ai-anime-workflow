export type PublicConfig = {
  openai_api_key: string;
  openai_api_key_configured: boolean;
  openai_base_url: string;
  openai_image_model: string;
  openai_text_model: string;
  openai_text_endpoint_mode: "chat_completions" | "responses";
  ollama_text_model: string;
  comfyui_mode: "local" | "remote";
  comfyui_base_url: string;
  comfyui_remote_base_url: string;
  output_dir: string;
};

export type DiskInfo = {
  total_gb: number;
  used_gb: number;
  free_gb: number;
};

export type LauncherStatus = {
  python: { ok: boolean };
  ffmpeg: { ok: boolean; path: string };
  ollama: { ok: boolean; detail: string };
  comfyui: {
    mode: "local" | "remote";
    base_url: string;
    process_running: boolean;
    pid: number | null;
    api_running: boolean;
    api_detail: string;
    log_tail: string;
  };
  openai: { configured: boolean };
  paths: Record<string, string>;
  disk: Record<string, DiskInfo>;
};

export type StatusResponse = {
  status: LauncherStatus;
  config: PublicConfig;
};

export type ScriptResult = {
  ok: boolean;
  exit_code: number;
  stdout: string;
  stderr: string;
};

export type EpisodeShot = {
  shot_id: string;
  duration: number;
  scene: string;
  dialogue: string;
  image_prompt: string;
  camera: string;
  emotion: string;
  source_image: string;
  anime_image: string;
  metadata_path?: string;
  cache_hit?: boolean;
  reference_bindings?: string[];
  workflow_template?: string;
  rerun_history?: ShotRerunRecord[];
  review_status?: "pending" | "approved" | "rejected" | "revise";
  review_note?: string;
  reviewed_at?: string;
};

export type ShotRerunRecord = {
  provider: string;
  model_version: string;
  workflow_template: string;
  prompt: string;
  reference_bindings: string[];
  source_image: string;
  anime_image: string;
  metadata_path: string;
  cache_hit: boolean;
  created_at: string;
};

export type Storyboard = {
  project_id: string;
  episode_id: string;
  title: string;
  genre: string;
  premise: string;
  protagonist: string;
  style_preset: string;
  platform: string;
  duration_seconds: number;
  shot_count: number;
  shots: EpisodeShot[];
  video_path?: string;
  review_versions?: StoryboardReviewVersion[];
};

export type StoryboardReviewVersion = {
  version_id: string;
  created_at: string;
  note: string;
  summary: Record<"pending" | "approved" | "rejected" | "revise", number>;
  shots: Array<Pick<EpisodeShot, "shot_id" | "scene" | "dialogue" | "image_prompt" | "review_status" | "review_note" | "anime_image">>;
};

export type EpisodeStoryboardRequest = {
  project_id: string;
  episode_id: string;
  title?: string;
  genre: string;
  premise: string;
  protagonist: string;
  style_preset: string;
  platform: string;
  duration_seconds: number;
  shot_count: number;
};

export type EpisodeResponse = {
  ok: boolean;
  storyboard: Storyboard;
  storyboard_path: string;
  provider?: string;
  video_path?: string;
};

export type Project = {
  project_id: string;
  name: string;
  genre: string;
  platform: string;
  premise: string;
  default_duration_seconds: number;
  default_shot_count: number;
  default_style_id: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type Character = {
  character_id: string;
  project_id: string;
  name: string;
  role: string;
  appearance: string;
  personality: string;
  costume: string;
  reference_image: string;
  prompt_fragment: string;
  created_at: string;
  updated_at: string;
};

export type StyleTemplate = {
  style_id: string;
  project_id: string;
  name: string;
  base_prompt: string;
  negative_prompt: string;
  aspect_ratio: string;
  palette: string;
  camera_style: string;
  provider: string;
  created_at: string;
  updated_at: string;
};

export type ContinuityReferenceType = "character" | "prop" | "location" | "style" | "action";

export type ContinuityReference = {
  reference_id: string;
  project_id: string;
  reference_type: ContinuityReferenceType;
  name: string;
  description: string;
  prompt_fragment: string;
  reference_image: string;
  notes: string;
  created_at: string;
  updated_at: string;
};

export type ProjectEpisode = {
  episode_id: string;
  project_id: string;
  episode_no: number;
  title: string;
  premise: string;
  duration_seconds: number;
  shot_count: number;
  status: "draft" | "storyboarded" | "imaged" | "exported" | "failed";
  storyboard_path: string;
  video_path: string;
  error: string;
  created_at: string;
  updated_at: string;
};

export type OutputItem = {
  filename: string;
  video_path: string;
  size_bytes: number;
  updated_at: number;
};

export type JobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export type JobProvider = "mock" | "openai" | "comfyui";

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

export type JobStep = "storyboard" | "images" | "video";

export type JobItemStatus = "pending" | "running" | "completed" | "failed" | "cancelled" | "skipped";

export type JobItem = {
  episode_id: string;
  step: JobStep;
  status: JobItemStatus;
  error: string;
  output_path: string;
  started_at: string;
  finished_at: string;
};

export type Job = {
  job_id: string;
  project_id: string;
  episode_ids: string[];
  steps: JobStep[];
  provider: JobProvider;
  workflow_template: string;
  confirm_openai: boolean;
  status: JobStatus;
  progress: number;
  completed_steps: number;
  total_steps: number;
  current_episode_id: string;
  current_step: string;
  error: string;
  cancel_requested: boolean;
  created_at: string;
  updated_at: string;
  started_at: string;
  finished_at: string;
  items: JobItem[];
};

export type CreateJobRequest = {
  project_id: string;
  episode_ids: string[];
  steps: Array<JobStep | "full">;
  provider: JobProvider;
  workflow_template?: string;
  confirm_openai?: boolean;
};

export type ProjectEpisodeProductionResponse = {
  ok: boolean;
  episode: ProjectEpisode;
  storyboard?: Storyboard;
  storyboard_path?: string;
  provider?: string;
  video_path?: string;
};

export type DocumentAdaptRequest = {
  filename: string;
  content_base64?: string;
  text?: string;
  project_id: string;
  project_name: string;
  genre: string;
  platform: string;
  duration_seconds: number;
  shot_count: number;
  max_episodes: number;
  storyboard_provider: "local" | "openai";
  confirm_openai?: boolean;
};

export type DocumentImportRecord = {
  import_id: string;
  project_id: string;
  filename: string;
  content_type: string;
  text_length: number;
  cleaned_text_path: string;
  episode_ids: string[];
  settings: Record<string, unknown>;
  created_at: string;
};

export type DocumentAdaptResponse = {
  ok: boolean;
  import: DocumentImportRecord;
  project: Project;
  episodes: ProjectEpisode[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const data = (await response.json()) as { error?: string };
      if (data.error) detail = data.error;
    } catch {
      // Keep the HTTP status text when the response is not JSON.
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export const api = {
  status: () => request<StatusResponse>("/api/status"),
  logs: (service: "comfyui" | "launcher") => request<{ log: string }>(`/api/logs?service=${service}`),
  saveConfig: (config: Partial<PublicConfig>) =>
    request<{ config: PublicConfig }>("/api/config", { method: "POST", body: JSON.stringify(config) }),
  startComfy: () => request<{ status: string; pid?: number; base_url?: string }>("/api/comfyui/start", { method: "POST", body: "{}" }),
  stopComfy: () => request<{ status: string; pid?: number; base_url?: string }>("/api/comfyui/stop", { method: "POST", body: "{}" }),
  runOpenAITest: () => request<ScriptResult>("/api/openai/test", { method: "POST", body: "{}" }),
  runMockTest: () => request<ScriptResult>("/api/mock/test", { method: "POST", body: "{}" }),
  getEpisode: (projectId: string, episodeId: string) =>
    request<EpisodeResponse>(`/api/episode?project_id=${encodeURIComponent(projectId)}&episode_id=${encodeURIComponent(episodeId)}`),
  createStoryboard: (payload: EpisodeStoryboardRequest) =>
    request<EpisodeResponse>("/api/episode/storyboard", { method: "POST", body: JSON.stringify(payload) }),
  generateEpisodeImages: (projectId: string, episodeId: string, provider: JobProvider, confirmOpenai = false) =>
    request<EpisodeResponse>("/api/episode/images", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, episode_id: episodeId, provider, confirm_openai: confirmOpenai }),
    }),
  exportEpisodeVideo: (projectId: string, episodeId: string) =>
    request<EpisodeResponse>("/api/episode/video", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, episode_id: episodeId }),
    }),
  listProjects: () => request<{ ok: boolean; projects: Project[] }>("/api/projects"),
  saveProject: (project: Partial<Project>) =>
    request<{ ok: boolean; project: Project }>("/api/projects", { method: "POST", body: JSON.stringify(project) }),
  listCharacters: (projectId: string) =>
    request<{ ok: boolean; characters: Character[] }>(`/api/projects/${encodeURIComponent(projectId)}/characters`),
  saveCharacter: (projectId: string, character: Partial<Character>) =>
    request<{ ok: boolean; character: Character }>(`/api/projects/${encodeURIComponent(projectId)}/characters`, {
      method: "POST",
      body: JSON.stringify(character),
    }),
  listStyles: (projectId: string) =>
    request<{ ok: boolean; styles: StyleTemplate[] }>(`/api/projects/${encodeURIComponent(projectId)}/styles`),
  saveStyle: (projectId: string, style: Partial<StyleTemplate>) =>
    request<{ ok: boolean; style: StyleTemplate }>(`/api/projects/${encodeURIComponent(projectId)}/styles`, {
      method: "POST",
      body: JSON.stringify(style),
    }),
  listReferences: (projectId: string) =>
    request<{ ok: boolean; references: ContinuityReference[] }>(`/api/projects/${encodeURIComponent(projectId)}/references`),
  saveReference: (projectId: string, reference: Partial<ContinuityReference>) =>
    request<{ ok: boolean; reference: ContinuityReference }>(`/api/projects/${encodeURIComponent(projectId)}/references`, {
      method: "POST",
      body: JSON.stringify(reference),
    }),
  listWorkflowTemplates: () => request<{ ok: boolean; templates: WorkflowTemplate[] }>("/api/workflow-templates"),
  listProjectEpisodes: (projectId: string) =>
    request<{ ok: boolean; episodes: ProjectEpisode[] }>(`/api/projects/${encodeURIComponent(projectId)}/episodes`),
  createEpisodeBatch: (projectId: string, count: number, direction: string) =>
    request<{ ok: boolean; episodes: ProjectEpisode[] }>(`/api/projects/${encodeURIComponent(projectId)}/episodes/batch`, {
      method: "POST",
      body: JSON.stringify({ count, direction }),
    }),
  listOutputs: () => request<{ ok: boolean; outputs: OutputItem[] }>("/api/outputs"),
  listJobs: () => request<{ ok: boolean; jobs: Job[] }>("/api/jobs"),
  getJob: (jobId: string) => request<{ ok: boolean; job: Job }>(`/api/jobs/${encodeURIComponent(jobId)}`),
  createJob: (payload: CreateJobRequest) =>
    request<{ ok: boolean; job: Job }>("/api/jobs", { method: "POST", body: JSON.stringify(payload) }),
  cancelJob: (jobId: string) =>
    request<{ ok: boolean; job: Job }>(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST", body: "{}" }),
  retryJob: (jobId: string, confirmOpenai = false) =>
    request<{ ok: boolean; job: Job }>(`/api/jobs/${encodeURIComponent(jobId)}/retry`, {
      method: "POST",
      body: JSON.stringify({ confirm_openai: confirmOpenai }),
    }),
  retryFailedJob: (jobId: string, confirmOpenai = false) =>
    request<{ ok: boolean; job: Job }>(`/api/jobs/${encodeURIComponent(jobId)}/retry-failed`, {
      method: "POST",
      body: JSON.stringify({ confirm_openai: confirmOpenai }),
    }),
  retryJobEpisode: (jobId: string, episodeId: string, confirmOpenai = false) =>
    request<{ ok: boolean; job: Job }>(`/api/jobs/${encodeURIComponent(jobId)}/episodes/${encodeURIComponent(episodeId)}/retry`, {
      method: "POST",
      body: JSON.stringify({ confirm_openai: confirmOpenai }),
    }),
  retryJobEpisodeFromStep: (jobId: string, episodeId: string, step: JobStep, confirmOpenai = false) =>
    request<{ ok: boolean; job: Job }>(
      `/api/jobs/${encodeURIComponent(jobId)}/episodes/${encodeURIComponent(episodeId)}/steps/${encodeURIComponent(step)}/retry`,
      {
        method: "POST",
        body: JSON.stringify({ confirm_openai: confirmOpenai }),
      },
    ),
  createProjectStoryboard: (projectId: string, episodeId: string) =>
    request<ProjectEpisodeProductionResponse>(
      `/api/projects/${encodeURIComponent(projectId)}/episodes/${encodeURIComponent(episodeId)}/storyboard`,
      { method: "POST", body: "{}" },
    ),
  generateProjectEpisodeImages: (projectId: string, episodeId: string, provider: JobProvider, confirmOpenai = false) =>
    request<ProjectEpisodeProductionResponse>(
      `/api/projects/${encodeURIComponent(projectId)}/episodes/${encodeURIComponent(episodeId)}/images`,
      { method: "POST", body: JSON.stringify({ provider, confirm_openai: confirmOpenai }) },
    ),
  exportProjectEpisodeVideo: (projectId: string, episodeId: string) =>
    request<ProjectEpisodeProductionResponse>(
      `/api/projects/${encodeURIComponent(projectId)}/episodes/${encodeURIComponent(episodeId)}/video`,
      { method: "POST", body: "{}" },
    ),
  adaptDocument: (payload: DocumentAdaptRequest) =>
    request<DocumentAdaptResponse>("/api/imports/adapt", { method: "POST", body: JSON.stringify(payload) }),
  saveStoryboard: (projectId: string, episodeId: string, storyboard: Storyboard) =>
    request<EpisodeResponse>("/api/storyboard/save", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, episode_id: episodeId, storyboard }),
    }),
  snapshotStoryboardReview: (projectId: string, episodeId: string, note: string) =>
    request<EpisodeResponse>("/api/storyboard/review/snapshot", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, episode_id: episodeId, note }),
    }),
  updateStoryboardShot: (projectId: string, episodeId: string, shotId: string, updates: Partial<EpisodeShot>) =>
    request<EpisodeResponse>("/api/storyboard/shot/update", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, episode_id: episodeId, shot_id: shotId, updates }),
    }),
  rewriteStoryboardShot: (projectId: string, episodeId: string, shotId: string, instruction: string, provider: "local" | "openai", confirmOpenai = false) =>
    request<EpisodeResponse>("/api/storyboard/shot/rewrite", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, episode_id: episodeId, shot_id: shotId, instruction, provider, confirm_openai: confirmOpenai }),
    }),
  regenerateStoryboardShotImage: (projectId: string, episodeId: string, shotId: string, provider: JobProvider, workflowTemplate: string, confirmOpenai = false) =>
    request<EpisodeResponse>("/api/storyboard/shot/image", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, episode_id: episodeId, shot_id: shotId, provider, workflow_template: workflowTemplate, confirm_openai: confirmOpenai }),
    }),
};
