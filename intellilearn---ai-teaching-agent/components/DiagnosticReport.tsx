
import React, { useEffect, useState } from 'react';
import { 
  Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer, 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, AreaChart, Area 
} from 'recharts';
import { getDiagnosisReport } from '../services/geminiService';
import { DiagnosisReport as DiagnosisReportType } from '../types';

const DiagnosticReport: React.FC = () => {
  const [report, setReport] = useState<DiagnosisReportType | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchReport = async () => {
      try {
        const data = await getDiagnosisReport('S20240101');
        setReport(data);
      } catch (error) {
        console.error("Diagnostic Error:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchReport();
  }, []);

  if (loading) return (
    <div className="flex flex-col items-center justify-center h-96 gap-4">
      <div className="w-12 h-12 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
      <p className="text-slate-500 font-medium tracking-tight">深度聚合多维学习数据，正在校准成长曲线...</p>
    </div>
  );

  if (!report) return (
    <div className="bg-white border border-slate-100 rounded-3xl p-12 text-center">
      <p className="text-slate-500 font-bold">无法加载报告，请检查网络设置或 API Key。</p>
    </div>
  );

  const radarData = (report.knowledge_map || []).map(km => ({
    subject: km.knowledge_area,
    A: (km.mastery_level || 0) * 100,
    fullMark: 100
  }));

  const errorPatternData = (report.error_patterns?.most_common_error_types || []).map(ep => ({
    name: ep.type,
    count: ep.count
  }));

  const trendData = (report.progress_trend || []).map(t => ({
    ...t,
    score: (t.score || 0) * 100,
    average: (t.average || 0) * 100
  }));

  return (
    <div className="space-y-8 animate-in fade-in duration-700 pb-20">
      {/* Header Info */}
      <div className="flex items-end justify-between px-4">
        <div>
           <h2 className="text-3xl font-black text-slate-900 mb-1">阶段性成长评估报告</h2>
           <p className="text-slate-500 text-sm font-medium">数据最后更新时间：{new Date().toLocaleDateString()}</p>
        </div>
        <div className="bg-blue-600 text-white px-4 py-2 rounded-2xl text-xs font-bold shadow-lg shadow-blue-100">
           ID: {report.student_id}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-slate-900">
        <div className="bg-white border border-slate-100 rounded-3xl p-6 shadow-sm hover:shadow-md transition-shadow">
          <p className="text-slate-400 text-[10px] font-bold uppercase tracking-widest mb-2">综合掌握度</p>
          <div className="flex items-baseline gap-1">
            <span className="text-3xl font-black">{( (report.overall_assessment?.mastery_score || 0) * 100).toFixed(1)}</span>
            <span className="text-slate-400 font-medium text-sm">%</span>
          </div>
          <p className="text-[10px] text-slate-400 mt-2 font-bold uppercase">较上月 +1.2%</p>
        </div>
        <div className="bg-white border border-slate-100 rounded-3xl p-6 shadow-sm hover:shadow-md transition-shadow">
          <p className="text-slate-400 text-[10px] font-bold uppercase tracking-widest mb-2">学习进步率</p>
          <div className="flex items-baseline gap-1">
            <span className="text-3xl font-black text-emerald-500">+{( (report.overall_assessment?.improvement_rate || 0) * 100).toFixed(1)}</span>
            <span className="text-slate-400 font-medium text-sm">%</span>
          </div>
          <p className="text-[10px] text-emerald-500/60 mt-2 font-bold uppercase">稳步增长中</p>
        </div>
        <div className="bg-white border border-slate-100 rounded-3xl p-6 shadow-sm hover:shadow-md transition-shadow">
          <p className="text-slate-400 text-[10px] font-bold uppercase tracking-widest mb-2">专注稳定性</p>
          <div className="flex items-baseline gap-1">
            <span className="text-3xl font-black text-blue-600">{(report.overall_assessment?.consistency_score || 0)}</span>
            <span className="text-slate-400 font-medium text-sm">/100</span>
          </div>
          <p className="text-[10px] text-blue-600/60 mt-2 font-bold uppercase">状态评级：良</p>
        </div>
        <div className="bg-slate-900 rounded-3xl p-6 text-white shadow-xl shadow-slate-200">
          <p className="text-white/40 text-[10px] font-bold uppercase tracking-widest mb-2">覆盖周期</p>
          <div className="text-sm font-bold truncate leading-tight mt-1">{report.report_period}</div>
          <p className="text-[10px] text-white/20 mt-3 font-bold uppercase">总计分析 42 道题目</p>
        </div>
      </div>

      {/* Progress Trend */}
      <div className="bg-white border border-slate-100 rounded-[32px] p-8 shadow-sm">
        <div className="flex items-center justify-between mb-10">
          <div>
            <h3 className="text-xl font-bold flex items-center gap-2 text-slate-900">
              <span className="w-1.5 h-6 bg-blue-600 rounded-full"></span>
              学习轨迹与班级基准
            </h3>
            <p className="text-slate-400 text-xs mt-1 font-medium">展示过去一段时间内，你的表现与班级平均水平的对比趋势</p>
          </div>
          <div className="flex gap-4 text-[10px] font-black uppercase tracking-widest text-slate-500">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 bg-blue-600 rounded-full"></span>
              个人得分
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 bg-slate-200 rounded-full border border-slate-300"></span>
              班级平均
            </div>
          </div>
        </div>
        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={trendData}>
              <defs>
                <linearGradient id="colorScore" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#2563EB" stopOpacity={0.15}/>
                  <stop offset="95%" stopColor="#2563EB" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F8FAFC" />
              <XAxis 
                dataKey="date" 
                axisLine={false} 
                tickLine={false} 
                tick={{fill: '#94a3b8', fontSize: 10, fontWeight: 'bold'}} 
              />
              <YAxis 
                hide 
                domain={[0, 100]} 
              />
              <Tooltip 
                contentStyle={{ borderRadius: '20px', border: 'none', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)', color: '#0f172a', padding: '12px' }}
                cursor={{ stroke: '#F1F5F9', strokeWidth: 2 }}
              />
              <Area 
                type="monotone" 
                dataKey="average" 
                stroke="#e2e8f0" 
                fill="transparent" 
                strokeWidth={2} 
                strokeDasharray="8 4" 
              />
              <Area 
                type="monotone" 
                dataKey="score" 
                stroke="#2563EB" 
                strokeWidth={4} 
                fillOpacity={1} 
                fill="url(#colorScore)" 
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 text-slate-900">
        <div className="bg-white border border-slate-100 rounded-[32px] p-8 shadow-sm">
          <h3 className="text-lg font-bold mb-2">多维能力雷达</h3>
          <p className="text-slate-400 text-xs mb-8 font-medium">反映你在不同知识板块的分布平衡度</p>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData}>
                <PolarGrid stroke="#F1F5F9" strokeWidth={2} />
                <PolarAngleAxis 
                  dataKey="subject" 
                  tick={{ fill: '#64748b', fontSize: 10, fontWeight: '800' }} 
                />
                <Radar 
                  name="当前掌握度" 
                  dataKey="A" 
                  stroke="#2563EB" 
                  strokeWidth={2}
                  fill="#2563EB" 
                  fillOpacity={0.15} 
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white border border-slate-100 rounded-[32px] p-8 shadow-sm">
          <h3 className="text-lg font-bold mb-2">错因分布透视</h3>
          <p className="text-slate-400 text-xs mb-8 font-medium">统计你在学习中频繁出现的错误行为类型</p>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={errorPatternData} layout="vertical" margin={{ left: 20 }}>
                <XAxis type="number" hide />
                <YAxis 
                  type="category" 
                  dataKey="name" 
                  axisLine={false} 
                  tickLine={false} 
                  width={100} 
                  tick={{fill: '#475569', fontSize: 11, fontWeight: 'bold'}} 
                />
                <Tooltip 
                  cursor={{fill: '#F8FAFC'}} 
                  contentStyle={{borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.05)'}}
                />
                <Bar 
                  dataKey="count" 
                  fill="#3B82F6" 
                  radius={[0, 10, 10, 0]} 
                  barSize={24} 
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Insights Section */}
      <div className="bg-slate-900 rounded-[48px] p-12 text-white relative overflow-hidden shadow-2xl">
        <div className="absolute -top-10 -right-10 opacity-10 pointer-events-none transform rotate-12">
          <svg className="w-80 h-80" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2L1 21h22L12 2zm0 3.45l8.15 14.1H3.85L12 5.45zM11 10v4h2v-4h-2zm0 6v2h2v-2h-2z"/></svg>
        </div>
        
        <div className="relative z-10">
          <div className="flex items-center gap-4 mb-10">
            <div className="w-12 h-12 rounded-2xl bg-blue-600 flex items-center justify-center text-xs font-black shadow-lg shadow-blue-500/20">AI</div>
            <div>
              <h3 className="text-2xl font-black">专家级教育洞察</h3>
              <p className="text-white/40 text-xs font-bold uppercase tracking-widest mt-1">由深度认知引擎生成</p>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {(report.personalized_insights || []).map((insight, idx) => (
              <div key={idx} className="flex gap-5 p-6 rounded-[28px] bg-white/5 border border-white/5 hover:bg-white/10 transition-all group">
                <span className="text-blue-400 font-black text-xl leading-none">0{idx+1}</span>
                <p className="text-white/80 leading-relaxed text-sm font-medium group-hover:text-white transition-colors">{insight}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DiagnosticReport;
