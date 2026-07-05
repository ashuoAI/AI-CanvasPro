<div align="center">

<img src="images\favicon.svg" width="64" height="64" alt="AI Canvas Logo"/>

# AI Canvas

**基于节点的 AI 多模态画布编辑器**

一款公开发布的 Electron 桌面应用，让你在无限画布上，通过可视化节点连线的方式，自由组合 AI 能力，生成文本、图像、视频与音频。

现已支持接入 RH AI 应用、ComfyUI 云端工作流和 ComfyUI 本地工作流，可将外部模型与工作流能力统一带入画布节点中编排复用。

[![作者：阿硕](https://img.shields.io/badge/作者-阿硕-pink?style=flat-square)](https://space.bilibili.com/1876480181)
[![Bilibili](https://img.shields.io/badge/Bilibili-主页-00A1D6?style=flat-square\&logo=bilibili)](https://space.bilibili.com/1876480181)
[![License](https://img.shields.io/badge/License-Non--Open--Source%20%7C%20NC-orange?style=flat-square)](LICENSE)

</div>

***

## 授权与非官方部署声明

本项目为 **公开发布的 Electron 桌面应用**，不是开源软件，也不是 OSI 定义下的开源项目。除非另有书面授权，版权方保留所有权利。

公开 GitHub 页面、公开下载或公开发布不等于开源授权，也不代表允许修改、再分发、改包发布或用于商业用途。关于开源定义可参考 [OSI Open Source Definition](https://opensource.org/osd)；关于仓库许可证可参考 [GitHub Licensing a repository](https://docs.github.com/articles/licensing-a-repository)。

未经作者单独书面授权，禁止将本项目或其衍生版本用于商业用途、SaaS、云服务、公开托管服务、收费服务、商业交付、外包交付、广告引流、会员订阅、二次分发、改包发布或其他直接/间接商业收益场景。

除作者明确公布的地址外，任何第三方公开部署、镜像站点、托管服务或改版服务均为非官方行为，与作者无关；请勿在非官方站点输入 API Key、授权码或其他敏感信息。

详细条款请查看 [LICENSE](./LICENSE) 和 [COMMERCIAL-LICENSE.md](./COMMERCIAL-LICENSE.md)。

***

## 视频演示

- [使用说明1](https://www.bilibili.com/video/BV1RX5z6gEXq/)
- [RH AI 应用 / ComfyUI 本地与云端接入教程](https://www.bilibili.com/video/BV1VqT764E7d)
- [新影视二创高效做法Scail2+语音工作室演示](https://www.bilibili.com/video/BV1nX7n6uEbi/)
- [浏览器节点用法](https://www.bilibili.com/video/BV1Q87u6sEpM/)
- [seedance2.0 线条控制运镜玩法](https://www.bilibili.com/video/BV1ZzjL6UEoA/)
- [Scail2 全面实测使用方法](https://www.bilibili.com/video/BV16DJH6jEmk/)
- [RH 模型 Bernini 详细使用说明](https://www.bilibili.com/video/BV1TwEb6gEsC)
- [游戏实际演示制作教程](https://www.bilibili.com/video/BV17soQB7EwB)
- [影视人物替换演示](https://www.bilibili.com/video/BV1YEDKBwEz7)
- [人物 / 场景一致性 360° 全景图提取 SD2.0 生成演示](https://www.bilibili.com/video/BV1FqdyBwEGx)
- [人物场景固定 seedance 2.0 生成](https://ashuoai.github.io/AI-CanvasPro/)

## ✨ 功能特性

### 🎨 无限画布

- 自由缩放、平移的无限画布
- 小地图导航 + 画布对齐网格
- 多画布 切换
- 适应画布（一键归位）
- 框选、多选、编组、对齐、复制粘贴和撤销重做

### 🤖 AI 节点类型

| 节点类型              | 说明                          | 支持模型                       |
| ----------------- | --------------------------- | -------------------------- |
| 📥 **源素材节点**      | 承载文本、图片、视频、音频素材，支持拖拽导入和节点连线 | 本地文件 / 远程素材 / 生成结果       |
| 🖼️ **AI 图像生成节点** | 输入提示词，一键生成图片，支持批量出图         | Banana Pro、GRSAI 等         |
| ✍️ **AI 文本生成节点**  | 多轮对话、流式输出，支持 @ 引用其他节点结果     | Gemini、GPT 系列等 OpenAI 兼容接口 |
| 🎬 **AI 视频生成节点**  | 文生视频 / 图生视频                 | 主流视频模型                     |
| 🔊 **AI 音频生成节点**  | 文本转语音生成                     | TTS 模型                     |
| ✂️ **剪辑节点**       | 把图片 / 视频片段编排成简单时间线并导出       | 本地媒体处理                     |
| 🧩 **拼图 / 分镜节点**  | 拼接图片、整理分镜、生成分镜脚本            | 画布编排能力                     |
| 🌐 **浏览器节点**      | 从网页提取图片、视频和文字，发送到画布继续创作     | Web 参考 / 素材采集              |
| 🌐 **360 全景图节点**  | 生成沉浸式 360 度全景图像             | 全景生成模型                     |
| 📐 **3D导演台节点**    | 创建和编辑 3D 场景，支持模型导入与场景布局     | 3D 渲染引擎                    |
| 💬 **注释节点**       | 添加文本注释、说明和标记，增强画布可读性、作为标记跳转 | 无（纯功能节点）                   |

### 🛠️ 媒体工具链

- 图片：裁剪、标注、遮罩编辑、擦除 / 重绘、主体识别、抠图、高清、扩图、宫格裁剪、360 全景图。
- 视频：裁剪、抠像、擦除、高清、倒放、音画分离、对口型、抽帧、场景检测、继续生成视频。
- 音频：播放预览、裁剪、音色克隆、音色转换、人声分离、语音工作室批量处理。
- 生成任务：任务进度、后台完成提示、声音提醒、取消、刷新后恢复、结果回填到节点。

### 💾 项目管理

- 多项目切换（左侧边栏项目面板）
- `Ctrl+S` 保存画布到本地 `user/Canvas Project/` 目录
- 自动缓存画布状态，刷新页面即时恢复
- 项目文件保存画布结构、节点、连线和素材路径；完整迁移建议使用项目资源收集 / `.aicpkg` 项目包，或同步携带 `output/`、`data/uploads/` 等素材目录。
- 支持资产库、工作流复用、文件管理、项目资源收集和项目包迁移

### 🧠 创作辅助

- 支持 `@` 引用画布节点、资产和上游结果，把文本设定、生成结果或参考素材带入当前提示词。
- 支持 `/` 打开预设命令菜单，按当前节点类型快速插入常用提示词模板。
- 支持右下角 Agent 入口，用自然语言描述画布操作。
- 支持 API 连接测试、订阅中心、VIP 工作流提示和自动更新。

## 🎬 适合做什么

- 角色 / 场景 / 产品图参考整理
- 文生图、图生图、图片编辑和批量出图
- 图片继续生成视频、视频编辑、视频抠像和高清
- 文案、脚本、分镜、旁白、音色克隆和音频处理
- 把常用节点流程保存成资产或工作流，后续一键复用

当前最新版本：[v0.5.3](https://github.com/ashuoAI/AI-CanvasPro/releases/tag/v0.5.3)

更新内容可以查看：[release_notes.txt](./release_notes.txt)

## 🚀 快速开始

### 方法 1：下载应用版（推荐普通用户）

普通用户建议优先使用应用版，不需要手动配置源码环境。Windows 和 macOS 都可以在 GitHub Releases 下载。

1. **下载应用**
   - 最新版下载页：[GitHub Releases Latest](https://github.com/ashuoAI/AI-CanvasPro/releases/latest)
   - 全部版本下载页：[GitHub Releases](https://github.com/ashuoAI/AI-CanvasPro/releases)
   - Windows 用户：在 Assets 中下载 `AI-CanvasPro-windows-*.exe`
   - macOS 用户：在 Assets 中下载 `AI-CanvasPro-Mac-arm64-*.dmg` 或 `.zip`
2. **安装并启动**
   - Windows：双击下载的 `.exe` 文件。
   - macOS：打开 `.dmg` 或解压 `.zip` 后启动应用。
3. **首次使用**
   打开应用后，先在设置里配置对应平台的 API Key，再开始创建画布节点。

***

## ⚙️ 配置 API Key

1. 点击左下角头像 → **设置**
2. 切换到 **API 输入** 标签页
3. 填写对应提供商的 API Key，点击**保存**

| 提供商                  | 说明                                                                                |
| -------------------- | --------------------------------------------------------------------------------- |
| **即梦官方（目前只能高级会员）**   | 设置-api输入-最下面登陆扫码 对应：图像生成-即梦，视频生成-即梦视频                                             |
| **RunningHub**       | 图像生成，前往 [runninghub.com](https://www.runninghub.cn/?inviteCode=rh-v1312) 获取 Key   |
| **APImart**          | 大语言模型,图像生成，前往 [APImart.ai](https://apimart.ai/zh/register?aff=ashuoai) 获取 Key     |
| **派欧云 (PPIO)（准备下架）** | 大语言模型,图片生成，前往 [ppio.com](https://ppio.com/user/register?invited_by=SF4VL3) 获取 Key |
| **GRSAI**            | 大语言模型,图像生成，前往 [grsai.com](https://grsai.com/zh/dashboard/user-info) 获取 Key        |
| **火山引擎（火山方舟）**      | 豆包 / 火山方舟模型，前往 [火山方舟控制台](https://console.volcengine.com/ark/) 或 [API Key 文档](https://www.volcengine.com/docs/82379/1541594) 获取 Key |
| **通用 OpenAI 接口**     | 支持任何兼容 OpenAI 格式的第三方接口                                                            |

***

### 基础操作

更多快捷键可以在 **设置 → 快捷键** 中查看和修改。

| 操作                        | 说明                                       |
| ------------------------- | ---------------------------------------- |
| **双击画布**                  | 快速添加 AI 生成节点                             |
| **左键拖拽**                  | 移动节点                                     |
| **右键画布**                  | 打开右键菜单                                   |
| **滚轮**                    | 缩放画布                                     |
| **中键/空格拖拽**               | 平移画布                                     |
| **Ctrl+S**                | 保存当前画布                                   |
| **Ctrl+Z / Shift+Ctrl+Z** | 撤销 / 重做                                  |
| **D**                     | 删除选中节点（可在“设置→键盘快捷键”里改成 Delete/Backspace） |
| **节点左侧** **`+`** **按钮**   | 打开节点添加菜单                                 |

### 连接节点

1. 鼠标悬停到节点边缘，出现连接锚点
2. 从输出锚点拖拽到目标节点的输入锚点
3. 连线建立后，上游节点的结果会自动流向下游

### `@` 引用和 `/` 预设

在生成节点的提示词编辑框中输入 `@`，会弹出引用菜单。你可以选择画布上的节点、资产或上游结果，把角色设定、场景说明、参考图、参考视频、参考音频等内容带到当前节点里继续生成。

在提示词编辑框中输入 `/`，会打开预设命令菜单。选择预设后会自动插入常用提示词模板，再按当前需求继续修改即可。不同节点会显示不同预设，以当前界面为准。

图片、视频、音频这类素材优先用连线传递；文本设定、说明和提示词片段常用 `@` 引用。

***

## 👤 作者

**阿硕 联系微信：shuoerone**

- 📺 Bilibili：[space.bilibili.com/1876480181](https://space.bilibili.com/1876480181)

## 反馈/交流群

<img src="https://api.ashuoai.com/static/contact/fankui.jpg?v=20260705" alt="反馈/交流群二维码" width="360">

新功能和BUG反馈可以在这里提出：[点击这里](https://i1etb6xynr.feishu.cn/wiki/N2C3wD6SgisOpek11mfcfJCinkr?from=from_copylink)
