<div align="center">

<img src="images\favicon.svg" width="64" height="64" alt="AI Canvas Logo"/>

# AI Canvas

**基于节点的 AI 多模态画布编辑器**

一款纯原生 Web 应用（HTML / CSS / JS），让你在无限画布上，通过可视化节点连线的方式，自由组合 AI 能力，生成文本、图像、视频与音频。

[!\[作者：阿硕\](https://img.shields.io/badge/作者-阿硕-pink?style=flat-square null)](https://space.bilibili.com/1876480181)
[!\[Bilibili\](https://img.shields.io/badge/Bilibili-主页-00A1D6?style=flat-square\&logo=bilibili null)](https://space.bilibili.com/1876480181)
[!\[License\](https://img.shields.io/badge/License-MIT-green?style=flat-square null)](LICENSE)

</div>

***

<br />

## ✨ 功能特性

### 🎨 无限画布

- 自由缩放、平移的无限画布
- 小地图导航 + 画布对齐网格
- 多画布 切换
- 适应画布（一键归位）

### 🤖 AI 节点类型

| 节点类型              | 说明                      | 支持模型                       |
| ----------------- | ----------------------- | -------------------------- |
| 🖼️ **AI 图像生成节点** | 输入提示词，一键生成图片，支持批量出图     | Banana Pro、GRSAI 等         |
| ✍️ **AI 文本生成节点**  | 多轮对话、流式输出，支持 @ 引用其他节点结果 | Gemini、GPT 系列等 OpenAI 兼容接口 |
| 🎬 **AI 视频生成节点**  | 文生视频 / 图生视频             | 主流视频模型                     |
| 🔊 **AI 音频生成节点**  | 文本转语音生成                 | TTS 模型                     |

### 💾 项目管理

- 多项目切换（左侧边栏项目面板）
- `Ctrl+S` 保存画布到本地 `user/Canvas Project/` 目录
- 自动缓存画布状态，刷新页面即时恢复
- 项目文件为标准 JSON 格式，方便迁移（类似comfyui操作，直接拖拽json文件到画布即可打开）

## 🚀 快速开始

### 方法 1：源码运行（推荐开发者）

1. 需要安装git /ffmpeg/python3.12以上
   1. git:[Git - Install for Windows](https://git-scm.com/install/windows)
   2. ffmpeg:[Download FFmpeg](https://ffmpeg.org/download.html)
   3. python:[Welcome to Python.org](https://www.python.org/)
2. **克隆仓库**
   ```bash
   任意一个不带中文路径的目录 上面的地址栏 输入 CMD
   # 克隆项目
   git clone https://github.com/ashuoAI/AI-CanvasPro.git
   # 进入项目
   cd AI-CanvasPro
   ```
3. **安装依赖并启动**
   ```bash
   # 创建虚拟环境
   python -m venv venv
   # 激活虚拟环境
   venv\Scripts\activate.bat
   # 安装依赖
   pip install -r requirements.txt
   # 启动服务
   python server.py
   ```
4. **打开浏览器**
   访问 <http://localhost:8777> 即可使用。

### 开发环境与验证

- 本地服务默认端口为 `8777`，可通过环境变量 `AICANVAS_PORT` 修改。
- 前端测试使用 Node.js 内置测试运行器：
  ```bash
  npm test
  ```
- 后端依赖集中维护在 `requirements.txt`，新增 Python 依赖时请同步写入该文件。
- 本地用户数据默认写入 `user/`、生成输出写入 `output/`，这些目录不应作为功能代码直接提交。

### 扩展节点与功能

- 节点类型元数据集中在 `modules/nodeMeta.js`，节点注册入口在 `modules/registry.js`。
- 新增节点组件时，优先复用 `components/` 下已有节点的 `render/update/unmount` 模式。
- 涉及画布状态的改动应通过 `src/core/store.js` 的 action 更新，并补充对应的 `tests/` 单元测试。
- 涉及节点命中、坐标转换、连线计算的改动应同步覆盖 `tests/math.test.js` 或相关交互测试。

### 方法 2：一键整合包（推荐普通用户）

1. **下载整合包**
   [点击下载](https://github.com/ashuoAI/AI-CanvasPro/releases)
2. **解压文件**
   将下载的压缩包解压到不带中文的路径，例如 `D:\AI-CanvasPro`
3. **一键启动**
   双击目录下的 **`双击运行.bat`** 文件，即可自动跳出项目画布。
   访问 <http://localhost:8777> 即可使用。

***

# 🖱️ 使用说明

更完整的用户手册请直接看：[使用说明.md](file:///h:/AI/Al%20Canvas%E7%BC%96%E7%A8%8B/%E4%BD%BF%E7%94%A8%E8%AF%B4%E6%98%8E.md)

## ⚙️ 配置 API Key

1. 点击左下角头像 → **设置**
2. 切换到 **API 输入** 标签页
3. 填写对应提供商的 API Key，点击**保存**

| 提供商              | 说明                                                                                |
| ---------------- | --------------------------------------------------------------------------------- |
| **RunningHub**   | 图像生成，前往 [runninghub.com](https://www.runninghub.cn/?inviteCode=rh-v1312) 获取 Key   |
| **APImart**      | 大语言模型,图像生成，前往 [APImart.ai](https://apimart.ai/zh/register?aff=ashuoai) 获取 Key     |
| **派欧云 (PPIO)**   | 大语言模型,图片生成，前往 [ppio.com](https://ppio.com/user/register?invited_by=SF4VL3) 获取 Key |
| **GRSAI**        | 大语言模型,图像生成，前往 [grsai.com](https://grsai.com/zh/dashboard/user-info) 获取 Key        |
| **通用 OpenAI 接口** | 支持任何兼容 OpenAI 格式的第三方接口                                                            |

***

### 基础操作

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

### 引用其他节点（@ 语法  / 预设 ）

在 生成节点的提示词编辑框中，输入 `@` 即可弹出引用菜单，选择画布上任意节点，其输出结果将被动态嵌入提示词中。

输入 `/` 引用预设命令，快速调用内置预设（后续支持自定义预设）

***

## 👤 作者

**阿硕**

- 📺 Bilibili：[space.bilibili.com/1876480181](https://space.bilibili.com/1876480181)

***

