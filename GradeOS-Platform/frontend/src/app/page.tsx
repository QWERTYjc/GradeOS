'use client';

import React from 'react';
import { motion } from 'framer-motion';
import ParticleField from '@/components/landing/ParticleField';
import Hero from '@/components/landing/Hero';
import WorkflowGraph from '@/components/landing/WorkflowGraph';
import DemoDock from '@/components/landing/DemoDock';
import { CheckCircle, Zap, Shield, BarChart, Users, BookOpen } from 'lucide-react';
import Link from 'next/link';
import clsx from 'clsx';
import { useAuthStore } from '@/store/authStore';
import { Role } from '@/types';

const features = [
  {
    icon: Zap,
    title: 'Real-time Parallel Grading',
    desc: 'Distributed worker pool that processes thousands of submissions in parallel with instant feedback.',
  },
  {
    icon: CheckCircle,
    title: 'Multi-Dimension Rubrics',
    desc: 'Supports subjective, objective, and handwritten formula recognition with strict rubric compliance.',
  },
  {
    icon: Shield,
    title: 'Secure by Design',
    desc: 'Enterprise-grade encryption and private deployment options to protect student data.',
  },
  {
    icon: BarChart,
    title: 'Class Analytics',
    desc: 'Auto-generated weak-point analysis, high-frequency mistakes, and growth trends.',
  },
  {
    icon: Users,
    title: 'Teacher Workspace',
    desc: 'Class management, assignment publishing, and grading insights in one place.',
  },
  {
    icon: BookOpen,
    title: 'Student AI Assistant',
    desc: 'Personalized study planning, score analysis, and targeted coaching tips.',
  },
];

export default function LandingPage() {
  const { user } = useAuthStore();
  const isTeacher = user?.role === Role.Teacher || user?.role === Role.Admin;

  return (
    <main
      className={clsx(
        'landing-shell relative text-ink min-h-screen selection:bg-azure selection:text-white overflow-x-hidden'
      )}
    >
      <ParticleField />

      <nav className="landing-nav fixed top-0 left-0 right-0 h-16 flex items-center justify-between px-6 md:px-12 z-50">
        <div className="flex items-center gap-2 font-bold text-xl tracking-tight">
          <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-cyan-500 rounded-lg flex items-center justify-center text-white text-sm font-bold">G</div>
          GradeOS
        </div>
        <div className="hidden md:flex items-center gap-8 text-sm font-medium text-gray-600">
          <a href="#features" className="hover:text-azure transition-colors">Features</a>
          <a href="#workflow" className="hover:text-azure transition-colors">Workflow</a>
          <a href="#demo" className="hover:text-azure transition-colors">Demo</a>
        </div>
        <div className="flex items-center gap-3">
          {user ? (
            <Link
              href={isTeacher ? '/teacher/dashboard' : '/student/dashboard'}
              className="px-4 py-2 text-gray-600 hover:text-azure text-sm font-medium transition-colors"
            >
              Open Console
            </Link>
          ) : (
            <>
              <Link href="/login" className="px-4 py-2 text-gray-600 hover:text-azure text-sm font-medium transition-colors">
                Login
              </Link>
              <Link href="/register" className="px-4 py-2 bg-black text-white text-sm font-medium rounded-lg hover:bg-gray-800 transition-colors">
                Register
              </Link>
            </>
          )}
        </div>
      </nav>

      <Hero />

      <section id="workflow" className="relative py-24 px-4 md:px-12 bg-mist/50">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-12 text-center"
          >
            <h2 className="landing-display text-3xl font-bold mb-4">Transparent and Observable Workflow</h2>
            <p className="text-gray-500 max-w-2xl mx-auto">
              Every step, retry, and log is visible so teachers always know what the system is doing.
            </p>
          </motion.div>

          <WorkflowGraph />
        </div>
      </section>

      <section id="features" className="py-24 px-4 md:px-12 bg-white">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-10 gap-y-8">
            {features.map((f, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.08 }}
                className="landing-feature-row"
              >
                <div className="landing-feature-icon">
                  <f.icon className="text-azure" size={22} />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-slate-900">{f.title}</h3>
                  <p className="text-sm text-slate-500 leading-relaxed mt-2">{f.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section id="demo" className="py-24 px-4 md:px-12 bg-mist/50">
        <div className="max-w-6xl mx-auto">
          <DemoDock />
        </div>
      </section>
    </main>
  );
}
