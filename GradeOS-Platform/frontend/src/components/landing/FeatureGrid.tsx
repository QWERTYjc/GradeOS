import React from 'react';
import { motion } from 'framer-motion';
import { 
  Brain, 
  Zap, 
  Shield, 
  BarChart3, 
  Users, 
  Clock,
  ScanLine,
  GitBranch
} from 'lucide-react';

const features = [
  {
    icon: ScanLine,
    title: "Vision原生识别",
    description: "基于 Gemini 3.0 Vision，直接理解图像内容，无需传统OCR预处理，支持手写体、公式、图表识别。",
    color: "blue",
    gradient: "from-blue-500 to-cyan-500"
  },
  {
    icon: GitBranch,
    title: "LangGraph编排",
    description: "采用 LangGraph 工作流引擎，支持多智能体并行处理、人工介入审核、断点续传等高级特性。",
    color: "cyan",
    gradient: "from-cyan-500 to-teal-500"
  },
  {
    icon: Brain,
    title: "深度推理批改",
    description: "AI不仅给出分数，更提供详细的评分理由、错误分析、改进建议，支持多轮自纠正。",
    color: "teal",
    gradient: "from-teal-500 to-emerald-500"
  },
  {
    icon: Zap,
    title: "批量并行处理",
    description: "支持多份试卷同时处理，自动检测学生边界，智能分批策略，最大化利用API并发能力。",
    color: "emerald",
    gradient: "from-emerald-500 to-amber-500"
  },
  {
    icon: Shield,
    title: "人机协同审核",
    description: "低置信度结果自动标记，教师可一键审核修改，确保评分准确性，支持评分标准预览。",
    color: "amber",
    gradient: "from-amber-500 to-orange-500"
  },
  {
    icon: BarChart3,
    title: "实时进度追踪",
    description: "WebSocket实时推送批改进度，可视化工作流执行状态，详细的日志记录和错误追踪。",
    color: "orange",
    gradient: "from-orange-500 to-red-500"
  }
];

export const FeatureGrid = () => {
  return (
    <section id="features" className="py-32 relative overflow-hidden bg-slate-950">
      {/* 背景装饰 */}
      <div className="absolute inset-0">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-px bg-gradient-to-r from-transparent via-slate-800 to-transparent" />
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-full h-px bg-gradient-to-r from-transparent via-slate-800 to-transparent" />
      </div>

      <div className="landing-container relative z-10">
        {/* 标题 */}
        <motion.div 
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center max-w-3xl mx-auto mb-20"
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-blue-500/10 border border-blue-500/20 mb-6">
            <Brain className="w-4 h-4 text-blue-400" />
            <span className="text-sm text-blue-400 font-medium">核心特性</span>
          </div>
          
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-6">
            为什么选择
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-400">
              GradeOS
            </span>
          </h2>
          
          <p className="text-lg text-slate-400">
            专为教育场景设计的AI批改系统，结合最新的多模态大模型和智能体技术
          </p>
        </motion.div>

        {/* 特性网格 */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: idx * 0.1 }}
              whileHover={{ y: -8, transition: { duration: 0.3 } }}
              className="group relative p-8 rounded-2xl bg-slate-900/50 border border-slate-800 hover:border-slate-700 transition-all duration-500 overflow-hidden"
            >
              {/* 悬停时的发光效果 */}
              <div className={`absolute inset-0 bg-gradient-to-br ${feature.gradient} opacity-0 group-hover:opacity-5 transition-opacity duration-500`} />
              
              {/* 图标 */}
              <div className={`relative w-14 h-14 rounded-xl bg-gradient-to-br ${feature.gradient} p-[1px] mb-6 group-hover:scale-110 group-hover:rotate-3 transition-all duration-500`}>
                <div className="w-full h-full rounded-xl bg-slate-900 flex items-center justify-center">
                  <feature.icon className="w-7 h-7 text-white" />
                </div>
              </div>

              {/* 内容 */}
              <h3 className="text-xl font-bold text-white mb-3 group-hover:text-transparent group-hover:bg-clip-text group-hover:bg-gradient-to-r group-hover:from-white group-hover:to-slate-300 transition-all duration-300">
                {feature.title}
              </h3>
              
              <p className="text-slate-400 leading-relaxed text-sm">
                {feature.description}
              </p>

              {/* 底部装饰线 */}
              <div className={`absolute bottom-0 left-0 w-0 h-1 bg-gradient-to-r ${feature.gradient} group-hover:w-full transition-all duration-500`} />
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default FeatureGrid;
