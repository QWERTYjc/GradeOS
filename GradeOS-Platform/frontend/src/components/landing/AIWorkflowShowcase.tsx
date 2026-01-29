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
    stats: { label: '支持格式', value: 'PDF/JPG/PNG' },
    features: ['批量文件并行处理', '自动文件完整性校验', '智能页面分割检测'],
    preview: {
      title: '试卷上传中...',
      items: [
        { name: '期中考试_数学_A卷.pdf', status: 'completed', progress: 100 },
        { name: '期中考试_数学_B卷.pdf', status: 'processing', progress: 67 },
        { name: '答题卡_001.jpg', status: 'pending', progress: 0 },
      ]
    }
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
    stats: { label: '识别精度', value: '99.2%' },
    features: ['手写文字精准识别', '几何畸变自动校正', '数学公式结构化提取'],
    preview: {
      title: '正在识别...',
      scanning: true,
      detectedText: ['解：设x为未知数', '∵ a² + b² = c²', '∴ x = 5']
    }
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
    stats: { label: '解析速度', value: '< 3s' },
    features: ['评分细则自动提取', '题目结构智能解析', '分值权重自动计算'],
    preview: {
      title: '评分标准已解析',
      rubric: [
        { q: 'Q1', points: 10, criteria: '解题思路清晰' },
        { q: 'Q2', points: 15, criteria: '计算过程完整' },
        { q: 'Q3', points: 20, criteria: '答案准确无误' },
      ]
    }
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
    stats: { label: '平均用时', value: '90s/份' },
    features: ['多智能体并行批改', '逐题评分理由生成', '置信度自动评估'],
    preview: {
      title: '批改中...',
      workers: [
        { id: 1, status: 'grading', student: '张三', progress: 80 },
        { id: 2, status: 'reviewing', student: '李四', progress: 100 },
        { id: 3, status: 'grading', student: '王五', progress: 45 },
      ]
    }
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
    stats: { label: '待审核', value: '12项' },
    features: ['低置信度自动标记', '一键确认或修改', '审核历史记录'],
    preview: {
      title: '待审核项目',
      flagged: [
        { student: '赵六', question: 'Q2', confidence: 0.65, reason: '步骤不完整' },
        { student: '钱七', question: 'Q5', confidence: 0.72, reason: '答案模糊' },
      ]
    }
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
    stats: { label: '导出格式', value: 'Excel/PDF' },
    features: ['成绩单自动生成', '统计分析报表', '多格式一键导出'],
    preview: {
      title: '成绩单预览',
      stats: { avg: 78.5, max: 98, min: 52, count: 32 },
      topStudents: ['张三 - 98', '李四 - 95', '王五 - 92']
    }
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
      className={`relative flex-shrink-0 w-[280px] md:w-[320px] cursor-pointer group ${isActive ? 'z-10' : 'z-0'
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

        {/* 统计 */}
        <div
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium"
          style={{ background: `${stage.color}10`, color: stage.color }}
        >
          <BarChart3 className="w-4 h-4" />
          <span>{stage.stats.label}: {stage.stats.value}</span>
        </div>

        {/* 连接线 */}
        {stage.step < workflowStages.length && (
          <div className="absolute top-1/2 -right-8 w-8 h-0.5 bg-gradient-to-r from-gray-300 to-transparent hidden lg:block" />
        )}
      </motion.div>
    </motion.div>
  );
};

// 预览面板组件
const PreviewPanel = ({ stage }: { stage: typeof workflowStages[0] }) => {
  return (
    <motion.div
      key={stage.id}
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.3 }}
      className="bg-white rounded-2xl border border-gray-200 shadow-xl overflow-hidden"
    >
      {/* 面板头部 */}
      <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ background: `${stage.color}15` }}
          >
            <stage.icon className="w-4 h-4" style={{ color: stage.color }} />
          </div>
          <span className="font-semibold text-gray-900">{stage.preview.title}</span>
        </div>
        <div className="flex gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-red-400" />
          <div className="w-2.5 h-2.5 rounded-full bg-yellow-400" />
          <div className="w-2.5 h-2.5 rounded-full bg-green-400" />
        </div>
      </div>

      {/* 面板内容 */}
      <div className="p-6">
        {stage.id === 'upload' && (
          <div className="space-y-3">
            {stage.preview.items?.map((item, i) => (
              <div key={i} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                <FileText className="w-5 h-5 text-gray-400" />
                <div className="flex-1">
                  <div className="text-sm text-gray-700">{item.name}</div>
                  <div className="progress-bar h-1.5 mt-2">
                    <div
                      className="progress-bar-fill transition-all duration-500"
                      style={{ width: `${item.progress}%` }}
                    />
                  </div>
                </div>
                <span className={`text-xs ${item.status === 'completed' ? 'text-emerald-500' :
                    item.status === 'processing' ? 'text-blue-500' : 'text-gray-400'
                  }`}>
                  {item.status === 'completed' ? '✓' : item.status === 'processing' ? '...' : '○'}
                </span>
              </div>
            ))}
          </div>
        )}

        {stage.id === 'scan' && (
          <div className="relative h-48 bg-gray-900 rounded-lg overflow-hidden">
            <div className="scan-line" />
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <ScanLine className="w-12 h-12 text-cyan-400 mx-auto mb-4 animate-pulse" />
                <p className="text-cyan-400 font-mono text-sm">正在扫描识别...</p>
              </div>
            </div>
            <div className="absolute bottom-4 left-4 right-4 space-y-1">
              {stage.preview.detectedText?.map((text, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.3 }}
                  className="text-xs font-mono text-emerald-400 bg-emerald-400/10 px-2 py-1 rounded"
                >
                  {text}
                </motion.div>
              ))}
            </div>
          </div>
        )}

        {stage.id === 'rubric' && (
          <div className="space-y-3">
            {stage.preview.rubric?.map((item, i) => (
              <div key={i} className="flex items-center justify-between p-3 bg-violet-50 rounded-lg border border-violet-100">
                <div className="flex items-center gap-3">
                  <span className="w-8 h-8 rounded-lg bg-violet-500 text-white flex items-center justify-center text-sm font-bold">
                    {item.q}
                  </span>
                  <span className="text-sm text-gray-700">{item.criteria}</span>
                </div>
                <span className="text-violet-600 font-semibold">{item.points}分</span>
              </div>
            ))}
          </div>
        )}

        {stage.id === 'grade' && (
          <div className="space-y-3">
            {stage.preview.workers?.map((worker) => (
              <div key={worker.id} className="p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center text-white text-xs font-bold">
                      W{worker.id}
                    </div>
                    <span className="text-sm text-gray-700">{worker.student}</span>
                  </div>
                  <span className={`text-xs ${worker.status === 'grading' ? 'text-emerald-500' : 'text-blue-500'
                    }`}>
                    {worker.status === 'grading' ? '批改中' : '审核中'}
                  </span>
                </div>
                <div className="progress-bar h-1.5">
                  <div
                    className="progress-bar-fill transition-all duration-1000"
                    style={{ width: `${worker.progress}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}

        {stage.id === 'review' && (
          <div className="space-y-3">
            {stage.preview.flagged?.map((item, i) => (
              <div key={i} className="p-3 bg-amber-50 rounded-lg border border-amber-200">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-gray-900">{item.student} - {item.question}</span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-amber-200 text-amber-800">
                    置信度 {(item.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                <p className="text-sm text-gray-600">{item.reason}</p>
              </div>
            ))}
          </div>
        )}

        {stage.id === 'export' && (
          <div className="space-y-4">
            <div className="grid grid-cols-4 gap-3">
              {[
                { label: '平均分', value: stage.preview.stats?.avg },
                { label: '最高分', value: stage.preview.stats?.max },
                { label: '最低分', value: stage.preview.stats?.min },
                { label: '人数', value: stage.preview.stats?.count },
              ].map((stat, i) => (
                <div key={i} className="text-center p-3 bg-red-50 rounded-lg">
                  <div className="text-lg font-bold text-red-600">{stat.value}</div>
                  <div className="text-xs text-gray-500">{stat.label}</div>
                </div>
              ))}
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <div className="text-sm font-medium text-gray-700 mb-2">前三名</div>
              <div className="space-y-1">
                {stage.preview.topStudents?.map((student, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    <span className="w-5 h-5 rounded-full bg-yellow-400 text-white flex items-center justify-center text-xs font-bold">
                      {i + 1}
                    </span>
                    <span className="text-gray-600">{student}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
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
            className="horizontal-scroll-section gap-6 px-4 lg:px-8 pb-4"
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

        {/* 预览面板 */}
        <div className="max-w-3xl mx-auto">
          <PreviewPanel stage={workflowStages[activeStage]} />
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
