
import React, { useEffect, useState } from 'react';
import { HashRouter, Routes, Route, Link } from 'react-router-dom';
import Layout from './components/Layout';
import AnalysisModule from './components/AnalysisModule';
import ErrorBook from './components/ErrorBook';
import { api } from './services/api';
import { ClassProblem } from './types';

const Dashboard: React.FC = () => {
  const [classProblems, setClassProblems] = useState<ClassProblem[]>([]);

  useEffect(() => {
    api.class.getWrongProblems().then(setClassProblems);
  }, []);

  return (
    <div className="space-y-12 pb-16">
      {/* Hero Section - 核心功能入口 */}
      <div className="relative rounded-[48px] bg-mist border border-slate-100 p-12 overflow-hidden min-h-[480px] flex items-center">
        <div className="relative z-10 max-w-2xl">
          <h1 className="text-5xl font-black text-slate-900 mb-6 tracking-tight leading-[1.05]">
            你好，张同学。<br />
            欢迎回到 <span className="text-blue-600">IntelliLearn</span>。
          </h1>
          <p className="text-xl text-slate-600 mb-10 font-medium leading-relaxed">
            今天准备攻克哪些难题？AI 已准备好为你提供深度的知识点诊断与思维纠偏。
          </p>
          <div className="flex gap-4">
            <Link to="/analysis" className="px-10 py-5 bg-slate-900 text-white rounded-[24px] font-bold shadow-2xl shadow-slate-200 hover:bg-slate-800 transition-all flex items-center gap-2 hover:scale-[1.02] active:scale-95">
              启动深度解析
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>
            </Link>
            <Link to="/error-book" className="px-10 py-5 bg-white border border-slate-100 text-slate-900 rounded-[24px] font-bold hover:bg-slate-50 transition-all hover:border-slate-200">
              错题本库
            </Link>
          </div>
        </div>
        
        {/* Abstract Tech Graphic */}
        <div className="absolute top-1/2 right-0 -translate-y-1/2 translate-x-1/4 pointer-events-none opacity-20">
           <svg className="w-[700px] h-[700px] text-blue-600" viewBox="0 0 200 200">
             <circle cx="100" cy="100" r="85" stroke="currentColor" strokeWidth="0.5" fill="none" strokeDasharray="10,10" className="animate-[spin_60s_linear_infinite]" />
             <circle cx="100" cy="100" r="65" stroke="currentColor" strokeWidth="1" fill="none" strokeDasharray="20,10" className="animate-[spin_45s_linear_infinite_reverse]" />
             <path d="M100 10 L100 190 M10 100 L190 100" stroke="currentColor" strokeWidth="0.1" />
           </svg>
        </div>
      </div>

      {/* Class System Integration Section */}
      <div className="space-y-6">
        <div className="flex items-center justify-between px-2">
          <div>
            <h3 className="text-2xl font-black text-slate-900">班级共性错题排行</h3>
            <p className="text-slate-400 text-sm font-medium">这些是初三 (2) 班同学们最近普遍困惑的知识点</p>
          </div>
          <div className="bg-emerald-50 text-emerald-600 px-4 py-2 rounded-xl text-xs font-black border border-emerald-100">
            实时同步中
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {classProblems.map((p, i) => (
            <div key={p.id} className="bg-white border border-slate-100 p-8 rounded-[40px] hover:shadow-xl hover:shadow-slate-100 transition-all border-b-4 border-b-blue-500/10">
              <div className="flex justify-between items-start mb-6">
                <span className="w-10 h-10 bg-slate-50 rounded-xl flex items-center justify-center text-slate-400 font-black text-xs">0{i+1}</span>
                <div className="text-right">
                  <p className="text-[10px] font-black text-slate-300 uppercase tracking-widest">错误率</p>
                  <p className="text-xl font-black text-red-500">{p.errorRate}</p>
                </div>
              </div>
              <p className="text-slate-800 font-bold text-sm leading-relaxed mb-6 line-clamp-3 h-[4.5rem]">{p.question}</p>
              <div className="flex flex-wrap gap-2">
                {p.tags.map(tag => (
                  <span key={tag} className="px-2.5 py-1 bg-slate-100 text-slate-500 text-[9px] font-black rounded-lg uppercase tracking-wider">{tag}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const App: React.FC = () => {
  return (
    <HashRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/analysis" element={<AnalysisModule />} />
          <Route path="/error-book" element={<ErrorBook />} />
        </Routes>
      </Layout>
    </HashRouter>
  );
};

export default App;
