
import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { SavedProblem } from '../types';

const ErrorBook: React.FC = () => {
  const [problems, setProblems] = useState<SavedProblem[]>([]);
  const [isSyncing, setIsSyncing] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const fetchAndMergeData = async () => {
    setIsSyncing(true);
    try {
      // 1. 从数据库接入层获取错题数据
      const dbErrors = await api.database.loadProblems();

      // 2. 获取作业系统自动批改的错题
      const homeworkErrors = await api.homework.getFlaggedHomework();

      // 3. 合并并去重
      const merged = [...dbErrors];
      homeworkErrors.forEach(hwErr => {
        if (!merged.find(m => m.id === hwErr.id)) {
          merged.push(hwErr);
        }
      });

      // 按时间倒序
      setProblems(merged.sort((a, b) => b.timestamp - a.timestamp));
    } catch (err) {
      console.error("Sync failed", err);
    } finally {
      setIsSyncing(false);
    }
  };

  useEffect(() => {
    fetchAndMergeData();
  }, []);

  const clearBook = () => {
    if (window.confirm('确定要清空错题本记录吗？')) {
      if (!api.config.isComplete) {
        localStorage.removeItem('sqlite_error_table');
        fetchAndMergeData();
      } else {
        alert("远程数据库数据需通过后台管理系统清理");
      }
    }
  };

  const deleteProblem = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    const updated = problems.filter(p => p.id !== id);
    setProblems(updated);
    
    // 更新本地缓存
    if (!api.config.isComplete) {
      const saved = JSON.parse(localStorage.getItem('sqlite_error_table') || '[]');
      const filtered = saved.filter((p: any) => p.id !== id);
      localStorage.setItem('sqlite_error_table', JSON.stringify(filtered));
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-10 pb-20 animate-in fade-in duration-700">
      <div className="flex items-end justify-between px-4">
        <div>
          <h2 className="text-3xl font-black text-slate-900 mb-1 flex items-center gap-3">
            个人错题本
            {isSyncing && (
              <span className="flex h-2 w-2 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-600"></span>
              </span>
            )}
          </h2>
          <p className="text-slate-500 text-sm font-medium">
            已聚合 {problems.length} 道题目
          </p>
        </div>
        <div className="flex gap-3">
          <button 
            onClick={fetchAndMergeData}
            className="px-6 py-2.5 bg-blue-50 text-blue-600 rounded-full text-xs font-black hover:bg-blue-100 transition-all"
          >
            同步作业数据
          </button>
          {!api.config.isComplete && (
            <button 
              onClick={clearBook}
              className="px-6 py-2.5 bg-slate-100 hover:bg-red-50 hover:text-red-600 text-slate-400 rounded-full text-xs font-black transition-all"
            >
              重置本地记录
            </button>
          )}
        </div>
      </div>

      {problems.length === 0 ? (
        <div className="bg-mist border border-dashed border-slate-200 rounded-[48px] py-32 flex flex-col items-center text-center">
          <div className="w-20 h-20 bg-white rounded-[32px] shadow-sm flex items-center justify-center text-slate-200 mb-6">
            <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" /></svg>
          </div>
          <h3 className="text-xl font-black text-slate-900 mb-2">错题本还是空的</h3>
          <p className="text-slate-400 text-sm max-w-xs font-medium">尚未发现作业错误或 AI 诊断记录</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {problems.map((problem) => (
            <div 
              key={problem.id}
              onClick={() => setSelectedId(selectedId === problem.id ? null : problem.id)}
              className={`group bg-white border rounded-[40px] transition-all cursor-pointer overflow-hidden ${
                selectedId === problem.id ? 'ring-4 ring-blue-600/5 border-blue-600 shadow-2xl' : 'border-slate-100 hover:shadow-xl hover:shadow-slate-100 hover:translate-y-[-4px]'
              }`}
            >
              <div className="p-8">
                <div className="flex justify-between items-start mb-6">
                  <div className="flex gap-2">
                    <span className={`px-3 py-1 text-[10px] font-black rounded-lg uppercase tracking-wider ${problem.id.startsWith('hw_') ? 'bg-emerald-50 text-emerald-600' : 'bg-blue-50 text-blue-600'}`}>
                      {problem.id.startsWith('hw_') ? '作业同步' : 'AI 诊断'}
                    </span>
                    <span className="px-3 py-1 bg-slate-50 text-slate-400 text-[10px] font-black rounded-lg uppercase tracking-wider">
                      {new Date(problem.timestamp).toLocaleDateString()}
                    </span>
                  </div>
                  <button 
                    onClick={(e) => deleteProblem(e, problem.id)}
                    className="p-2 opacity-0 group-hover:opacity-100 hover:bg-red-50 hover:text-red-500 rounded-full transition-all text-slate-300"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                  </button>
                </div>

                <div className="flex gap-6">
                  {problem.image && (
                    <div className="w-24 h-24 rounded-2xl overflow-hidden flex-shrink-0 border border-slate-50">
                      <img src={problem.image} className="w-full h-full object-cover" alt="题目截图" />
                    </div>
                  )}
                  <div className="flex-1">
                    <p className="text-slate-800 font-bold text-sm leading-relaxed line-clamp-3 mb-4">
                      {problem.question || "题目内容见图片..."}
                    </p>
                    <div className="flex items-center gap-2">
                       <div className={`w-1.5 h-1.5 rounded-full ${problem.id.startsWith('hw_') ? 'bg-emerald-500' : 'bg-blue-600'}`}></div>
                       <span className="text-[11px] font-black text-slate-400 uppercase tracking-widest">{problem.analysis.error_type}</span>
                    </div>
                  </div>
                </div>

                {selectedId === problem.id && (
                  <div className="mt-8 pt-8 border-t border-slate-50 space-y-8 animate-in slide-in-from-top-4">
                    <div>
                      <h4 className="text-[10px] font-black text-slate-300 uppercase tracking-widest mb-4">诊断核心</h4>
                      <p className="text-slate-900 font-black leading-tight text-lg">{problem.analysis.root_cause}</p>
                    </div>

                    <div>
                      <h4 className="text-[10px] font-black text-slate-300 uppercase tracking-widest mb-4">纠偏步骤</h4>
                      <div className="space-y-4">
                        {problem.analysis.detailed_analysis.step_by_step_correction.map((step, idx) => (
                          <div key={idx} className="flex gap-4">
                            <span className="text-blue-600 font-black text-xs pt-0.5">{idx + 1}.</span>
                            <p className="text-slate-600 text-xs font-medium leading-relaxed">{step}</p>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="bg-slate-50 rounded-2xl p-5 border border-slate-100">
                      <h4 className="text-[10px] font-black text-slate-300 uppercase tracking-widest mb-3">正确解答参考</h4>
                      <p className="text-slate-700 text-xs font-bold leading-relaxed">{problem.analysis.detailed_analysis.correct_solution}</p>
                    </div>
                  </div>
                )}
                
                <div className="mt-6 flex justify-end">
                   <span className="text-[10px] font-black text-blue-600 uppercase tracking-widest group-hover:mr-2 transition-all">
                      {selectedId === problem.id ? '收起详情' : '展开深度解析 →'}
                   </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ErrorBook;
