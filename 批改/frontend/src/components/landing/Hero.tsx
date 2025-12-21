'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import Link from 'next/link';

export default function Hero() {
    return (
        <section className="relative min-h-screen flex flex-col justify-center items-center text-center px-4 pt-20">
            {/* Badge */}
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="mb-8 inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 border border-blue-100 text-blue-600 text-xs font-medium tracking-wide"
            >
                <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
                </span>
                LIVE SYSTEM V3.0
            </motion.div>

            {/* Main Title */}
            <div className="max-w-4xl mx-auto mb-6 overflow-hidden">
                <motion.h1
                    initial={{ y: '100%' }}
                    animate={{ y: 0 }}
                    transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                    className="text-5xl md:text-7xl font-bold tracking-tight text-ink leading-[1.1]"
                >
                    AI 批改，让反馈变成
                    <br />
                    <span className="text-transparent bg-clip-text bg-gradient-to-r from-azure to-cyan">
                        实时可视系统
                    </span>
                </motion.h1>
            </div>

            {/* Subtitle */}
            <motion.p
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4, duration: 0.8 }}
                className="max-w-2xl mx-auto text-lg text-gray-500 mb-10 leading-relaxed"
            >
                不仅仅是打分。我们构建了一个可追溯、可观测、并行处理的智能批改流水线。
                <br className="hidden md:block" />
                像监控服务器集群一样监控您的作业批改进度。
            </motion.p>

            {/* CTA Buttons */}
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.6 }}
                className="flex flex-col sm:flex-row gap-4 items-center"
            >
                <Link href="/console" className="group relative px-8 py-4 bg-ink text-white rounded-full font-medium overflow-hidden inline-block">
                    <div className="absolute inset-0 w-full h-full bg-gradient-to-r from-azure to-neon opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                    <div className="absolute inset-0 w-1/2 h-full bg-white/20 skew-x-12 -translate-x-[150%] group-hover:translate-x-[250%] transition-transform duration-700 ease-in-out" />
                    <span className="relative flex items-center gap-2">
                        立即体验
                        <ArrowRight size={18} />
                    </span>
                </Link>


            </motion.div>

            {/* Scroll Indicator */}
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 1, duration: 1 }}
                className="absolute bottom-10 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 text-gray-300"
            >
                <span className="text-[10px] uppercase tracking-widest">Scroll to Explore</span>
                <div className="w-[1px] h-12 bg-gradient-to-b from-gray-300 to-transparent" />
            </motion.div>
        </section>
    );
}
