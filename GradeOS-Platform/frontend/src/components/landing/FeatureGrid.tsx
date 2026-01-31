'use client';

import React from 'react';
import { motion } from 'framer-motion';
import {
  Brain,
  Zap,
  ScanLine,
  GitBranch,
} from 'lucide-react';

const BentoCard = ({ children, className, delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true }}
    transition={{ duration: 0.5, delay }}
    className={`relative overflow-hidden rounded-3xl bg-neutral-50/50 border border-neutral-200 p-8 shadow-sm hover:shadow-md transition-shadow ${className}`}
  >
    {children}
  </motion.div>
);

export const FeatureGrid = () => {
  return (
    <section className="py-32 relative bg-white">
      <div className="landing-container">
        <div className="mb-20 text-center max-w-2xl mx-auto">
          <h2 className="text-4xl font-bold tracking-tight text-neutral-900 mb-6">
            不止于批改<br />
            <span className="text-blue-600">重塑反馈流程</span>
          </h2>
          <p className="text-lg text-neutral-600">
            GradeOS 通过原生视觉识别与多智能体协作，解决传统 OCR 识别率低、逻辑判断弱的痛点。
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-6 gap-6 auto-rows-[300px]">

          {/* Native Vision - Large Card */}
          <BentoCard className="md:col-span-4 bg-gradient-to-br from-blue-50 to-indigo-50/50" delay={0.1}>
            <div className="h-full flex flex-col justify-between relative z-10">
              <div>
                <div className="w-12 h-12 rounded-xl bg-blue-600 text-white flex items-center justify-center mb-6 shadow-lg shadow-blue-600/20">
                  <ScanLine size={24} />
                </div>
                <h3 className="text-2xl font-bold text-neutral-900 mb-2">Vision 原生识别</h3>
                <p className="text-neutral-600 max-w-md">
                  跳过传统 OCR 文本提取，直接基于 Gemini 3.0 Vision 理解图像语义。
                  完美处理手写公式、几何图形与潦草字迹。
                </p>
              </div>
              <div className="absolute right-0 bottom-0 w-64 h-48 bg-blue-200/20 rounded-tl-3xl backdrop-blur-sm border-t border-l border-white/50" />
            </div>
          </BentoCard>

          {/* Parallel Processing - Tall Card */}
          <BentoCard className="md:col-span-2 md:row-span-2 bg-neutral-900 text-white" delay={0.2}>
            <div className="h-full flex flex-col">
              <div className="w-12 h-12 rounded-xl bg-emerald-500 text-white flex items-center justify-center mb-6 shadow-lg shadow-emerald-500/20">
                <Zap size={24} />
              </div>
              <h3 className="text-2xl font-bold mb-2">高并发流水线</h3>
              <p className="text-neutral-400 mb-8">
                真正的生产级性能。支持千份试卷并行处理，自动负载均衡。
              </p>

              {/* Simulated Terminal List */}
              <div className="flex-1 overflow-hidden space-y-3 font-mono text-xs text-neutral-500 opacity-60">
                <div className="flex gap-2"><span className="text-emerald-500">✓</span> Worker-01: Processing Batch #204</div>
                <div className="flex gap-2"><span className="text-emerald-500">✓</span> Worker-02: Grading Completed</div>
                <div className="flex gap-2"><span className="text-emerald-500">✓</span> Worker-03: Image Preprocessing</div>
                <div className="flex gap-2"><span className="text-emerald-500">✓</span> Worker-04: Rubric Analysis</div>
                <div className="flex gap-2"><span className="text-emerald-500">✓</span> Worker-05: Results Exported</div>
              </div>
            </div>
          </BentoCard>

          {/* Agentic Workflow - Medium Card */}
          <BentoCard className="md:col-span-2 bg-white" delay={0.3}>
            <div className="w-12 h-12 rounded-xl bg-violet-600 text-white flex items-center justify-center mb-6 shadow-lg shadow-violet-600/20">
              <GitBranch size={24} />
            </div>
            <h3 className="text-xl font-bold text-neutral-900 mb-2">LangGraph 编排</h3>
            <p className="text-neutral-600 text-sm">
              基于图论的工作流引擎。支持复杂的条件分支、循环修正与人机回环。
            </p>
          </BentoCard>

          {/* Self-Reflection & Review - Medium Card */}
          <BentoCard className="md:col-span-2 bg-white" delay={0.4}>
            <div className="w-12 h-12 rounded-xl bg-amber-500 text-white flex items-center justify-center mb-6 shadow-lg shadow-amber-500/20">
              <Brain size={24} />
            </div>
            <h3 className="text-xl font-bold text-neutral-900 mb-2">自白与逻辑复核</h3>
            <p className="text-neutral-600 text-sm">
              独有的 Agent 自我反思机制。模型会输出"判分自白"，并进行二次逻辑一致性检查。
            </p>
          </BentoCard>

        </div>
      </div>
    </section>
  );
};
