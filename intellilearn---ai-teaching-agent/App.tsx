
import React from 'react';
import { HashRouter, Routes, Route, Link } from 'react-router-dom';
import Layout from './components/Layout';
import AnalysisModule from './components/AnalysisModule';
import DiagnosticReport from './components/DiagnosticReport';

const Dashboard: React.FC = () => {
  return (
    <div className="space-y-12 pb-16">
      {/* Hero Section */}
      <div className="relative rounded-[48px] bg-mist border border-slate-100 p-12 overflow-hidden min-h-[420px] flex items-center">
        <div className="relative z-10 max-w-2xl">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600/10 text-blue-600 rounded-full text-xs font-black mb-8 border border-blue-600/5">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-600"></span>
            </span>
            系统状态：自适应分析模型已就绪
          </div>
          <h1 className="text-5xl font-black text-slate-900 mb-6 tracking-tight leading-[1.05]">
            你好，张同学。<br />
            今日建议攻克 <span className="text-blue-600">函数平移</span>。
          </h1>
          <p className="text-xl text-slate-600 mb-10 font-medium leading-relaxed">
            AI 已为你同步生成了 2 个高价值复习任务，通过率预测提升 <span className="text-emerald-500 font-bold">14%</span>。
          </p>
          <div className="flex gap-4">
            <Link to="/analysis" className="px-10 py-5 bg-slate-900 text-white rounded-[24px] font-bold shadow-2xl shadow-slate-200 hover:bg-slate-800 transition-all flex items-center gap-2 hover:scale-[1.02] active:scale-95">
              启动深度解析
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>
            </Link>
            <Link to="/report" className="px-10 py-5 bg-white border border-slate-100 text-slate-900 rounded-[24px] font-bold hover:bg-slate-50 transition-all hover:border-slate-200">
              数据趋势看板
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

      {/* Stats Summary - More realistic ranges */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {[
          { label: '待处理错题', value: '14', unit: '道', color: 'text-blue-600', sub: '近7日新增 5 道' },
          { label: '重点突破点', value: '3', unit: '项', color: 'text-amber-500', sub: '主要集中在解析几何' },
          { label: '近期正确率', value: '78.5', unit: '%', color: 'text-emerald-500', sub: '优于 65% 的同级学生' },
          { label: '学习累计时长', value: '42.5', unit: 'H', color: 'text-indigo-600', sub: '本周投入时长显著增加' },
        ].map((stat, i) => (
          <div key={i} className="bg-white p-7 rounded-[32px] border border-slate-100 shadow-sm hover:shadow-md transition-all hover:translate-y-[-4px]">
            <p className="text-slate-400 font-black uppercase text-[10px] tracking-[0.2em] mb-3">{stat.label}</p>
            <div className="flex items-baseline gap-1 mb-2">
              <span className={`text-4xl font-black tracking-tight ${stat.color}`}>{stat.value}</span>
              <span className="text-slate-400 text-sm font-bold">{stat.unit}</span>
            </div>
            <p className="text-[10px] text-slate-400 font-bold uppercase">{stat.sub}</p>
          </div>
        ))}
      </div>

      {/* Suggested Tasks */}
      <div className="space-y-8">
        <div className="flex items-center justify-between px-2">
          <h3 className="text-2xl font-black flex items-center gap-3 text-slate-900">
            <span className="w-2.5 h-8 bg-blue-600 rounded-full"></span>
            AI 智能补强建议
          </h3>
          <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest bg-slate-50 px-3 py-1 rounded-full">同步自学情档案</span>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
           <div className="bg-white border border-slate-100 p-8 rounded-[40px] group cursor-pointer hover:border-blue-600 transition-all hover:shadow-xl hover:shadow-blue-50">
              <div className="w-14 h-14 bg-blue-50 text-blue-600 rounded-[20px] flex items-center justify-center mb-6 font-black text-xl group-hover:scale-110 transition-transform shadow-sm shadow-blue-100">01</div>
              <h4 className="font-black text-xl mb-3 text-slate-900 group-hover:text-blue-600 transition-colors">二次函数：符号陷阱</h4>
              <p className="text-slate-500 text-sm leading-relaxed font-medium">针对你在上周练习中，关于开口方向符号判断的 2 次失误进行的针对性练习。</p>
              <div className="mt-10 flex items-center justify-between text-[10px] font-black uppercase tracking-widest">
                <span className="text-blue-600 bg-blue-50 px-2 py-1 rounded">预计 12 MIN</span>
                <span className="text-slate-300 group-hover:text-blue-600 transition-colors">GO ANALYZE →</span>
              </div>
           </div>
           
           <div className="bg-white border border-slate-100 p-8 rounded-[40px] group cursor-pointer hover:border-blue-600 transition-all hover:shadow-xl hover:shadow-blue-50">
              <div className="w-14 h-14 bg-emerald-50 text-emerald-600 rounded-[20px] flex items-center justify-center mb-6 font-black text-xl group-hover:scale-110 transition-transform shadow-sm shadow-emerald-100">02</div>
              <h4 className="font-black text-xl mb-3 text-slate-900 group-hover:text-emerald-600 transition-colors">不等式：边界条件复盘</h4>
              <p className="text-slate-500 text-sm leading-relaxed font-medium">扫描到你在“等号成立”的临界状态处理上存在系统性疏漏，建议立即回顾。</p>
              <div className="mt-10 flex items-center justify-between text-[10px] font-black uppercase tracking-widest">
                <span className="text-emerald-600 bg-emerald-50 px-2 py-1 rounded">预计 8 MIN</span>
                <span className="text-slate-300 group-hover:text-emerald-600 transition-colors">GO ANALYZE →</span>
              </div>
           </div>
           
           <div className="bg-white border border-slate-100 p-8 rounded-[40px] group cursor-pointer hover:border-blue-600 transition-all hover:shadow-xl hover:shadow-blue-50">
              <div className="w-14 h-14 bg-indigo-50 text-indigo-600 rounded-[20px] flex items-center justify-center mb-6 font-black text-xl group-hover:scale-110 transition-transform shadow-sm shadow-indigo-100">03</div>
              <h4 className="font-black text-xl mb-3 text-slate-900 group-hover:text-indigo-600 transition-colors">圆与直线：位置关系特训</h4>
              <p className="text-slate-500 text-sm leading-relaxed font-medium">通过几何画板动态模拟，帮助你直观理解圆心距与半径的关系，解决计算疲劳。</p>
              <div className="mt-10 flex items-center justify-between text-[10px] font-black uppercase tracking-widest">
                <span className="text-indigo-600 bg-indigo-50 px-2 py-1 rounded">预计 15 MIN</span>
                <span className="text-slate-300 group-hover:text-indigo-600 transition-colors">GO ANALYZE →</span>
              </div>
           </div>
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
          <Route path="/report" element={<DiagnosticReport />} />
        </Routes>
      </Layout>
    </HashRouter>
  );
};

export default App;
