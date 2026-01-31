'use client';

import React, { useEffect, useState, useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import { FileText, Users, Clock, Award, Workflow, Cpu, GitBranch, ShieldCheck } from 'lucide-react';

// 技术特性展示
const techFeatures = [
  {
    icon: Workflow,
    label: "LangGraph",
    value: "工作流编排",
    desc: "多智能体协作",
    color: "#3b82f6"
  },
  {
    icon: Cpu,
    label: "Gemini 3.0",
    value: "Vision原生",
    desc: "视觉理解模型",
    color: "#06b6d4"
  },
  {
    icon: GitBranch,
    label: "并行处理",
    value: "批量批改",
    desc: "多学生同时处理",
    color: "#8b5cf6"
  },
  {
    icon: ShieldCheck,
    label: "人机协同",
    value: "审核机制",
    desc: "可介入审核修改",
    color: "#10b981"
  },
];



// 技术特性卡片
const TechFeatureCard = ({ feature, index }: { feature: typeof techFeatures[0]; index: number }) => {
  const Icon = feature.icon;
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-50px" });

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 20 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ delay: index * 0.1 }}
      whileHover={{ y: -5, transition: { duration: 0.2 } }}
      className="group cursor-default"
    >
      <div
        className="flex items-center gap-4 p-4 rounded-xl bg-white border transition-all duration-300 hover:shadow-md"
        style={{ borderColor: `${feature.color}20` }}
      >
        {/* 图标 */}
        <div
          className="w-12 h-12 rounded-lg flex items-center justify-center transition-all duration-300"
          style={{ background: `${feature.color}15` }}
        >
          <Icon className="w-6 h-6" style={{ color: feature.color }} />
        </div>

        {/* 内容 */}
        <div className="flex-1">
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-0.5">
            {feature.label}
          </div>
          <div
            className="text-lg font-bold text-gray-900 transition-colors"
            style={{ color: feature.color }}
          >
            {feature.value}
          </div>
          <div className="text-xs text-gray-500">
            {feature.desc}
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export const StatsRow = () => {
  const sectionRef = useRef(null);
  const isInView = useInView(sectionRef, { once: true, margin: "-100px" });

  return (
    <section ref={sectionRef} className="py-20 bg-gradient-to-b from-white to-blue-50/30">
      <div className="landing-container">
        {/* 技术特性 */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          className="mb-16"
        >
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {techFeatures.map((feature, idx) => (
              <TechFeatureCard key={idx} feature={feature} index={idx} />
            ))}
          </div>
        </motion.div>


      </div>
    </section>
  );
};

export default StatsRow;
