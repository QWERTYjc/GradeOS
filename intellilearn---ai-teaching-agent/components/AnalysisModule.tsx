
import React, { useState } from 'react';
import { analyzeProblem, getRecommendations, getClassWrongProblems } from '../services/geminiService';
import { AnalysisResult, Recommendation } from '../types';

const AnalysisModule: React.FC = () => {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [processStatus, setProcessStatus] = useState('');
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [reco, setReco] = useState<Recommendation | null>(null);
  
  const [showBank, setShowBank] = useState(false);
  const [classProblems, setClassProblems] = useState<Array<{ id: string; question: string; errorRate: string; tags: string[] }>>([]);
  const [isLoadingBank, setIsLoadingBank] = useState(false);

  const handleAnalyze = async () => {
    if (!question || !answer) return;
    setIsAnalyzing(true);
    setProcessStatus('正在唤醒认知核心...');
    setResult(null);
    setReco(null);
    try {
      const analysisResult = await analyzeProblem('数学', question, answer, (status) => {
        setProcessStatus(status);
      });
      setResult(analysisResult);
      setProcessStatus('正在规划个性化强化路径...');
      const recommendations = await getRecommendations(analysisResult);
      setReco(recommendations);
    } catch (error) {
      console.error(error);
      alert('诊断分析受阻，请检查网络或配置。');
    } finally {
      setIsAnalyzing(false);
      setProcessStatus('');
    }
  };

  const openBank = async () => {
    setShowBank(true);
    if (classProblems.length === 0) {
      setIsLoadingBank(true);
      try {
        const problems = await getClassWrongProblems();
        setClassProblems(problems);
      } catch (error) {
        console.error("Failed to load class bank", error);
      } finally {
        setIsLoadingBank(false);
      }
    }
  };

  const importProblem = (q: string) => {
    setQuestion(q);
    setShowBank(false);
  };

  const translateSeverity = (severity: string) => {
    const map: Record<string, string> = { high: '极高影响', medium: '中等程度', low: '轻微偏差' };
    return map[severity?.toLowerCase() || ''] || severity || '普通影响';
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 pb-20">
      {/* Class Bank Modal */}
      {showBank && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/20 backdrop-blur-[2px]" onClick={() => setShowBank(false)}></div>
          <div className="relative bg-white w-full max-w-2xl rounded-[32px] shadow-2xl border border-slate-100 overflow-hidden animate-in fade-in zoom-in duration-300">
            <div className="px-8 py-6 border-b border-slate-50 flex items-center justify-between bg-slate-50/50">
              <h3 className="text-xl font-bold flex items-center gap-2 text-slate-900">
                <svg className="w-6 h-6 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
                班级高频错题库
              </h3>
              <button onClick={() => setShowBank(false)} className="p-2 hover:bg-slate-200 rounded-full transition-colors text-slate-400">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <div className="p-8 max-h-[60vh] overflow-y-auto space-y-4">
              {isLoadingBank ? (
                <div className="flex flex-col items-center justify-center py-12 gap-4">
                  <div className="w-10 h-10 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                  <p className="text-slate-500 font-medium text-sm">同步班级实时档案...</p>
                </div>
              ) : (
                (classProblems || []).map((p) => (
                  <div key={p.id} className="group p-5 bg-white hover:bg-slate-50 border border-slate-100 rounded-2xl transition-all cursor-pointer" onClick={() => importProblem(p.question)}>
                    <div className="flex justify-between items-start mb-3">
                      <div className="flex gap-2">
                        {(p.tags || []).map(tag => (
                          <span key={tag} className="px-2 py-0.5 bg-blue-50 text-blue-600 text-[10px] font-bold rounded">{tag}</span>
                        ))}
                      </div>
                      <span className="text-[10px] font-bold text-red-500 bg-red-50 px-2 py-0.5 rounded">错误率: {p.errorRate}</span>
                    </div>
                    <p className="text-sm font-medium text-slate-800 line-clamp-2 leading-relaxed">{p.question}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Input Section */}
      <div className="bg-white rounded-3xl border border-slate-100 shadow-sm p-8 relative overflow-hidden">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-600 rounded-xl flex items-center justify-center text-white shadow-lg shadow-blue-200">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" /></svg>
            </div>
            <h2 className="text-2xl font-bold text-slate-900">错题深度扫描</h2>
          </div>
          
          <button 
            onClick={openBank}
            className="flex items-center gap-2 px-4 py-2 bg-slate-50 border border-slate-100 hover:border-blue-600 hover:text-blue-600 transition-all text-xs font-bold rounded-full text-slate-600"
          >
            从班级题库导入
          </button>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <div className="space-y-3">
            <label className="text-xs font-bold text-slate-400 uppercase tracking-widest px-1">问题内容</label>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="粘贴题目原文或从题库导入..."
              className="w-full h-48 p-5 rounded-2xl border border-slate-100 bg-slate-50/50 focus:ring-4 focus:ring-blue-600/5 focus:bg-white outline-none transition-all resize-none text-sm leading-relaxed font-medium text-slate-900"
            />
          </div>
          <div className="space-y-3">
            <label className="text-xs font-bold text-slate-400 uppercase tracking-widest px-1">解题尝试</label>
            <textarea
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="输入你的解答逻辑或错误答案..."
              className="w-full h-48 p-5 rounded-2xl border border-slate-100 bg-slate-50/50 focus:ring-4 focus:ring-blue-600/5 focus:bg-white outline-none transition-all resize-none text-sm leading-relaxed font-medium text-slate-900"
            />
          </div>
        </div>

        <button
          onClick={handleAnalyze}
          disabled={isAnalyzing}
          className={`w-full py-5 rounded-2xl font-bold text-lg transition-all flex flex-col items-center justify-center gap-1 ${
            isAnalyzing 
            ? 'bg-slate-100 text-slate-400 cursor-not-allowed' 
            : 'bg-blue-600 text-white hover:bg-blue-700 shadow-xl shadow-blue-100 active:scale-[0.98]'
          }`}
        >
          {isAnalyzing ? (
            <>
              <div className="flex items-center gap-3">
                <div className="w-5 h-5 border-2 border-slate-400 border-t-transparent rounded-full animate-spin"></div>
                <span>分析进行中...</span>
              </div>
              <span className="text-[10px] animate-pulse uppercase tracking-widest opacity-60 font-bold">{processStatus}</span>
            </>
          ) : (
            <div className="flex items-center gap-3">
              <span>立即解析</span>
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" /></svg>
            </div>
          )}
        </button>
      </div>

      {result && (
        <div className="animate-in fade-in slide-in-from-bottom-8 duration-700 space-y-10">
          {/* Logic Call Log */}
          <div className="bg-white border border-slate-100 rounded-2xl p-4 flex items-center justify-between shadow-sm">
            <div className="flex items-center gap-3">
               <div className="flex -space-x-2">
                  <div className="w-6 h-6 rounded-full bg-blue-600 flex items-center justify-center text-[10px] text-white font-bold border-2 border-white">AI</div>
                  <div className="w-6 h-6 rounded-full bg-slate-900 flex items-center justify-center text-[10px] text-white font-bold border-2 border-white">DB</div>
               </div>
               <span className="text-[10px] font-bold uppercase text-slate-400 tracking-wide">认知引擎同步：学生档案 + 云端知识图谱</span>
            </div>
            <span className="px-2 py-1 bg-emerald-50 text-emerald-600 text-[9px] font-bold rounded border border-emerald-100">DATA VERIFIED</span>
          </div>

          {/* Diagnostic Results Dashboard */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 bg-white rounded-3xl border border-slate-100 p-8 shadow-sm">
              <h3 className="text-slate-400 text-[10px] font-bold uppercase tracking-[0.2em] mb-6">错因根源分析</h3>
              <p className="text-xl font-bold text-slate-900 leading-relaxed">
                {result.root_cause}
              </p>
              <div className="mt-8 pt-8 border-t border-slate-50 grid grid-cols-2 gap-8">
                <div>
                  <p className="text-[10px] font-bold text-slate-400 uppercase mb-2">主要错误特征</p>
                  <span className="px-3 py-1 bg-red-50 text-red-600 rounded-lg text-xs font-bold border border-red-100">{result.error_type}</span>
                </div>
                <div>
                  <p className="text-[10px] font-bold text-slate-400 uppercase mb-2">整体评估权重</p>
                  <span className="px-3 py-1 bg-amber-50 text-amber-600 rounded-lg text-xs font-bold border border-amber-100">{translateSeverity(result.error_severity)}</span>
                </div>
              </div>
            </div>

            <div className="bg-slate-50 rounded-3xl p-8 flex flex-col justify-between border border-slate-100">
              <div>
                <h3 className="text-slate-400 text-[10px] font-bold uppercase tracking-[0.2em] mb-6">关联知识漏洞</h3>
                <div className="space-y-4">
                  {(result.knowledge_gaps || []).map((gap, idx) => (
                    <div key={idx} className="space-y-2">
                      <div className="flex justify-between text-xs font-bold">
                        <span className="text-slate-700">{gap.knowledge_point}</span>
                        <span className="text-blue-600">{(gap.mastery_level * 100).toFixed(0)}%</span>
                      </div>
                      <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
                        <div className="h-full bg-blue-600" style={{ width: `${gap.mastery_level * 100}%` }}></div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <p className="text-[10px] text-slate-400 font-medium italic mt-6">* 数据已结合历史表现校准</p>
            </div>
          </div>

          {/* Step-by-Step Path */}
          <div className="bg-white rounded-[32px] border border-slate-100 overflow-hidden shadow-sm">
            <div className="px-8 py-6 bg-slate-50/50 border-b border-slate-50 flex items-center justify-between">
              <h3 className="font-bold text-lg text-slate-900">思维重塑路径</h3>
              <span className="text-[10px] text-slate-400 font-bold uppercase tracking-widest">AI 分步引导</span>
            </div>
            <div className="p-10">
              <div className="relative space-y-12">
                <div className="absolute left-4 top-2 bottom-2 w-px bg-slate-100"></div>
                {(result.detailed_analysis?.step_by_step_correction || []).map((step, idx) => (
                  <div key={idx} className="relative pl-12">
                    <div className="absolute left-0 top-0 w-8 h-8 rounded-full bg-white border border-blue-600 text-blue-600 flex items-center justify-center font-bold text-sm shadow-sm">
                      {idx + 1}
                    </div>
                    <p className="text-slate-800 leading-relaxed font-medium">{step}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Recommendations Area */}
          {reco && (
            <div className="space-y-6">
              <div className="flex items-center gap-4">
                <h3 className="text-2xl font-bold text-slate-900">智能强化方案</h3>
                <div className="h-px flex-1 bg-slate-100"></div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {(reco.immediate_actions || []).map((action, idx) => (
                  <div key={idx} className="bg-white rounded-3xl border border-slate-100 p-8 hover:shadow-lg transition-all group">
                    <h4 className="text-lg font-bold mb-4 text-slate-900">{action.content}</h4>
                    <div className="space-y-3">
                      {(action.resources || []).map((res) => (
                        <div key={res.id} className="flex items-center justify-between p-4 bg-slate-50 rounded-2xl hover:bg-blue-50 transition-colors cursor-pointer border border-transparent">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center font-bold">
                              {res.type === 'video' ? '▶' : '✍'}
                            </div>
                            <span className="text-sm font-bold text-slate-700">{res.title}</span>
                          </div>
                          <span className="text-[10px] font-bold text-slate-300">GO</span>
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
  );
};

export default AnalysisModule;
