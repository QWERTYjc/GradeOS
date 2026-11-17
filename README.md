# GradeOS

**GradeOS** 是本地优先的智能工作台。一个侧栏连接通用任务、批改、文件、Skills、任务与本地账号设置。
原系统保存在 [GradeOS-old](https://github.com/QWERTYjc/GradeOS-old)。

现已包含原材料导入、答卷分组、评分标准确认、Pi 批改、任务暂停/取消、人工复核、
可编辑文档和 PDF 批注导出。单个 Node 服务直接提供静态页面，状态保存到本地文件。

- Agent 依赖 `@earendil-works/pi-agent-core` 和 `@earendil-works/pi-ai`，均锁定 1.5.2；报告排版使用本地 KaTeX 0.16.45。
- Python 只负责 PDF、图像和确定性报告：Pillow、pypdf、ReportLab；另需 Poppler。
- 公开代码包不包含考试、答卷或数据集素材；研究环境中的私有评测资产单独保留。
- 可独立克隆、安装和运行，无需启动旧 GradeOS 服务或数据库。

## 系统界面

- **工作台**：独立对话、文件引用、真实模型执行和成果画布。
- **批改**：沿用现有材料导入、评分确认、批改和复核流程。
- **文件**：统一查找工作台文件和批改产出，以固定版本继续处理，编辑另存新版本。
- **Skills**：教辅、HTML 演示文稿、CSV 数据和代码文本；支持导入 SKILL.md 并显式启用。
- **任务与设置**：后台任务状态、停止任务、本地显示名称、存储位置、模型连接与减少动效。

通用助手只能读取本工作区文件和批改产出、保存文件；不会自动获得其他对话或批改全量上下文。
文件保存在数据目录的 `files/<id>/v<revision>/`，对话和引用快照在 `system.json`。
只有调用模型时，相关上下文才会发送至已配置的服务。本地存储不代表模型推理离线。

当前使用本地服务和浏览器；未打包原生桌面安装器。演示文稿为 HTML、表格为 CSV，
尚无原生 PPTX/XLSX 编辑、终端执行、云账号登录或跨设备同步。官网独立规划。

## 安装与启动

需要 Node >=22.19、Python >=3.11 和 [uv](https://docs.astral.sh/uv/)。

```sh
git clone https://github.com/QWERTYjc/GradeOS.git
cd GradeOS
# macOS 的 PDF 工具；Linux 见下方。
brew install poppler
npm ci --ignore-scripts
uv sync --locked
npm run doctor
npm start
```

打开 <http://127.0.0.1:4173>。Linux 可用
`sudo apt-get install poppler-utils fonts-wqy-zenhei` 安装 PDF 工具和中文批注字体。
不需要前端构建步骤。PDF 工具默认使用本仓库 `.venv`，也支持 `PI_WORKSPACE_PYTHON`。

报告支持分章目录、题号搜索、阅读位置记忆和全文阅读。分数、上下标、积分与矩阵在
浏览器内排版，兼容已有报告的 LaTeX 和可明确识别的 Unicode/OCR 公式。渲染使用
原生 MathML，无 CDN、额外字体下载或模型调用；需要支持 MathML 的现代浏览器。
无法可靠排版的公式保留原文。编辑与 Markdown 下载保留完整评分依据和原始公式，
选中公式添加注释或引用时绑定原文位置。显示变化不会改写已有分数或复核状态。

无 key 时可以导入、查看和整理材料，运行所有离线测试。调用模型前，将 `.env.example`
复制为 `.env`，仅填入自己的 `OPENROUTER_API_KEY`；可选搜索使用 `BRAVE_SEARCH_API_KEY`。
服务启动前加载该文件，key 不发送给浏览器。旧仓库的 `.env` 不会被复制或读取。

## 本地验证与许可

安装依赖后运行 `npm run check`。考试材料与个人评分记录由使用者保存在本地。参见[评测工具](evals/README.md)、[架构](docs/ARCHITECTURE.md)和[批改流程](COHORT.md)。源代码使用 GPL-3.0-only，第三方许可随源码保留。
