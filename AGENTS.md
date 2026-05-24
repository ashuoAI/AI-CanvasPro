# AI CanvasPro 项目说明

## 基本约定

- 默认使用中文交流与撰写说明。
- 代码注释要详细，尤其是业务规则、状态流转、路径安全、异步任务恢复、兼容旧数据等不容易从代码直接看出的部分。
- 修改代码时优先保持现有风格。本项目不少 JavaScript 文件经过混淆或压缩，能局部改动时不要顺手大规模重排。

## 项目定位

AI CanvasPro 是一个基于节点画布的 AI 多模态创作工具，核心能力围绕无限画布、节点连线、AI 文本/图像/视频/音频生成、素材管理、工作流、项目保存与桌面端集成展开。

项目同时支持：

- 浏览器访问本地服务：默认 `http://localhost:8777`。
- Electron 桌面应用：`package.json` 的入口是 `electron/main.js`。
- 本地文件与数据目录：项目、上传素材、输出文件、工作流等默认保存在仓库下的 `user/`、`data/`、`output/`，桌面打包环境会使用 Electron 用户数据目录或可配置的数据根目录。

## 技术栈与运行方式

- 前端是原生 HTML / CSS / JavaScript ESM，没有 React、Vue、Vite 等常见框架入口。
- 后端是 Python 标准库 `http.server` + 自定义路由服务，入口为 `server.py`。
- 桌面端使用 Electron，主进程在 `electron/main.js`，预加载脚本在 `electron/preload.cjs`。
- `package.json` 只声明很少的依赖和入口，没有 `scripts`；常用命令需要直接运行。
- Python 依赖在 `requirements.txt`：`requests`、`pillow`、`scenedetect`、`opencv-python`、`pymysql`。
- 默认服务端口是 `8777`，可通过环境变量 `AICANVAS_PORT` 改写。

常见本地启动方式：

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python server.py
```

Electron 开发启动通常围绕 `electron/main.js` 和本地 Python 服务工作；如果需要运行桌面壳，先确认依赖已安装，再使用 Electron 入口启动。

## 目录结构

- `index.html`：主画布页面。
- `login.html`：登录页面。
- `main.js`：前端主入口，负责注册节点、初始化渲染器、画布交互、项目启动、设置面板、任务中心、自动更新提示等。
- `style.css` 与 `styles/`：样式文件。`styles/` 按功能拆分，如画布、节点、菜单、设置、任务、主题、响应式等。
- `src/components/`：节点组件与节点相关 UI。包含源素材节点、AI 生成节点、故事板、注释、3D/全景场景等。
- `src/components/aigenImage/`、`src/components/aigenVideo/`、`src/components/aigenText/`：AI 生成节点的 UI、状态同步与任务编排逻辑。
- `src/core/`：画布核心逻辑，包括渲染、交互、数学计算、视口聚焦、任务生命周期、虚拟化和 store。
- `src/core/stores/`：状态分域。`appStore.js` 汇出 facade、graph、ui、workspace、legacy kernel 等入口。
- `src/modules/`：业务模块集合，如项目管理、素材管理、历史记录、剪贴板、设置、预览模式、工作流、快捷键、图像编辑、视频/音频工具、全景场景、订阅权限等。
- `src/services/`：前端服务封装，如项目服务、文件服务、诊断、外部链接、媒体任务、缩略图缓存、本地资源清理等。
- `src/utils/`：通用工具，如 DOM、格式化、校验、路径、缩略图持久化、调试脱敏等。
- `src/config/modelConfig.js`：图像模型和提供商配置，包含 GRSAI、PPIO、APIMart、RunningHub、AICanvas 开发占位模型等。
- `api/`：前端请求层和各类 AI/本地 API 封装。包括图像、视频、文本、音频、上传、配置、订阅、RunningHub、Dreamina、APIMart、错误解析等。
- `api/adapters/`：第三方提供商适配器，如 RunningHub、PPIO、Gemini、APImart。
- `api/errors/`：统一 API 错误类型与不同提供商错误解析器。
- `backend/services/`：Python 后端的路由与业务服务拆分。
- `backend/sql/init_database.sql`：MySQL 初始化脚本，包含用户、认证 token、个人项目、个人设置、项目协作等表。
- `electron/`：Electron 主进程、IPC、预加载、安全设置、最近项目、自动更新、本地媒体任务队列、诊断、本地资源清理等。
- `assets/`、`images/`、`vendor/`：静态资源、图标、光标、Three.js 及示例加载器、内置 3D 角色资源。
- `data/`、`output/`、`user/`：运行期数据目录，开发时可能产生或修改，不应轻易当成源码重构对象。
- `docs/`、`README.md`、`使用说明.md`：项目文档。当前部分文档在命令行中可能因编码显示为乱码，修改前要确认编码。

## 前端架构要点

- 画布主容器和节点渲染围绕 `src/core/renderer.js`、`src/core/interaction.js`、`src/core/math.js` 与 store 工作。
- 节点通过 `src/modules/registry.js` 注册。主入口注册了 `source-text`、`source-image`、`source-video`、`source-audio`、`comment-note`、`ai-image`、`ai-text`、`ai-video`、`ai-audio`、`scene-detection`、`group`、`debug`、`storyboard`、`storyboard-script`、`panorama-scene`、`panorama-360` 等类型。
- `src/core/store.js` 已是兼容入口，会提示迁移到 `src/core/stores/appStore.js` 或分域 store。新代码优先使用 `graphStore`、`uiStore`、`workspaceStore` 等分域入口。
- AI 节点通常分为 UI 模块、状态同步模块和任务编排模块；修改某一类节点时，优先在对应子目录内寻找既有 helper。
- 前端请求统一通过 `api/requester.js` 一类封装处理超时、重试、错误解析和诊断日志。
- 引用节点内容、素材引用、缩略图、任务恢复等逻辑分散在 `src/modules/` 与对应节点模块中，改动前要搜索相关测试。

## 后端架构要点

- `server.py` 是本地 HTTP 服务入口，负责环境变量、目录路径、静态文件、CORS/本地访问控制、缓存头、路由分发和服务对象初始化。
- `HttpRouteDispatcher` 负责把 `/api/v2/...` 请求转交给更细的服务。
- 主要服务包括：
  - `ConfigRouteService`：API Key、自定义 AI 配置。
  - `JsonFileRouteService`：项目、素材、工作流、用户设置等 JSON 文件读写。
  - `LibraryFileRouteService`：预设、素材缩略图、工作流缩略图。
  - `MediaFileRouteService`：上传、输出保存、从 URL 保存、缩略图/派生图、输出文件管理。
  - `LocalMediaProcessingRouteService`：本地媒体处理。
  - `RemoteProxyRouteService`：远程任务查询、上传代理、RunningHub 工作流代理。
  - `DreaminaRouteService` / `DreaminaCliService`：即梦登录、提交、查询与本地 CLI/浏览器自动化相关流程。
  - `DatabaseRouteService`、`ProjectDataService`、`SettingsDataService`、`UserAuthService`：数据库项目、设置与认证能力。
  - `SubscriptionGateService`、`SubscriptionRemoteClient`：订阅/CDKEY/模型权限相关逻辑。
- 后端有大量路径安全处理，尤其是 `output/`、`data/uploads/`、`data/assets/`、`cam-output/` 等虚拟路径到本地路径的映射。改文件读写相关逻辑时必须保留路径归一化与越权检查。

## Electron 架构要点

- `electron/main.js` 会启动或探测本地 Python 服务，加载 `http://127.0.0.1:8777/`，并管理单实例、窗口状态、日志、诊断、自动更新、项目打开/保存和本地媒体任务。
- `electron/preload.cjs` 通过 `contextBridge` 暴露安全 API：
  - `window.aiCanvasDesktop`：版本、更新检查、更新事件。
  - `window.electronAPI`：项目、剪贴板、安全设置、素材导入、媒体任务、本地预览 URL、系统文件夹、外部链接、诊断、本地资源清理等。
- 主进程启用了 `contextIsolation`、禁用 `nodeIntegration`，并使用 sandbox。渲染进程不要直接假设 Node API 可用。
- 桌面端会使用本地访问 token、私有预览协议、恢复快照、最近项目列表和系统 recent documents。

## 数据与配置

- API 配置默认在 `user/config.json`，用户设置在 `user/settings.json`，快捷键在 `user/shortcuts.json`。
- V2 项目、素材和工作流通过 `/api/v2/projects`、`/api/v2/assets`、`/api/v2/workflows` 等接口读写 JSON。
- 上传文件默认在 `data/uploads/`，输出文件默认在 `output/`，素材库默认在 `data/assets/`。
- 重要环境变量包括：
  - `AICANVAS_PORT`
  - `AIC_BIND_HOST`
  - `AIC_LAN_MODE` / `AIC_ENABLE_LAN`
  - `AIC_ALLOWED_ORIGINS`
  - `AIC_LOCAL_TOKEN`
  - `AIC_USER_DIR`
  - `AIC_CANVAS_DIR`
  - `AIC_DATA_DIR`
  - `AIC_UPLOADS_DIR`
  - `AIC_ASSETS_DIR`
  - `AIC_OUTPUT_DIR`
  - `AIC_FFMPEG_EXE`
  - `AIC_FFPROBE_EXE`
- `ecosystem.config.js` 是 PM2 部署配置示例，包含端口、数据库连接、JWT/认证密钥等生产部署参数；不要把其中的默认密钥当成安全生产配置。

## 第三方 AI 与模型

项目内置或适配了多类提供商/模型：

- 图像：GRSAI、PPIO、APIMart、RunningHub、AICanvas 开发占位模型。
- 视频：Dreamina/即梦、APIMart、RunningHub/RunningHub 工作流等。
- 音频：TTS、音色克隆、音频分离、RunningHub 工作流等。
- 文本：Gemini、OpenAI 兼容接口和其他配置来源。
- 上传/代理：RunningHub、APIMart、Bed 图床、本地保存与远程 URL 转存。

模型权限、VIP/CDKEY 与特定 RunningHub 工作流 ID 在前后端都有对应判断，修改模型列表或任务恢复逻辑时要同步检查订阅访问控制与测试。

## 测试

- JavaScript 单元测试分散在 `api/` 和 `src/` 旁边，文件名通常是 `*.test.js`。
- 测试使用 Node 内置 `node:test` 与 `node:assert/strict`，可按文件运行：

```bash
node --test api/requester.test.js
node --test src/modules/assetRestoreLayout.test.js
```

- 也可以尝试批量运行：

```bash
node --test "api/*.test.js" "src/**/*.test.js"
```

- `playwright.config.js` 配置了 Chromium smoke/e2e 测试，默认会启动静态服务到 `127.0.0.1:4173`；当前仓库中没有明显的 `e2e/` 目录时，先确认测试文件是否存在再运行。
- Python 侧没有看到独立测试框架配置；后端改动至少应手动启动 `python server.py` 并验证相关 API。

## 开发注意事项

- 许多源码文件包含混淆包装，但仍是 ESM 模块。修改时优先定位清晰命名的函数、导出和测试，不要格式化整文件。
- 文件读写、上传、代理、外部 URL 打开、Electron IPC 都是安全敏感区域。新增能力时要做路径归一化、扩展名/大小限制、请求来源校验和错误兜底。
- 运行期目录 `data/`、`output/`、`user/` 可能包含用户数据或生成文件，清理前必须确认需求。
- `README.md`、`使用说明.md` 等中文文档可能存在编码显示问题；修改前先确认实际编码，避免把文档二次损坏。
- 前端 UI 改动要同时检查 `styles/` 中对应拆分样式和历史大文件 `style.css`，避免只改一处导致桌面端或旧入口样式不一致。
- 新增节点类型通常需要同步处理：节点组件、注册、默认尺寸、工具栏、保存/恢复、入边/出边策略、任务生命周期、测试。
- 新增 API 提供商或模型时通常需要同步处理：`src/config/modelConfig.js`、对应 `api/*Api.js` 或 adapter、错误解析、上传策略、订阅限制、节点 UI 和恢复逻辑。
- 对异步生成任务要保留恢复能力，注意 `taskId`、`provider`、`model`、任务状态、轮询查询路径和本地输出保存之间的一致性。

## 已知项目状态

- 当前仓库根目录存在 `.vs/`、`data/`、`output/`、`user/` 等本地运行或编辑器目录。
- `AGENTS.md` 在本次整理前只包含“注释要详细”的项目要求，且命令行显示存在编码异常；本文件已改写为清晰的 UTF-8 中文说明。
