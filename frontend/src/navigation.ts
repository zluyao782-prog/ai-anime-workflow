import {
  Activity,
  Bot,
  Clapperboard,
  FileText,
  Image,
  KeyRound,
  Server,
  Upload,
  Video,
} from "lucide-react";

export const navItems = [
  { value: "overview", label: "总览", icon: Activity },
  { value: "projects", label: "项目库", icon: Clapperboard },
  { value: "characters", label: "角色库", icon: Bot },
  { value: "styles", label: "风格模板", icon: Image },
  { value: "episode-studio", label: "剧集生产", icon: Clapperboard },
  { value: "document-adapt", label: "文档改编", icon: Upload },
  { value: "storyboard-review", label: "分镜审稿", icon: FileText },
  { value: "outputs", label: "成品库", icon: Video },
  { value: "services", label: "服务启动", icon: Server },
  { value: "config", label: "API 配置", icon: KeyRound },
  { value: "image-test", label: "图片测试", icon: Image },
  { value: "video-test", label: "视频测试", icon: Video },
] as const;

export type TabValue = (typeof navItems)[number]["value"];
