'use client';

import React, { useEffect, useRef, useState } from 'react';
import { motion, useScroll, useTransform, useSpring, useMotionValue } from 'framer-motion';
import { 
  FileUp, 
  ScanLine, 
  BrainCircuit, 
  CheckCircle2, 
  Zap,
  ArrowRight,
  Sparkles
} from 'lucide-react';

// AI批改工作流阶段定义
const workflowStages = [
  {
    id: 'intake',
    title: '智能接收',
    subtitle: 'Intake',
    description: '自动识别并接收多种格式的试卷文件，支持PDF、图片批量上传',
    icon: FileUp,
    color: 'from-blue-500 to-cyan-500',
    details: [
      '支持 PDF/JPG/PNG 多种格式',
      '批量文件并行处理',
      '自动文件完整性校验'
    ]
  },
  {
    id: 'preprocess',
    title: '图像预处理',
    subtitle: 'Preprocess',
    description: '图像增强、去噪、旋转校正，确保最佳识别效果',
    icon: ScanLine,
    color: 'from-cyan-500 to-teal-500',
    details: [
      '智能图像增强算法',
      '手写文字区域检测',
      '几何畸变自动校正'
    ]
  },
  {
    id: 'rubric_parse',
    title: '评分标准解析',
    subtitle: 'Rubric Parse',
    description: 'AI自动解析评分标准，提取题目结构和分值分布',
    icon: Sparkles,
    color: 'from-teal-500 to-emerald-500',
    details: [
      '自动识别评分细则',
      '题目结构智能解析',
      '分值权重自动计算'
    ]
  },
  {
    id: 'grade_batch',
    title: 'AI智能批改',
    subtitle: 'Grading',
    description: '多智能体并行批改，逐题分析并给出详细评分理由',
    icon: BrainCircuit,
    color: 'from-emerald-500 to-amber-500',
    details: [
      '多智能体并行处理',
      '逐题深度分析',
      '评分理由自动生成'
    ]
  },
  {
    id: 'review',
    title: '结果审核',
    subtitle: 'Review',
    description: '人工介入审核低置信度结果，确保评分准确性',
    icon: CheckCircle2,
    color: 'from-amber-500 to-orange-500',
    details: [
      '低置信度自动标记',
      '人工介入审核界面',
      '一键确认或修改分数'
    ]
  },
  {
    id: 'export',
    title: '结果导出',
    subtitle: 'Export',
    description: '生成详细的成绩报告和分析统计，支持多种格式导出',
    icon: Zap,
    color: 'from-orange-500 to-red-500',
    details: [
      '成绩单自动生成',
      '统计分析报表',
      'Excel/PDF 格式导出'
    ]
  }
];

// 粒子背景组件
const ParticleBackground = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    let animationId: number;
    let particles: Array<{
      x: number;
      y: number;
      vx: number;
      vy: number;
      size: number;
      opacity: number;
    }> = [];
    
    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    
    const createParticles = () => {
      particles = [];
      for (let i = 0; i < 50; i++) {
        particles.push({
          x: Math.random() * canvas.width,
          y: Math.random() * canvas.height,
          vx: (Math.random() - 0.5) * 0.5,
          vy: (Math.random() - 0.5) * 0.5,
          size: Math.random() * 2 + 1,
          opacity: Math.random() * 0.5 + 0.2
        });
      }
    };
    
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      
      particles.forEach((p, i) => {
        p.x += p.vx;
        p.y += p.vy;
        
        if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
        if (p.y < 0 || p.y > canvas.height) p.vy *= -1;
        
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(59, 130, 246, ${p.opacity})`;
        ctx.fill();
        
        // 连接线
        particles.slice(i + 1).forEach(p2 => {
          const dx = p.x - p2.x;
          const dy = p.y - p2.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          
          if (dist < 150) {
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.strokeStyle = `rgba(59, 130, 246, ${0.1 * (1 - dist / 150)})`;
            ctx.stroke();
          }
        });
      });
      
      animationId = requestAnimationFrame(draw);
    };
    
    resize();
    createParticles();
    draw();
    
    window.addEventListener('resize', () => {
      resize();
      createParticles();
    });
    
    return () => {
      cancelAnimationFrame(animationId);
    };
  }, []);
  
  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 pointer-events-none"
      style={{ opacity: 0.6 }}
    />
  );
};

// 工作流程节点组件
const WorkflowNode = ({ 
  stage, 
  index, 
  progress 
}: { 
  stage: typeof workflowStages[0]; 
  index: number;
  progress: number;
}) => {
  const nodeRef = useRef<HTMLDivElement>(null);
  const Icon = stage.icon;
  const isActive = progress >= index / workflowStages.length;
  const isCompleted = progress >= (index + 1) / workflowStages.length;
  
  // 对角线偏移计算
  const diagonalOffset = index * 80;
  
  return (
    <motion.div
      ref={nodeRef}
      initial={{ opacity: 0, x: -100, y: 50, rotateY: -30 }}
      whileInView={{ opacity: 1, x: 0, y: 0, rotateY: 0 }}
      viewport={{ once: true, margin: "-100px" }}
      transition={{ 
        duration: 0.8, 
        delay: index * 0.15,
        type: "spring",
        stiffness: 100
      }}
      style={{
        marginLeft: `${diagonalOffset}px`,
      }}
      className="relative"
    >
      {/* 连接线 */}
      {index < workflowStages.length - 1 && (
        <motion.div
          className="absolute top-1/2 left-full w-32 h-0.5 bg-gradient-to-r from-blue-500/50 to-transparent"
          initial={{ scaleX: 0 }}
          whileInView={{ scaleX: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: index * 0.15 + 0.3 }}
          style={{ 
            transformOrigin: 'left',
            transform: 'rotate(25deg)',
            marginTop: '60px',
            marginLeft: '20px'
          }}
        />
      )}
      
      {/* 节点卡片 */}
      <motion.div
        whileHover={{ 
          scale: 1.05, 
          rotateX: 5,
          z: 50,
          transition: { duration: 0.3 }
        }}
        className={`
          relative w-[380px] p-6 rounded-2xl backdrop-blur-xl
          border transition-all duration-500
          ${isCompleted 
            ? 'border-emerald-500/50 bg-emerald-500/10' 
            : isActive 
              ? 'border-blue-500/50 bg-blue-500/10 shadow-[0_0_30px_rgba(59,130,246,0.3)]' 
              : 'border-slate-700/50 bg-slate-900/40'
          }
        `}
        style={{
          transformStyle: 'preserve-3d',
          perspective: '1000px'
        }}
      >
        {/* 状态指示器 */}
        <div className="absolute -left-3 top-1/2 -translate-y-1/2">
          <motion.div
            animate={isActive ? {
              scale: [1, 1.2, 1],
              opacity: [0.5, 1, 0.5]
            } : {}}
            transition={{ duration: 2, repeat: Infinity }}
            className={`
              w-6 h-6 rounded-full border-2 flex items-center justify-center
              ${isCompleted 
                ? 'bg-emerald-500 border-emerald-400' 
                : isActive 
                  ? 'bg-blue-500 border-blue-400' 
                  : 'bg-slate-700 border-slate-600'
              }
            `}
          >
            {isCompleted && <CheckCircle2 className="w-4 h-4 text-white" />}
            {isActive && !isCompleted && <motion.div 
              className="w-2 h-2 bg-white rounded-full"
              animate={{ scale: [1, 1.5, 1] }}
              transition={{ duration: 1, repeat: Infinity }}
            />}
          </motion.div>
        </div>
        
        {/* 头部 */}
        <div className="flex items-start gap-4 mb-4">
          <motion.div
            whileHover={{ rotate: 360 }}
            transition={{ duration: 0.6 }}
            className={`
              w-14 h-14 rounded-xl flex items-center justify-center
              bg-gradient-to-br ${stage.color}
              shadow-lg
            `}
          >
            <Icon className="w-7 h-7 text-white" />
          </motion.div>
          
          <div className="flex-1">
            <div className="text-xs font-mono text-slate-500 uppercase tracking-wider mb-1">
              {stage.subtitle}
            </div>
            <h3 className="text-xl font-bold text-white">{stage.title}</h3>
          </div>
          
          {/* 序号 */}
          <div className="text-4xl font-bold text-slate-700/50 font-mono">
            {String(index + 1).padStart(2, '0')}
          </div>
        </div>
        
        {/* 描述 */}
        <p className="text-slate-400 text-sm leading-relaxed mb-4">
          {stage.description}
        </p>
        
        {/* 详情列表 */}
        <ul className="space-y-2">
          {stage.details.map((detail, i) => (
            <motion.li
              key={i}
              initial={{ opacity: 0, x: -10 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.15 + i * 0.1 + 0.3 }}
              className="flex items-center gap-2 text-xs text-slate-500"
            >
              <div className={`w-1.5 h-1.5 rounded-full bg-gradient-to-r ${stage.color}`} />
              {detail}
            </motion.li>
          ))}
        </ul>
        
        {/* 进度条 */}
        {isActive && !isCompleted && (
          <motion.div
            className="absolute bottom-0 left-0 right-0 h-1 bg-slate-800 rounded-b-2xl overflow-hidden"
          >
            <motion.div
              className={`h-full bg-gradient-to-r ${stage.color}`}
              animate={{ x: ["-100%", "100%"] }}
              transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
            />
          </motion.div>
        )}
      </motion.div>
    </motion.div>
  );
};

// 主组件
export const AIWorkflowShowcase = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [currentStage, setCurrentStage] = useState(0);
  
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"]
  });
  
  const smoothProgress = useSpring(scrollYProgress, {
    stiffness: 100,
    damping: 30,
    restDelta: 0.001
  });
  
  // 视差效果
  const backgroundY = useTransform(smoothProgress, [0, 1], ["0%", "30%"]);
  const textY = useTransform(smoothProgress, [0, 1], ["0%", "-20%"]);
  
  // 计算当前阶段
  useEffect(() => {
    const unsubscribe = smoothProgress.on("change", (v) => {
      const stage = Math.floor(v * workflowStages.length);
      setCurrentStage(Math.min(stage, workflowStages.length - 1));
    });
    return () => unsubscribe();
  }, [smoothProgress]);
  
  return (
    <section 
      ref={containerRef}
      className="relative min-h-[300vh] bg-slate-950"
    >
      {/* 固定内容区 */}
      <div className="sticky top-0 h-screen overflow-hidden">
        {/* 动态背景 */}
        <motion.div 
          className="absolute inset-0"
          style={{ y: backgroundY }}
        >
          {/* 渐变背景 */}
          <div className="absolute inset-0 bg-gradient-to-br from-slate-950 via-slate-900 to-blue-950" />
          
          {/* 网格 */}
          <div 
            className="absolute inset-0 opacity-20"
            style={{
              backgroundImage: `
                linear-gradient(to right, rgba(59, 130, 246, 0.1) 1px, transparent 1px),
                linear-gradient(to bottom, rgba(59, 130, 246, 0.1) 1px, transparent 1px)
              `,
              backgroundSize: '60px 60px'
            }}
          />
          
          {/* 粒子效果 */}
          <ParticleBackground />
          
          {/* 发光球体 */}
          <motion.div
            animate={{
              scale: [1, 1.2, 1],
              opacity: [0.3, 0.5, 0.3]
            }}
            transition={{ duration: 8, repeat: Infinity }}
            className="absolute top-1/4 right-1/4 w-96 h-96 bg-blue-500/20 rounded-full blur-[100px]"
          />
          <motion.div
            animate={{
              scale: [1, 1.3, 1],
              opacity: [0.2, 0.4, 0.2]
            }}
            transition={{ duration: 10, repeat: Infinity, delay: 2 }}
            className="absolute bottom-1/4 left-1/4 w-80 h-80 bg-cyan-500/20 rounded-full blur-[80px]"
          />
        </motion.div>
        
        {/* 内容 */}
        <div className="relative z-10 h-full flex">
          {/* 左侧标题区 */}
          <motion.div 
            className="w-1/3 h-full flex flex-col justify-center px-12"
            style={{ y: textY }}
          >
            <motion.div
              initial={{ opacity: 0, x: -50 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              className="space-y-6"
            >
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-blue-500/10 border border-blue-500/20">
                <Sparkles className="w-4 h-4 text-blue-400" />
                <span className="text-sm text-blue-400 font-medium">AI-Powered</span>
              </div>
              
              <h2 className="text-5xl font-bold text-white leading-tight">
                智能批改
                <br />
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-400">
                  工作流
                </span>
              </h2>
              
              <p className="text-slate-400 text-lg leading-relaxed">
                基于 LangGraph 的多智能体编排系统，
                实现从试卷接收到结果导出的全流程自动化
              </p>
              
              {/* 阶段指示器 */}
              <div className="flex items-center gap-3 pt-4">
                {workflowStages.map((_, i) => (
                  <motion.div
                    key={i}
                    className={`h-1 rounded-full transition-all duration-300 ${
                      i <= currentStage 
                        ? 'w-8 bg-blue-500' 
                        : 'w-2 bg-slate-700'
                    }`}
                  />
                ))}
              </div>
              
              <div className="text-sm text-slate-500">
                阶段 {currentStage + 1} / {workflowStages.length}
              </div>
            </motion.div>
          </motion.div>
          
          {/* 右侧工作流展示 */}
          <div className="w-2/3 h-full flex items-center overflow-hidden">
            <motion.div 
              className="pl-20 pr-10"
              style={{
                y: useTransform(smoothProgress, [0, 1], [0, -200])
              }}
            >
              <div className="space-y-12 py-20">
                {workflowStages.map((stage, index) => (
                  <WorkflowNode
                    key={stage.id}
                    stage={stage}
                    index={index}
                    progress={smoothProgress.get()}
                  />
                ))}
              </div>
            </motion.div>
          </div>
        </div>
        
        {/* 滚动提示 */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1 }}
          className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2"
        >
          <span className="text-xs text-slate-500 uppercase tracking-widest">Scroll</span>
          <motion.div
            animate={{ y: [0, 8, 0] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          >
            <ArrowRight className="w-5 h-5 text-slate-500 rotate-90" />
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
};

export default AIWorkflowShowcase;
