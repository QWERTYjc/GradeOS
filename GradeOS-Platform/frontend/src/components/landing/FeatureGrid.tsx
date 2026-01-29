'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Brain, 
  Zap, 
  Shield, 
  BarChart3, 
  Users, 
  Clock,
  ScanLine,
  GitBranch,
  Eye,
  FileCheck,
  Sparkles,
  ArrowRight
} from 'lucide-react';

interface Feature {
  icon: React.ElementType;
  title: string;
  description: string;
  details: string[];
  color: string;
  gradient: string;
  stat: { value: string; label: string };
}

const features: Feature[] = [
  {
    icon: ScanLine,
    title: "Vision原生识别",
    description: "基于 Gemini 3.0 Vision，直接理解图像内容，无需传统OCR预处理",
    details: [
      "手写体精准识别，支持潦草字迹",
      "数学公式结构化提取",
      "图表、几何图形自动解析"
    ],
    color: "#3b82f6",
    gradient: "from-blue-500 to-blue-600",
    stat: { value: '99.2%', label: '识别精度' }
  },
  {
    icon: GitBranch,
    title: "LangGraph编排",
    description: "采用 LangGraph 工作流引擎，支持复杂的多智能体协作",
    details: [
      "多智能体并行处理架构",
      "支持人工介入断点",
      "工作流可视化追踪"
    ],
    color: "#06b6d4",
    gradient: "from-cyan-500 to-cyan-600",
    stat: { value: '3-8', label: '并行Worker' }
  },
  {
    icon: Brain,
    title: "深度推理批改",
    description: "AI不仅给出分数，更提供详细的评分理由和改进建议",
    details: [
      "逐题评分理由自动生成",
      "错误分析与知识点定位",
      "个性化学习建议"
    ],
    color: "#8b5cf6",
    gradient: "from-violet-500 to-violet-600",
    stat: { value: '98%', label: 'Rubric匹配' }
  },
  {
    icon: Zap,
    title: "批量并行处理",
    description: "支持多份试卷同时处理，最大化利用API并发能力",
    details: [
      "自动检测学生边界",
      "智能分批策略优化",
      "队列管理与负载均衡"
    ],
    color: "#10b981",
    gradient: "from-emerald-500 to-emerald-600",
    stat: { value: '90s', label: '平均批改' }
  },
  {
    icon: Eye,
    title: "人机协同审核",
    description: "低置信度结果自动标记，教师可一键审核修改",
    details: [
      "置信度实时评估",
      "待审核项目自动聚合",
      "审核历史完整记录"
    ],
    color: "#f59e0b",
    gradient: "from-amber-500 to-amber-600",
    stat: { value: '< 5%', label: '需审核率' }
  },
  {
    icon: BarChart3,
    title: "实时进度追踪",
    description: "WebSocket实时推送批改进度，可视化工作流执行状态",
    details: [
      "实时进度条与状态更新",
      "详细的执行日志记录",
      "异常自动告警通知"
    ],
    color: "#ef4444",
    gradient: "from-red-500 to-red-600",
    stat: { value: '24ms', label: '响应延迟' }
  }
];

// 3D翻转卡片组件
const FeatureCard = ({ feature, index }: { feature: Feature; index: number }) => {
  const [isFlipped, setIsFlipped] = useState(false);
  const Icon = feature.icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-50px" }}
      transition={{ delay: index * 0.1, duration: 0.5 }}
      className="relative h-[320px] cursor-pointer group perspective-1000"
      onMouseEnter={() => setIsFlipped(true)}
      onMouseLeave={() => setIsFlipped(false)}
      onClick={() => setIsFlipped(!isFlipped)}
    >
      <motion.div
        className="relative w-full h-full preserve-3d"
        animate={{ rotateY: isFlipped ? 180 : 0 }}
        transition={{ duration: 0.6, type: "spring", stiffness: 260, damping: 20 }}
        style={{ transformStyle: 'preserve-3d' }}
      >
        {/* 正面 */}
        <div 
          className="absolute inset-0 backface-hidden rounded-2xl p-6 flex flex-col"
          style={{ 
            backfaceVisibility: 'hidden',
            background: 'linear-gradient(145deg, #ffffff 0%, #f8fafc 100%)',
            border: '1px solid rgba(226, 232, 240, 0.8)',
            boxShadow: '0 4px 20px rgba(0,0,0,0.05)'
          }}
        >
          {/* 图标 */}
          <div 
            className={`w-14 h-14 rounded-xl bg-gradient-to-br ${feature.gradient} p-[1px] mb-5 group-hover:scale-110 transition-transform duration-300`}
          >
            <div className="w-full h-full rounded-xl bg-white flex items-center justify-center">
              <Icon className="w-7 h-7" style={{ color: feature.color }} />
            </div>
          </div>

          {/* 标题 */}
          <h3 className="text-xl font-bold text-gray-900 mb-3">
            {feature.title}
          </h3>
          
          {/* 描述 */}
          <p className="text-gray-600 text-sm leading-relaxed flex-1">
            {feature.description}
          </p>

          {/* 统计 */}
          <div className="mt-4 pt-4 border-t border-gray-100">
            <div className="flex items-baseline gap-2">
              <span 
                className="text-2xl font-bold"
                style={{ color: feature.color }}
              >
                {feature.stat.value}
              </span>
              <span className="text-sm text-gray-500">{feature.stat.label}</span>
            </div>
          </div>

          {/* 翻转提示 */}
          <div className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
            <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center">
              <ArrowRight className="w-4 h-4 text-gray-400 rotate-[-45deg]" />
            </div>
          </div>
        </div>

        {/* 背面 */}
        <div 
          className="absolute inset-0 backface-hidden rounded-2xl p-6 flex flex-col"
          style={{ 
            backfaceVisibility: 'hidden',
            transform: 'rotateY(180deg)',
            background: `linear-gradient(145deg, ${feature.color}08 0%, ${feature.color}15 100%)`,
            border: `1px solid ${feature.color}30`,
          }}
        >
          {/* 头部 */}
          <div className="flex items-center gap-3 mb-5">
            <div 
              className="w-10 h-10 rounded-lg flex items-center justify-center"
              style={{ background: `${feature.color}20` }}
            >
              <Icon className="w-5 h-5" style={{ color: feature.color }} />
            </div>
            <h3 className="text-lg font-bold" style={{ color: feature.color }}>
              {feature.title}
            </h3>
          </div>

          {/* 详细特性 */}
          <ul className="space-y-3 flex-1">
            {feature.details.map((detail, i) => (
              <li key={i} className="flex items-start gap-3">
                <div 
                  className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
                  style={{ background: `${feature.color}20` }}
                >
                  <Sparkles className="w-3 h-3" style={{ color: feature.color }} />
                </div>
                <span className="text-sm text-gray-700">{detail}</span>
              </li>
            ))}
          </ul>

          {/* 底部统计 */}
          <div 
            className="mt-4 pt-4 border-t rounded-lg px-4 py-2"
            style={{ borderColor: `${feature.color}20`, background: `${feature.color}10` }}
          >
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">{feature.stat.label}</span>
              <span 
                className="text-xl font-bold"
                style={{ color: feature.color }}
              >
                {feature.stat.value}
              </span>
            </div>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
};

export const FeatureGrid = () => {
  return (
    <section className="py-24 relative overflow-hidden bg-white">
      {/* 背景装饰 */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-gray-200 to-transparent" />
        <div className="absolute bottom-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-gray-200 to-transparent" />
        
        {/* 浮动光点 */}
        <div className="absolute top-20 left-20 w-2 h-2 rounded-full bg-blue-400/30 animate-pulse" />
        <div className="absolute top-40 right-32 w-3 h-3 rounded-full bg-cyan-400/20 animate-pulse" style={{ animationDelay: '1s' }} />
        <div className="absolute bottom-32 left-1/3 w-2 h-2 rounded-full bg-violet-400/30 animate-pulse" style={{ animationDelay: '2s' }} />
      </div>

      <div className="landing-container relative z-10">
        {/* 标题 */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center max-w-3xl mx-auto mb-16"
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-blue-500/10 border border-blue-500/20 mb-6">
            <Sparkles className="w-4 h-4 text-blue-500" />
            <span className="text-sm text-blue-600 font-medium">核心特性</span>
          </div>
          
          <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
            为什么选择
            <span className="gradient-text"> GradeOS</span>
          </h2>
          
          <p className="text-lg text-gray-600">
            专为教育场景设计的AI批改系统，结合最新的多模态大模型和智能体技术，
            提供业界领先的批改体验
          </p>
        </motion.div>

        {/* 特性网格 */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, idx) => (
            <FeatureCard key={idx} feature={feature} index={idx} />
          ))}
        </div>

        {/* 底部CTA */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mt-16"
        >
          <div className="inline-flex items-center gap-4 p-6 rounded-2xl bg-gradient-to-r from-blue-50 to-cyan-50 border border-blue-100">
            <div className="text-left">
              <div className="text-sm text-gray-600 mb-1">准备好体验智能批改了？</div>
              <div className="text-lg font-semibold text-gray-900">立即开始免费试用</div>
            </div>
            <a 
              href="/console" 
              className="px-6 py-3 rounded-xl bg-blue-600 text-white font-semibold hover:bg-blue-700 transition-colors flex items-center gap-2"
            >
              <span>开始体验</span>
              <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </motion.div>
      </div>

      <style jsx>{`
        .perspective-1000 {
          perspective: 1000px;
        }
        .preserve-3d {
          transform-style: preserve-3d;
        }
        .backface-hidden {
          backface-visibility: hidden;
          -webkit-backface-visibility: hidden;
        }
      `}</style>
    </section>
  );
};

export default FeatureGrid;
