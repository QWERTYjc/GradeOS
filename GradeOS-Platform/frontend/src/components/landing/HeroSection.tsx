import React from 'react';
import { ArrowRight, Terminal, Sparkles, Zap } from 'lucide-react';
import Link from 'next/link';
import { motion } from 'framer-motion';

export const HeroSection = () => {
  return (
    <section className="relative min-h-[90vh] flex items-center justify-center overflow-hidden bg-slate-950">
      {/* Background Elements */}
      <div className="absolute inset-0 pointer-events-none">
        {/* 网格 */}
        <div 
          className="absolute inset-0 opacity-20"
          style={{
            backgroundImage: `
              linear-gradient(to right, rgba(59, 130, 246, 0.1) 1px, transparent 1px),
              linear-gradient(to bottom, rgba(59, 130, 246, 0.1) 1px, transparent 1px)
            `,
            backgroundSize: '80px 80px'
          }}
        />
        
        {/* 发光球 */}
        <motion.div
          animate={{
            scale: [1, 1.2, 1],
            opacity: [0.3, 0.5, 0.3]
          }}
          transition={{ duration: 10, repeat: Infinity }}
          className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-500/30 rounded-full blur-[120px]"
        />
        <motion.div
          animate={{
            scale: [1, 1.3, 1],
            opacity: [0.2, 0.4, 0.2]
          }}
          transition={{ duration: 12, repeat: Infinity, delay: 3 }}
          className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-cyan-500/30 rounded-full blur-[100px]"
        />
      </div>

      <div className="landing-container relative z-10 grid lg:grid-cols-2 gap-12 items-center">
        {/* Left Content */}
        <div className="space-y-8 text-center lg:text-left">
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-blue-500/10 border border-blue-500/20"
          >
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
            </span>
            <span className="text-sm font-semibold tracking-wider text-blue-400 uppercase">AI Grading System</span>
          </motion.div>

          <motion.h1 
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="text-5xl lg:text-7xl font-bold leading-tight text-white"
          >
            智能批改
            <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-cyan-400 to-teal-400">
              新范式
            </span>
          </motion.h1>

          <motion.p 
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="text-lg text-slate-400 max-w-xl mx-auto lg:mx-0 leading-relaxed"
          >
            基于 Gemini 3.0 Vision 和 LangGraph 工作流编排，
            实现试卷自动识别、智能批改、结果导出的全流程自动化
          </motion.p>

          <motion.div 
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="flex flex-col sm:flex-row items-center gap-4 justify-center lg:justify-start"
          >
            <Link href="/console" className="group px-8 py-4 rounded-full bg-gradient-to-r from-blue-600 to-cyan-500 text-white font-semibold transition-all hover:shadow-lg hover:shadow-blue-500/30 hover:scale-105 flex items-center gap-2">
              <span>立即体验</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Link>

            <Link href="#workflow" className="px-8 py-4 rounded-full border border-slate-700 text-slate-300 font-semibold hover:border-blue-500/50 hover:text-white transition-all flex items-center gap-2">
              <Terminal className="w-4 h-4" />
              <span>了解工作流</span>
            </Link>
          </motion.div>

          {/* 技术标签 */}
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.5 }}
            className="pt-8 flex flex-wrap items-center gap-3 justify-center lg:justify-start"
          >
            {['LangGraph', 'Gemini 3.0', 'Vision AI', '多智能体'].map((tag, i) => (
              <span 
                key={i}
                className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-400"
              >
                {tag}
              </span>
            ))}
          </motion.div>
        </div>

        {/* Right Visual - AI Grading Preview */}
        <motion.div 
          initial={{ opacity: 0, x: 50 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.8, delay: 0.3 }}
          className="relative hidden lg:block"
        >
          <div className="relative">
            {/* 主面板 */}
            <motion.div
              animate={{ y: [0, -10, 0] }}
              transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
              className="relative bg-slate-900/80 backdrop-blur-xl border border-slate-800 rounded-2xl p-6 shadow-2xl"
            >
              {/* 标题栏 */}
              <div className="flex items-center gap-3 mb-6 pb-4 border-b border-slate-800">
                <div className="flex gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-500/80" />
                  <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
                  <div className="w-3 h-3 rounded-full bg-green-500/80" />
                </div>
                <div className="flex items-center gap-2 px-3 py-1 rounded-md bg-slate-800/50">
                  <Sparkles className="w-3 h-3 text-blue-400" />
                  <span className="text-xs text-slate-400 font-mono">AI Grading Console</span>
                </div>
              </div>

              {/* 内容 */}
              <div className="space-y-4 font-mono text-sm">
                <div className="flex items-center gap-3 text-slate-300">
                  <span className="text-blue-400">➜</span>
                  <span className="text-cyan-400">gradeos</span>
                  <span className="text-slate-400">batch submit</span>
                  <span className="text-amber-400">--files=midterm.pdf</span>
                </div>
                
                <div className="pl-6 space-y-2">
                  <motion.div 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.5 }}
                    className="flex items-center gap-2 text-emerald-400/90"
                  >
                    <span className="text-xs">✓</span>
                    <span>已识别 32 份试卷，共 128 页</span>
                  </motion.div>
                  
                  <motion.div 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.8 }}
                    className="flex items-center gap-2 text-blue-400/90"
                  >
                    <Zap className="w-3 h-3" />
                    <span>评分标准解析完成：10 道题目</span>
                  </motion.div>
                  
                  <motion.div 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 1.1 }}
                    className="flex items-center gap-2 text-purple-400/90"
                  >
                    <span className="animate-pulse">●</span>
                    <span>正在批改：学生 15/32...</span>
                  </motion.div>
                </div>

                {/* 进度条 */}
                <div className="pt-4">
                  <div className="flex justify-between text-xs text-slate-500 mb-2">
                    <span>Batch Progress</span>
                    <span>47%</span>
                  </div>
                  <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: '47%' }}
                      transition={{ duration: 2, delay: 0.5 }}
                      className="h-full bg-gradient-to-r from-blue-500 to-cyan-500 rounded-full"
                    />
                  </div>
                </div>
              </div>
            </motion.div>

            {/* 浮动卡片 - 最近完成 */}
            <motion.div
              animate={{ y: [0, -15, 0] }}
              transition={{ duration: 5, repeat: Infinity, ease: "easeInOut", delay: 0.5 }}
              className="absolute -right-8 -bottom-4 p-4 bg-slate-900/90 backdrop-blur-xl border border-slate-800 rounded-xl shadow-xl"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center text-white font-bold">
                  A
                </div>
                <div>
                  <div className="text-xs text-slate-500">最新批改</div>
                  <div className="text-sm font-semibold text-white">张三 - 92分</div>
                </div>
              </div>
            </motion.div>

            {/* 浮动卡片 - 系统状态 */}
            <motion.div
              animate={{ y: [0, 10, 0] }}
              transition={{ duration: 4, repeat: Infinity, ease: "easeInOut", delay: 1 }}
              className="absolute -left-8 top-1/2 p-3 bg-slate-900/90 backdrop-blur-xl border border-slate-800 rounded-xl shadow-xl"
            >
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-xs font-mono text-emerald-400">System Online</span>
              </div>
            </motion.div>
          </div>
        </motion.div>
      </div>
    </section>
  );
};

export default HeroSection;
