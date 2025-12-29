
import React, { useState, useRef } from 'react';
import { analyzeProblemIntelligently, getRecommendations } from '../services/geminiService';
import { api } from '../services/api';
import { AnalysisResult, Recommendation, SavedProblem } from '../types';

const AnalysisModule: React.FC = () => {
  const [question, setQuestion] = useState('');
  const [image, setImage] = useState<string | null>(null);
  const [answer, setAnswer] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [processStatus, setProcessStatus] = useState('');
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [reco, setReco] = useState<Recommendation | null>(null);
  
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => setImage(reader.result as string);
      reader.readAsDataURL(file);
    }
  };

  const handleAnalyze = async () => {
    if (!question && !image) return;
    setIsAnalyzing(true);
    setProcessStatus('正在激活 AI 诊断引擎...');
    setResult(null);
    setReco(null);
    try {
      const analysisResult = await analyzeProblemIntelligently('数学', question, image || undefined, (status) => {
        setProcessStatus(status);
      });
      setResult(analysisResult);
      
      // 构建错题对象并调用数据库接入层
      const newProblem: SavedProblem = {
        id: Math.random().toString(36).substr(2, 9),
        timestamp: Date.now(),
        subject: '数学',
        question: question,
        image: image || undefined,
        analysis: analysisResult
      };

      setProcessStatus('正在保存诊断记录...');
      await api.database.saveProblem(newProblem);
      
      setProcessStatus('正在生成个性化补强方案...');
      const recommendations = await getRecommendations(analysisResult);
      setReco(recommendations);
    } catch (error) {
      console.error("Diagnostic pipeline failed:", error);
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-8 pb-20">
      <div className="bg-white rounded-[40px] border border-slate-100 shadow-sm overflow-hidden p-10">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-2xl font-black text-slate-900">AI 错题智能解析</h2>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
          <div className="space-y-4">
            <div 
              onClick={() => fileInputRef.current?.click()}
              className={`relative h-64 border-2 border-dashed rounded-[32px] flex flex-col items-center justify-center cursor-pointer transition-all ${image ? 'border-blue-600 bg-blue-50/10' : 'border-slate-100 bg-slate-50/50 hover:bg-slate-50'}`}
            >
              {image ? (
                <>
                  <img src={image} className="h-full w-full object-contain rounded-[30px]" alt="preview" />
                  <div className="absolute inset-0 bg-blue-600/5 opacity-0 hover:opacity-100 flex items-center justify-center transition-opacity rounded-[30px]">
                     <span className="bg-white px-4 py-2 rounded-full text-xs font-bold text-blue-600">更换照片</span>
                  </div>
                </>
              ) : (
                <div className="text-center group">
                  <div className="w-16 h-16 bg-white rounded-2xl shadow-sm flex items-center justify-center mx-auto mb-4 text-slate-300 group-hover:text-blue-600 transition-colors">
                    <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                  </div>
                  <p className="text-sm font-bold text-slate-500">点击上传题目照片</p>
                  <p className="text-[10px] text-slate-400 font-bold uppercase mt-1">识别公式、图像与手写批改</p>
                </div>
              )}
              <input type="file" ref={fileInputRef} onChange={handleFileChange} hidden accept="image/*" />
            </div>
          </div>

          <div className="space-y-6">
            <div className="space-y-2">
              <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">题目文本 / 补充说明</label>
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="在此输入题目文字，或在上传照片后补充关键信息..."
                className="w-full h-32 p-5 bg-slate-50/50 border border-slate-100 rounded-[24px] focus:ring-4 focus:ring-blue-600/5 focus:bg-white outline-none transition-all resize-none text-sm font-medium"
              />
            </div>
            <div className="space-y-2">
              <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">个人解答思路</label>
              <textarea
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="写下你的解题步骤或觉得困惑的地方..."
                className="w-full h-32 p-5 bg-slate-50/50 border border-slate-100 rounded-[24px] focus:ring-4 focus:ring-blue-600/5 focus:bg-white outline-none transition-all resize-none text-sm font-medium"
              />
            </div>
          </div>
        </div>

        <button
          onClick={handleAnalyze}
          disabled={isAnalyzing}
          className={`w-full mt-10 py-5 rounded-[24px] font-black text-lg transition-all flex flex-col items-center justify-center gap-1 ${
            isAnalyzing ? 'bg-slate-900 text-white cursor-wait' : 'bg-blue-600 text-white shadow-2xl shadow-blue-100 hover:scale-[1.005] active:scale-[0.99]'
          }`}
        >
          {isAnalyzing ? (
            <div className="flex items-center gap-4">
              <div className="w-5 h-5 border-2 border-blue-500 border-t-white rounded-full animate-spin"></div>
              <div className="text-left">
                 <p className="text-sm leading-none mb-1">正在执行深度分析</p>
                 <p className="text-[10px] text-white/40 font-bold uppercase tracking-widest">{processStatus}</p>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <span>开始 AI 智能解析</span>
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M14 5l7 7m0 0l-7 7m7-7H3" /></svg>
            </div>
          )}
        </button>
      </div>

      {result && (
        <div className="animate-in fade-in slide-in-from-bottom-10 duration-1000 space-y-8">
           <div className="bg-emerald-50 border border-emerald-100 rounded-2xl p-4 flex items-center gap-3">
              <svg className="w-5 h-5 text-emerald-500" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" /></svg>
              <p className="text-xs font-bold text-emerald-700">解析已自动同步并保存</p>
           </div>

           <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2 bg-white rounded-[40px] border border-slate-100 p-10 shadow-sm relative overflow-hidden">
                 <div className="absolute top-0 right-0 w-32 h-32 bg-blue-50 rounded-bl-full -mr-16 -mt-16 opacity-50"></div>
                 <h3 className="text-slate-400 text-[10px] font-black uppercase tracking-[0.25em] mb-6">核心诊断结论</h3>
                 <p className="text-2xl font-black text-slate-900 leading-tight mb-8">{result.root_cause}</p>
                 <div className="pt-8 border-t border-slate-50 flex gap-12">
                    <div>
                       <p className="text-[10px] font-black text-slate-300 uppercase mb-2">偏差类型</p>
                       <span className="px-3 py-1 bg-red-50 text-red-600 text-xs font-black rounded-lg border border-red-100">{result.error_type}</span>
                    </div>
                    <div>
                       <p className="text-[10px] font-black text-slate-300 uppercase mb-2">影响权重</p>
                       <span className="px-3 py-1 bg-blue-50 text-blue-600 text-xs font-black rounded-lg border border-blue-100 uppercase">{result.error_severity}</span>
                    </div>
                 </div>
              </div>
              
              <div className="bg-slate-900 rounded-[40px] p-10 text-white flex flex-col justify-between">
                 <div>
                    <h3 className="text-white/30 text-[10px] font-black uppercase tracking-[0.25em] mb-8">知识雷达</h3>
                    <div className="space-y-6">
                       {result.knowledge_gaps.map((gap, i) => (
                         <div key={i}>
                            <div className="flex justify-between text-xs font-black mb-2">
                               <span>{gap.knowledge_point}</span>
                               <span className="text-blue-400">{(gap.mastery_level * 100).toFixed(0)}%</span>
                            </div>
                            <div className="h-1 bg-white/10 rounded-full overflow-hidden">
                               <div className="h-full bg-blue-500 rounded-full" style={{ width: `${gap.mastery_level * 100}%` }}></div>
                            </div>
                         </div>
                       ))}
                    </div>
                 </div>
                 <p className="text-[10px] text-white/20 font-bold uppercase mt-8">基于历史学情数据加权</p>
              </div>
           </div>

           <div className="bg-white rounded-[48px] border border-slate-100 p-12 shadow-sm">
              <h3 className="text-xl font-black text-slate-900 mb-12 flex items-center gap-4">
                 <span className="w-2 h-8 bg-blue-600 rounded-full"></span>
                 思维纠偏引导
              </h3>
              <div className="space-y-12 relative">
                 <div className="absolute left-[15px] top-4 bottom-4 w-px bg-slate-100"></div>
                 {result.detailed_analysis.step_by_step_correction.map((step, i) => (
                    <div key={i} className="flex gap-8 group">
                       <div className="relative z-10 w-8 h-8 rounded-full bg-white border-2 border-slate-100 flex items-center justify-center text-xs font-black text-slate-400 group-hover:border-blue-600 group-hover:text-blue-600 transition-all shadow-sm">
                          {i + 1}
                       </div>
                       <p className="text-slate-700 font-medium leading-relaxed flex-1 group-hover:text-slate-900 transition-colors pt-1">{step}</p>
                    </div>
                 ))}
              </div>
           </div>
        </div>
      )}
    </div>
  );
};

export default AnalysisModule;
