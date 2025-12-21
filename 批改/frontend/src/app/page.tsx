'use client';

import React from 'react';
import { motion } from 'framer-motion';
import ParticleField from '@/components/landing/ParticleField';
import Hero from '@/components/landing/Hero';
import WorkflowGraph from '@/components/landing/WorkflowGraph';
import DemoDock from '@/components/landing/DemoDock';
import { CheckCircle, Zap, Shield, BarChart } from 'lucide-react';
import Link from 'next/link';

const features = [
  {
    icon: Zap,
    title: '实时并行批改',
    desc: '基于分布式 Worker 池，支持数千份作业同时处理，秒级反馈。',
  },
  {
    icon: CheckCircle,
    title: '多维评分标准',
    desc: '支持主观题、客观题、手写公式识别，严格遵循预设 Rubric。',
  },
  {
    icon: Shield,
    title: '数据安全合规',
    desc: '企业级加密传输，支持私有化部署，确保学生数据隐私安全。',
  },
  {
    icon: BarChart,
    title: '班级学情看板',
    desc: '自动生成班级薄弱点分析、高频错题集与个性化进步曲线。',
  },
];

export default function LandingPage() {
  return (
    <main className="relative bg-white text-ink min-h-screen selection:bg-azure selection:text-white overflow-x-hidden">
      {/* Background Layer */}
      <ParticleField />

      {/* Navbar */}
      <nav className="fixed top-0 left-0 right-0 h-16 flex items-center justify-between px-6 md:px-12 z-50 bg-white/80 backdrop-blur-md border-b border-gray-100">
        <div className="flex items-center gap-2 font-bold text-xl tracking-tight">
          <div className="w-6 h-6 bg-azure rounded-lg flex items-center justify-center text-white text-xs">AI</div>
          AntiGravity
        </div>
        <div className="hidden md:flex items-center gap-8 text-sm font-medium text-gray-600">
          <a href="#features" className="hover:text-azure transition-colors">功能</a>
          <a href="#workflow" className="hover:text-azure transition-colors">工作流</a>
          <a href="#demo" className="hover:text-azure transition-colors">演示</a>
          <a href="#pricing" className="hover:text-azure transition-colors">价格</a>
        </div>
        <Link href="/console" className="px-4 py-2 bg-black text-white text-sm font-medium rounded-lg hover:bg-gray-800 transition-colors">
          登录控制台
        </Link>
      </nav>

      {/* Hero Section */}
      <Hero />

      {/* Workflow Visualization Section */}
      <section id="workflow" className="relative py-24 px-4 md:px-12 bg-mist/50">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-12 text-center"
          >
            <h2 className="text-3xl font-bold mb-4">透明、可观测的批改流水线</h2>
            <p className="text-gray-500 max-w-2xl mx-auto">
              拒绝黑盒。每一个步骤、每一次重试、每一条日志都清晰可见。
            </p>
          </motion.div>

          <WorkflowGraph />
        </div>
      </section>

      {/* Features Grid */}
      <section id="features" className="py-24 px-4 md:px-12 bg-white">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            {features.map((f, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="p-6 rounded-2xl bg-white border border-gray-100 hover:border-blue-200 hover:shadow-xl hover:shadow-blue-500/5 transition-all group"
              >
                <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  <f.icon className="text-azure" size={24} />
                </div>
                <h3 className="text-lg font-bold mb-2">{f.title}</h3>
                <p className="text-sm text-gray-500 leading-relaxed">{f.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Interactive Demo Section */}
      <section id="demo" className="py-24 px-4 md:px-12 bg-gradient-to-b from-white to-blue-50/30">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-12 text-center"
          >
            <h2 className="text-3xl font-bold mb-4">亲身体验智能批改</h2>
            <p className="text-gray-500 max-w-2xl mx-auto">
              上传一份作业，体验从识别到生成评语的全过程。
            </p>
          </motion.div>

          <DemoDock />
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-4 md:px-12 border-t border-gray-100 bg-white">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-6">
          <div className="text-sm text-gray-400">
            © 2025 Antigravity AI. All rights reserved.
          </div>
          <div className="flex gap-6 text-sm text-gray-500">
            <a href="#" className="hover:text-ink">隐私政策</a>
            <a href="#" className="hover:text-ink">服务条款</a>
            <a href="#" className="hover:text-ink">联系我们</a>
          </div>
        </div>
      </footer>
    </main>
  );
}
