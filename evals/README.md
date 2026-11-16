# 批改测试资产

| 数据集 | 已接入资产 | 可验证范围 |
| --- | --- | --- |
| `m2` | 2023 DSE M2 评分标准 21 页、学生答卷 28 页、评分详情 3 页、原官方标签 | 100 满分、官方 76 分、12 题、全部 34 个评分详情项 |
| `chemistry` | 2023 DSE 化学评分标准、公开学生样例、Paper 1 题目，共 3 份原 PDF | 原页导入、裁切和批改输入；无官方逐项标签，不宣称准确率通过 |
| `medly/` | 173 份数学答题扫描、12 题原题与评分标准、相关图示 | 原来源完整性及按需准备；本快照缺独立绑定的 examiner 标签 |
| `planned/` | GradeOS 的 24 个跨学科泛化用例清单及 schema | 全部仍为 planned，不是已执行测试 |

M2 三份 PDF、`labels.json` 均按原字节复制。原 manifest 保存在
`docs/provenance/m2-original-manifest.json`，官方标签没有改写。
官方评分详情没有披露内部 M/A 分配；逐项评测不推造这些分配。
Q9/Q10 的来源冲突仍保留为诊断资料，官方 76 分和逐项分数仍是严格比较基准。

化学原始 PDF 保留完整文件。输入只选择原测试所用的评分标准第 3–8、2 页和样例
第 3–21 页；等级、后续样例与评语不进入答卷输入。单独题目文件全 33 页保留供工作台参考。
不把公开样例的等级转换为逐项分数，也不把模型历史结果当成参考标签。
来源与哈希记录在 `docs/provenance/chemistry-sources.json`。

## 无模型调用的资产验证与准备

```sh
npm run fixtures:check
npm run fixtures:prepare -- --fixture m2 --output runs/m2-input
npm run fixtures:prepare -- --fixture chemistry --output runs/chemistry-input
```

`check` 校验所有声明输入的哈希、页数和页面选择，并从 M2 官方 PDF 重新解析 34 项。
输出标为 `check-only`，不能称为 `M2 fixture regression pass`。

`prepare` 只读取 `input.json` 的允许角色（scheme、student、question）。不读取 posthoc
文件；输出中只包含选中的原始材料、原页图像和运行所需 manifest。
生成的 `manifest.json` 可直接交给 `src/run.mjs`，`cohort.json` 可交给 `src/run-cohort.mjs`。
同一输出目录不可重复使用。

## 导入工作台

```sh
npm run fixtures:workspace -- --fixture m2 --data .workspace-m2
npm start -- --data .workspace-m2
```

导入命令只接受新目录，避免覆盖或并发修改已有工作台。它走真实 PDF 上传处理函数，
不创建付费批改任务。浏览器中可查看 49 页 M2 原材料；评分详情不会被导入。
化学可使用 `--fixture chemistry --data .workspace-chemistry`。

## 运行与事后评测

先生成计划，不调用模型：

```sh
node src/run.mjs --input runs/m2-input --output runs/m2-preflight
node src/run-cohort.mjs --manifest runs/m2-input/cohort.json --output runs/m2-cohort-preflight
```

实际批改沿用 README 中的工作台或显式 `--execute` CLI；需自行提供 OpenRouter key，
使用新输出目录，并记录模型、推理、缓存、预算与全部请求。准备输入不会启动批改。

结果冻结且所有任务结束后：

```sh
npm run fixtures:evaluate -- --fixture m2 --run runs/m2-completed
```

支持单份 `grading.json` 与 cohort 的逐学生冻结文件。先检查终态、任务名单与结果哈希，
然后才打开标签。非终态、被修改的结果或缺失任务拒绝评测；失败结果不算零分。
输出 `fixture-evaluation.json`，记录总分、每题及 34 项差异，失败返回非零退出码。
相同总分但题项互相抵消的错误仍判失败；每次结果保留，不选择最好的一次。

## 权利与体积

考试资料的原版权归各原权利人，本仓库代码许可证不授予考试资料许可。
本仓库按私有测试资产管理。原 PDF 只存一份；渲染图片、工作台、历史请求、运行结果、
旧后端快照和依赖目录不提交。
Medly 原始题目、标准与答卷已迁入；多轮生成物和 50 份扫描容量测试 PDF 没有整包搬入。

```sh
npm run medly:prepare -- --answer maths_0001 --output runs/medly-0001
```

它生成 `runs/medly-0001/prepared`，可交给相同的 Pi CLI。原始扫描像素直接嵌入 PDF，
题目和标准文字原样排版（保留字面的 LaTeX），图示同时附入评分标准输入。
当前 173 份是旧项目已使用的开发选择，不是完整 Medly 数据集或独立留出集。
没有把旧模型预测当作参考分数；输入清单与每个源文件都由 SHA-256 校验。
