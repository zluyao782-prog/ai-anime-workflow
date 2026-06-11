import * as Tabs from "@radix-ui/react-tabs";
import clsx from "clsx";
import {
  Activity,
  Bot,
  CheckCircle2,
  Clapperboard,
  Layers3,
  ExternalLink,
  FileText,
  Image,
  KeyRound,
  Play,
  RefreshCw,
  Save,
  Server,
  Settings,
  Square,
  Upload,
  Video,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  Character,
  ContinuityReference,
  DocumentAdaptResponse,
  EpisodeStoryboardRequest,
  Job,
  JobItem,
  JobProvider,
  JobStep,
  LauncherStatus,
  OutputItem,
  Project,
  ProjectEpisode,
  PublicConfig,
  ScriptResult,
  Storyboard,
  StyleTemplate,
  WorkflowTemplate,
} from "./api";
import { navItems, TabValue } from "./navigation";

const defaultConfig: PublicConfig = {
  openai_api_key: "",
  openai_api_key_configured: false,
  openai_base_url: "https://aigate.zhixingjidian.cn",
  openai_image_model: "gpt-image-2",
  openai_text_model: "gpt-4.1-mini",
  openai_text_endpoint_mode: "chat_completions",
  ollama_text_model: "qwen2.5:0.5b",
  comfyui_mode: "local",
  comfyui_base_url: "http://127.0.0.1:8188",
  comfyui_remote_base_url: "",
  output_dir: "data/exports",
};

const defaultEpisodeForm: EpisodeStoryboardRequest = {
  project_id: "demo_drama",
  episode_id: "episode_001",
  genre: "悬疑",
  premise: "雨夜主角收到一封匿名信，信里写着明天会有人消失",
  protagonist: "年轻侦探林夏，黑发，冷静但敏锐",
  style_preset: "clean_anime_drama",
  platform: "douyin",
  duration_seconds: 30,
  shot_count: 6,
};

const defaultProjectDraft = {
  project_id: "demo_drama",
  name: "雨夜侦探",
  genre: "悬疑",
  platform: "douyin",
  premise: "雨夜主角收到匿名信，发现失踪案和自己有关",
  default_duration_seconds: 30,
  default_shot_count: 6,
  default_style_id: "clean_anime_drama",
};

const defaultCharacterDraft = {
  character_id: "hero",
  name: "林夏",
  role: "年轻侦探",
  appearance: "黑发，蓝色风衣，冷静敏锐",
  personality: "克制、观察力强",
  costume: "蓝色风衣",
  reference_image: "",
  prompt_fragment: "black hair, blue trench coat, calm detective",
};

const defaultStyleDraft = {
  style_id: "clean_anime_drama",
  name: "干净动漫短剧",
  base_prompt: "clean anime drama, cinematic lighting, vertical composition",
  negative_prompt: "low quality, blurry, inconsistent character",
  aspect_ratio: "9:16",
  palette: "冷蓝与暖黄对比",
  camera_style: "cinematic vertical shots",
  provider: "mock",
};

const defaultReferenceDraft = {
  reference_id: "rain_alley",
  reference_type: "location" as const,
  name: "雨夜小巷",
  description: "湿润反光的狭窄小巷，冷蓝路灯，远处有暖黄色窗光",
  prompt_fragment: "rainy narrow alley, wet reflective pavement, cool blue streetlight, warm window glow",
  reference_image: "",
  notes: "",
};

const defaultDocumentDraft = {
  filename: "story.txt",
  text: "雨夜主角收到匿名信，发现失踪案和自己有关。",
  project_id: "adapted_drama",
  project_name: "导入改编短剧",
  genre: "悬疑",
  platform: "douyin",
  duration_seconds: 60,
  shot_count: 8,
  max_episodes: 5,
  storyboard_provider: "local" as "local" | "openai",
};

export function App() {
  const [activeTab, setActiveTab] = useState<TabValue>("overview");
  const [status, setStatus] = useState<LauncherStatus | null>(null);
  const [config, setConfig] = useState<PublicConfig>(defaultConfig);
  const [configDraft, setConfigDraft] = useState<PublicConfig>(defaultConfig);
  const [apiKeyDraft, setApiKeyDraft] = useState("");
  const [serviceLog, setServiceLog] = useState("");
  const [imageLog, setImageLog] = useState("");
  const [videoLog, setVideoLog] = useState("");
  const [notice, setNotice] = useState("");
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [loadError, setLoadError] = useState("");
  const [episodeForm, setEpisodeForm] = useState<EpisodeStoryboardRequest>(defaultEpisodeForm);
  const [episodeProvider, setEpisodeProvider] = useState<JobProvider>("mock");
  const [episode, setEpisode] = useState<Storyboard | null>(null);
  const [episodeLog, setEpisodeLog] = useState("先生成分镜；图片阶段默认使用 mock，不会消耗真实 API。");
  const [projects, setProjects] = useState<Project[]>([]);
  const [currentProjectId, setCurrentProjectId] = useState(defaultProjectDraft.project_id);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [styles, setStyles] = useState<StyleTemplate[]>([]);
  const [references, setReferences] = useState<ContinuityReference[]>([]);
  const [workflowTemplates, setWorkflowTemplates] = useState<WorkflowTemplate[]>([]);
  const [projectEpisodes, setProjectEpisodes] = useState<ProjectEpisode[]>([]);
  const [outputs, setOutputs] = useState<OutputItem[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [selectedJobDetail, setSelectedJobDetail] = useState<Job | null>(null);
  const [projectDraft, setProjectDraft] = useState(defaultProjectDraft);
  const [characterDraft, setCharacterDraft] = useState(defaultCharacterDraft);
  const [styleDraft, setStyleDraft] = useState(defaultStyleDraft);
  const [referenceDraft, setReferenceDraft] = useState(defaultReferenceDraft);
  const [batchCount, setBatchCount] = useState(10);
  const [batchDirection, setBatchDirection] = useState("每集一个线索，结尾留下反转");
  const [selectedEpisodeIds, setSelectedEpisodeIds] = useState<string[]>([]);
  const [jobStepMode, setJobStepMode] = useState<"full" | JobStep>("full");
  const [jobProvider, setJobProvider] = useState<JobProvider>("mock");
  const [documentDraft, setDocumentDraft] = useState(defaultDocumentDraft);
  const [documentContentBase64, setDocumentContentBase64] = useState("");
  const [documentResult, setDocumentResult] = useState<DocumentAdaptResponse | null>(null);
  const [documentLog, setDocumentLog] = useState("导入 txt、markdown 或可复制文本 PDF，按短视频节奏自动分集并生成分镜。");
  const [reviewEpisodeId, setReviewEpisodeId] = useState(defaultEpisodeForm.episode_id);
  const [reviewStoryboard, setReviewStoryboard] = useState<Storyboard | null>(null);
  const [reviewShotId, setReviewShotId] = useState("");
  const [reviewInstruction, setReviewInstruction] = useState("更悬疑，结尾留钩子");
  const [reviewImageProvider, setReviewImageProvider] = useState<JobProvider>("mock");
  const [reviewWorkflowTemplate, setReviewWorkflowTemplate] = useState("mock_image");
  const [reviewSnapshotNote, setReviewSnapshotNote] = useState("审稿检查点");
  const [reviewLog, setReviewLog] = useState("选择项目和剧集，载入分镜后审稿。");
  const currentProjectIdRef = useRef(currentProjectId);

  const refreshStatus = async () => {
    const data = await api.status();
    setStatus(data.status);
    setConfig(data.config);
    setLoadError("");
  };

  const refreshLogs = async () => {
    const data = await api.logs("comfyui");
    setServiceLog(data.log || "暂无日志");
  };

  const refreshProjectLibrary = async (projectId = currentProjectId) => {
    const [projectData, outputData] = await Promise.all([api.listProjects(), api.listOutputs()]);
    setProjects(projectData.projects);
    setOutputs(outputData.outputs);
    if (!projectId) {
      setCharacters([]);
      setStyles([]);
      setReferences([]);
      setProjectEpisodes([]);
      return;
    }
    if (!projectData.projects.some((project) => project.project_id === projectId)) {
      setCharacters([]);
      setStyles([]);
      setReferences([]);
      setProjectEpisodes([]);
      return;
    }
    const [characterData, styleData, referenceData, episodeData] = await Promise.all([
      api.listCharacters(projectId).catch(() => ({ characters: [] as Character[] })),
      api.listStyles(projectId).catch(() => ({ styles: [] as StyleTemplate[] })),
      api.listReferences(projectId).catch(() => ({ references: [] as ContinuityReference[] })),
      api.listProjectEpisodes(projectId).catch(() => ({ episodes: [] as ProjectEpisode[] })),
    ]);
    if (projectId !== currentProjectIdRef.current) return;
    setCharacters(characterData.characters);
    setStyles(styleData.styles);
    setReferences(referenceData.references);
    setProjectEpisodes(episodeData.episodes);
  };

  const refreshJobs = async () => {
    const data = await api.listJobs();
    setJobs(data.jobs);
    if (selectedJobId) {
      const selected = data.jobs.find((job) => job.job_id === selectedJobId);
      if (selected) setSelectedJobDetail(selected);
    }
    return data.jobs;
  };

  const loadJobDetail = async (jobId: string) => {
    const data = await api.getJob(jobId);
    setSelectedJobId(jobId);
    setSelectedJobDetail(data.job);
    return data.job;
  };

  useEffect(() => {
    Promise.all([refreshStatus(), refreshProjectLibrary(), refreshJobs()]).catch((error: Error) => setLoadError(error.message));
    api.listWorkflowTemplates().then((data) => setWorkflowTemplates(data.templates)).catch((error: Error) => setNotice(error.message));
  }, []);

  useEffect(() => {
    setConfigDraft(config);
    setApiKeyDraft("");
  }, [config]);

  useEffect(() => {
    currentProjectIdRef.current = currentProjectId;
  }, [currentProjectId]);

  useEffect(() => {
    setSelectedEpisodeIds((current) => current.filter((episodeId) => projectEpisodes.some((episode) => episode.episode_id === episodeId)));
  }, [projectEpisodes]);

  useEffect(() => {
    const hasActiveJobs = jobs.some((job) => job.status === "queued" || job.status === "running");
    if (!hasActiveJobs) return;
    const timer = window.setInterval(() => {
      refreshJobs()
        .then((nextJobs) => {
          if (!nextJobs.some((job) => job.status === "queued" || job.status === "running")) {
            refreshProjectLibrary(currentProjectIdRef.current).catch((error: Error) => setNotice(error.message));
          }
        })
        .catch((error: Error) => setNotice(error.message));
    }, 2000);
    return () => window.clearInterval(timer);
  }, [jobs]);

  useEffect(() => {
    if (!selectedJobId || !selectedJobDetail) return;
    if (selectedJobDetail.status !== "queued" && selectedJobDetail.status !== "running") return;
    const timer = window.setInterval(() => {
      loadJobDetail(selectedJobId).catch((error: Error) => setNotice(error.message));
    }, 2000);
    return () => window.clearInterval(timer);
  }, [selectedJobId, selectedJobDetail]);

  const runBusy = async (name: string, action: () => Promise<void>) => {
    setBusyAction(name);
    setNotice("");
    try {
      await action();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusyAction(null);
    }
  };

  const startComfy = () =>
    runBusy("start-comfy", async () => {
      await api.startComfy();
      await wait(1800);
      await refreshStatus();
      await refreshLogs();
    });

  const stopComfy = () =>
    runBusy("stop-comfy", async () => {
      await api.stopComfy();
      await refreshStatus();
      await refreshLogs();
    });

  const testComfyConnection = () =>
    runBusy("test-comfy", async () => {
      await refreshStatus();
      setNotice("已刷新 ComfyUI 连接状态");
    });

  const saveConfig = (event: FormEvent<HTMLFormElement>) =>
    runBusy("save-config", async () => {
      event.preventDefault();
      const data: Record<string, string> = {
        openai_api_key: apiKeyDraft,
        openai_base_url: configDraft.openai_base_url,
        openai_image_model: configDraft.openai_image_model,
        openai_text_model: configDraft.openai_text_model,
        openai_text_endpoint_mode: configDraft.openai_text_endpoint_mode,
        ollama_text_model: configDraft.ollama_text_model,
        comfyui_mode: configDraft.comfyui_mode,
        comfyui_base_url: configDraft.comfyui_base_url,
        comfyui_remote_base_url: configDraft.comfyui_remote_base_url,
        output_dir: configDraft.output_dir,
      };
      if (!data.openai_api_key) delete data.openai_api_key;
      const result = await api.saveConfig(data);
      setConfig(result.config);
      setNotice("配置已保存");
      await refreshStatus();
    });

  const runImageTest = () =>
    runBusy("image-test", async () => {
      setImageLog("运行中...");
      const result = await api.runOpenAITest();
      setImageLog(formatScriptResult(result));
      await refreshStatus();
    });

  const runVideoTest = () =>
    runBusy("video-test", async () => {
      setVideoLog("运行中...");
      const result = await api.runMockTest();
      setVideoLog(formatScriptResult(result));
      await refreshStatus();
    });

  const loadEpisode = () =>
    runBusy("episode-load", async () => {
      const result = await api.getEpisode(episodeForm.project_id, episodeForm.episode_id);
      setEpisode(result.storyboard);
      setEpisodeLog(`已载入分镜：${result.storyboard_path}`);
    });

  const createStoryboard = (event: FormEvent<HTMLFormElement>) =>
    runBusy("episode-storyboard", async () => {
      event.preventDefault();
      const result = await api.createStoryboard(episodeForm);
      setEpisode(result.storyboard);
      setEpisodeLog(`分镜已生成：${result.storyboard_path}`);
    });

  const generateImages = () =>
    runBusy("episode-images", async () => {
      if (episodeProvider === "openai") {
        const estimatedImages = episode?.shots.length ?? episodeForm.shot_count;
        const confirmed = window.confirm(`将使用 gpt-image-2 API 生成 ${estimatedImages} 张图片，可能消耗真实额度，是否继续？`);
        if (!confirmed) {
          setNotice("已取消真实 API 图片生成。");
          return;
        }
      }
      const result = await api.generateEpisodeImages(
        episodeForm.project_id,
        episodeForm.episode_id,
        episodeProvider,
        episodeProvider === "openai",
      );
      setEpisode(result.storyboard);
      setEpisodeLog(`图片生成完成，provider=${result.provider || episodeProvider}，分镜已更新：${result.storyboard_path}`);
    });

  const exportVideo = () =>
    runBusy("episode-video", async () => {
      const result = await api.exportEpisodeVideo(episodeForm.project_id, episodeForm.episode_id);
      setEpisode(result.storyboard);
      setEpisodeLog(`视频已导出：${result.video_path}`);
    });

  const selectProject = (project: Project) => {
    currentProjectIdRef.current = project.project_id;
    setCurrentProjectId(project.project_id);
    setProjectDraft({
      project_id: project.project_id,
      name: project.name,
      genre: project.genre,
      platform: project.platform,
      premise: project.premise,
      default_duration_seconds: project.default_duration_seconds,
      default_shot_count: project.default_shot_count,
      default_style_id: project.default_style_id,
    });
    setEpisodeForm((current) => ({
      ...current,
      project_id: project.project_id,
      genre: project.genre || current.genre,
      platform: project.platform || current.platform,
      premise: project.premise || current.premise,
      style_preset: project.default_style_id || current.style_preset,
      duration_seconds: project.default_duration_seconds || current.duration_seconds,
      shot_count: project.default_shot_count || current.shot_count,
    }));
    refreshProjectLibrary(project.project_id).catch((error: Error) => setNotice(error.message));
  };

  const saveProjectDraft = (event: FormEvent<HTMLFormElement>) =>
    runBusy("project-save", async () => {
      event.preventDefault();
      const result = await api.saveProject(projectDraft);
      currentProjectIdRef.current = result.project.project_id;
      setCurrentProjectId(result.project.project_id);
      setProjectDraft({
        project_id: result.project.project_id,
        name: result.project.name,
        genre: result.project.genre,
        platform: result.project.platform,
        premise: result.project.premise,
        default_duration_seconds: result.project.default_duration_seconds,
        default_shot_count: result.project.default_shot_count,
        default_style_id: result.project.default_style_id,
      });
      setEpisodeForm((current) => ({ ...current, project_id: result.project.project_id }));
      setNotice("项目已保存");
      await refreshProjectLibrary(result.project.project_id);
    });

  const saveCharacterDraft = (event: FormEvent<HTMLFormElement>) =>
    runBusy("character-save", async () => {
      event.preventDefault();
      await api.saveCharacter(currentProjectId, characterDraft);
      setNotice("角色已保存");
      await refreshProjectLibrary(currentProjectId);
    });

  const saveStyleDraft = (event: FormEvent<HTMLFormElement>) =>
    runBusy("style-save", async () => {
      event.preventDefault();
      await api.saveStyle(currentProjectId, styleDraft);
      setNotice("风格模板已保存");
      await refreshProjectLibrary(currentProjectId);
    });

  const saveReferenceDraft = (event: FormEvent<HTMLFormElement>) =>
    runBusy("reference-save", async () => {
      event.preventDefault();
      await api.saveReference(currentProjectId, referenceDraft);
      setNotice("连续性素材已保存");
      await refreshProjectLibrary(currentProjectId);
    });

  const createBatchEpisodes = (event: FormEvent<HTMLFormElement>) =>
    runBusy("episode-batch", async () => {
      event.preventDefault();
      await api.createEpisodeBatch(currentProjectId, batchCount, batchDirection);
      setEpisodeLog(`已为 ${currentProjectId} 创建 ${batchCount} 集草稿。`);
      setNotice("剧集大纲已创建");
      await refreshProjectLibrary(currentProjectId);
    });

  const toggleEpisodeSelection = (episodeId: string, checked: boolean) => {
    setSelectedEpisodeIds((current) => {
      if (checked) return Array.from(new Set([...current, episodeId]));
      return current.filter((item) => item !== episodeId);
    });
  };

  const createProductionJob = () =>
    runBusy("job-create", async () => {
      if (!currentProjectId) throw new Error("请先选择项目");
      if (selectedEpisodeIds.length === 0) throw new Error("请先勾选要批量生产的剧集");
      const selectedEpisodes = projectEpisodes.filter((projectEpisode) => selectedEpisodeIds.includes(projectEpisode.episode_id));
      const estimatedImages = selectedEpisodes.reduce((sum, projectEpisode) => sum + projectEpisode.shot_count, 0);
      if (jobProvider === "openai") {
        const confirmed = window.confirm(
          `将使用 gpt-image-2 API 生产 ${selectedEpisodeIds.length} 集，预计最多调用 ${estimatedImages} 张图片。确认后可能消耗真实额度，是否继续？`,
        );
        if (!confirmed) {
          setNotice("已取消真实 API 任务，没有创建队列。");
          return;
        }
      }
      const result = await api.createJob({
        project_id: currentProjectId,
        episode_ids: selectedEpisodeIds,
        steps: [jobStepMode],
        provider: jobProvider,
        confirm_openai: jobProvider === "openai",
      });
      setEpisodeLog(`任务已加入队列：${result.job.job_id}`);
      setNotice("批量生产任务已创建");
      const nextJobs = await refreshJobs();
      if (!nextJobs.some((job) => job.status === "queued" || job.status === "running")) {
        await refreshProjectLibrary(currentProjectId);
      }
    });

  const cancelJob = (job: Job) =>
    runBusy(`job-cancel-${job.job_id}`, async () => {
      await api.cancelJob(job.job_id);
      await refreshJobs();
    });

  const retryJob = (job: Job) =>
    runBusy(`job-retry-${job.job_id}`, async () => {
      if (job.provider === "openai") {
        const confirmed = window.confirm(`将重试 gpt-image-2 API 任务 ${job.job_id}，可能继续消耗真实额度，是否继续？`);
        if (!confirmed) {
          setNotice("已取消真实 API 重试，没有创建新任务。");
          return;
        }
      }
      await api.retryJob(job.job_id, job.provider === "openai");
      await refreshJobs();
    });

  const confirmOpenAIRetry = (job: Job, label: string) => {
    if (job.provider !== "openai") return true;
    return window.confirm(`将重试 gpt-image-2 API 任务 ${label}，可能消耗真实额度，是否继续？`);
  };

  const retryFailedJob = (job: Job) =>
    runBusy(`job-retry-failed-${job.job_id}`, async () => {
      if (!confirmOpenAIRetry(job, `${job.job_id} 的失败步骤`)) {
        setNotice("已取消真实 API 重跑。");
        return;
      }
      const result = await api.retryFailedJob(job.job_id, job.provider === "openai");
      setNotice("失败步骤已加入重跑队列");
      setEpisodeLog(`已创建重跑任务：${result.job.job_id}`);
      await Promise.all([refreshJobs(), loadJobDetail(job.job_id)]);
    });

  const retryJobEpisode = (job: Job, episodeId: string) =>
    runBusy(`job-retry-episode-${job.job_id}-${episodeId}`, async () => {
      if (!confirmOpenAIRetry(job, `${job.job_id} / ${episodeId}`)) {
        setNotice("已取消真实 API 重跑。");
        return;
      }
      const result = await api.retryJobEpisode(job.job_id, episodeId, job.provider === "openai");
      setNotice("本集已加入重跑队列");
      setEpisodeLog(`已创建重跑任务：${result.job.job_id}`);
      await Promise.all([refreshJobs(), loadJobDetail(job.job_id)]);
    });

  const retryJobEpisodeFromStep = (job: Job, episodeId: string, step: JobStep) =>
    runBusy(`job-retry-step-${job.job_id}-${episodeId}-${step}`, async () => {
      if (!confirmOpenAIRetry(job, `${job.job_id} / ${episodeId} / ${jobStepLabel(step)}`)) {
        setNotice("已取消真实 API 重跑。");
        return;
      }
      const result = await api.retryJobEpisodeFromStep(job.job_id, episodeId, step, job.provider === "openai");
      setNotice("指定步骤已加入重跑队列");
      setEpisodeLog(`已创建重跑任务：${result.job.job_id}`);
      await Promise.all([refreshJobs(), loadJobDetail(job.job_id)]);
    });

  const createProjectEpisodeStoryboard = (projectEpisode: ProjectEpisode) =>
    runBusy(`project-storyboard-${projectEpisode.episode_id}`, async () => {
      const result = await api.createProjectStoryboard(projectEpisode.project_id, projectEpisode.episode_id);
      if (result.storyboard) setEpisode(result.storyboard);
      setEpisodeForm((current) => ({
        ...current,
        project_id: projectEpisode.project_id,
        episode_id: projectEpisode.episode_id,
        title: result.storyboard?.title ?? projectEpisode.title,
        premise: result.storyboard?.premise ?? projectEpisode.premise,
        duration_seconds: result.storyboard?.duration_seconds ?? projectEpisode.duration_seconds,
        shot_count: result.storyboard?.shot_count ?? projectEpisode.shot_count,
      }));
      setEpisodeLog(`项目分镜已生成：${result.storyboard_path || projectEpisode.storyboard_path}`);
      await refreshProjectLibrary(projectEpisode.project_id);
    });

  const generateProjectImages = (projectEpisode: ProjectEpisode) =>
    runBusy(`project-images-${projectEpisode.episode_id}`, async () => {
      if (episodeProvider === "openai") {
        const confirmed = window.confirm(`将使用 gpt-image-2 API 为 ${projectEpisode.title} 生成 ${projectEpisode.shot_count} 张图片，可能消耗真实额度，是否继续？`);
        if (!confirmed) {
          setNotice("已取消真实 API 图片生成。");
          return;
        }
      }
      const result = await api.generateProjectEpisodeImages(
        projectEpisode.project_id,
        projectEpisode.episode_id,
        episodeProvider,
        episodeProvider === "openai",
      );
      if (result.storyboard) setEpisode(result.storyboard);
      setEpisodeLog(`项目图片生成完成，provider=${result.provider || episodeProvider}。`);
      await refreshProjectLibrary(projectEpisode.project_id);
    });

  const exportProjectVideo = (projectEpisode: ProjectEpisode) =>
    runBusy(`project-video-${projectEpisode.episode_id}`, async () => {
      const result = await api.exportProjectEpisodeVideo(projectEpisode.project_id, projectEpisode.episode_id);
      if (result.storyboard) setEpisode(result.storyboard);
      setEpisodeLog(`项目视频已导出：${result.video_path || result.episode.video_path}`);
      await refreshProjectLibrary(projectEpisode.project_id);
    });

  const selectDocumentFile = (file: File | null) =>
    runBusy("document-file", async () => {
      if (!file) return;
      const content = await file.arrayBuffer();
      setDocumentContentBase64(arrayBufferToBase64(content));
      setDocumentDraft((current) => ({ ...current, filename: file.name, text: "" }));
      setDocumentLog(`已载入文件：${file.name}，${formatBytes(file.size)}`);
    });

  const adaptDocument = () =>
    runBusy("document-adapt", async () => {
      if (documentDraft.storyboard_provider === "openai") {
        const confirmed = window.confirm("将调用外部文本 API 生成分镜，可能消耗额度。是否继续？");
        if (!confirmed) {
          setNotice("已取消外部文本 API 分镜生成。");
          return;
        }
      }
      const payload = {
        ...documentDraft,
        content_base64: documentContentBase64 || undefined,
        text: documentContentBase64 ? undefined : documentDraft.text,
        confirm_openai: documentDraft.storyboard_provider === "openai",
      };
      const result = await api.adaptDocument(payload);
      setDocumentResult(result);
      setDocumentLog(`已生成 ${result.episodes.length} 集，导入记录：${result.import.import_id}`);
      currentProjectIdRef.current = result.project.project_id;
      setCurrentProjectId(result.project.project_id);
      await refreshProjectLibrary(result.project.project_id);
    });

  const loadReviewStoryboard = () =>
    runBusy("review-load", async () => {
      const result = await api.getEpisode(currentProjectId, reviewEpisodeId);
      setReviewStoryboard(result.storyboard);
      setReviewShotId(result.storyboard.shots[0]?.shot_id ?? "");
      setReviewWorkflowTemplate(result.storyboard.shots[0]?.workflow_template ?? "mock_image");
      setReviewLog(`已载入分镜：${result.storyboard_path}`);
    });

  const saveReviewStoryboard = () =>
    runBusy("review-save", async () => {
      if (!reviewStoryboard) throw new Error("请先载入分镜");
      const result = await api.saveStoryboard(currentProjectId, reviewEpisodeId, reviewStoryboard);
      setReviewStoryboard(result.storyboard);
      setReviewLog(`分镜已保存：${result.storyboard_path}`);
      await refreshProjectLibrary(currentProjectId);
    });

  const snapshotReviewStoryboard = () =>
    runBusy("review-snapshot", async () => {
      if (!reviewStoryboard) throw new Error("请先载入分镜");
      await api.saveStoryboard(currentProjectId, reviewEpisodeId, reviewStoryboard);
      const result = await api.snapshotStoryboardReview(currentProjectId, reviewEpisodeId, reviewSnapshotNote);
      setReviewStoryboard(result.storyboard);
      setReviewLog(`审稿版本已保存：${result.storyboard.review_versions?.slice(-1)[0]?.version_id ?? ""}`);
      await refreshProjectLibrary(currentProjectId);
    });

  const updateReviewStoryboard = (updates: Partial<Storyboard>) => {
    setReviewStoryboard((current) => (current ? { ...current, ...updates } : current));
  };

  const updateReviewShot = (shotId: string, updates: Partial<Storyboard["shots"][number]>) => {
    setReviewStoryboard((current) => {
      if (!current) return current;
      return {
        ...current,
        shots: current.shots.map((shot) => (shot.shot_id === shotId ? { ...shot, ...updates } : shot)),
      };
    });
  };

  const toggleReviewReferenceBinding = (referenceId: string, checked: boolean) => {
    if (!reviewShotId) return;
    const existing = currentReviewShot?.reference_bindings ?? [];
    const next = checked ? Array.from(new Set([...existing, referenceId])) : existing.filter((item) => item !== referenceId);
    updateReviewShot(reviewShotId, { reference_bindings: next });
  };

  const rewriteReviewShot = () =>
    runBusy("review-rewrite-shot", async () => {
      if (!reviewStoryboard) throw new Error("请先载入分镜");
      if (!reviewShotId) throw new Error("请选择要重写的镜头");
      const result = await api.rewriteStoryboardShot(currentProjectId, reviewEpisodeId, reviewShotId, reviewInstruction, "local");
      setReviewStoryboard(result.storyboard);
      setReviewLog(`已本地重写镜头：${reviewShotId}`);
    });

  const regenerateReviewShotImage = () =>
    runBusy("review-regenerate-shot-image", async () => {
      if (!reviewStoryboard) throw new Error("请先载入分镜");
      if (!reviewShotId) throw new Error("请选择要生成图片的镜头");
      if (reviewImageProvider === "openai") {
        const confirmed = window.confirm("将调用外部图片 API 重新生成当前镜头，可能消耗额度。是否继续？");
        if (!confirmed) {
          setNotice("已取消外部图片 API 单镜头生成。");
          return;
        }
      }
      const result = await api.regenerateStoryboardShotImage(
        currentProjectId,
        reviewEpisodeId,
        reviewShotId,
        reviewImageProvider,
        reviewWorkflowTemplate,
        reviewImageProvider === "openai",
      );
      setReviewStoryboard(result.storyboard);
      setReviewLog(`已重生成镜头图片：${reviewShotId} / ${result.provider ?? reviewImageProvider}`);
      await refreshProjectLibrary(currentProjectId);
    });

  const disk = status?.disk["/mnt/d"];
  const statusCards = useMemo(() => buildStatusCards(status, config), [status, config]);
  const imageReadyCount = episode?.shots.filter((shot) => Boolean(shot.anime_image)).length ?? 0;
  const currentProject = projects.find((project) => project.project_id === currentProjectId);
  const currentProjectJobs = jobs.filter((job) => job.project_id === currentProjectId);
  const selectedImageEstimate = projectEpisodes
    .filter((projectEpisode) => selectedEpisodeIds.includes(projectEpisode.episode_id))
    .reduce((sum, projectEpisode) => sum + projectEpisode.shot_count, 0);
  const currentReviewShot = reviewStoryboard?.shots.find((shot) => shot.shot_id === reviewShotId) ?? null;
  const activeNavItem = navItems.find((item) => item.value === activeTab) ?? navItems[0];
  const ActiveIcon = activeNavItem.icon;
  const runningJobs = jobs.filter((job) => job.status === "queued" || job.status === "running").length;
  const comfyMode = config.comfyui_mode ?? "local";
  const comfyEffectiveUrl = comfyMode === "remote" ? config.comfyui_remote_base_url || config.comfyui_base_url : config.comfyui_base_url;
  const readyEpisodes = projectEpisodes.filter((projectEpisode) => projectEpisode.status === "exported").length;
  const draftedEpisodes = projectEpisodes.filter((projectEpisode) => Boolean(projectEpisode.storyboard_path)).length;
  const imagedEpisodes = projectEpisodes.filter((projectEpisode) => projectEpisode.status === "imaged" || projectEpisode.status === "exported").length;
  const failedEpisodes = projectEpisodes.filter((projectEpisode) => projectEpisode.status === "failed").length;
  const reviewBoundReferences = currentReviewShot?.reference_bindings?.length ?? 0;
  const reviewRerunCount = currentReviewShot?.rerun_history?.length ?? 0;
  const reviewSummary = reviewStoryboard?.shots.reduce(
    (summary, shot) => {
      const status = shot.review_status ?? "pending";
      summary[status] += 1;
      return summary;
    },
    { pending: 0, approved: 0, rejected: 0, revise: 0 },
  ) ?? { pending: 0, approved: 0, rejected: 0, revise: 0 };
  const nextAction = !currentProject
    ? { label: "创建项目", detail: "先建立作品设定、题材和默认风格。", tab: "projects" as TabValue, icon: Clapperboard }
    : projectEpisodes.length === 0
      ? { label: "导入文档", detail: "把故事文本拆成剧集草稿和第一版分镜。", tab: "document-adapt" as TabValue, icon: Upload }
      : draftedEpisodes < projectEpisodes.length
        ? { label: "生成分镜", detail: "把未完成草稿推进到可审稿状态。", tab: "episode-studio" as TabValue, icon: FileText }
        : imagedEpisodes < projectEpisodes.length
          ? { label: "打开审稿", detail: "检查镜头连续性、绑定素材并重跑图片。", tab: "storyboard-review" as TabValue, icon: Layers3 }
          : { label: "查看成品", detail: "检查导出结果，准备发布或继续批量生产。", tab: "outputs" as TabValue, icon: Video };

  if (loadError && !status) {
    return <pre className="m-4 rounded-ui border border-red-200 bg-red-50 p-4 text-sm text-red-700">启动器加载失败：{loadError}</pre>;
  }

  return (
    <Tabs.Root value={activeTab} onValueChange={(value) => setActiveTab(value as TabValue)} className="min-h-screen bg-surface text-ink-900">
      <div className="grid min-h-screen grid-cols-[272px_minmax(0,1fr)] max-[900px]:grid-cols-1">
        <aside className="sticky top-0 h-screen border-r border-slate-950/10 bg-[#121821] px-3.5 py-4 text-slate-100 max-[900px]:z-30 max-[900px]:h-auto max-[900px]:border-b max-[900px]:border-r-0 max-[900px]:py-3">
          <div className="flex items-center gap-3 border-b border-white/10 px-1 pb-4">
            <div className="grid h-10 w-10 place-items-center rounded-ui border border-teal-300/30 bg-teal-400/15 font-mono text-sm font-bold text-teal-200">AI</div>
            <div>
              <div className="text-sm font-semibold text-white">动漫工作台</div>
              <div className="font-mono text-[11px] text-slate-400">Local Production Suite</div>
            </div>
          </div>
          <div className="my-4 rounded-ui border border-white/10 bg-white/[0.04] p-3 max-[900px]:hidden">
            <div className="text-[11px] font-medium text-slate-400">当前项目</div>
            <div className="mt-1 truncate text-sm font-semibold text-white">{currentProject?.name ?? "未选择项目"}</div>
            <div className="mt-1 truncate font-mono text-[11px] text-slate-400">{currentProjectId}</div>
          </div>
          <Tabs.List className="grid gap-1 max-[900px]:mt-3 max-[900px]:flex max-[900px]:overflow-x-auto max-[900px]:pb-1" aria-label="主导航">
            {navItems.map((item) => (
              <Tabs.Trigger
                key={item.value}
                value={item.value}
                className="group flex h-11 items-center gap-2.5 rounded-ui px-3 text-left text-sm text-slate-300 outline-none transition hover:bg-white/10 hover:text-white data-[state=active]:bg-white data-[state=active]:text-slate-950 focus-visible:ring-4 focus-visible:ring-teal-300/25 max-[900px]:shrink-0"
              >
                <item.icon className="h-4 w-4 shrink-0" />
                {item.label}
              </Tabs.Trigger>
            ))}
          </Tabs.List>
          <div className="mt-4 grid grid-cols-2 gap-2 border-t border-white/10 pt-4 text-[11px] max-[900px]:hidden">
            <div className="rounded-ui bg-white/[0.04] px-2.5 py-2">
              <div className="text-slate-400">剧集</div>
              <div className="mt-1 font-mono text-sm text-white">{projectEpisodes.length}</div>
            </div>
            <div className="rounded-ui bg-white/[0.04] px-2.5 py-2">
              <div className="text-slate-400">任务</div>
              <div className="mt-1 font-mono text-sm text-white">{runningJobs}</div>
            </div>
          </div>
        </aside>

        <main className="min-w-0 px-6 pb-8 max-[760px]:px-4">
          <header className="sticky top-0 z-20 -mx-6 mb-5 border-b border-line bg-surface/95 px-6 py-4 backdrop-blur max-[900px]:top-auto max-[760px]:-mx-4 max-[760px]:px-4">
            <div className="flex items-start justify-between gap-6 max-[860px]:grid">
              <div className="min-w-0">
                <div className="inline-flex items-center gap-2 rounded-ui border border-line bg-white px-2.5 py-1 text-xs font-medium text-ink-700 shadow-sm">
                  <ActiveIcon className="h-3.5 w-3.5 text-teal-600" />
                  {activeNavItem.label}
                </div>
                <h1 className="mt-2 text-balance text-2xl font-semibold leading-tight text-ink-900">把短剧从分镜推进到可发布成片</h1>
                <p className="mt-1 text-sm text-ink-500">项目、素材、分镜、任务和导出集中在一个本地工作台。</p>
              </div>
              <div className="flex flex-wrap items-center justify-end gap-2 max-[860px]:justify-start">
                <Button
                  variant="secondary"
                  onClick={() =>
                    runBusy("refresh", async () => {
                      await Promise.all([refreshStatus(), refreshProjectLibrary(currentProjectId)]);
                    })
                  }
                  busy={busyAction === "refresh"}
                  icon={RefreshCw}
                >
                  刷新状态
                </Button>
                <Button onClick={startComfy} busy={busyAction === "start-comfy"} icon={Play}>
                  启动 ComfyUI
                </Button>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-4 gap-2 max-[1100px]:grid-cols-2 max-[560px]:grid-cols-1">
              <HeaderMetric label="项目" value={String(projects.length)} />
              <HeaderMetric label="本项目剧集" value={String(projectEpisodes.length)} />
              <HeaderMetric label="连续性素材" value={String(references.length)} />
              <HeaderMetric label="运行中任务" value={String(runningJobs)} />
            </div>
          </header>

          {notice && <div className="mb-3 rounded-ui border border-teal-200 bg-teal-50 px-3 py-2 text-sm text-teal-900 shadow-sm">{notice}</div>}

          <Tabs.Content value="overview">
            <section className="grid grid-cols-[1.35fr_0.65fr] gap-4 max-[1020px]:grid-cols-1">
              <ProductionCommand
                projectName={currentProject?.name ?? "未选择项目"}
                projectId={currentProjectId}
                episodeCount={projectEpisodes.length}
                readyEpisodes={readyEpisodes}
                runningJobs={runningJobs}
                failedEpisodes={failedEpisodes}
                onDocument={() => setActiveTab("document-adapt")}
                onReview={() => setActiveTab("storyboard-review")}
                onQueue={() => setActiveTab("episode-studio")}
              />
              <NextActionCard
                label={nextAction.label}
                detail={nextAction.detail}
                icon={nextAction.icon}
                onClick={() => setActiveTab(nextAction.tab)}
              />
            </section>
            <section className="mt-4 grid grid-cols-4 gap-4 max-[1100px]:grid-cols-2 max-[640px]:grid-cols-1">
              {statusCards.map((card) => (
                <StatusCard key={card.title} {...card} />
              ))}
            </section>
            <section className="mt-4 grid grid-cols-[1.2fr_0.8fr] gap-4 max-[900px]:grid-cols-1">
              <Panel title="安装路径" icon={FileText}>
                <dl className="grid gap-2 text-xs">
                  {Object.entries(status?.paths ?? {}).map(([key, value]) => (
                    <div key={key} className="grid grid-cols-[140px_minmax(0,1fr)] gap-3">
                      <dt className="text-ink-500">{key}</dt>
                      <dd className="m-0 break-all font-mono">{value}</dd>
                    </div>
                  ))}
                </dl>
              </Panel>
              <Panel title="D 盘空间" icon={Server}>
                <div className="font-mono text-xs text-ink-700">
                  {disk ? `总计 ${disk.total_gb}GB / 已用 ${disk.used_gb}GB / 可用 ${disk.free_gb}GB` : "等待状态刷新"}
                </div>
              </Panel>
            </section>
          </Tabs.Content>

          <Tabs.Content value="projects">
            <section className="grid grid-cols-[380px_minmax(0,1fr)] gap-4 max-[980px]:grid-cols-1">
              <Panel title="项目设置" icon={Clapperboard}>
                <form onSubmit={saveProjectDraft} className="grid gap-3">
                  <Field label="项目 ID">
                    <input className="input" value={projectDraft.project_id} onChange={(event) => setProjectDraft({ ...projectDraft, project_id: event.target.value })} />
                  </Field>
                  <Field label="项目名称">
                    <input className="input" value={projectDraft.name} onChange={(event) => setProjectDraft({ ...projectDraft, name: event.target.value })} />
                  </Field>
                  <div className="grid grid-cols-2 gap-2">
                    <Field label="题材">
                      <input className="input" value={projectDraft.genre} onChange={(event) => setProjectDraft({ ...projectDraft, genre: event.target.value })} />
                    </Field>
                    <Field label="平台">
                      <select className="input" value={projectDraft.platform} onChange={(event) => setProjectDraft({ ...projectDraft, platform: event.target.value })}>
                        <option value="douyin">抖音</option>
                        <option value="bilibili">B站</option>
                        <option value="kuaishou">快手</option>
                        <option value="xiaohongshu">小红书</option>
                      </select>
                    </Field>
                  </div>
                  <Field label="系列设定">
                    <textarea className="input min-h-[96px] resize-y py-2 leading-6" value={projectDraft.premise} onChange={(event) => setProjectDraft({ ...projectDraft, premise: event.target.value })} />
                  </Field>
                  <div className="grid grid-cols-2 gap-2">
                    <Field label="默认时长秒">
                      <input className="input" type="number" min={3} max={180} value={projectDraft.default_duration_seconds} onChange={(event) => setProjectDraft({ ...projectDraft, default_duration_seconds: Number(event.target.value) })} />
                    </Field>
                    <Field label="默认分镜数">
                      <input className="input" type="number" min={1} max={24} value={projectDraft.default_shot_count} onChange={(event) => setProjectDraft({ ...projectDraft, default_shot_count: Number(event.target.value) })} />
                    </Field>
                  </div>
                  <Field label="默认风格 ID">
                    <input className="input" value={projectDraft.default_style_id} onChange={(event) => setProjectDraft({ ...projectDraft, default_style_id: event.target.value })} />
                  </Field>
                  <Button type="submit" busy={busyAction === "project-save"} icon={Save}>
                    保存项目
                  </Button>
                </form>
              </Panel>

              <Panel title="项目列表" icon={FileText} action={<Button variant="secondary" size="sm" onClick={() => runBusy("project-refresh", () => refreshProjectLibrary(currentProjectId))} busy={busyAction === "project-refresh"} icon={RefreshCw}>刷新</Button>}>
                {projects.length ? (
                  <div className="grid gap-2">
                    {projects.map((project) => (
                      <button
                        key={project.project_id}
                        type="button"
                        className={clsx(
                          "rounded-ui border bg-white p-4 text-left shadow-sm transition hover:border-slate-300 hover:bg-slate-50 hover:shadow-panel focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-100",
                          project.project_id === currentProjectId ? "border-teal-300 bg-teal-50" : "border-line",
                        )}
                        onClick={() => selectProject(project)}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="text-sm font-semibold">{project.name}</div>
                          <span className="rounded-ui bg-slate-100 px-2 py-1 text-xs text-ink-500">{project.status}</span>
                        </div>
                        <div className="mt-1 font-mono text-xs text-ink-500">{project.project_id} / {project.genre} / {project.platform}</div>
                        <div className="mt-2 line-clamp-2 text-sm leading-6 text-ink-700">{project.premise || "未填写系列设定"}</div>
                        <div className="mt-2 font-mono text-[11px] text-ink-500">更新：{formatTime(project.updated_at)}</div>
                      </button>
                    ))}
                  </div>
                ) : (
                  <EmptyState text="暂无项目，先保存左侧项目设置。" />
                )}
              </Panel>
            </section>
          </Tabs.Content>

          <Tabs.Content value="characters">
            <section className="grid grid-cols-[380px_minmax(0,1fr)] gap-4 max-[980px]:grid-cols-1">
              <Panel title={`角色设定 / ${currentProjectId}`} icon={Bot}>
                <form onSubmit={saveCharacterDraft} className="grid gap-3">
                  <Field label="角色 ID">
                    <input className="input" value={characterDraft.character_id} onChange={(event) => setCharacterDraft({ ...characterDraft, character_id: event.target.value })} />
                  </Field>
                  <div className="grid grid-cols-2 gap-2">
                    <Field label="姓名">
                      <input className="input" value={characterDraft.name} onChange={(event) => setCharacterDraft({ ...characterDraft, name: event.target.value })} />
                    </Field>
                    <Field label="身份">
                      <input className="input" value={characterDraft.role} onChange={(event) => setCharacterDraft({ ...characterDraft, role: event.target.value })} />
                    </Field>
                  </div>
                  <Field label="外观">
                    <textarea className="input min-h-[80px] resize-y py-2 leading-6" value={characterDraft.appearance} onChange={(event) => setCharacterDraft({ ...characterDraft, appearance: event.target.value })} />
                  </Field>
                  <Field label="性格">
                    <textarea className="input min-h-[72px] resize-y py-2 leading-6" value={characterDraft.personality} onChange={(event) => setCharacterDraft({ ...characterDraft, personality: event.target.value })} />
                  </Field>
                  <Field label="服装">
                    <input className="input" value={characterDraft.costume} onChange={(event) => setCharacterDraft({ ...characterDraft, costume: event.target.value })} />
                  </Field>
                  <Field label="Prompt 片段">
                    <textarea className="input min-h-[72px] resize-y py-2 leading-6" value={characterDraft.prompt_fragment} onChange={(event) => setCharacterDraft({ ...characterDraft, prompt_fragment: event.target.value })} />
                  </Field>
                  <Button type="submit" busy={busyAction === "character-save"} icon={Save} disabled={!currentProjectId}>
                    保存角色
                  </Button>
                </form>
              </Panel>
              <Panel title="当前项目角色" icon={FileText}>
                {characters.length ? (
                  <div className="grid gap-2">
                    {characters.map((character) => (
                      <article key={character.character_id} className="rounded-ui border border-line bg-white p-4 shadow-sm">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="text-sm font-semibold">{character.name}</div>
                          <span className="font-mono text-xs text-ink-500">{character.character_id}</span>
                        </div>
                        <div className="mt-1 text-xs text-ink-500">{character.role}</div>
                        <div className="mt-2 text-sm leading-6">{character.appearance}</div>
                        <div className="mt-2 text-sm leading-6 text-ink-600">{character.personality}</div>
                        <div className="mt-2 break-all font-mono text-xs leading-5 text-ink-500">{character.prompt_fragment || character.costume}</div>
                      </article>
                    ))}
                  </div>
                ) : (
                  <EmptyState text="当前项目还没有角色。" />
                )}
              </Panel>
            </section>
          </Tabs.Content>

          <Tabs.Content value="styles">
            <section className="grid grid-cols-[380px_minmax(0,1fr)] gap-4 max-[980px]:grid-cols-1">
              <Panel title={`风格模板 / ${currentProjectId}`} icon={Image}>
                <form onSubmit={saveStyleDraft} className="grid gap-3">
                  <Field label="模板 ID">
                    <input className="input" value={styleDraft.style_id} onChange={(event) => setStyleDraft({ ...styleDraft, style_id: event.target.value })} />
                  </Field>
                  <Field label="名称">
                    <input className="input" value={styleDraft.name} onChange={(event) => setStyleDraft({ ...styleDraft, name: event.target.value })} />
                  </Field>
                  <Field label="基础 Prompt">
                    <textarea className="input min-h-[96px] resize-y py-2 leading-6" value={styleDraft.base_prompt} onChange={(event) => setStyleDraft({ ...styleDraft, base_prompt: event.target.value })} />
                  </Field>
                  <Field label="负面 Prompt">
                    <textarea className="input min-h-[80px] resize-y py-2 leading-6" value={styleDraft.negative_prompt} onChange={(event) => setStyleDraft({ ...styleDraft, negative_prompt: event.target.value })} />
                  </Field>
                  <div className="grid grid-cols-2 gap-2">
                    <Field label="画幅">
                      <input className="input" value={styleDraft.aspect_ratio} onChange={(event) => setStyleDraft({ ...styleDraft, aspect_ratio: event.target.value })} />
                    </Field>
                    <Field label="Provider">
                      <select className="input" value={styleDraft.provider} onChange={(event) => setStyleDraft({ ...styleDraft, provider: event.target.value })}>
                        <option value="mock">mock</option>
                        <option value="openai">openai</option>
                      </select>
                    </Field>
                  </div>
                  <Field label="色彩">
                    <input className="input" value={styleDraft.palette} onChange={(event) => setStyleDraft({ ...styleDraft, palette: event.target.value })} />
                  </Field>
                  <Field label="镜头风格">
                    <input className="input" value={styleDraft.camera_style} onChange={(event) => setStyleDraft({ ...styleDraft, camera_style: event.target.value })} />
                  </Field>
                  <Button type="submit" busy={busyAction === "style-save"} icon={Save} disabled={!currentProjectId}>
                    保存模板
                  </Button>
                </form>
              </Panel>
              <Panel title="当前项目模板" icon={FileText}>
                {styles.length ? (
                  <div className="grid gap-2">
                    {styles.map((style) => (
                      <article key={style.style_id} className="rounded-ui border border-line bg-white p-4 shadow-sm">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="text-sm font-semibold">{style.name}</div>
                          <span className="font-mono text-xs text-ink-500">{style.style_id} / {style.aspect_ratio}</span>
                        </div>
                        <div className="mt-2 break-all font-mono text-xs leading-5 text-ink-600">{style.base_prompt}</div>
                        <div className="mt-2 break-all font-mono text-xs leading-5 text-ink-500">{style.negative_prompt}</div>
                      </article>
                    ))}
                  </div>
                ) : (
                  <EmptyState text="当前项目还没有风格模板。" />
                )}
              </Panel>
            </section>
          </Tabs.Content>

          <Tabs.Content value="document-adapt">
            <section className="grid grid-cols-[420px_minmax(0,1fr)] gap-4 max-[1080px]:grid-cols-1">
              <Panel title="文档导入" icon={Upload}>
                <div className="grid gap-3">
                  <Field label="源文件">
                    <input
                      className="input py-1.5"
                      type="file"
                      accept=".txt,.md,.markdown,.pdf"
                      onChange={(event) => selectDocumentFile(event.target.files?.[0] ?? null)}
                    />
                  </Field>
                  <Field label="或粘贴文本">
                    <textarea
                      className="input min-h-[160px] resize-y py-2 leading-6"
                      value={documentDraft.text}
                      onChange={(event) => {
                        setDocumentContentBase64("");
                        setDocumentDraft({ ...documentDraft, text: event.target.value, filename: "pasted.txt" });
                      }}
                    />
                  </Field>
                  <div className="grid grid-cols-2 gap-2">
                    <Field label="项目 ID">
                      <input className="input" value={documentDraft.project_id} onChange={(event) => setDocumentDraft({ ...documentDraft, project_id: event.target.value })} />
                    </Field>
                    <Field label="项目名称">
                      <input className="input" value={documentDraft.project_name} onChange={(event) => setDocumentDraft({ ...documentDraft, project_name: event.target.value })} />
                    </Field>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <Field label="题材">
                      <input className="input" value={documentDraft.genre} onChange={(event) => setDocumentDraft({ ...documentDraft, genre: event.target.value })} />
                    </Field>
                    <Field label="平台">
                      <select className="input" value={documentDraft.platform} onChange={(event) => setDocumentDraft({ ...documentDraft, platform: event.target.value })}>
                        <option value="douyin">抖音</option>
                        <option value="bilibili">B站</option>
                      </select>
                    </Field>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <Field label="每集时长">
                      <select className="input" value={documentDraft.duration_seconds} onChange={(event) => setDocumentDraft({ ...documentDraft, duration_seconds: Number(event.target.value) })}>
                        <option value={30}>30 秒</option>
                        <option value={60}>60 秒</option>
                        <option value={90}>90 秒</option>
                        <option value={180}>180 秒</option>
                      </select>
                    </Field>
                    <Field label="镜头数">
                      <select className="input" value={documentDraft.shot_count} onChange={(event) => setDocumentDraft({ ...documentDraft, shot_count: Number(event.target.value) })}>
                        <option value={6}>6 镜</option>
                        <option value={8}>8 镜</option>
                        <option value={12}>12 镜</option>
                      </select>
                    </Field>
                    <Field label="最多集数">
                      <input className="input" type="number" min={1} max={50} value={documentDraft.max_episodes} onChange={(event) => setDocumentDraft({ ...documentDraft, max_episodes: Number(event.target.value) })} />
                    </Field>
                  </div>
                  <Field label="分镜生成">
                    <select className="input" value={documentDraft.storyboard_provider} onChange={(event) => setDocumentDraft({ ...documentDraft, storyboard_provider: event.target.value as "local" | "openai" })}>
                      <option value="local">本地规则</option>
                      <option value="openai">OpenAI-compatible 文本 API</option>
                    </select>
                  </Field>
                  <Button type="button" onClick={adaptDocument} busy={busyAction === "document-adapt"} icon={Upload}>
                    导入并生成分镜
                  </Button>
                </div>
              </Panel>

              <div className="grid gap-3">
                <Panel title="改编结果" icon={FileText}>
                  <div className="break-all rounded-ui border border-line bg-slate-50 px-3 py-2 font-mono text-xs leading-6 text-ink-700">{documentLog}</div>
                  {documentResult ? (
                    <div className="mt-3 grid gap-2">
                      <div className="rounded-ui border border-teal-100 bg-teal-50 px-3 py-2 text-sm text-teal-900">
                        项目：<span className="font-mono">{documentResult.project.project_id}</span> / 导入：<span className="font-mono">{documentResult.import.import_id}</span>
                      </div>
                      {documentResult.episodes.map((item) => (
                        <article key={item.episode_id} className="rounded-ui border border-line bg-white p-4 shadow-sm">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="text-sm font-semibold">{item.title}</div>
                            <span className="rounded-ui bg-emerald-50 px-2 py-1 text-xs text-emerald-700">{item.status}</span>
                          </div>
                          <div className="mt-1 font-mono text-xs text-ink-500">
                            {item.episode_id} / {item.duration_seconds}s / {item.shot_count} 镜
                          </div>
                          <div className="mt-2 line-clamp-2 text-sm leading-6 text-ink-700">{item.premise}</div>
                          {item.storyboard_path && <div className="mt-2 break-all font-mono text-[11px] text-ink-500">{item.storyboard_path}</div>}
                        </article>
                      ))}
                    </div>
                  ) : (
                    <EmptyState text="导入后会在这里显示生成的剧集。" />
                  )}
                </Panel>
                <Panel title="分镜 API" icon={KeyRound}>
                  <div className="grid gap-2 font-mono text-xs text-ink-600">
                    <div>Base URL: {config.openai_base_url}</div>
                    <div>Text model: {config.openai_text_model}</div>
                    <div>Endpoint: {config.openai_text_endpoint_mode}</div>
                    <div>Key: {config.openai_api_key_configured ? config.openai_api_key : "未配置"}</div>
                  </div>
                </Panel>
              </div>
            </section>
          </Tabs.Content>

          <Tabs.Content value="storyboard-review">
            <section className="grid grid-cols-[360px_minmax(0,1fr)] gap-4 max-[1080px]:grid-cols-1">
              <Panel title="审稿选择" icon={FileText}>
                <div className="grid gap-3">
                  <Field label="项目">
                    <select
                      className="input"
                      value={currentProjectId}
                      onChange={(event) => {
                        currentProjectIdRef.current = event.target.value;
                        setCurrentProjectId(event.target.value);
                        setReviewStoryboard(null);
                        refreshProjectLibrary(event.target.value).catch((error: Error) => setNotice(error.message));
                      }}
                    >
                      {projects.map((project) => (
                        <option key={project.project_id} value={project.project_id}>
                          {project.name} / {project.project_id}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="剧集">
                    <select className="input" value={reviewEpisodeId} onChange={(event) => setReviewEpisodeId(event.target.value)}>
                      {projectEpisodes.map((item) => (
                        <option key={item.episode_id} value={item.episode_id}>
                          E{item.episode_no} / {item.title} / {item.status}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Button type="button" onClick={loadReviewStoryboard} busy={busyAction === "review-load"} icon={RefreshCw} disabled={!currentProjectId || !reviewEpisodeId}>
                    载入分镜
                  </Button>
                  <div className="break-all rounded-ui border border-line bg-slate-50 px-3 py-2 font-mono text-xs leading-6 text-ink-700 shadow-inner">{reviewLog}</div>
                  <form onSubmit={saveReferenceDraft} className="grid gap-2 rounded-ui border border-line bg-white p-4 shadow-sm">
                    <div className="text-xs font-semibold text-ink-700">连续性素材</div>
                    <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-2">
                      <select className="input" value={referenceDraft.reference_type} onChange={(event) => setReferenceDraft({ ...referenceDraft, reference_type: event.target.value as typeof referenceDraft.reference_type })}>
                        <option value="character">角色</option>
                        <option value="prop">道具</option>
                        <option value="location">地点</option>
                        <option value="style">风格</option>
                        <option value="action">动作</option>
                      </select>
                      <input className="input" value={referenceDraft.name} onChange={(event) => setReferenceDraft({ ...referenceDraft, name: event.target.value })} />
                    </div>
                    <textarea className="input min-h-[64px] resize-y py-2 text-xs leading-5" value={referenceDraft.prompt_fragment} onChange={(event) => setReferenceDraft({ ...referenceDraft, prompt_fragment: event.target.value })} />
                    <Button type="submit" busy={busyAction === "reference-save"} icon={Save}>
                      保存素材
                    </Button>
                    <div className="grid gap-1">
                      {references.slice(0, 8).map((reference) => (
                        <div key={reference.reference_id} className="truncate rounded-ui bg-slate-50 px-2 py-1 text-xs text-ink-700">
                          {reference.reference_type} / {reference.name}
                        </div>
                      ))}
                    </div>
                  </form>
                </div>
              </Panel>

              <div className="grid gap-3">
                {reviewStoryboard ? (
                  <>
                    <section className="grid grid-cols-4 gap-3 max-[900px]:grid-cols-2 max-[560px]:grid-cols-1">
                      <StatusMetric label="待审" value={`${reviewSummary.pending} 条`} />
                      <StatusMetric label="通过" value={`${reviewSummary.approved} 条`} />
                      <StatusMetric label="待修改" value={`${reviewSummary.revise} 条`} />
                      <StatusMetric label="驳回" value={`${reviewSummary.rejected} 条`} />
                    </section>
                    {currentReviewShot && (
                      <Panel title="当前镜头" icon={Layers3} action={<Button size="sm" type="button" onClick={regenerateReviewShotImage} busy={busyAction === "review-regenerate-shot-image"} icon={Image}>重生成</Button>}>
                        <div className="grid grid-cols-[minmax(0,1fr)_220px] gap-4 max-[860px]:grid-cols-1">
                          <div className="grid gap-2">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="rounded-ui bg-teal-50 px-2 py-1 font-mono text-xs font-semibold text-teal-700">{currentReviewShot.shot_id}</span>
                              <span className="rounded-ui bg-slate-100 px-2 py-1 text-xs text-ink-600">{currentReviewShot.duration}s</span>
                              <span className="rounded-ui bg-slate-100 px-2 py-1 text-xs text-ink-600">{currentReviewShot.camera || "未设镜头"}</span>
                              <span className={clsx("rounded-ui px-2 py-1 text-xs", reviewStatusClass(currentReviewShot.review_status))}>{reviewStatusLabel(currentReviewShot.review_status)}</span>
                            </div>
                            <p className="m-0 text-sm leading-6 text-ink-900">{currentReviewShot.scene}</p>
                            <div className="rounded-ui border border-line bg-slate-50 px-3 py-2 font-mono text-xs leading-5 text-ink-600">{currentReviewShot.image_prompt || "未填写图片 Prompt"}</div>
                            <Field label="审稿批注">
                              <textarea className="input min-h-[72px] resize-y py-2 leading-6" value={currentReviewShot.review_note || ""} onChange={(event) => updateReviewShot(currentReviewShot.shot_id, { review_note: event.target.value })} />
                            </Field>
                            <div className="flex flex-wrap gap-2">
                              <Button size="sm" type="button" variant="secondary" onClick={() => updateReviewShot(currentReviewShot.shot_id, { review_status: "approved" })} icon={CheckCircle2}>
                                通过
                              </Button>
                              <Button size="sm" type="button" variant="secondary" onClick={() => updateReviewShot(currentReviewShot.shot_id, { review_status: "revise" })} icon={RefreshCw}>
                                待修改
                              </Button>
                              <Button size="sm" type="button" variant="secondary" onClick={() => updateReviewShot(currentReviewShot.shot_id, { review_status: "rejected" })} icon={Square}>
                                驳回
                              </Button>
                            </div>
                          </div>
                          <div className="grid content-start gap-2 rounded-ui border border-line bg-slate-50 p-3 text-xs text-ink-600">
                            <div className="flex items-center justify-between gap-2">
                              <span>Workflow</span>
                              <span className="font-mono text-ink-900">{currentReviewShot.workflow_template || "mock_image"}</span>
                            </div>
                            <div className="flex items-center justify-between gap-2">
                              <span>引用</span>
                              <span className="font-mono text-ink-900">{reviewBoundReferences}</span>
                            </div>
                            <div className="flex items-center justify-between gap-2">
                              <span>重跑</span>
                              <span className="font-mono text-ink-900">{reviewRerunCount}</span>
                            </div>
                            <div className="flex items-center justify-between gap-2">
                              <span>版本</span>
                              <span className="font-mono text-ink-900">{reviewStoryboard.review_versions?.length ?? 0}</span>
                            </div>
                          </div>
                        </div>
                      </Panel>
                    )}
                    <Panel title="整集信息" icon={Clapperboard} action={<Button size="sm" type="button" onClick={saveReviewStoryboard} busy={busyAction === "review-save"} icon={Save}>保存</Button>}>
                      <div className="grid gap-3">
                        <div className="grid grid-cols-2 gap-2 max-[720px]:grid-cols-1">
                          <Field label="标题">
                            <input className="input" value={reviewStoryboard.title} onChange={(event) => updateReviewStoryboard({ title: event.target.value })} />
                          </Field>
                          <Field label="主角">
                            <input className="input" value={reviewStoryboard.protagonist} onChange={(event) => updateReviewStoryboard({ protagonist: event.target.value })} />
                          </Field>
                        </div>
                        <Field label="剧情梗概">
                          <textarea className="input min-h-[84px] resize-y py-2 leading-6" value={reviewStoryboard.premise} onChange={(event) => updateReviewStoryboard({ premise: event.target.value })} />
                        </Field>
                        <Field label="风格 Prompt">
                          <textarea className="input min-h-[72px] resize-y py-2 leading-6" value={reviewStoryboard.style_preset} onChange={(event) => updateReviewStoryboard({ style_preset: event.target.value })} />
                        </Field>
                        <div className="grid grid-cols-[minmax(0,1fr)_auto] items-end gap-2 max-[720px]:grid-cols-1">
                          <Field label="版本备注">
                            <input className="input" value={reviewSnapshotNote} onChange={(event) => setReviewSnapshotNote(event.target.value)} />
                          </Field>
                          <Button type="button" variant="secondary" onClick={snapshotReviewStoryboard} busy={busyAction === "review-snapshot"} icon={Save}>
                            保存版本
                          </Button>
                        </div>
                        {(reviewStoryboard.review_versions ?? []).length > 0 && (
                          <div className="grid gap-1 rounded-ui bg-slate-50 px-3 py-2 text-xs text-ink-600">
                            {(reviewStoryboard.review_versions ?? []).slice(-3).map((version) => (
                              <div key={version.version_id} className="flex flex-wrap items-center justify-between gap-2">
                                <span className="font-mono">{version.version_id} / {formatTime(version.created_at)}</span>
                                <span>通过 {version.summary.approved} / 待修改 {version.summary.revise} / 驳回 {version.summary.rejected}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </Panel>

                    <Panel title="单镜头重写" icon={RefreshCw}>
                      <div className="grid grid-cols-[180px_minmax(0,1fr)_auto] items-end gap-2 max-[820px]:grid-cols-1">
                        <Field label="镜头">
                          <select
                            className="input"
                            value={reviewShotId}
                            onChange={(event) => {
                              const nextShotId = event.target.value;
                              setReviewShotId(nextShotId);
                              const nextShot = reviewStoryboard.shots.find((shot) => shot.shot_id === nextShotId);
                              setReviewWorkflowTemplate(nextShot?.workflow_template ?? "mock_image");
                            }}
                          >
                            {reviewStoryboard.shots.map((shot) => (
                              <option key={shot.shot_id} value={shot.shot_id}>
                                {shot.shot_id}
                              </option>
                            ))}
                          </select>
                        </Field>
                        <Field label="重写要求">
                          <input className="input" value={reviewInstruction} onChange={(event) => setReviewInstruction(event.target.value)} />
                        </Field>
                        <Button type="button" onClick={rewriteReviewShot} busy={busyAction === "review-rewrite-shot"} icon={RefreshCw}>
                          本地重写
                        </Button>
                      </div>
                      <div className="mt-3 grid grid-cols-[180px_auto] items-end gap-2 max-[520px]:grid-cols-1">
                        <Field label="图片生成">
                      <select className="input" value={reviewImageProvider} onChange={(event) => setReviewImageProvider(event.target.value as JobProvider)}>
                        <option value="mock">mock</option>
                        <option value="openai">openai</option>
                        <option value="comfyui">comfyui</option>
                      </select>
                        </Field>
                        <Button type="button" onClick={regenerateReviewShotImage} busy={busyAction === "review-regenerate-shot-image"} icon={Image}>
                          重生成图片
                        </Button>
                      </div>
                      <div className="mt-3 grid gap-2">
                        <Field label="Workflow Template">
                          <select
                            className="input"
                            value={reviewWorkflowTemplate}
                            onChange={(event) => {
                              const nextTemplateId = event.target.value;
                              const template = workflowTemplates.find((item) => item.template_id === nextTemplateId);
                              setReviewWorkflowTemplate(nextTemplateId);
                              if (template) setReviewImageProvider(template.provider);
                              if (reviewShotId) updateReviewShot(reviewShotId, { workflow_template: nextTemplateId });
                            }}
                          >
                            {workflowTemplates.map((template) => (
                              <option key={template.template_id} value={template.template_id}>
                                {template.name} / {template.provider}
                              </option>
                            ))}
                          </select>
                        </Field>
                        <div className="grid gap-2 rounded-ui border border-line bg-slate-50 p-2">
                          <div className="text-xs font-semibold text-ink-700">当前镜头引用</div>
                          {references.length ? (
                            <div className="grid grid-cols-2 gap-2 max-[720px]:grid-cols-1">
                              {references.map((reference) => (
                                <label key={reference.reference_id} className="flex items-center gap-2 rounded-ui bg-white px-2 py-1 text-xs text-ink-700">
                                  <input
                                    type="checkbox"
                                    checked={Boolean(currentReviewShot?.reference_bindings?.includes(reference.reference_id))}
                                    onChange={(event) => toggleReviewReferenceBinding(reference.reference_id, event.target.checked)}
                                  />
                                  <span className="truncate">{reference.name}</span>
                                </label>
                              ))}
                            </div>
                          ) : (
                            <div className="text-xs text-ink-500">暂无连续性素材。</div>
                          )}
                        </div>
                      </div>
                    </Panel>

                    <Panel title="分镜表" icon={FileText}>
                      <div className="grid gap-3">
                        {reviewStoryboard.shots.map((shot) => (
                          <article key={shot.shot_id} className="grid gap-3 rounded-ui border border-line bg-white p-4 shadow-sm">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="rounded-ui bg-teal-50 px-2 py-1 font-mono text-xs font-semibold text-teal-700">{shot.shot_id}</span>
                                <span className={clsx("rounded-ui px-2 py-1 text-xs", reviewStatusClass(shot.review_status))}>{reviewStatusLabel(shot.review_status)}</span>
                              </div>
                              <input className="input w-24" type="number" min={1} max={60} value={shot.duration} onChange={(event) => updateReviewShot(shot.shot_id, { duration: Number(event.target.value) })} />
                            </div>
                            <Field label="画面">
                              <textarea className="input min-h-[72px] resize-y py-2 leading-6" value={shot.scene} onChange={(event) => updateReviewShot(shot.shot_id, { scene: event.target.value })} />
                            </Field>
                            <Field label="台词">
                              <input className="input" value={shot.dialogue} onChange={(event) => updateReviewShot(shot.shot_id, { dialogue: event.target.value })} />
                            </Field>
                            <Field label="图片 Prompt">
                              <textarea className="input min-h-[84px] resize-y py-2 font-mono text-xs leading-5" value={shot.image_prompt} onChange={(event) => updateReviewShot(shot.shot_id, { image_prompt: event.target.value })} />
                            </Field>
                            <div className="grid grid-cols-2 gap-2">
                              <Field label="镜头">
                                <input className="input" value={shot.camera} onChange={(event) => updateReviewShot(shot.shot_id, { camera: event.target.value })} />
                              </Field>
                              <Field label="情绪">
                                <input className="input" value={shot.emotion} onChange={(event) => updateReviewShot(shot.shot_id, { emotion: event.target.value })} />
                              </Field>
                            </div>
                            <div className="grid grid-cols-2 gap-2 max-[720px]:grid-cols-1">
                              <Field label="源图">
                                <input className="input font-mono text-xs" value={shot.source_image || "未生成"} readOnly />
                              </Field>
                              <Field label="成图">
                                <input className="input font-mono text-xs" value={shot.anime_image || "未生成"} readOnly />
                              </Field>
                            </div>
                            <div className="grid gap-1 rounded-ui bg-slate-50 px-3 py-2 text-xs text-ink-600">
                              <div>模板：{shot.workflow_template || "mock_image"} / 引用：{shot.reference_bindings?.join(", ") || "无"}</div>
                              <div>重跑：{shot.rerun_history?.length ?? 0} 次</div>
                              {(shot.rerun_history ?? []).slice(-3).map((record) => (
                                <div key={`${record.created_at}-${record.anime_image}`} className="truncate font-mono">
                                  {record.created_at} / {record.workflow_template} / {record.provider} / {record.anime_image}
                                </div>
                              ))}
                            </div>
                          </article>
                        ))}
                      </div>
                    </Panel>
                  </>
                ) : (
                  <EmptyState text="选择已有分镜的剧集后载入审稿。" />
                )}
              </div>
            </section>
          </Tabs.Content>

          <Tabs.Content value="episode-studio">
            <WorkflowStepStrip
              steps={[
                { label: "项目设定", done: Boolean(currentProject) },
                { label: "剧集草稿", done: projectEpisodes.length > 0 },
                { label: "分镜", done: draftedEpisodes > 0 },
                { label: "图片", done: imagedEpisodes > 0 },
                { label: "视频", done: readyEpisodes > 0 },
              ]}
            />
            <section className="grid grid-cols-[360px_minmax(0,1fr)] gap-4 max-[1080px]:grid-cols-1">
              <Panel title="剧集参数" icon={Clapperboard}>
                <form onSubmit={createStoryboard} className="grid gap-3">
                  <div className="rounded-ui border border-teal-100 bg-teal-50 px-3 py-2 text-sm text-teal-900">
                    当前项目：<span className="font-mono">{currentProject?.name || currentProjectId}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <Field label="项目 ID">
                      <input className="input" value={episodeForm.project_id} onChange={(event) => setEpisodeForm({ ...episodeForm, project_id: event.target.value })} />
                    </Field>
                    <Field label="剧集 ID">
                      <input className="input" value={episodeForm.episode_id} onChange={(event) => setEpisodeForm({ ...episodeForm, episode_id: event.target.value })} />
                    </Field>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <Field label="题材">
                      <input className="input" value={episodeForm.genre} onChange={(event) => setEpisodeForm({ ...episodeForm, genre: event.target.value })} />
                    </Field>
                    <Field label="平台">
                      <select className="input" value={episodeForm.platform} onChange={(event) => setEpisodeForm({ ...episodeForm, platform: event.target.value })}>
                        <option value="douyin">抖音</option>
                        <option value="bilibili">B站</option>
                        <option value="kuaishou">快手</option>
                        <option value="xiaohongshu">小红书</option>
                      </select>
                    </Field>
                  </div>
                  <Field label="剧情梗概">
                    <textarea className="input min-h-[88px] resize-y py-2 leading-6" value={episodeForm.premise} onChange={(event) => setEpisodeForm({ ...episodeForm, premise: event.target.value })} />
                  </Field>
                  <Field label="固定主角">
                    <textarea className="input min-h-[72px] resize-y py-2 leading-6" value={episodeForm.protagonist} onChange={(event) => setEpisodeForm({ ...episodeForm, protagonist: event.target.value })} />
                  </Field>
                  <Field label="画风预设">
                    <input className="input" value={episodeForm.style_preset} onChange={(event) => setEpisodeForm({ ...episodeForm, style_preset: event.target.value })} />
                  </Field>
                  <div className="grid grid-cols-2 gap-2">
                    <Field label="总时长秒">
                      <input className="input" type="number" min={3} max={180} value={episodeForm.duration_seconds} onChange={(event) => setEpisodeForm({ ...episodeForm, duration_seconds: Number(event.target.value) })} />
                    </Field>
                    <Field label="分镜数量">
                      <input className="input" type="number" min={1} max={24} value={episodeForm.shot_count} onChange={(event) => setEpisodeForm({ ...episodeForm, shot_count: Number(event.target.value) })} />
                    </Field>
                  </div>
                  <div className="grid grid-cols-[1fr_auto] items-end gap-2">
                    <Field label="图片生成">
                      <select className="input" value={episodeProvider} onChange={(event) => setEpisodeProvider(event.target.value as JobProvider)}>
                        <option value="mock">mock 占位图</option>
                        <option value="openai">gpt-image-2 API</option>
                        <option value="comfyui">ComfyUI 工作流</option>
                      </select>
                    </Field>
                    <Button variant="secondary" type="button" onClick={loadEpisode} busy={busyAction === "episode-load"} icon={RefreshCw}>
                      载入
                    </Button>
                  </div>
                  <div className="flex flex-wrap gap-2 pt-1">
                    <Button type="submit" busy={busyAction === "episode-storyboard"} icon={FileText}>
                      生成分镜
                    </Button>
                    <Button type="button" variant="secondary" onClick={generateImages} busy={busyAction === "episode-images"} icon={Image} disabled={!episode}>
                      生成图片
                    </Button>
                    <Button type="button" variant="secondary" onClick={exportVideo} busy={busyAction === "episode-video"} icon={Video} disabled={!episode || imageReadyCount === 0}>
                      合成视频
                    </Button>
                  </div>
                </form>
              </Panel>

              <div className="grid gap-3">
                <Panel title="项目级批量生产" icon={Clapperboard}>
                  <div className="mb-3 grid grid-cols-4 gap-2 max-[760px]:grid-cols-2">
                    <MiniMetric label="草稿" value={String(projectEpisodes.length)} />
                    <MiniMetric label="已有分镜" value={String(draftedEpisodes)} />
                    <MiniMetric label="可合成" value={String(imagedEpisodes)} />
                    <MiniMetric label="异常" value={String(failedEpisodes)} tone={failedEpisodes ? "danger" : "default"} />
                  </div>
                  <form onSubmit={createBatchEpisodes} className="grid gap-3">
                    <div className="grid grid-cols-[120px_minmax(0,1fr)_auto] items-end gap-2 max-[720px]:grid-cols-1">
                      <Field label="集数">
                        <input className="input" type="number" min={1} max={100} value={batchCount} onChange={(event) => setBatchCount(Number(event.target.value))} />
                      </Field>
                      <Field label="批量方向">
                        <input className="input" value={batchDirection} onChange={(event) => setBatchDirection(event.target.value)} />
                      </Field>
                      <Button type="submit" busy={busyAction === "episode-batch"} icon={Save} disabled={!currentProjectId}>
                        创建草稿
                      </Button>
                    </div>
                  </form>
                  <div className="mt-3 grid gap-3 rounded-ui border border-slate-200 bg-slate-50 p-4">
                    <div className="grid grid-cols-[1fr_1fr_auto] items-end gap-2 max-[820px]:grid-cols-1">
                      <Field label="任务步骤">
                        <select className="input" value={jobStepMode} onChange={(event) => setJobStepMode(event.target.value as "full" | JobStep)}>
                          <option value="full">完整流程：分镜 + 图片 + 视频</option>
                          <option value="storyboard">只生成分镜</option>
                          <option value="images">只生成图片</option>
                          <option value="video">只合成视频</option>
                        </select>
                      </Field>
                      <Field label="图片 Provider">
                        <select className="input" value={jobProvider} onChange={(event) => setJobProvider(event.target.value as JobProvider)}>
                          <option value="mock">mock 占位图</option>
                          <option value="openai">gpt-image-2 API</option>
                          <option value="comfyui">ComfyUI 工作流</option>
                        </select>
                      </Field>
                      <Button type="button" onClick={createProductionJob} busy={busyAction === "job-create"} icon={Play} disabled={selectedEpisodeIds.length === 0}>
                        加入队列
                      </Button>
                    </div>
                    <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-ink-500">
                      <div>
                        已选 <span className="font-mono text-ink-900">{selectedEpisodeIds.length}</span> 集，预计图片{" "}
                        <span className="font-mono text-ink-900">{selectedImageEstimate}</span> 张
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          variant="secondary"
                          size="sm"
                          type="button"
                          onClick={() => setSelectedEpisodeIds(projectEpisodes.map((projectEpisode) => projectEpisode.episode_id))}
                          disabled={projectEpisodes.length === 0}
                        >
                          全选
                        </Button>
                        <Button variant="secondary" size="sm" type="button" onClick={() => setSelectedEpisodeIds([])} disabled={selectedEpisodeIds.length === 0}>
                          清空
                        </Button>
                      </div>
                    </div>
                  </div>
                  <div className="mt-3 grid gap-2">
                    {projectEpisodes.length ? (
                      projectEpisodes.map((projectEpisode) => (
                        <EpisodeRow
                          key={projectEpisode.episode_id}
                          episode={projectEpisode}
                          busyAction={busyAction}
                          selected={selectedEpisodeIds.includes(projectEpisode.episode_id)}
                          onSelected={toggleEpisodeSelection}
                          onStoryboard={createProjectEpisodeStoryboard}
                          onImages={generateProjectImages}
                          onVideo={exportProjectVideo}
                        />
                      ))
                    ) : (
                      <EmptyState text="当前项目还没有剧集草稿。" />
                    )}
                  </div>
                </Panel>

                <Panel
                  title="任务队列"
                  icon={Activity}
                  action={<Button variant="secondary" size="sm" type="button" onClick={() => runBusy("jobs-refresh", async () => { await refreshJobs(); })} busy={busyAction === "jobs-refresh"} icon={RefreshCw}>刷新</Button>}
                >
                  {currentProjectJobs.length ? (
                    <div className="grid gap-2">
                      {currentProjectJobs.map((job) => (
                        <JobRow
                          key={job.job_id}
                          job={job}
                          busyAction={busyAction}
                          selected={selectedJobId === job.job_id}
                          onDetail={(selectedJob) => runBusy(`job-detail-${selectedJob.job_id}`, async () => { await loadJobDetail(selectedJob.job_id); })}
                          onCancel={cancelJob}
                          onRetry={retryJob}
                        />
                      ))}
                    </div>
                  ) : (
                    <EmptyState text="当前项目还没有队列任务。" />
                  )}
                </Panel>

                {selectedJobDetail && (
                  <JobDetailPanel
                    job={selectedJobDetail}
                    busyAction={busyAction}
                    onRetryFailed={retryFailedJob}
                    onRetryEpisode={retryJobEpisode}
                    onRetryStep={retryJobEpisodeFromStep}
                  />
                )}

                <section className="grid grid-cols-4 gap-4 max-[900px]:grid-cols-2 max-[560px]:grid-cols-1">
                  <StatusMetric label="分镜" value={episode ? `${episode.shots.length} 条` : "未生成"} />
                  <StatusMetric label="图片" value={episode ? `${imageReadyCount}/${episode.shots.length}` : "0/0"} />
                  <StatusMetric label="时长" value={episode ? `${episode.duration_seconds}s` : `${episodeForm.duration_seconds}s`} />
                  <StatusMetric label="视频" value={episode?.video_path ? "已导出" : "未导出"} />
                </section>

                <Panel title="生产日志" icon={FileText}>
                  <div className="break-all rounded-ui border border-line bg-slate-50 px-3 py-2 font-mono text-xs leading-6 text-ink-700">{episodeLog}</div>
                </Panel>

                <Panel title="分镜列表" icon={Clapperboard}>
                  {episode ? (
                    <div className="grid gap-2">
                      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-2">
                        <div>
                          <div className="text-sm font-semibold">{episode.title}</div>
                          <div className="mt-0.5 text-xs text-ink-500">
                            {episode.project_id} / {episode.episode_id} / {episode.genre}
                          </div>
                        </div>
                        {episode.video_path && <div className="max-w-full break-all font-mono text-xs text-ink-500">{episode.video_path}</div>}
                      </div>
                      <div className="grid gap-2">
                        {episode.shots.map((shot) => (
                          <article key={shot.shot_id} className="grid gap-3 rounded-ui border border-line bg-white p-4 shadow-sm">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div className="flex items-center gap-2">
                                <span className="rounded-ui bg-teal-50 px-2 py-1 font-mono text-xs font-semibold text-teal-700">{shot.shot_id}</span>
                                <span className="font-mono text-xs text-ink-500">{shot.duration}s</span>
                                <span className="text-xs text-ink-500">{shot.camera}</span>
                              </div>
                              <span className={clsx("rounded-ui px-2 py-1 text-xs", shot.anime_image ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-ink-500")}>
                                {shot.anime_image ? "图片已生成" : "等待图片"}
                              </span>
                            </div>
                            <div className="grid gap-1 text-sm leading-6">
                              <div>{shot.scene}</div>
                              <div className="text-ink-500">台词：{shot.dialogue}</div>
                            </div>
                            <div className="break-all rounded-ui bg-slate-50 px-2.5 py-2 font-mono text-xs leading-5 text-ink-600">{shot.image_prompt}</div>
                            {(shot.source_image || shot.anime_image) && (
                              <div className="grid gap-1 font-mono text-[11px] leading-5 text-ink-500">
                                {shot.source_image && <div className="break-all">source: {shot.source_image}</div>}
                                {shot.anime_image && <div className="break-all">anime: {shot.anime_image}</div>}
                              </div>
                            )}
                          </article>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="rounded-ui border border-dashed border-line bg-slate-50 px-3 py-8 text-center text-sm text-ink-500">填写参数后生成第一版分镜。</div>
                  )}
                </Panel>
              </div>
            </section>
          </Tabs.Content>

          <Tabs.Content value="outputs">
            <Panel title="成品库" icon={Video} action={<Button variant="secondary" size="sm" onClick={() => runBusy("outputs-refresh", () => refreshProjectLibrary(currentProjectId))} busy={busyAction === "outputs-refresh"} icon={RefreshCw}>刷新</Button>}>
              {outputs.length ? (
                <div className="grid gap-2">
                  {outputs.map((item) => (
                    <article key={item.video_path} className="rounded-ui border border-line bg-white p-4 shadow-sm">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="text-sm font-semibold">{item.filename}</div>
                        <div className="font-mono text-xs text-ink-500">{formatBytes(item.size_bytes)}</div>
                      </div>
                      <div className="mt-1 break-all font-mono text-xs text-ink-500">{item.video_path}</div>
                      <div className="mt-2 font-mono text-[11px] text-ink-500">更新：{formatTime(item.updated_at)}</div>
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyState text="暂无导出成品。" />
              )}
            </Panel>
          </Tabs.Content>

          <Tabs.Content value="services">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              {comfyMode === "remote" ? (
                <Button onClick={testComfyConnection} busy={busyAction === "test-comfy"} icon={RefreshCw}>
                  测试远程 ComfyUI
                </Button>
              ) : (
                <>
                  <Button onClick={startComfy} busy={busyAction === "start-comfy"} icon={Play}>
                    启动 ComfyUI
                  </Button>
                  <Button variant="secondary" onClick={stopComfy} busy={busyAction === "stop-comfy"} icon={Square}>
                    停止 ComfyUI
                  </Button>
                </>
              )}
              <a className="button-ghost" href={comfyEffectiveUrl || "http://127.0.0.1:8188"} target="_blank" rel="noreferrer">
                <ExternalLink className="h-4 w-4" />
                打开 ComfyUI
              </a>
            </div>
            <div className="mb-3 rounded-ui border border-line bg-white px-3 py-2 text-sm text-ink-700 shadow-sm">
              当前 ComfyUI：<span className="font-mono">{comfyMode}</span> / <span className="break-all font-mono">{status?.comfyui.base_url || comfyEffectiveUrl}</span>
            </div>
            <Panel title="服务日志" icon={FileText} action={<Button variant="secondary" size="sm" onClick={() => runBusy("logs", refreshLogs)} icon={RefreshCw}>刷新日志</Button>}>
              <LogBlock value={comfyMode === "remote" ? status?.comfyui.api_detail || "远程模式不读取本地 ComfyUI 日志。" : serviceLog || status?.comfyui.log_tail || "暂无日志"} />
            </Panel>
          </Tabs.Content>

          <Tabs.Content value="config">
            <form onSubmit={saveConfig} className="grid max-w-3xl gap-3 rounded-ui border border-line bg-panel p-4">
              <Field label="OpenAI API Key">
                <input className="input" type="password" name="openai_api_key" value={apiKeyDraft} onChange={(event) => setApiKeyDraft(event.target.value)} placeholder={config.openai_api_key_configured ? config.openai_api_key : "sk-..."} autoComplete="off" />
              </Field>
              <Field label="API Base URL">
                <input className="input" name="openai_base_url" value={configDraft.openai_base_url} onChange={(event) => setConfigDraft({ ...configDraft, openai_base_url: event.target.value })} />
              </Field>
              <Field label="图片模型">
                <input className="input" name="openai_image_model" value={configDraft.openai_image_model} onChange={(event) => setConfigDraft({ ...configDraft, openai_image_model: event.target.value })} />
              </Field>
              <Field label="分镜文本模型">
                <input className="input" name="openai_text_model" value={configDraft.openai_text_model} onChange={(event) => setConfigDraft({ ...configDraft, openai_text_model: event.target.value })} />
              </Field>
              <Field label="分镜接口模式">
                <select className="input" name="openai_text_endpoint_mode" value={configDraft.openai_text_endpoint_mode} onChange={(event) => setConfigDraft({ ...configDraft, openai_text_endpoint_mode: event.target.value as "chat_completions" | "responses" })}>
                  <option value="chat_completions">/v1/chat/completions</option>
                  <option value="responses">/v1/responses</option>
                </select>
              </Field>
              <Field label="文本模型">
                <input className="input" name="ollama_text_model" value={configDraft.ollama_text_model} onChange={(event) => setConfigDraft({ ...configDraft, ollama_text_model: event.target.value })} />
              </Field>
              <Field label="ComfyUI 来源">
                <select className="input" name="comfyui_mode" value={configDraft.comfyui_mode} onChange={(event) => setConfigDraft({ ...configDraft, comfyui_mode: event.target.value as "local" | "remote" })}>
                  <option value="local">本地服务</option>
                  <option value="remote">远程服务</option>
                </select>
              </Field>
              <Field label="本地 ComfyUI 地址">
                <input className="input" name="comfyui_base_url" value={configDraft.comfyui_base_url} onChange={(event) => setConfigDraft({ ...configDraft, comfyui_base_url: event.target.value })} />
              </Field>
              <Field label="远程 ComfyUI 地址">
                <input className="input" name="comfyui_remote_base_url" value={configDraft.comfyui_remote_base_url} onChange={(event) => setConfigDraft({ ...configDraft, comfyui_remote_base_url: event.target.value })} placeholder="http://server:8188" />
              </Field>
              <Field label="输出目录">
                <input className="input" name="output_dir" value={configDraft.output_dir} onChange={(event) => setConfigDraft({ ...configDraft, output_dir: event.target.value })} />
              </Field>
              <div className="flex items-center gap-2">
                <Button type="submit" busy={busyAction === "save-config"} icon={Save}>
                  保存配置
                </Button>
              </div>
            </form>
          </Tabs.Content>

          <Tabs.Content value="image-test">
            <Panel title="gpt-image-2 图片测试" icon={Image}>
              <p className="mb-3 text-sm text-ink-500">生成一张基础分镜图，然后调用配置的图片 API 生成动漫图。需要先保存 API Key 和 Base URL。</p>
              <Button onClick={runImageTest} busy={busyAction === "image-test"} icon={Clapperboard}>
                运行图片测试
              </Button>
              <div className="mt-3">
                <LogBlock value={imageLog} minHeight="min-h-[260px]" />
              </div>
            </Panel>
          </Tabs.Content>

          <Tabs.Content value="video-test">
            <Panel title="本地视频合成测试" icon={Video}>
              <p className="mb-3 text-sm text-ink-500">使用 mock 图片流程和 FFmpeg 生成一个 9:16 测试视频，用来确认导出链路可用。</p>
              <Button onClick={runVideoTest} busy={busyAction === "video-test"} icon={Clapperboard}>
                运行视频测试
              </Button>
              <div className="mt-3">
                <LogBlock value={videoLog} minHeight="min-h-[260px]" />
              </div>
            </Panel>
          </Tabs.Content>
        </main>
      </div>
    </Tabs.Root>
  );
}

function Button({
  children,
  icon: Icon,
  variant = "primary",
  size = "md",
  busy = false,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  icon?: React.ComponentType<{ className?: string }>;
  variant?: "primary" | "secondary";
  size?: "sm" | "md";
  busy?: boolean;
}) {
  return (
    <button
      {...props}
      disabled={busy || props.disabled}
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-ui border text-sm font-medium outline-none transition focus-visible:ring-4 disabled:cursor-not-allowed disabled:opacity-60",
        size === "sm" ? "h-10 px-3" : "h-11 px-4",
        variant === "primary"
          ? "border-teal-600 bg-teal-600 text-white shadow-sm hover:border-teal-700 hover:bg-teal-700 focus-visible:ring-teal-100"
          : "border-line bg-white text-ink-900 shadow-sm hover:border-slate-300 hover:bg-slate-50 focus-visible:ring-slate-200",
        props.className,
      )}
    >
      {busy ? <RefreshCw className="h-4 w-4 animate-spin" /> : Icon ? <Icon className="h-4 w-4" /> : null}
      {children}
    </button>
  );
}

function ProductionCommand({
  projectName,
  projectId,
  episodeCount,
  readyEpisodes,
  runningJobs,
  failedEpisodes,
  onDocument,
  onReview,
  onQueue,
}: {
  projectName: string;
  projectId: string;
  episodeCount: number;
  readyEpisodes: number;
  runningJobs: number;
  failedEpisodes: number;
  onDocument: () => void;
  onReview: () => void;
  onQueue: () => void;
}) {
  return (
    <section className="rounded-ui border border-line bg-white p-5 shadow-panel">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="inline-flex items-center gap-2 rounded-ui bg-teal-50 px-2.5 py-1 text-xs font-semibold text-teal-700">
            <Activity className="h-3.5 w-3.5" />
            生产指挥台
          </div>
          <h2 className="mt-3 truncate text-xl font-semibold leading-tight text-ink-900">{projectName}</h2>
          <div className="mt-1 break-all font-mono text-xs text-ink-500">{projectId}</div>
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs max-[520px]:w-full">
          <MiniMetric label="剧集" value={String(episodeCount)} />
          <MiniMetric label="成片" value={`${readyEpisodes}/${episodeCount || 0}`} />
          <MiniMetric label="任务" value={String(runningJobs)} />
          <MiniMetric label="异常" value={String(failedEpisodes)} tone={failedEpisodes ? "danger" : "default"} />
        </div>
      </div>
      <div className="mt-5 grid grid-cols-3 gap-2 max-[760px]:grid-cols-1">
        <CommandButton label="导入文档" detail="拆集与初稿" icon={Upload} onClick={onDocument} />
        <CommandButton label="打开审稿" detail="连续性与重跑" icon={FileText} onClick={onReview} />
        <CommandButton label="创建任务" detail="批量入队" icon={Play} onClick={onQueue} />
      </div>
    </section>
  );
}

function CommandButton({
  label,
  detail,
  icon: Icon,
  onClick,
}: {
  label: string;
  detail: string;
  icon: React.ComponentType<{ className?: string }>;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex min-h-[74px] items-center gap-3 rounded-ui border border-line bg-slate-50 px-3 text-left outline-none transition hover:border-teal-200 hover:bg-teal-50 focus-visible:ring-4 focus-visible:ring-teal-100"
    >
      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-ui bg-white text-teal-700 shadow-sm">
        <Icon className="h-4 w-4" />
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-semibold text-ink-900">{label}</span>
        <span className="mt-0.5 block text-xs text-ink-500">{detail}</span>
      </span>
    </button>
  );
}

function NextActionCard({
  label,
  detail,
  icon: Icon,
  onClick,
}: {
  label: string;
  detail: string;
  icon: React.ComponentType<{ className?: string }>;
  onClick: () => void;
}) {
  return (
    <section className="rounded-ui border border-teal-200 bg-teal-50 p-5 shadow-panel">
      <div className="flex h-full flex-col justify-between gap-5">
        <div>
          <div className="grid h-10 w-10 place-items-center rounded-ui bg-white text-teal-700 shadow-sm">
            <Icon className="h-4 w-4" />
          </div>
          <div className="mt-4 text-xs font-semibold text-teal-700">下一步建议</div>
          <h2 className="mt-1 text-xl font-semibold text-ink-900">{label}</h2>
          <p className="m-0 mt-2 text-sm leading-6 text-ink-700">{detail}</p>
        </div>
        <Button type="button" onClick={onClick} icon={Icon}>
          {label}
        </Button>
      </div>
    </section>
  );
}

function WorkflowStepStrip({ steps }: { steps: Array<{ label: string; done: boolean }> }) {
  return (
    <section className="mb-4 grid grid-cols-5 gap-2 rounded-ui border border-line bg-white p-2 shadow-sm max-[860px]:grid-cols-1">
      {steps.map((step, index) => (
        <div
          key={step.label}
          className={clsx(
            "flex min-h-[52px] items-center gap-2 rounded-ui px-3 text-sm",
            step.done ? "bg-teal-50 text-teal-800" : "bg-slate-50 text-ink-500",
          )}
        >
          <span className={clsx("grid h-6 w-6 shrink-0 place-items-center rounded-ui font-mono text-xs", step.done ? "bg-teal-600 text-white" : "bg-white text-ink-500")}>
            {step.done ? <CheckCircle2 className="h-3.5 w-3.5" /> : index + 1}
          </span>
          <span className="font-medium">{step.label}</span>
        </div>
      ))}
    </section>
  );
}

function MiniMetric({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "danger" }) {
  return (
    <article className={clsx("rounded-ui border px-3 py-2", tone === "danger" ? "border-red-200 bg-red-50" : "border-line bg-white")}>
      <div className={clsx("text-[11px] font-medium", tone === "danger" ? "text-red-700" : "text-ink-500")}>{label}</div>
      <div className={clsx("mt-0.5 font-mono text-lg font-semibold leading-6", tone === "danger" ? "text-red-800" : "text-ink-900")}>{value}</div>
    </article>
  );
}

function StatusCard({ title, ok, detail, icon: Icon }: { title: string; ok: boolean; detail: string; icon: React.ComponentType<{ className?: string }> }) {
  return (
    <article className="min-h-[108px] rounded-ui border border-line bg-panel p-4 shadow-panel">
      <div className="flex items-center justify-between gap-2 text-sm font-semibold">
        <span className="inline-flex items-center gap-2 text-ink-900">
          <span className={clsx("grid h-8 w-8 place-items-center rounded-ui", ok ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700")}>
            <Icon className="h-4 w-4" />
          </span>
          {title}
        </span>
        <span className={clsx("rounded-ui px-2 py-1 text-[11px] font-medium", ok ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700")}>{ok ? "可用" : "待处理"}</span>
      </div>
      <div className="mt-3 break-all rounded-ui bg-slate-50 px-2.5 py-2 font-mono text-xs leading-5 text-ink-500">{detail}</div>
    </article>
  );
}

function HeaderMetric({ label, value }: { label: string; value: string }) {
  return (
    <article className="rounded-ui border border-line bg-white px-3 py-2 shadow-sm">
      <div className="text-[11px] font-medium text-ink-500">{label}</div>
      <div className="mt-0.5 font-mono text-lg font-semibold leading-6 text-ink-900">{value}</div>
    </article>
  );
}

function StatusMetric({ label, value }: { label: string; value: string }) {
  return (
    <article className="rounded-ui border border-line bg-panel p-4 shadow-panel">
      <div className="text-xs text-ink-500">{label}</div>
      <div className="mt-1 break-all font-mono text-lg font-semibold text-ink-900">{value}</div>
    </article>
  );
}

function EpisodeRow({
  episode,
  busyAction,
  selected,
  onSelected,
  onStoryboard,
  onImages,
  onVideo,
}: {
  episode: ProjectEpisode;
  busyAction: string | null;
  selected: boolean;
  onSelected: (episodeId: string, checked: boolean) => void;
  onStoryboard: (episode: ProjectEpisode) => void;
  onImages: (episode: ProjectEpisode) => void;
  onVideo: (episode: ProjectEpisode) => void;
}) {
  const canExportVideo = episode.status === "imaged" || episode.status === "exported";
  return (
    <article className="rounded-ui border border-line bg-white p-4 shadow-sm transition hover:shadow-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 gap-3">
          <input
            className="mt-1 h-5 w-5 accent-teal-600"
            type="checkbox"
            checked={selected}
            onChange={(event) => onSelected(episode.episode_id, event.target.checked)}
            aria-label={`选择 ${episode.title}`}
          />
          <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-ui bg-slate-100 px-2 py-1 font-mono text-xs text-ink-600">E{episode.episode_no}</span>
            <span className="text-sm font-semibold">{episode.title}</span>
            <span className={clsx("rounded-ui px-2 py-1 text-xs", episode.status === "failed" ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700")}>{episode.status}</span>
          </div>
          <div className="mt-1 font-mono text-xs text-ink-500">
            {episode.episode_id} / {episode.duration_seconds}s / {episode.shot_count} 镜
          </div>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" type="button" onClick={() => onStoryboard(episode)} busy={busyAction === `project-storyboard-${episode.episode_id}`} icon={FileText}>
            分镜
          </Button>
          <Button variant="secondary" size="sm" type="button" onClick={() => onImages(episode)} busy={busyAction === `project-images-${episode.episode_id}`} icon={Image} disabled={!episode.storyboard_path}>
            图片
          </Button>
          <Button variant="secondary" size="sm" type="button" onClick={() => onVideo(episode)} busy={busyAction === `project-video-${episode.episode_id}`} icon={Video} disabled={!canExportVideo}>
            视频
          </Button>
        </div>
      </div>
      <div className="mt-2 text-sm leading-6 text-ink-700">{episode.premise}</div>
      {(episode.storyboard_path || episode.video_path || episode.error) && (
        <div className="mt-2 grid gap-1 font-mono text-[11px] leading-5 text-ink-500">
          {episode.storyboard_path && <div className="break-all">storyboard: {episode.storyboard_path}</div>}
          {episode.video_path && <div className="break-all">video: {episode.video_path}</div>}
          {episode.error && <div className="break-all text-red-700">error: {episode.error}</div>}
        </div>
      )}
    </article>
  );
}

function JobRow({
  job,
  busyAction,
  selected,
  onDetail,
  onCancel,
  onRetry,
}: {
  job: Job;
  busyAction: string | null;
  selected: boolean;
  onDetail: (job: Job) => void;
  onCancel: (job: Job) => void;
  onRetry: (job: Job) => void;
}) {
  const active = job.status === "queued" || job.status === "running";
  return (
    <article className={clsx("rounded-ui border p-4 shadow-sm transition hover:shadow-panel", selected ? "border-teal-300 bg-teal-50" : "border-line bg-white")}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className={clsx("rounded-ui px-2 py-1 text-xs", jobStatusClass(job.status))}>{jobStatusLabel(job.status)}</span>
            <span className="break-all font-mono text-xs text-ink-500">{job.job_id}</span>
          </div>
          <div className="mt-1 font-mono text-xs text-ink-500">
            {job.provider} / {job.steps.join("+")} / {job.episode_ids.length} 集 / {job.completed_steps}/{job.total_steps}
          </div>
          {(job.current_episode_id || job.current_step) && (
            <div className="mt-1 font-mono text-xs text-ink-500">
              当前：{job.current_episode_id || "-"} / {job.current_step || "-"}
            </div>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            size="sm"
            type="button"
            onClick={() => onDetail(job)}
            busy={busyAction === `job-detail-${job.job_id}`}
          >
            详情
          </Button>
          <Button
            variant="secondary"
            size="sm"
            type="button"
            onClick={() => onCancel(job)}
            busy={busyAction === `job-cancel-${job.job_id}`}
            disabled={!active || job.cancel_requested}
          >
            取消
          </Button>
          <Button
            variant="secondary"
            size="sm"
            type="button"
            onClick={() => onRetry(job)}
            busy={busyAction === `job-retry-${job.job_id}`}
            disabled={job.status !== "failed" && job.status !== "cancelled"}
          >
            重试
          </Button>
        </div>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-ui bg-slate-100">
        <div className="h-full bg-teal-600 transition-all" style={{ width: `${Math.max(0, Math.min(100, job.progress))}%` }} />
      </div>
      <div className="mt-2 flex flex-wrap justify-between gap-2 font-mono text-[11px] text-ink-500">
        <span>{job.progress}%</span>
        <span>{formatTime(job.updated_at)}</span>
      </div>
      {job.error && <div className="mt-2 break-all rounded-ui bg-red-50 px-2.5 py-2 font-mono text-xs leading-5 text-red-700">{job.error}</div>}
    </article>
  );
}

function JobDetailPanel({
  job,
  busyAction,
  onRetryFailed,
  onRetryEpisode,
  onRetryStep,
}: {
  job: Job;
  busyAction: string | null;
  onRetryFailed: (job: Job) => void;
  onRetryEpisode: (job: Job, episodeId: string) => void;
  onRetryStep: (job: Job, episodeId: string, step: JobStep) => void;
}) {
  const rows = job.episode_ids.map((episodeId) => ({
    episodeId,
    storyboard: jobItemFor(job.items, episodeId, "storyboard"),
    images: jobItemFor(job.items, episodeId, "images"),
    video: jobItemFor(job.items, episodeId, "video"),
  }));
  const failedCount = job.items.filter((item) => item.status === "failed").length;
  return (
    <Panel
      title="任务详情"
      icon={FileText}
      action={
        <Button
          variant="secondary"
          size="sm"
          type="button"
          onClick={() => onRetryFailed(job)}
          busy={busyAction === `job-retry-failed-${job.job_id}`}
          disabled={failedCount === 0}
        >
          重跑失败
        </Button>
      }
    >
      <div className="mb-3 grid gap-1 font-mono text-xs text-ink-500">
        <div className="break-all">{job.job_id}</div>
        <div>
          {job.provider} / {job.steps.join("+")} / {job.status} / {job.progress}%
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs text-ink-500">
              <th className="py-2 pr-3 font-medium">剧集</th>
              <th className="py-2 pr-3 font-medium">分镜</th>
              <th className="py-2 pr-3 font-medium">图片</th>
              <th className="py-2 pr-3 font-medium">视频</th>
              <th className="py-2 pr-3 font-medium">错误 / 输出</th>
              <th className="py-2 pr-3 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const rowError = [row.storyboard, row.images, row.video].find((item) => item?.error)?.error || "";
              const outputPath = row.video?.output_path || row.images?.output_path || row.storyboard?.output_path || "";
              return (
                <tr key={row.episodeId} className="border-b border-line align-top">
                  <td className="py-2 pr-3 font-mono text-xs">{row.episodeId}</td>
                  <td className="py-2 pr-3">{row.storyboard ? <JobItemBadge item={row.storyboard} /> : <span className="text-xs text-ink-400">不包含</span>}</td>
                  <td className="py-2 pr-3">{row.images ? <JobItemBadge item={row.images} /> : <span className="text-xs text-ink-400">不包含</span>}</td>
                  <td className="py-2 pr-3">{row.video ? <JobItemBadge item={row.video} /> : <span className="text-xs text-ink-400">不包含</span>}</td>
                  <td className="max-w-[280px] py-2 pr-3">
                    {rowError ? (
                      <div className="break-all font-mono text-xs leading-5 text-red-700">{rowError}</div>
                    ) : outputPath ? (
                      <div className="break-all font-mono text-[11px] leading-5 text-ink-500">{outputPath}</div>
                    ) : (
                      <span className="text-xs text-ink-400">暂无输出</span>
                    )}
                  </td>
                  <td className="py-2 pr-3">
                    <div className="flex flex-wrap gap-1.5">
                      <Button
                        variant="secondary"
                        size="sm"
                        type="button"
                        onClick={() => onRetryEpisode(job, row.episodeId)}
                        busy={busyAction === `job-retry-episode-${job.job_id}-${row.episodeId}`}
                      >
                        本集
                      </Button>
                      {job.steps.includes("storyboard") && (
                        <Button
                          variant="secondary"
                          size="sm"
                          type="button"
                          onClick={() => onRetryStep(job, row.episodeId, "storyboard")}
                          busy={busyAction === `job-retry-step-${job.job_id}-${row.episodeId}-storyboard`}
                        >
                          分镜
                        </Button>
                      )}
                      {job.steps.includes("images") && (
                        <Button
                          variant="secondary"
                          size="sm"
                          type="button"
                          onClick={() => onRetryStep(job, row.episodeId, "images")}
                          busy={busyAction === `job-retry-step-${job.job_id}-${row.episodeId}-images`}
                        >
                          图片
                        </Button>
                      )}
                      {job.steps.includes("video") && (
                        <Button
                          variant="secondary"
                          size="sm"
                          type="button"
                          onClick={() => onRetryStep(job, row.episodeId, "video")}
                          busy={busyAction === `job-retry-step-${job.job_id}-${row.episodeId}-video`}
                        >
                          视频
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function jobItemFor(items: JobItem[], episodeId: string, step: JobStep) {
  return items.find((item) => item.episode_id === episodeId && item.step === step);
}

function JobItemBadge({ item }: { item: JobItem }) {
  return (
    <div className="grid gap-1">
      <span className={clsx("inline-flex w-fit rounded-ui px-2 py-1 text-xs", jobItemStatusClass(item.status))}>
        {jobItemStatusLabel(item.status)}
      </span>
      {(item.started_at || item.finished_at) && (
        <div className="font-mono text-[11px] leading-4 text-ink-400">
          {item.finished_at ? formatTime(item.finished_at) : item.started_at ? `开始 ${formatTime(item.started_at)}` : ""}
        </div>
      )}
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="rounded-ui border border-dashed border-slate-300 bg-slate-50 px-4 py-10 text-center text-sm text-ink-500">{text}</div>;
}

function Panel({ title, icon: Icon, action, children }: { title: string; icon: React.ComponentType<{ className?: string }>; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-ui border border-line bg-panel p-4 shadow-panel">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="inline-flex items-center gap-2 text-[15px] font-semibold text-ink-900">
          <span className="grid h-8 w-8 place-items-center rounded-ui bg-slate-100 text-ink-700">
            <Icon className="h-4 w-4" />
          </span>
          {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="grid gap-1.5 text-sm font-medium text-ink-700">
      <span>{label}</span>
      {children}
    </label>
  );
}

function LogBlock({ value, minHeight = "min-h-[220px]" }: { value?: string; minHeight?: string }) {
  return <pre className={clsx("max-h-[460px] overflow-auto rounded-ui border border-slate-800 bg-[#111827] p-4 font-mono text-xs leading-6 text-slate-100 shadow-inner", minHeight)}>{value || "暂无日志"}</pre>;
}

function buildStatusCards(status: LauncherStatus | null, config: PublicConfig) {
  return [
    {
      title: "ComfyUI",
      ok: Boolean(status?.comfyui.api_running),
      detail: status?.comfyui.api_running ? status?.comfyui.base_url || config.comfyui_base_url : `${status?.comfyui.base_url || config.comfyui_base_url} / 未连接`,
      icon: Server,
    },
    {
      title: "Ollama",
      ok: Boolean(status?.ollama.ok),
      detail: status?.ollama.ok ? "服务可用" : "未运行",
      icon: Bot,
    },
    {
      title: "图片 API",
      ok: Boolean(status?.openai.configured),
      detail: status?.openai.configured ? `${config.openai_base_url} / ${config.openai_api_key}` : `${config.openai_base_url} / 未配置 Key`,
      icon: KeyRound,
    },
    {
      title: "FFmpeg",
      ok: Boolean(status?.ffmpeg.ok),
      detail: status?.ffmpeg.path || "未找到",
      icon: CheckCircle2,
    },
  ];
}

function formatScriptResult(result: ScriptResult) {
  return `${result.ok ? "成功" : "失败"}\n\n${result.stdout || ""}\n${result.stderr || ""}`;
}

function formatBytes(value: number) {
  if (!Number.isFinite(value) || value <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let size = value;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function arrayBufferToBase64(buffer: ArrayBuffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let index = 0; index < bytes.length; index += 1) {
    binary += String.fromCharCode(bytes[index]);
  }
  return window.btoa(binary);
}

function formatTime(value: string | number) {
  const date = typeof value === "number" ? new Date(value * 1000) : new Date(value);
  if (Number.isNaN(date.getTime())) return "未知";
  return date.toLocaleString("zh-CN", { hour12: false });
}

function jobStatusLabel(status: Job["status"]) {
  const labels: Record<Job["status"], string> = {
    queued: "排队中",
    running: "运行中",
    completed: "已完成",
    failed: "失败",
    cancelled: "已取消",
  };
  return labels[status];
}

function jobStatusClass(status: Job["status"]) {
  if (status === "completed") return "bg-emerald-50 text-emerald-700";
  if (status === "failed") return "bg-red-50 text-red-700";
  if (status === "cancelled") return "bg-slate-100 text-ink-500";
  if (status === "running") return "bg-amber-50 text-amber-700";
  return "bg-amber-50 text-amber-700";
}

function jobStepLabel(step: JobStep) {
  const labels: Record<JobStep, string> = {
    storyboard: "分镜",
    images: "图片",
    video: "视频",
  };
  return labels[step];
}

function jobItemStatusLabel(status: JobItem["status"]) {
  const labels: Record<JobItem["status"], string> = {
    pending: "等待",
    running: "运行中",
    completed: "完成",
    failed: "失败",
    cancelled: "取消",
    skipped: "跳过",
  };
  return labels[status];
}

function jobItemStatusClass(status: JobItem["status"]) {
  if (status === "completed") return "bg-emerald-50 text-emerald-700";
  if (status === "failed") return "bg-red-50 text-red-700";
  if (status === "cancelled" || status === "skipped") return "bg-slate-100 text-ink-500";
  if (status === "running") return "bg-amber-50 text-amber-700";
  return "bg-amber-50 text-amber-700";
}

function reviewStatusLabel(status?: "pending" | "approved" | "rejected" | "revise") {
  const labels = {
    pending: "待审",
    approved: "通过",
    rejected: "驳回",
    revise: "待修改",
  };
  return labels[status ?? "pending"];
}

function reviewStatusClass(status?: "pending" | "approved" | "rejected" | "revise") {
  if (status === "approved") return "bg-emerald-50 text-emerald-700";
  if (status === "rejected") return "bg-red-50 text-red-700";
  if (status === "revise") return "bg-amber-50 text-amber-700";
  return "bg-slate-100 text-ink-500";
}

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}
