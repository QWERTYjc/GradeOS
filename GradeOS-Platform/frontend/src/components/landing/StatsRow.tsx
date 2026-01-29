import React from 'react';
import { motion } from 'framer-motion';
import { 
  Workflow, 
  Cpu, 
  GitBranch, 
  ShieldCheck 
} from 'lucide-react';

// 技术特性展示（非虚拟统计数据）
const techFeatures = [
  { 
    icon: Workflow,
    label: "LangGraph", 
    value: "工作流编排",
    desc: "多智能体协作"
  },
  { 
    icon: Cpu,
    label: "Gemini 3.0", 
    value: "Vision原生",
    desc: "视觉理解模型"
  },
  { 
    icon: GitBranch,
    label: "并行处理", 
    value: "批量批改",
    desc: "多学生同时处理"
  },
  { 
    icon: ShieldCheck,
    label: "人机协同", 
    value: "审核机制",
    desc: "可介入审核修改"
  },
];

export const StatsRow = () => {
  return (
    <section className="py-16 border-y border-slate-800/50 bg-slate-950/50 relative overflow-hidden">
      {/* 背景装饰 */}
      <div className="absolute inset-0">
        <div className="absolute inset-0 bg-gradient-to-r from-blue-500/5 via-transparent to-cyan-500/5" />
      </div>
      
      <div className="landing-container relative z-10">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {techFeatures.map((feature, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: idx * 0.1 }}
              whileHover={{ y: -5, transition: { duration: 0.2 } }}
              className="group cursor-default"
            >
              <div className="flex items-center gap-4 p-4 rounded-xl bg-slate-900/50 border border-slate-800/50 hover:border-slate-700/50 transition-all duration-300">
                {/* 图标 */}
                <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-blue-500/20 to-cyan-500/20 flex items-center justify-center group-hover:from-blue-500/30 group-hover:to-cyan-500/30 transition-all duration-300">
                  <feature.icon className="w-6 h-6 text-blue-400" />
                </div>
                
                {/* 内容 */}
                <div className="flex-1">
                  <div className="text-xs text-slate-500 uppercase tracking-wider mb-0.5">
                    {feature.label}
                  </div>
                  <div className="text-lg font-bold text-white group-hover:text-blue-400 transition-colors">
                    {feature.value}
                  </div>
                  <div className="text-xs text-slate-600">
                    {feature.desc}
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default StatsRow;
