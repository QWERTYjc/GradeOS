'use client';

import React, { useRef, useState, useEffect } from 'react';
import { motion, useScroll, useTransform, useInView } from 'framer-motion';
import {
  FileUp,
  ScanLine,
  BrainCircuit,
  CheckCircle2,
  Zap,
  ChevronLeft,
  ChevronRight,
  Eye,
  FileText,
  Users,
  Clock,
  BarChart3
} from 'lucide-react';

// 工作流阶段详细定义
const workflowStages = [
  {
    id: 'upload',
    step: 1,
    title: '智能接收',
    subtitle: 'Smart Intake',
    description: '支持多种格式批量上传，自动识别试卷结构',
    icon: FileUp,
    color: '#3b82f6',
    gradient: 'from-blue-500 to-blue-600',
    features: ['批量文件并行处理', '自动文件完整性校验', '智能页面分割检测']
  },
  {
    id: 'scan',
    step: 2,
    title: '图像预处理',
    subtitle: 'Image Preprocessing',
    description: '基于 Gemini 3.0 Vision 的图像增强与识别',
    icon: ScanLine,
    color: '#06b6d4',
    gradient: 'from-cyan-500 to-cyan-600',
    features: ['手写文字精准识别', '几何畸变自动校正', '数学公式结构化提取']
  },
  {
    id: 'rubric',
    step: 3,
    title: '评分标准解析',
    subtitle: 'Rubric Analysis',
    description: 'AI自动解析评分细则，建立评分框架',
    icon: FileText,
    color: '#8b5cf6',
    gradient: 'from-violet-500 to-violet-600',
    features: ['评分细则自动提取', '题目结构智能解析', '分值权重自动计算']
  },
  {
    id: 'grade',
    step: 4,
    title: 'AI智能批改',
    subtitle: 'AI Grading',
    description: '多智能体并行处理，逐题深度分析',
    icon: BrainCircuit,
    color: '#10b981',
    gradient: 'from-emerald-500 to-emerald-600',
    features: ['多智能体并行批改', '逐题评分理由生成', '置信度自动评估']
  },
  {
    id: 'review',
    step: 5,
    title: '结果审核',
    subtitle: 'Human Review',
    description: '低置信度结果自动标记，人工介入审核',
    icon: Eye,
    color: '#f59e0b',
    gradient: 'from-amber-500 to-amber-600',
    features: ['低置信度自动标记', '一键确认或修改', '审核历史记录']
  },
  {
    id: 'export',
    step: 6,
    title: '结果导出',
    subtitle: 'Export Results',
    description: '生成详细报告，支持多种格式导出',
    icon: Zap,
    color: '#ef4444',
    gradient: 'from-red-500 to-red-600',
    features: ['成绩单自动生成', '统计分析报表', '多格式一键导出']
  },
];

// 单个工作流卡片组件
const WorkflowCard = ({ stage, isActive, onClick }: {
  stage: typeof workflowStages[0];
  isActive: boolean;
  onClick: () => void;
}) => {
  const Icon = stage.icon;
  const cardRef = useRef(null);
  const isInView = useInView(cardRef, { once: true, margin: "-100px" });

  return (
    <motion.div
      ref={cardRef}
      initial={{ opacity: 0, y: 50 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.6 }}
      onClick={onClick}
      className={`relative flex-shrink-0 w-[280px] md:w-[320px] cursor-pointer group snap-center ${isActive ? 'z-10' : 'z-0'
        }`}
    >
      <motion.div
        animate={{
          scale: isActive ? 1.05 : 1,
          y: isActive ? -10 : 0,
        }}
        transition={{ type: "spring", stiffness: 300, damping: 30 }}
        className={`relative bg-white rounded-2xl p-6 border-2 transition-all duration-300 ${isActive
          ? `border-[${stage.color}] shadow-2xl`
          : 'border-gray-100 shadow-lg hover:border-gray-200'
          }`}
        style={{
          boxShadow: isActive ? `0 25px 50px -12px ${stage.color}20` : undefined
        }}
      >
        {/* 步骤编号 */}
        <div className="absolute -top-4 -right-4 w-12 h-12 rounded-full bg-gradient-to-br from-gray-900 to-gray-700 text-white flex items-center justify-center font-bold text-lg shadow-lg">
          {stage.step}
        </div>

        {/* 头部 */}
        <div className="flex items-start gap-4 mb-4">
          <div
            className="w-14 h-14 rounded-xl flex items-center justify-center transition-transform group-hover:scale-110"
            style={{ background: `${stage.color}15` }}
          >
            <Icon className="w-7 h-7" style={{ color: stage.color }} />
          </div>
          <div>
            <div className="text-xs font-medium text-gray-400 uppercase tracking-wider">
              {stage.subtitle}
            </div>
            <h3 className="text-xl font-bold text-gray-900">{stage.title}</h3>
          </div>
        </div>

        {/* 描述 */}
        <p className="text-gray-600 text-sm mb-4 leading-relaxed">
          {stage.description}
        </p>

        {/* 特性列表 */}
        <ul className="space-y-2 mb-4">
          {stage.features.map((feature, i) => (
            <li key={i} className="flex items-center gap-2 text-sm text-gray-500">
              <div
                className="w-1.5 h-1.5 rounded-full"
                style={{ background: stage.color }}
              />
              {feature}
            </li>
          ))}
        </ul>



        {/* 连接线 */}
        {stage.step < workflowStages.length && (
          <div className="absolute top-1/2 -right-8 w-8 h-0.5 bg-gradient-to-r from-gray-300 to-transparent hidden lg:block" />
        )}
      </motion.div>
    </motion.div>
  );
};



export const AIWorkflowVisualization = () => {
  const [activeStage, setActiveStage] = useState(0);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const sectionRef = useRef<HTMLDivElement>(null);
  const isInView = useInView(sectionRef, { once: true, margin: "-200px" });

  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ["start end", "end start"]
  });

  const backgroundY = useTransform(scrollYProgress, [0, 1], ["0%", "20%"]);

  const scrollToCard = (index: number) => {
    if (scrollContainerRef.current) {
      const cards = scrollContainerRef.current.children;
      if (cards[index]) {
        const card = cards[index] as HTMLElement;
        scrollContainerRef.current.scrollTo({
          left: card.offsetLeft - 50,
          behavior: 'smooth'
        });
      }
    }
    setActiveStage(index);
  };

  return (
    <section ref={sectionRef} className="py-24 relative overflow-hidden bg-gradient-to-b from-white via-blue-50/50 to-white">
      {/* 背景装饰 */}
      <motion.div
        className="absolute inset-0 pointer-events-none"
        style={{ y: backgroundY }}
      >
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-blue-200/30 rounded-full blur-[100px]" />
        <div className="absolute bottom-0 right-1/4 w-80 h-80 bg-cyan-200/20 rounded-full blur-[80px]" />
      </motion.div>

      <div className="landing-container relative z-10">
        {/* 标题区 */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          className="text-center max-w-3xl mx-auto mb-16"
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-blue-500/10 border border-blue-500/20 mb-6">
            <BrainCircuit className="w-4 h-4 text-blue-500" />
            <span className="text-sm text-blue-600 font-medium">AI Workflow</span>
          </div>

          <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
            智能批改
            <span className="gradient-text">全流程可视化</span>
          </h2>

          <p className="text-lg text-gray-600">
            从试卷上传到成绩导出，每一步都清晰可见。基于 LangGraph 的多智能体编排系统，
            让复杂的批改流程变得简单透明。
          </p>
        </motion.div>

        {/* 水平滚动工作流卡片 */}
        <div className="relative mb-12">
          {/* 滚动按钮 */}
          <button
            onClick={() => scrollToCard(Math.max(0, activeStage - 1))}
            className="absolute left-0 top-1/2 -translate-y-1/2 z-20 w-12 h-12 rounded-full bg-white shadow-lg border border-gray-200 flex items-center justify-center text-gray-600 hover:text-blue-600 hover:border-blue-300 transition-all hidden lg:flex"
          >
            <ChevronLeft className="w-6 h-6" />
          </button>

          <button
            onClick={() => scrollToCard(Math.min(workflowStages.length - 1, activeStage + 1))}
            className="absolute right-0 top-1/2 -translate-y-1/2 z-20 w-12 h-12 rounded-full bg-white shadow-lg border border-gray-200 flex items-center justify-center text-gray-600 hover:text-blue-600 hover:border-blue-300 transition-all hidden lg:flex"
          >
            <ChevronRight className="w-6 h-6" />
          </button>

          {/* 卡片容器 */}
          <div
            ref={scrollContainerRef}
            className="flex overflow-x-auto gap-6 px-4 lg:px-8 py-16 snap-x snap-mandatory scrollbar-hide w-full"
            style={{
              scrollbarWidth: 'none',
              msOverflowStyle: 'none'
            }}
          >
            {workflowStages.map((stage, index) => (
              <WorkflowCard
                key={stage.id}
                stage={stage}
                isActive={index === activeStage}
                onClick={() => setActiveStage(index)}
              />
            ))}
          </div>
        </div>



        {/* 阶段指示器 */}
        <div className="flex justify-center gap-2 mt-8">
          {workflowStages.map((_, index) => (
            <button
              key={index}
              onClick={() => scrollToCard(index)}
              className={`h-2 rounded-full transition-all duration-300 ${index === activeStage
                ? 'w-8 bg-blue-500'
                : 'w-2 bg-gray-300 hover:bg-gray-400'
                }`}
            />
          ))}
        </div>
      </div>
    </section>
  );
};

export default AIWorkflowVisualization;
