'use client';

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  ArrowRight, 
  Terminal, 
  Sparkles, 
  Zap,
  FileUp,
  ScanLine,
  BrainCircuit,
  CheckCircle2,
  Trophy,
  Play,
  Pause,
  RotateCcw
} from 'lucide-react';
import Link from 'next/link';

// AI批改工作流阶段
const workflowStages = [
  { id: 'upload', label: '试卷上传', icon: FileUp, color: 'text-blue-500', bg: 'bg-blue-500/10' },
  { id: 'scan', label: '图像识别', icon: ScanLine, color: 'text-cyan-500', bg: 'bg-cyan-500/10' },
  { id: 'ai', label: 'AI批改', icon: BrainCircuit, color: 'text-indigo-500', bg: 'bg-indigo-500/10' },
  { id: 'review', label: '结果审核', icon: CheckCircle2, color: 'text-emerald-500', bg: 'bg-emerald-500/10' },
  { id: 'export', label: '成绩导出', icon: Trophy, color: 'text-amber-500', bg: 'bg-amber-500/10' },
];

// 模拟控制台日志
const consoleLogs = [
  { type: 'info', text: 'Initializing GradeOS Console v3.0...', time: '09:23:14' },
  { type: 'success', text: '✓ Connected to Gemini 3.0 Vision API', time: '09:23:15' },
  { type: 'info', text: 'Loading rubric: midterm_math_2024.pdf', time: '09:23:16' },
  { type: 'success', text: '✓ Rubric parsed: 10 questions, 100 points', time: '09:23:18' },
  { type: 'processing', text: '▶ Processing batch: 32 students', time: '09:23:20' },
  { type: 'progress', text: 'Grading student 15/32...', time: '09:24:45' },
  { type: 'success', text: '✓ Batch completed! Avg: 78.5/100', time: '09:26:12' },
];

export const HeroSection = () => {
  const [activeStage, setActiveStage] = useState(0);
  const [isPlaying, setIsPlaying] = useState(true);
  const [logs, setLogs] = useState<string[]>([]);
  const [progress, setProgress] = useState(0);
  const [showScore, setShowScore] = useState(false);

  // 工作流动画循环
  useEffect(() => {
    if (!isPlaying) return;
    
    const interval = setInterval(() => {
      setActiveStage((prev) => {
        const next = (prev + 1) % workflowStages.length;
        return next;
      });
    }, 2000);

    return () => clearInterval(interval);
  }, [isPlaying]);

  // 进度条动画
  useEffect(() => {
    if (!isPlaying) return;
    
    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          setShowScore(true);
          setTimeout(() => {
            setShowScore(false);
            setProgress(0);
          }, 2000);
          return 100;
        }
        return prev + 2;
      });
    }, 100);

    return () => clearInterval(interval);
  }, [isPlaying]);

  // 打字机效果日志
  useEffect(() => {
    let currentLogIndex = 0;
    let currentCharIndex = 0;
    
    const typeLog = () => {
      if (currentLogIndex >= consoleLogs.length) {
        setTimeout(() => {
          setLogs([]);
          currentLogIndex = 0;
          typeLog();
        }, 3000);
        return;
      }

      const log = consoleLogs[currentLogIndex];
      
      if (currentCharIndex === 0) {
        setLogs(prev => [...prev, '']);
      }

      if (currentCharIndex < log.text.length) {
        setLogs(prev => {
          const newLogs = [...prev];
          newLogs[newLogs.length - 1] = log.text.slice(0, currentCharIndex + 1);
          return newLogs;
        });
        currentCharIndex++;
        setTimeout(typeLog, 30);
      } else {
        currentCharIndex = 0;
        currentLogIndex++;
        setTimeout(typeLog, 500);
      }
    };

    if (isPlaying) {
      typeLog();
    }

    return () => {
      setLogs([]);
    };
  }, [isPlaying]);

  const getLogColor = (log: string) => {
    if (log.includes('✓')) return 'text-emerald-400';
    if (log.includes('▶')) return 'text-blue-400';
    if (log.includes('Processing')) return 'text-cyan-400';
    if (log.includes('completed')) return 'text-amber-400';
    return 'text-slate-400';
  };

  return (
    <section className="hero-section">
      {/* 背景网格 */}
      <div className="hero-grid" />
      
      {/* 浮动光球 */}
      <div className="hero-orb hero-orb-1" />
      <div className="hero-orb hero-orb-2" />

      <div className="landing-container relative z-10 py-20 lg:py-0 min-h-screen flex items-center">
        <div className="grid lg:grid-cols-2 gap-12 lg:gap-20 items-center w-full">
          {/* 左侧内容 */}
          <div className="space-y-8">
            {/* 标签 */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-blue-500/10 border border-blue-500/20"
            >
              <div className="pulse-dot" />
              <span className="text-sm font-medium text-blue-600">AI-Powered Grading System</span>
            </motion.div>

            {/* 标题 */}
            <motion.h1
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1 }}
              className="text-5xl lg:text-6xl xl:text-7xl font-bold text-gray-900 leading-tight"
            >
              智能批改
              <br />
              <span className="gradient-text-animated">从此可视化</span>
            </motion.h1>

            {/* 描述 */}
            <motion.p
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
              className="text-lg text-gray-600 max-w-xl leading-relaxed"
            >
              不只是打分，而是完整的批改控制台。实时追踪每一次识别、每一次评分、
              每一次修正的来龙去脉，让AI批改过程全透明。
            </motion.p>

            {/* CTA按钮 */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.3 }}
              className="flex flex-col sm:flex-row items-center gap-4"
            >
              <Link 
                href="/console" 
                className="btn-primary group flex items-center gap-2"
              >
                <span>开始体验</span>
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </Link>
              
              <button 
                onClick={() => setIsPlaying(!isPlaying)}
                className="btn-secondary flex items-center gap-2"
              >
                {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                <span>{isPlaying ? '暂停演示' : '播放演示'}</span>
              </button>
            </motion.div>

            {/* 技术标签 */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.6, delay: 0.5 }}
              className="flex flex-wrap items-center gap-3 pt-4"
            >
              {['Gemini 3.0', 'LangGraph', 'Vision AI', '多智能体'].map((tag, i) => (
                <span 
                  key={i}
                  className="px-3 py-1.5 rounded-lg bg-white border border-gray-200 text-xs text-gray-600 shadow-sm"
                >
                  {tag}
                </span>
              ))}
            </motion.div>

            {/* 统计数据 */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.6 }}
              className="grid grid-cols-3 gap-6 pt-8"
            >
              {[
                { value: '90s', label: '平均批改' },
                { value: '98%', label: '准确率' },
                { value: '32+', label: '并行处理' },
              ].map((stat, i) => (
                <div key={i} className="text-center sm:text-left">
                  <div className="text-2xl sm:text-3xl font-bold text-gray-900">{stat.value}</div>
                  <div className="text-sm text-gray-500">{stat.label}</div>
                </div>
              ))}
            </motion.div>
          </div>

          {/* 右侧 - 控制台预览 */}
          <motion.div
            initial={{ opacity: 0, x: 50 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, delay: 0.3 }}
            className="relative"
          >
            {/* 主控制台窗口 */}
            <div className="console-preview rounded-2xl p-6 relative overflow-hidden">
              {/* 扫描线效果 */}
              <div className="scan-line" />
              
              {/* 窗口标题栏 */}
              <div className="flex items-center justify-between mb-6 border-b border-slate-700/50 pb-4">
                <div className="flex items-center gap-3">
                  <div className="flex gap-2">
                    <div className="w-3 h-3 rounded-full bg-red-500/80" />
                    <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
                    <div className="w-3 h-3 rounded-full bg-green-500/80" />
                  </div>
                  <span className="text-slate-400 text-sm font-mono ml-3">GradeOS Console</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  <span className="text-xs text-emerald-400 font-mono">LIVE</span>
                </div>
              </div>

              {/* 工作流阶段指示器 */}
              <div className="flex items-center justify-between mb-6">
                {workflowStages.map((stage, index) => {
                  const Icon = stage.icon;
                  const isActive = index === activeStage;
                  const isCompleted = index < activeStage;
                  
                  return (
                    <motion.div
                      key={stage.id}
                      className="flex flex-col items-center gap-2"
                      animate={{
                        scale: isActive ? 1.1 : 1,
                        opacity: isActive || isCompleted ? 1 : 0.5,
                      }}
                    >
                      <div className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-300 ${
                        isActive 
                          ? `${stage.bg} ${stage.color} ring-2 ring-offset-2 ring-offset-slate-900 ring-current` 
                          : isCompleted 
                            ? 'bg-emerald-500/20 text-emerald-400' 
                            : 'bg-slate-800 text-slate-500'
                      }`}>
                        <Icon className="w-5 h-5" />
                      </div>
                      <span className={`text-xs ${isActive ? stage.color : 'text-slate-500'}`}>
                        {stage.label}
                      </span>
                    </motion.div>
                  );
                })}
              </div>

              {/* 进度条 */}
              <div className="mb-6">
                <div className="flex justify-between text-xs text-slate-400 mb-2">
                  <span>Processing</span>
                  <span>{progress}%</span>
                </div>
                <div className="progress-bar h-2">
                  <motion.div 
                    className="progress-bar-fill"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>

              {/* 控制台日志 */}
              <div className="bg-slate-900/50 rounded-lg p-4 h-48 overflow-hidden font-mono text-xs">
                <div className="space-y-1">
                  {logs.map((log, i) => (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      className={`${getLogColor(log)}`}
                    >
                      <span className="text-slate-600 mr-2">[{consoleLogs[i]?.time || '00:00:00'}]</span>
                      {log}
                      {i === logs.length - 1 && <span className="writing-cursor" />}
                    </motion.div>
                  ))}
                </div>
              </div>

              {/* 分数飞入动画 */}
              <AnimatePresence>
                {showScore && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.5, y: 20 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 1.2, y: -20 }}
                    className="absolute inset-0 flex items-center justify-center bg-slate-900/80 backdrop-blur-sm"
                  >
                    <div className="text-center">
                      <div className="text-6xl font-bold gradient-text mb-2">92</div>
                      <div className="text-slate-400 text-sm">Average Score</div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* 浮动装饰卡片 */}
            <motion.div
              animate={{ y: [0, -10, 0] }}
              transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
              className="absolute -right-4 -bottom-4 glass-card rounded-xl p-4 shadow-xl"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center text-white font-bold">
                  A
                </div>
                <div>
                  <div className="text-xs text-gray-500">最新完成</div>
                  <div className="text-sm font-semibold text-gray-900">张三 - 95分</div>
                </div>
              </div>
            </motion.div>

            {/* 系统状态卡片 */}
            <motion.div
              animate={{ y: [0, 10, 0] }}
              transition={{ duration: 3, repeat: Infinity, ease: "easeInOut", delay: 0.5 }}
              className="absolute -left-4 top-1/2 glass-card rounded-lg px-4 py-2 shadow-xl"
            >
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-xs font-medium text-gray-600">System Online</span>
              </div>
            </motion.div>
          </motion.div>
        </div>
      </div>

      {/* 滚动指示器 */}
      <div className="scroll-indicator">
        <span>SCROLL</span>
      </div>
    </section>
  );
};

export default HeroSection;
