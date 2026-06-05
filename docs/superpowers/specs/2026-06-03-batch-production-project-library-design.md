# 批量生产项目库设计

日期：2026-06-03

## 背景

当前本地 AI 动漫工作台已经具备基础单集链路：

- 生成单集分镜
- 使用 mock 或 gpt-image-2 API 生成分镜图片
- 使用 FFmpeg 将图片合成为 9:16 MP4
- 在本地 Web UI 中管理 ComfyUI、API 配置和单集生产

下一阶段目标不是立刻做自动发布或复杂 ComfyUI 视频工作流，而是把单集 demo 流程升级为可长期使用的短剧系列生产工作台。优先选择“方案 B：项目库 + 角色库优先”。

## 目标

第一阶段实现一个轻量但可持续扩展的批量生产模块，让用户能管理一个短剧系列，并稳定批量生产多集内容。

验收目标：

- 能创建 1 个或多个短剧项目。
- 每个项目能保存固定角色设定。
- 每个项目能选择或保存固定画风模板。
- 能批量创建 5-20 集剧集大纲。
- 能对每一集生成分镜、图片和视频。
- 能在成品库查看所有导出视频和相关图片路径。

## 非目标

本阶段不做以下功能：

- 自动发布抖音或 B 站。
- 爬虫抓取小说或剧本资源。
- 复杂账号数据分析。
- 完整 ComfyUI 图生视频、补帧、运镜工作流。
- 多用户、权限、云端同步。

这些功能保留为后续阶段，避免主线过早变重。

## 用户流程

```text
创建项目
  -> 填写角色设定
  -> 选择风格模板
  -> 批量创建剧集大纲
  -> 单集或批量生成分镜
  -> 单集或批量生成图片
  -> 单集或批量合成视频
  -> 在成品库查看结果
```

## 页面结构

左侧导航调整为：

```text
总览
项目库
角色库
风格模板
剧集生产
成品库
服务启动
API 配置
图片测试
视频测试
```

### 项目库

项目库用于管理短剧系列。

字段：

- `project_id`：项目唯一标识，兼容文件夹名。
- `name`：项目名称。
- `genre`：题材，如悬疑、甜宠、逆袭、古风。
- `platform`：目标平台，如 douyin、bilibili。
- `default_duration_seconds`：默认单集时长。
- `default_shot_count`：默认分镜数量。
- `default_style_id`：默认风格模板。
- `premise`：系列总设定。
- `status`：active 或 archived。
- `created_at` / `updated_at`。

页面能力：

- 创建项目。
- 选择当前项目。
- 查看项目的剧集数量、已出图数量、已导出视频数量。
- 编辑项目基础设定。

### 角色库

角色库以项目为边界保存固定角色。

字段：

- `character_id`
- `project_id`
- `name`
- `role`
- `appearance`
- `personality`
- `costume`
- `reference_image`
- `prompt_fragment`

设计原则：

- 分镜生成时使用角色的身份和性格。
- 图片生成时使用角色的外观、服装和参考图路径。
- 暂时不做复杂角色关系图，只保存能直接进入 prompt 的设定。

页面能力：

- 为当前项目新增角色。
- 编辑角色设定。
- 选择项目主角。
- 后续可扩展角色参考图上传。

### 风格模板

风格模板用于减少每集重复配置，保持画面统一。

字段：

- `style_id`
- `name`
- `base_prompt`
- `negative_prompt`
- `aspect_ratio`
- `palette`
- `camera_style`
- `provider`

默认模板：

- `clean_anime_drama`
- `dark_suspense_anime`
- `sweet_romance_anime`

页面能力：

- 选择默认模板。
- 编辑模板 prompt。
- 给项目绑定一个默认模板。

### 剧集生产

剧集生产从当前单集表单升级为项目内工作台。

页面布局：

- 左侧：当前项目、批量创建按钮、剧集列表。
- 右侧：当前剧集的分镜、图片状态、视频状态。

剧集状态：

```text
draft
storyboarded
imaged
exported
failed
```

字段：

- `episode_id`
- `project_id`
- `episode_no`
- `title`
- `premise`
- `duration_seconds`
- `shot_count`
- `status`
- `storyboard_path`
- `video_path`
- `error`
- `created_at` / `updated_at`

批量创建能力：

- 输入集数，如 10。
- 输入系列推进方向，如“每集一个线索，最后留反转”。
- 系统创建连续剧集大纲。
- 第一版可以使用规则模板生成，后续再接入文本模型。

生产能力：

- 单集生成分镜。
- 单集生成图片。
- 单集合成视频。
- 批量生成分镜。
- 批量生成图片。
- 批量合成视频。

批量操作第一版可以同步执行，后续再升级任务队列。为避免一次请求过长，前端应逐集调用 API，并显示每集结果。

### 成品库

成品库集中展示输出结果，不要求用户去文件夹翻。

展示内容：

- 项目名称。
- 集数。
- 视频路径。
- 导出时间。
- 图片数量。
- 失败信息。

能力：

- 查看最新导出视频路径。
- 查看单集图片目录。
- 载入对应剧集。
- 后续扩展打开文件夹、复制标题文案、发布准备。

## 数据存储

继续使用本地 JSON 文件，保持轻量。

建议目录：

```text
data/projects/{project_id}/project.json
data/projects/{project_id}/characters/{character_id}.json
data/projects/{project_id}/styles/{style_id}.json
data/projects/{project_id}/episodes/{episode_id}.json
data/storyboards/{project_id}/{episode_id}/storyboard.json
data/assets/source_frames/{project_id}/{episode_id}/
data/assets/anime_frames/{project_id}/{episode_id}/
data/assets/api_metadata/{project_id}/{episode_id}/
data/exports/{project_id}-{episode_id}.mp4
```

`data/storyboards`、`data/assets` 和 `data/exports` 保持现有路径，避免破坏当前已跑通的生产链路。新增 `data/projects` 用于项目、角色、风格、剧集元数据。

## 后端 API

建议新增接口：

```text
GET  /api/projects
POST /api/projects
GET  /api/projects/{project_id}
POST /api/projects/{project_id}

GET  /api/projects/{project_id}/characters
POST /api/projects/{project_id}/characters

GET  /api/projects/{project_id}/styles
POST /api/projects/{project_id}/styles

GET  /api/projects/{project_id}/episodes
POST /api/projects/{project_id}/episodes/batch
POST /api/projects/{project_id}/episodes/{episode_id}/storyboard
POST /api/projects/{project_id}/episodes/{episode_id}/images
POST /api/projects/{project_id}/episodes/{episode_id}/video

GET  /api/outputs
```

现有 `/api/episode/*` 可以先保留，用于兼容当前单集页面。新模块优先走 `/api/projects/*`。

## 生产逻辑

项目级生产参数向下传递：

- 项目提供题材、平台、默认时长、默认分镜数。
- 角色提供固定主角和 prompt 片段。
- 风格模板提供画风 prompt。
- 剧集提供当前集梗概。

生成分镜时组合：

```text
项目总设定 + 当前集梗概 + 主角设定 + 风格模板 + 平台要求
```

生成图片时组合：

```text
分镜 image_prompt + 角色外观 + 风格模板 base_prompt + negative_prompt
```

合成视频时继续使用 FFmpeg。ComfyUI 视频工作流暂不接入批量模块，但接口边界要保留：未来可把 `video_exporter` 从 FFmpeg 替换或扩展为 ComfyUI 视频工作流。

## 错误处理

每个项目、角色、风格、剧集保存时做基础校验：

- ID 不能为空。
- ID 只能使用中文、英文、数字、下划线、短横线。
- 剧集数量限制在 1-50。
- 单集分镜数量限制在 1-24。
- 单集时长限制在 3-180 秒。

生产失败时：

- 将当前剧集状态设为 `failed`。
- 保存 `error` 字段。
- 不删除已生成的分镜或图片。
- 用户可以重新执行当前步骤。

## 测试计划

后端测试：

- 创建项目后能读取项目列表。
- 创建角色后能在项目下读取。
- 创建风格模板后能绑定项目。
- 批量创建 10 集后，剧集编号连续。
- 单集分镜生成会读取项目、角色和风格设定。
- 单集图片生成后更新剧集状态。
- 单集视频导出后更新 `video_path`。
- 失败时保存 `error`，不破坏已有文件。

前端验证：

- 项目库能创建并选择项目。
- 角色库能新增角色。
- 风格模板能编辑默认模板。
- 剧集生产能批量创建剧集。
- 单集能生成分镜、图片、视频。
- 成品库能看到导出视频路径。

## 第一阶段交付边界

第一阶段只交付轻量项目化批量生产能力：

- 项目库
- 角色库
- 风格模板
- 剧集列表
- 批量创建剧集
- 单集生产动作
- 成品库列表

批量全自动队列、ComfyUI 视频工作流、自动发布、爬虫资源库作为后续阶段。

## 后续阶段

第二阶段：批量队列

- 一键批量生成分镜。
- 一键批量生成图片。
- 一键批量导出视频。
- 每集状态实时更新。
- 失败重试。

第三阶段：质量增强

- ComfyUI 图生视频工作流。
- 转场、运镜、补帧。
- 字幕和封面。
- 视频预览。

第四阶段：发布准备

- 标题、简介、标签生成。
- 抖音/B 站发布清单。
- 封面选择。
- 半自动发布。
