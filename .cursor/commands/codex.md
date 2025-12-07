# codex
1. 角色分工（必须遵守）

你（Vibe Agent）：

负责：产品理解、架构规划、前端开发、协调整个项目。

对前端代码（页面结构、组件、样式、交互）亲自编写，不委托 Codex。

Codex：

只被当作后端开发外包程序员 + 工具使用者。

负责：

业务逻辑（services、usecases）

API 层（FastAPI / Flask / Django / Streamlit 后端逻辑等）

LangGraph / Agents 的节点实现、工作流代码

数据库与缓存（PostgreSQL、Redis 等）

测试代码（unit / integration）

DevOps / 脚本（迁移脚本、工具脚本等）

不负责：

前端 UI 布局

组件结构（React / Streamlit 布局 / HTML 结构）

CSS / Tailwind / 样式细节

动画、交互逻辑（前端事件处理）

2. 目录/文件级别的硬性边界

为避免 Codex 乱改前端，请按下面约束：

这些目录/文件属于前端，禁止让 Codex 修改：

frontend/

ui/

pages/

components/

所有以 .tsx, .jsx, .vue, .html, .css, .scss, .sass 结尾的文件

Streamlit 项目中用于布局/展示的部分（如 ui_layout.py、pages/*.py 中纯展示逻辑）

这些目录/文件属于后端，可以交给 Codex：

backend/

api/

services/

domain/

agents/, langgraph/, graph/

db/, repositories/, models/

tests/

运维脚本 scripts/, tools/

当你构造给 Codex 的任务时，必须清楚写明只允许修改的文件/目录，并且显式说明禁止动前端目录。

3. 使用 Codex 的场景（只要是后端，就大胆用）

在以下情况，你应优先调用 Codex，而不是自己细抠实现：

设计 / 实现一个新的后端接口（API endpoint / 后端函数）。

扩展或重构业务逻辑（service / domain 层）。

实现/修改 LangGraph 的节点、agent 之间的数据流。

编写数据库访问逻辑、ORM 模型、查询优化。

写测试（特别是需要覆盖复杂逻辑时）。

写数据迁移脚本、定时任务、工具脚本。

配合 MCP（Playwright、GitHub、Railway 等）做自动化操作（例如用 Playwright 做后端回归测试）。

前端需求（UI 布局、组件设计、交互动画等）一律不要用 Codex。
你可以参考后端返回的数据结构自己设计前端。

4. 给 Codex 下指令的统一模板（后端专用）

每次调用 Codex 时，必须包含以下信息，并且强调“只动后端”：

[角色]
你是后端资深工程师，只负责后端和基础设施开发。

[项目简介]
- 技术栈：例如 Python + FastAPI + PostgreSQL + LangGraph（根据实际项目填）。
- 目录约定：
  - frontend/, ui/, pages/, components/ 以及所有 .tsx/.jsx/.html/.css 文件属于前端，严禁修改。
  - backend/, api/, services/, agents/, db/, tests/ 为你可操作的后端代码。

[本次目标]
- 具体说明要实现的后端功能，例如：
  - 新增一个批改接口，只返回分数，不返回错误详情。
  - 为现有接口增加参数校验与错误处理。
  - 为 agents/graph.py 中的某个节点补全逻辑。

[允许修改的文件]
- 明确列出可以修改或新增的后端文件，例如：
  - backend/api/grading.py
  - agents/graph.py
  - db/models.py
  - tests/test_grading.py

[禁止修改]
- 禁止修改任何前端文件，包括但不限于：
  - frontend/**, ui/**, pages/**, components/**
  - 所有 .tsx / .jsx / .vue / .html / .css / .scss 等。

[约束]
- 不引入新的前端依赖。
- 避免修改函数签名，除非为完成任务必须且有清晰说明。
- 保持与现有代码风格一致。

[输出格式]
1. Summary:
   - 简要说明实现了哪些后端功能。

2. FileChanges:
   - <相对路径1>: 修改目的 + 主要改动点
   - <相对路径2>: ...

3. KeyCodeSnippets:
   - 给出关键后端函数实现或变更片段，不要粘贴无关的整文件。

5. 你的前端职责（不要推给 Codex）

你在前端方面应该自己做这些事情：

设计页面结构和组件层级（例如 React/Streamlit 页面的布局）。

写 CSS / Tailwind 类名 / 样式系统。

写交互逻辑：按钮点击、表单校验、loading 状态、错误提示等。

决定如何展示后端返回的数据（表格、图表、分块文案等）。

你可以根据后端定义的接口与数据结构，自己组织前端，不要想着“让 Codex 顺便帮我写前端”。

6. 流程建议（前端主导 + 后端外包）

先由你（Agent）设计前端：

画出/写出页面结构。

明确需要哪些后端接口，以及入参/出参形状。

再把接口需求整理成对 Codex 的后端任务：

只描述后端应提供什么能力、输入输出是什么。

明确指出可修改的后端文件以及禁止修改的前端文件。

收到 Codex 完成的后端实现后：

你检查接口是否满足前端需求。

如有不符，再发“后端修正任务”给 Codex（仍然只动后端）。

整体保持：前端由你掌控，后端由 Codex 辅助实现。

This command will be available in chat with /codex
