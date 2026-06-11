# AI Anime Workflow

本项目是一个本地优先的 AI 动漫短剧生产工作台，面向个人自媒体账号使用。当前目标是支持短剧项目管理、角色和风格模板、分镜生成、图片生成、视频合成、批量任务队列，以及后续接入发布工作流。

## 功能

- React + TypeScript + Vite 本地 Web UI
- Python launcher API
- 项目库、角色库、风格模板、剧集生产、成品库
- 本地 JSON 持久任务队列
- mock 图片生成，默认不消耗真实 API
- gpt-image-2/OpenAI 图片接口接入，并要求二次确认
- ComfyUI 自定义节点和示例工作流
- FFmpeg 竖屏视频合成

## 目录

```text
anime_workflow/        Python 后端、队列、项目库、生成服务
frontend/              React 前端源码
web/launcher/          前端构建产物，launcher 直接服务该目录
scripts/               本地启动和诊断脚本
workflows/comfyui/     ComfyUI 工作流模板
comfyui_custom_nodes/  ComfyUI 自定义节点
tests/                 Python 单元测试
docs/                  设计规格和实现计划
config/                配置模板
```

## 本地运行

安装 Python 依赖后启动 launcher：

```bash
.venv/bin/python scripts/start_launcher.py
```

打开：

```text
http://127.0.0.1:7860
```

前端开发构建：

```bash
cd frontend
npm install
npm run build
```

运行测试：

```bash
.venv/bin/python -m unittest discover -s tests -v
```

本地生产链路 smoke（需要先启动 launcher）：

```bash
python scripts/smoke_production_loop.py --provider comfyui --workflow-template comfyui_external_anime --confirm-openai
```

警告：`openai` 和 `comfyui` provider 可能消耗真实图片 API 额度。没有传入 `--confirm-openai` 时，真实 provider smoke 会在发起网络请求前退出，不会运行。

## 配置

复制配置模板：

```bash
cp config/settings.example.json config/settings.local.json
```

`config/settings.local.json` 用于保存本地 API Key、输出目录等私有配置，已被 `.gitignore` 排除，不应提交到公开仓库。

## GitHub 注意事项

公开仓库不会提交：

- API Key 和本地配置
- 生成图片、视频、任务历史
- ComfyUI 第三方完整安装目录
- Python 虚拟环境和 Node 依赖

需要 ComfyUI 时，请按 `scripts/` 和 `workflows/comfyui/` 中的说明在本地安装。
