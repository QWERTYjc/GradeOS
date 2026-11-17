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

## 可选私有 M2 评测资产

以下命令仅适用于已经自行取得授权并安装私有评测材料的环境；公开代码包不附带这些材料。在第一次导入前使用一个新目录：

```sh
npm run fixtures:workspace -- --fixture m2 --data .workspace-m2
npm start -- --data .workspace-m2
```

导入 21 页 MS 和 28 页答卷，不导入评分详情、不启动模型请求。任务的评分标准确认、
批改启动和复核沿用工作台流程。不要同时开启两个服务写入同一个工作台目录。

```sh
npm run check:public
npm run fixtures:prepare -- --fixture m2 --output runs/m2-input
node src/run.mjs --input runs/m2-input --output runs/m2-preflight
npm run medly:prepare -- --answer maths_0001 --output runs/medly-0001
```

`check:public` 运行 Node/Python 离线测试；`check` 额外校验私有评测资产，`preflight` 只生成计划。
真正的 CLI 模型执行需要显式添加 `--execute`，使用新输出目录并提供 key；预算和模型
选项仍由原 Pi harness 控制。CLI cohort 的可选本地 Vision OCR 使用 `grade:cohort:macos`，
普通 `grade:cohort` 可以跨平台运行。工作台在 macOS 上仍自动使用本地 OCR。

## 测试数据与后续替代

| 资料 | 状态 |
| --- | --- |
| M2 | 原始三 PDF、原官方标签；34 项/12 题严格事后对比 |
| 化学 | 三 PDF，沿用原测试页面选择；缺逐项官方标签 |
| Medly 数学 | 173 答题源文件及 12 题来源；按需准备；本快照缺独立绑定的 examiner 标签 |
| 泛化测试 | 24 个 planned 用例与 schema，尚未成为可执行标签集 |

详细命令、标签隔离与来源见 [测试资产说明](evals/README.md)。
迁移来源、依赖边界和生产替代阶段见 [架构与替代路径](docs/ARCHITECTURE.md)。
工作台交互见 [WORKSPACE](WORKSPACE.md)，批改流程见 [COHORT](COHORT.md)。
历史实验配置与结果保存在 [原型实验记录](docs/EXPERIMENT.md)。

当前交付是可独立运行的替代基础。生产登录、学校权限、支付、发布、现有用户与成绩迁移
仍在后续范围。离线检查不表示 M2 实际批改通过，也不证明通用准确率或生产切换就绪。

代码沿用原项目 GPL-3.0，Pi、KaTeX 和图标的 MIT 声明保留。考试及数据集资料各自保留原权利，
不适用代码许可证；这些资料不进入公开代码包。渲染图、模型轨迹、工作台、依赖和密钥都不提交。

开源导出范围与历史数据边界见 [公开发布说明](docs/PUBLIC_RELEASE.md)。
