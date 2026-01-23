import React from 'react';
import { ArrowRight, Terminal } from 'lucide-react';
import Link from 'next/link';

export const HeroSection = () => {
    return (
        <section className="relative min-h-[90vh] flex items-center justify-center overflow-hidden landing-shell">
            {/* Background Elements */}
            <div className="absolute inset-0 pointer-events-none">
                <div className="landing-grid absolute inset-0 z-0" />
                <div className="landing-hero-glow landing-hero-glow-1" />
                <div className="landing-hero-glow landing-hero-glow-2" />
            </div>

            <div className="landing-container relative z-10 grid lg:grid-cols-2 gap-12 items-center">
                {/* Left Content */}
                <div className="space-y-8 text-center lg:text-left">
                    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 animate-fadeIn">
                        <span className="relative flex h-2 w-2">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
                        </span>
                        <span className="text-xs font-semibold tracking-wider text-blue-400 uppercase">GradeOS v2.0 Live</span>
                    </div>

                    <h1 className="landing-display text-5xl lg:text-7xl font-bold leading-tight text-white animate-fadeIn" style={{ animationDelay: '0.1s' }}>
                        The Future of <br />
                        <span className="landing-gradient-text">Automated Grading</span>
                    </h1>

                    <p className="text-lg text-slate-400 max-w-xl mx-auto lg:mx-0 leading-relaxed animate-fadeIn" style={{ animationDelay: '0.2s' }}>
                        Transform your grading workflow with AI-powered analysis.
                        Experience the precision of neural networks combined with the control of a command console.
                    </p>

                    <div className="flex flex-col sm:flex-row items-center gap-4 justify-center lg:justify-start animate-fadeIn" style={{ animationDelay: '0.3s' }}>
                        <Link href="/console" className="landing-cta-primary group flex items-center gap-2">
                            <span>Enter Console</span>
                            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                        </Link>

                        <Link href="#demo" className="landing-cta-secondary flex items-center gap-2 group">
                            <Terminal className="w-4 h-4 text-slate-400 group-hover:text-blue-500 transition-colors" />
                            <span>View Terminal</span>
                        </Link>
                    </div>

                    <div className="pt-8 flex items-center gap-8 justify-center lg:justify-start opacity-0 animate-[fadeIn_0.6s_ease-out_0.5s_forwards]">
                        <div className="text-center lg:text-left">
                            <div className="text-2xl font-bold text-white">99.8%</div>
                            <div className="text-xs text-slate-500 uppercase tracking-widest">Accuracy</div>
                        </div>
                        <div className="w-px h-10 bg-slate-800" />
                        <div className="text-center lg:text-left">
                            <div className="text-2xl font-bold text-white">100x</div>
                            <div className="text-xs text-slate-500 uppercase tracking-widest">Faster</div>
                        </div>
                        <div className="w-px h-10 bg-slate-800" />
                        <div className="text-center lg:text-left">
                            <div className="text-2xl font-bold text-white">24/7</div>
                            <div className="text-xs text-slate-500 uppercase tracking-widest">Availability</div>
                        </div>
                    </div>
                </div>

                {/* Right Visual - Abstract Console */}
                <div className="relative hidden lg:block perspective-[2000px]">
                    <div className="relative transform rotate-y-[-10deg] rotate-x-[5deg] hover:rotate-y-[0deg] hover:rotate-x-[0deg] transition-transform duration-700 ease-out preserve-3d">
                        {/* Main Glass Panel */}
                        <div className="glass-panel p-6 rounded-2xl animate-float relative z-20">
                            <div className="flex items-center gap-3 mb-6 border-b border-white/5 pb-4">
                                <div className="flex gap-2">
                                    <div className="w-3 h-3 rounded-full bg-red-500/80" />
                                    <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
                                    <div className="w-3 h-3 rounded-full bg-green-500/80" />
                                </div>
                                <div className="text-xs text-slate-500 font-mono">user@gradeos-core:~</div>
                            </div>

                            <div className="space-y-3 font-mono text-sm">
                                <div className="flex gap-2">
                                    <span className="text-blue-400">➜</span>
                                    <span className="text-purple-400">gradeos</span>
                                    <span className="text-slate-300">batch process --input=midterms_2024</span>
                                </div>
                                <div className="pl-4 text-slate-400 animate-pulse">
                                    Waiting for task...
                                </div>

                                <div className="space-y-2 pl-4 pt-2">
                                    <div className="flex items-center gap-3 text-green-400/90 bg-green-900/10 p-2 rounded border border-green-500/20">
                                        <span className="text-xs">✔</span>
                                        <span>Parsing PDF batch [32 files]</span>
                                    </div>
                                    <div className="flex items-center gap-3 text-blue-400/90 bg-blue-900/10 p-2 rounded border border-blue-500/20">
                                        <span className="text-xs">ℹ</span>
                                        <span>Initializing Neural Grader v4.2</span>
                                    </div>
                                    <div className="flex items-center gap-3 text-amber-400/90 bg-amber-900/10 p-2 rounded border border-amber-500/20">
                                        <span className="text-xs">⚡</span>
                                        <span>Processing Agent 1 active</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Floating Elements */}
                        <div className="absolute -right-8 -bottom-8 p-4 glass-panel rounded-xl z-30 animate-float" style={{ animationDelay: '2s' }}>
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-lg bg-blue-600/20 flex items-center justify-center text-blue-400">
                                    A+
                                </div>
                                <div>
                                    <div className="text-xs text-slate-400">Grade Accuracy</div>
                                    <div className="text-sm font-bold text-white">Perfect</div>
                                </div>
                            </div>
                        </div>

                        <div className="absolute -left-12 top-1/2 p-4 glass-panel rounded-xl z-30 animate-float" style={{ animationDelay: '3s' }}>
                            <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center">
                                    <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                                </div>
                                <div className="text-xs font-mono text-green-400">System Online</div>
                            </div>
                        </div>
                    </div>

                    {/* Glow behind panel */}
                    <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[120%] h-[120%] bg-blue-500/10 blur-[80px] -z-10" />
                </div>
            </div>
        </section>
    );
};
