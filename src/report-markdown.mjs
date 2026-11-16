import { resolve, dirname } from 'node:path';

const methodNames = {
  'gradeos.student_summary': '单份答卷摘要',
  'gradeos.class_report': '小项得分与内部得分段',
  'gradeos.global_logic_audit': '全局逻辑审计',
  'harness.repeatability': '同卷评分稳定性',
};
const number = (value, digits = 2) => value == null ? '未提供' : Number(value).toFixed(digits);
const percent = value => value == null ? '未提供' : `${number(value * 100)}%`;
const money = value => value == null ? '未提供' : `$${number(value, 8)}`;
const cell = value => String(value ?? '未提供').replaceAll('|', '\\|').replace(/\r?\n/g, ' ');
const link = (label, path) => `[${cell(label).replace(/[\[\]]/g, '\\$&')}](${encodeURI(path).replace(/[()#]/g, c => `%${c.charCodeAt(0).toString(16)}`)})`;
const distribution = values => Object.entries(values).map(([score, count]) => `${Number.isFinite(Number(score)) ? `${score} 分` : '待定'} × ${count}`).join('；');
const knownCount = values => Object.entries(values).reduce((sum, [score, count]) => sum + (Number.isFinite(Number(score)) ? count : 0), 0);
const table = (head, rows, alignment) => [
  `| ${head.join(' | ')} |`, `| ${(alignment ?? head.map(() => '---')).join(' | ')} |`,
  ...rows.map(row => `| ${row.map(cell).join(' | ')} |`), '',
];

// Presentation only: model narrative, frozen awards and deterministic analytics remain authoritative.
export function renderReportMarkdown(report, analysis, options = {}) {
  const { output, index, summary, costs, sourceSummary, sourceCohort, presentation = {} } = options;
  const stat = analysis.harness_repeatability;
  const native = analysis.gradeos_class_report;
  const coverage = analysis.coverage;
  const repeated = analysis.cohort_context.unique_answer_sources === 1 && coverage.requested_records > 1;
  const source = (label, name) => output ? link(label, resolve(output, name)) : label;
  const gradePaths = new Map(index?.records.map(row => [row.student_id, row.grading_path]) ?? []);
  const evidence = ref => {
    const id = ref.split('/')[0];
    const path = gradePaths.get(id) ?? (output ? resolve(output, 'results', `${id}.json`) : null);
    return path ? link(ref, path) : cell(ref);
  };
  const linkMentions = text => text.replace(/\b([A-Za-z0-9_-]+\/[^\s记录；，。]+)/g, ref => evidence(ref));
  const varied = stat.items.filter(row => row.varies);
  const totalScores = Object.keys(stat.score_distribution).map(Number).filter(Number.isFinite);
  const range = totalScores.length ? `${Math.min(...totalScores)}–${Math.max(...totalScores)} 分` : '未提供';
  const lines = [`# ${presentation.title ?? report.title}`, '',
    `*${presentation.byline ?? '批改汇总 · 待教师审阅'}*`, '',
    '> **摘要**', '> ', ...report.executive_summary.split('\n').map(line => `> ${line}`), '',
    ...(presentation.notices ?? []).flatMap(note => [note, '']),
    '[结果概览](#结果概览) · [复核重点](#复核重点) · [分析与学习观察](#分析与学习观察) · [学生个人反馈](#学生个人反馈) · [完整小项明细](#完整小项明细) · [费用与耗时](#费用与耗时) · [方法与来源](#方法与来源)', '',
    '## 结果概览', '',
    ...table(['数值完整记录', '平均分', '总分范围'], [[
      `**${coverage.scored_records} / ${coverage.requested_records}**`, `**${number(native.average_score, 1)}**`, `**${range}**`,
    ]]),
    `纳入 ${coverage.scored_records} / ${coverage.requested_records} 条数值记录；答卷来源数为 ${analysis.cohort_context.unique_answer_sources ?? '未知'}。主 Agent 已读取 ${report.records_read.length} 条结果。${source('查看冻结结果索引', 'results/index.json')}。`, '',
  ];
  if (repeated) lines.push('本报告衡量**同一答卷重复批改的稳定性**。下文“任务”代表一次评分运行；这些记录不能用于推断真实班级或学生群体。', '');
  if (coverage.requested_records > 1) {
    lines.push('### 总分分布', '');
    const showBars = coverage.scored_records > 0 && coverage.scored_records <= 50;
    lines.push(...table(['总分', '次数', '占有效记录比例', ...(showBars ? ['分布'] : [])],
      Object.entries(stat.score_distribution).map(([score, count]) => [
        `${score} 分`, count, percent(coverage.scored_records ? count / coverage.scored_records : null),
        ...(showBars ? ['■'.repeat(count)] : []),
      ]), ['---:', '---:', '---:', ...(showBars ? ['---'] : [])]));
    if (showBars) lines.push('*每个 ■ 表示一次评分；分母为本批有效数值记录。*', '');
    lines.push(`内部 60% 及格线达标比例：**${percent(native.pass_rate)}**。内部得分段：${Object.entries(native.score_distribution).map(([band, count]) => `${band}：${count}`).join(' · ')}。这些分档不对应官方考试等级。`, '');
  }
  if (repeated) {
    lines.push('### 重复评分的一致性', '',
      `得分不变的小项：**${stat.constant_items} / ${stat.item_count}**；总分标准差：**${number(stat.population_sd, 3)} 分**。`, '',
      ...table(['小项', '满分', '各得分出现次数', '平均得分率'], varied.map(row => [
        `**${row.item_id}**`, row.max_score, distribution(row.score_distribution), percent(row.mean_score_rate),
      ]), ['---', '---:', '---', '---:']));
    if (!varied.length) lines.push('本批有数值结果的小项未观察到得分变化；缺失记录见完整明细。', '');
  }
  lines.push(`数值依据：${source('GradeOS 分析与重复评分统计', 'gradeos-analysis.json')}。得分一致性与评分准确性是不同指标；本报告未使用官方参考标签。`, '',
    '---', '', '## 复核重点', '',
    '以下为主 Agent 提出的复核顺序，建议需回到原答卷与 MS 核查。所有冻结分数保持原值。', '',
    ...table(['顺序 / 小项', '发现', '建议动作', '结果证据'], report.review_priorities.map((row, i) => [
      `**${i + 1} · ${row.item_ids.join('、')}**`, row.reason, row.action,
      (row.evidence_refs??row.student_ids.map(id=>`${id}/${row.item_ids[0]}`)).map(evidence).join(' · '),
    ])));
  if (!report.review_priorities.length) lines.push('本次报告没有列出额外复核项目。', '');
  lines.push('## 分析与学习观察', '');
  for (const section of report.analysis_sections) {
    lines.push(`### ${methodNames[section.method_id] ?? section.method_id}`, '', section.interpretation, '',
      `证据：${section.evidence_refs.length ? section.evidence_refs.map(evidence).join(' · ') : source('本批确定性统计', 'gradeos-analysis.json')}。`, '');
    if (section.method_id === 'harness.repeatability' && repeated)
      lines.push('*此处“独立重复性统计”意为另行计算的重复评分统计，不表示独立学生样本。*', '');
  }
  lines.push(analysis.cohort_context.unique_answer_sources === 1 ? '### 针对这份答卷的学习观察' : '### 本批答卷的学习观察', '', ...report.learning_observations.map(x => `- ${linkMentions(x)}`), '',
    report.source_bound_selection?'上述观察来自已保存的得分与复核状态；模型选择学习重点，练习动作由来源约束生成，不新增原因推断或学生作答证据。':'上述观察来自已保存的批改理由，不视为学生原笔迹的逐字引文，也不代替人工复核。', '');
  const execution = ['---', '', '## 费用与耗时', ''];
  if (summary) {
    execution.push(...table(['阶段', '调用数', '耗时', '已知费用（USD）'], [[
      summary.new_grading_calls === 0 ? '本次主 Agent 汇总' : '本次批次执行',
      summary.admitted_requests, `${number(summary.elapsed_seconds, 3)} 秒`, `**${money(summary.provider_reported_cost_usd)}**`,
    ]]));
    if (summary.new_grading_calls === 0) execution.push('本次汇总读取之前已落盘的结果，未重新批改答卷。它与原批改阶段分开执行。', '');
    execution.push(`费用回执：${source('本次执行摘要', 'summary.json')}。未结算请求数：${summary.unknown_cost_requests ?? '未知'}。`, '');
  } else execution.push('完整运行的费用与耗时以终态执行摘要为准；报告提交时尚未附入终态回执。', '');
  if (costs) {
    const amounts = [
      ['此前 30 份批改与调度', costs.prior_30_grading_and_dispatch_usd],
      ['本次成功汇总', costs.successful_report_usd],
      ['上述两阶段相加', costs.prior_grading_plus_successful_reporting_usd],
      ['上述两阶段平均每份', costs.per_student_prior_grading_plus_successful_reporting_usd],
      ['另计：此前 MS 整理', costs.plus_historical_ms_usd != null && costs.prior_grading_plus_successful_reporting_usd != null ? Number(costs.plus_historical_ms_usd) - Number(costs.prior_grading_plus_successful_reporting_usd) : null],
      ['上述两阶段 + 此前 MS 整理', costs.plus_historical_ms_usd],
    ].filter(([, value]) => value != null);
    execution.push('### 历史阶段费用拆分', '', ...table(['口径', '费用（USD）'], amounts.map(([label, value]) => [label, money(value)]), ['---', '---:']),
      '**以上为不同阶段的历史费用相加，并非新跑一轮的端到端费用；不含失败调试。** 同卷重复输入存在缓存复用，不能把这个均价直接外推到不同学生的答卷。', '');
    if (sourceSummary) execution.push(`原批改批次用时 **${number(sourceSummary.elapsed_seconds, 3)} 秒**，模型调用 **${sourceSummary.admitted_requests} 次**。${sourceCohort ? link('原批次执行回执', resolve(sourceCohort, 'summary.json')) : ''}。两个阶段分别计时，不据此宣称一次连续整轮的端到端耗时。`, '');
    execution.push('### 失败尝试同样计入账本', '', ...table(['口径', '费用（USD）'], [
      ['首次失败尝试：流式回执', costs.failed_attempt_stream_receipts_usd],
      ['首次失败尝试：中止请求补充核账', costs.aborted_request_generation_receipt_usd],
      ['首次失败尝试合计', costs.failed_attempt_reconciled_usd],
      ['失败 + 成功：全部报告尝试', costs.all_reporting_attempts_usd],
      ['此前批改与调度 + 全部报告尝试（不含 MS）', costs.all_observed_grading_and_reporting_attempts_usd],
    ].filter(([, value]) => value != null).map(([label, value]) => [label, money(value)]), ['---', '---:']),
      ...(presentation.cost_notes ?? []).flatMap(note => [note, '']),
      `对账后未知费用请求数：**${costs.unknown_cost_after_generation_reconciliation ?? '未知'}**。精确金额与计费范围见${source('费用账本', 'cost-accounting.json')}。`, '');
  }
  if (index?.records.length) {
    lines.push('## 学生个人反馈', '',
      '每份个人报告包含总体评价、逐题解释和练习建议。反馈是对已保存判分的补充，不能作为独立评分或新图像证据。', '',
      ...table([repeated ? '评分任务' : '记录编号', '反馈状态', '报告'], index.records.map(row => [row.student_id,
        row.feedback_status === 'submitted' ? '已生成' : row.feedback_status === 'failed' ? '生成未完成' : '未生成',
        row.feedback_status === 'submitted' && row.feedback_path ? link('阅读个人报告', resolve(dirname(row.feedback_path), 'REPORT.zh-CN.md')) : '—',
      ])));
  } else lines.push('## 学生个人反馈', '', '本次未附个人报告索引。', '');
  lines.push('---', '', '## 完整小项明细', '',
    '平均得分率 = 本小项有效得分的均值 ÷ 本小项满分；它是题项得分指标，不等于知识掌握率。分布中的“×”表示该得分出现的次数。', '',
    ...table(['小项', '满分', '平均得分率', '得分 × 次数', repeated ? '稳定性 / 缺失' : '数值覆盖'], stat.items.map(row => [
      repeated && row.varies ? `**${row.item_id}**` : row.item_id, row.max_score, percent(row.mean_score_rate), distribution(row.score_distribution),
      `${repeated ? (row.varies ? '**有波动**' : knownCount(row.score_distribution) ? '未见波动' : '无数值') : `${knownCount(row.score_distribution)} 条有效`}${row.unknown_count ? `；待定 / 缺失 ${row.unknown_count}` : ''}`,
    ]), ['---', '---:', '---:', '---', '---']),
    '## 分析边界', '', ...report.limitations.map(x => `- ${x}`), '');
  if (coverage.excluded_from_numeric_audit?.length)
    lines.push(`排除于数值审计的记录：${coverage.excluded_from_numeric_audit.map(row => cell(typeof row === 'string' ? row : JSON.stringify(row))).join('；')}。这些记录不按零分处理。`, '');
  lines.push(...execution);
  lines.push('## 方法与来源', '',
    report.source_bound_selection?'数值统计由 GradeOS 现有函数与单独的重复评分统计计算；Pi 主 Agent 选择证据与练习重点，正文由固定规则根据真实记录生成。结构化模型选择与所有源文件分别保留。':'数值统计由 GradeOS 现有函数与单独的重复评分统计计算；解释、学习观察及复核建议来自 Pi 主 Agent。原始模型报告与数值文件均单独保存。', '',
    ...table(['实际调用的方法', '用途 / 边界', '实现'], (analysis.methods ?? []).map(method => [
      methodNames[method.method_id] ?? method.method_id,
      method.method_id === 'gradeos.student_summary' ? '单份结果摘要；按小项统计' : method.method_id === 'gradeos.class_report' ? '平均分、分档与低分项；知识点字段仅作小项代理' : '跨记录逻辑与离群提示；未执行内部 M/A 证据审计',
      link(method.function, method.source_path),
    ])),
    '内部规则：A ≥ 85%、B ≥ 70%、C ≥ 60%、D ≥ 50%、E < 50%；低分项 < 60%，高分项 ≥ 85%。分档为系统内部规则，高低分项阈值仅用于题项得分率。', '',
    '### 可追溯附件', '',
    ...table(['附件', '内容'], [
      [source('冻结结果索引', 'results/index.json'), '每个 Agent 的落盘记录、原批改文件路径及校验值'],
      [source('主 Agent 报告记录', 'report.json'), report.source_bound_selection?'模型结构化选择、按记录生成的叙述、已读名单及来源绑定':'未经排版改写的模型叙述、已读名单及证据引用'],
      [source('GradeOS 分析输出', 'gradeos-analysis.json'), '完整统计、覆盖范围、函数来源与源文件 SHA-256'],
      ...(summary ? [[source('执行摘要', 'summary.json'), '模型调用、实际耗时与费用回执']] : []),
      ...(costs ? [[source('费用账本', 'cost-accounting.json'), '成功、失败及中止请求的精确费用核账']] : []),
      ...(presentation.attachments ?? []).map(row => [link(row.label, row.path), row.description]),
    ]),
    '*本文件仅呈现已保存的结果；Markdown 重排不会改变评分、补充模型证据或触发新的批改调用。*', '');
  return lines.join('\n');
}
