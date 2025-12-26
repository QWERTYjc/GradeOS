'use client';

import React, { useState } from 'react';
import DashboardLayout from '@/components/layout/DashboardLayout';

interface AnalysisResult {
  error_type: string;
  error_severity: string;
  root_cause: string;
  knowledge_gaps: Array<{ knowledge_point: string; mastery_level: number; confidence: number }>;
  detailed_analysis: {
    step_by_step_correction: string[];
    common_mistakes: string;
    correct_solution: string;
  };
}

interface Recommendation {
  immediate_actions: Array<{ type: string; content: string; resources: Array<{ id: string; title: string; type: string }> }>;
  practice_exercises: Array<{ exercise_id: string; question: string; difficulty: number }>;
}

// Mock 班级错题库
const MOCK_CLASS_PROBLEMS = [
  { id: 'p-001', question: '已知二次函数 y=x²-4x+3，求其顶点坐标', errorRate: '32%', tags: ['二次函数', '顶点式'] },
  { id: 'p-002', question: '解不等式 2x-1 > 3x+2', errorRate: '28%', tags: ['不等式', '变号'] },
  { id: 'p-003', question: '圆 x²+y²=4 与直线 y=x+k 相切，求 k 的值', errorRate: '45%', tags: ['圆', '切线'] },
];

export default function ErrorAnalysisPage() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [processStatus, setProcessStatus] = useState('');
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [reco, setReco] = useState<Recommendation | null>(null);
  const [showBank, setShowBank] = useState(false);

  const handleAnalyze = async () => {
    if (!question || !answer) return;
    setIsAnalyzing(true);
    setProcessStatus('正在唤醒认知核心...');
    setResult(null);
    setReco(null);

    // 模拟 AI 分析过程
    await new Promise(r => setTimeout(r, 1000));
    setProcessStatus('正在调取云端知识图谱...');
    await new Promise(r => setTimeout(r, 1000));
    setProcessStatus('正在生成深度诊断...');
    await new Promise(r => setTimeout(r, 1000));

    // 模拟分析结果
    setResult({
      error_type: '概念错误',
      error_severity: 'medium',
      root_cause: '对二次函数顶点式的理解存在偏差，特别是在符号判断方面。学生混淆了 h 的正负号与图像平移方向的关系。',
      knowledge_gaps: [
        { knowledge_point: '二次函数顶点式', mastery_level: 0.65, confidence: 0.85 },
        { knowledge_point: '配方法', mastery_level: 0.72, confidence: 0.90 },
        { knowledge_point: '函数平移', mastery_level: 0.58, confidence: 0.80 }
      ],
      detailed_analysis: {
        step_by_step_correction: [
          '首先确认二次函数的一般形式 y=ax²+bx+c',
          '使用配方法将其转换为顶点式 y=a(x-h)²+k',
          '注意 h 的符号：当 h>0 时，图像向右平移',
          '确定顶点坐标为 (h, k)，注意 k 的几何意义是最值'
        ],
        common_mistakes: '忽略 a 的正负影响开口方向，h 的正负号与平移方向混淆',
        correct_solution: '对于 y=x²-4x+3，配方得 y=(x-2)²-1，顶点为 (2, -1)'
      }
    });

    setProcessStatus('正在规划个性化强化路径...');
    await new Promise(r => setTimeout(r, 800));

    setReco({
      immediate_actions: [
        {
          type: 'review',
          content: '复习配方法基础知识',
          resources: [
            { id: 'r1', title: '配方法详解视频', type: 'video' },
            { id: 'r2', title: '配方法练习题集', type: 'exercise' }
          ]
        },
        {
          type: 'practice',
          content: '顶点式转换专项训练',
          resources: [
            { id: 'r3', title: '顶点式10道精选', type: 'exercise' },
            { id: 'r4', title: '图像平移动画演示', type: 'video' }
          ]
        }
      ],
      practice_exercises: [
        { exercise_id: 'e1', question: '将 y=x²+6x+5 化为顶点式', difficulty: 2 },
        { exercise_id: 'e2', question: '求 y=-2x²+8x-3 的顶点坐标', difficulty: 3 }
      ]
    });

    setIsAnalyzing(false);
    setProcessStatus('');
  };

  const importProblem = (q: string) => {
    setQuestion(q);
    setShowBank(false);
  };

  const getSeverityLabel = (severity: string) => {
    const map: Record<string, string> = { high: '极高影响', medium: '中等程度', low: '轻微偏差' };
    return map[severity] || severity;
  };

  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-8">
        {/* 页面标题 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">🔍 错题深度分析</h1>
            <p className="text-slate-500 text-sm mt-1">AI 驱动的错因诊断与个性化补强方案</p>
          </div>
          <button
            onClick={() => setShowBank(true)}
            className="px-4 py-2 bg-slate-100 hover:bg-slate-200 rounded-lg text-sm font-medium text-slate-700 transition-colors"
          >
            📚 从班级题库导入
          </button>
        </div>

        {/* 班级题库弹窗 */}
        {showBank && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-2xl w-full max-w-2xl mx-4 overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center">
                <h3 className="font-bold text-slate-800">📚 班级高频错题库</h3>
                <button onClick={() => setShowBank(false)} className="text-slate-400 hover:text-slate-600">✕</button>
              </div>
              <div className="p-6 space-y-3 max-h-96 overflow-y-auto">
                {MOCK_CLASS_PROBLEMS.map(p => (
                  <div
                    key={p.id}
                    onClick={() => importProblem(p.question)}
                    className="p-4 bg-slate-50 hover:bg-blue-50 rounded-xl cursor-pointer transition-colors border border-transparent hover:border-blue-200"
                  >
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex gap-2">
                        {p.tags.map(tag => (
                          <span key={tag} className="px-2 py-0.5 bg-blue-100 text-blue-600 text-xs font-medium rounded">{tag}</span>
                        ))}
                      </div>
                      <span className="text-xs font-medium text-red-500 bg-red-50 px-2 py-0.5 rounded">错误率: {p.errorRate}</span>
                    </div>
                    <p className="text-sm text-slate-700">{p.question}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* 输入区域 */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <div>
              <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">问题内容</label>
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="粘贴题目原文或从题库导入..."
                className="w-full h-40 p-4 rounded-xl border border-slate-200 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all resize-none text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">你的解答</label>
              <textarea
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="输入你的解答逻辑或错误答案..."
                className="w-full h-40 p-4 rounded-xl border border-slate-200 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all resize-none text-sm"
              />
            </div>
          </div>

          <button
            onClick={handleAnalyze}
            disabled={isAnalyzing || !question || !answer}
            className={`w-full py-4 rounded-xl font-bold transition-all ${
              isAnalyzing
                ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                : 'bg-blue-600 text-white hover:bg-blue-700 shadow-lg shadow-blue-200'
            }`}
          >
            {isAnalyzing ? (
              <div className="flex flex-col items-center gap-1">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />
                  <span>分析进行中...</span>
                </div>
                <span className="text-xs opacity-60">{processStatus}</span>
              </div>
            ) : (
              '🚀 立即解析'
            )}
          </button>
        </div>

        {/* 分析结果 */}
        {result && (
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* 错因分析 */}
            <div className="bg-white rounded-2xl border border-slate-200 p-6">
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">错因根源分析</h3>
              <p className="text-lg font-medium text-slate-800 leading-relaxed mb-6">{result.root_cause}</p>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-xs text-slate-400">错误类型</span>
                  <div className="mt-1">
                    <span className="px-3 py-1 bg-red-50 text-red-600 rounded-lg text-sm font-medium">{result.error_type}</span>
                  </div>
                </div>
                <div>
                  <span className="text-xs text-slate-400">影响程度</span>
                  <div className="mt-1">
                    <span className="px-3 py-1 bg-amber-50 text-amber-600 rounded-lg text-sm font-medium">{getSeverityLabel(result.error_severity)}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* 知识漏洞 */}
            <div className="bg-slate-50 rounded-2xl p-6">
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">关联知识漏洞</h3>
              <div className="space-y-4">
                {result.knowledge_gaps.map((gap, idx) => (
                  <div key={idx}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="font-medium text-slate-700">{gap.knowledge_point}</span>
                      <span className="text-blue-600 font-bold">{(gap.mastery_level * 100).toFixed(0)}%</span>
                    </div>
                    <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                      <div className="h-full bg-blue-600 rounded-full transition-all" style={{ width: `${gap.mastery_level * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* 思维重塑路径 */}
            <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
              <div className="px-6 py-4 bg-slate-50 border-b border-slate-100">
                <h3 className="font-bold text-slate-800">🧠 思维重塑路径</h3>
              </div>
              <div className="p-6">
                <div className="space-y-6">
                  {result.detailed_analysis.step_by_step_correction.map((step, idx) => (
                    <div key={idx} className="flex gap-4">
                      <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center font-bold text-sm flex-shrink-0">
                        {idx + 1}
                      </div>
                      <p className="text-slate-700 pt-1">{step}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* 强化方案 */}
            {reco && (
              <div className="space-y-4">
                <h3 className="text-lg font-bold text-slate-800">✨ 智能强化方案</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {reco.immediate_actions.map((action, idx) => (
                    <div key={idx} className="bg-white rounded-2xl border border-slate-200 p-6 hover:shadow-lg transition-shadow">
                      <h4 className="font-bold text-slate-800 mb-4">{action.content}</h4>
                      <div className="space-y-2">
                        {action.resources.map(res => (
                          <div key={res.id} className="flex items-center gap-3 p-3 bg-slate-50 rounded-xl hover:bg-blue-50 cursor-pointer transition-colors">
                            <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center">
                              {res.type === 'video' ? '▶' : '✍'}
                            </div>
                            <span className="text-sm font-medium text-slate-700">{res.title}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
