'use client';

import React from 'react';
import Link from 'next/link';
import { Github, Twitter, Linkedin } from 'lucide-react';

export const PageFooter = () => {
    return (
        <footer className="bg-gray-900 text-white">
            {/* CTA Section */}
            <div className="border-b border-gray-800">
                <div className="landing-container py-16">
                    <div className="flex flex-col lg:flex-row items-center justify-between gap-8">
                        <div className="text-center lg:text-left">
                            <h2 className="text-3xl font-bold mb-3">
                                准备好提升批改效率？
                            </h2>
                            <p className="text-gray-400 max-w-lg">
                                加入数千名教师的行列，体验AI带来的批改革命。免费开始使用，无需信用卡。
                            </p>
                        </div>
                        <div className="flex flex-col sm:flex-row gap-4">
                            <Link
                                href="/console"
                                className="px-8 py-4 rounded-xl bg-blue-600 text-white font-semibold hover:bg-blue-700 transition-colors text-center"
                            >
                                免费开始使用
                            </Link>
                            <Link
                                href="/contact"
                                className="px-8 py-4 rounded-xl bg-gray-800 text-white font-semibold hover:bg-gray-700 transition-colors text-center"
                            >
                                联系销售
                            </Link>
                        </div>
                    </div>
                </div>
            </div>

            {/* Main Footer */}
            <div className="landing-container py-16">
                <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-12">
                    {/* Brand */}
                    <div className="lg:col-span-1">
                        <div className="flex items-center gap-3 mb-6">
                            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center font-bold text-white text-lg">
                                G
                            </div>
                            <span className="text-xl font-bold">GradeOS</span>
                        </div>
                        <p className="text-gray-400 text-sm mb-6 leading-relaxed">
                            智能批改平台，让教育更专注。基于最先进的AI技术，为教师提供高效、准确的批改体验。
                        </p>
                        <div className="flex items-center gap-4">
                            <a
                                href="#"
                                className="w-10 h-10 rounded-lg bg-gray-800 flex items-center justify-center text-gray-400 hover:text-white hover:bg-gray-700 transition-all"
                            >
                                <Github className="w-5 h-5" />
                            </a>
                            <a
                                href="#"
                                className="w-10 h-10 rounded-lg bg-gray-800 flex items-center justify-center text-gray-400 hover:text-white hover:bg-gray-700 transition-all"
                            >
                                <Twitter className="w-5 h-5" />
                            </a>
                            <a
                                href="#"
                                className="w-10 h-10 rounded-lg bg-gray-800 flex items-center justify-center text-gray-400 hover:text-white hover:bg-gray-700 transition-all"
                            >
                                <Linkedin className="w-5 h-5" />
                            </a>
                        </div>
                    </div>

                    {/* Product */}
                    <div>
                        <h4 className="font-semibold text-white mb-6 text-sm uppercase tracking-wider">
                            产品
                        </h4>
                        <ul className="space-y-3 text-gray-400 text-sm">
                            <li>
                                <Link href="#features" className="hover:text-blue-400 transition-colors">
                                    核心特性
                                </Link>
                            </li>
                            <li>
                                <Link href="/console" className="hover:text-blue-400 transition-colors">
                                    控制台
                                </Link>
                            </li>

                            <li>
                                <Link href="/changelog" className="hover:text-blue-400 transition-colors">
                                    更新日志
                                </Link>
                            </li>
                        </ul>
                    </div>

                    {/* Resources */}
                    <div>
                        <h4 className="font-semibold text-white mb-6 text-sm uppercase tracking-wider">
                            资源
                        </h4>
                        <ul className="space-y-3 text-gray-400 text-sm">
                            <li>
                                <Link href="/docs" className="hover:text-blue-400 transition-colors">
                                    文档中心
                                </Link>
                            </li>
                            <li>
                                <Link href="/blog" className="hover:text-blue-400 transition-colors">
                                    博客
                                </Link>
                            </li>
                            <li>
                                <Link href="/tutorials" className="hover:text-blue-400 transition-colors">
                                    教程
                                </Link>
                            </li>
                            <li>
                                <Link href="/faq" className="hover:text-blue-400 transition-colors">
                                    常见问题
                                </Link>
                            </li>
                            <li>
                                <Link href="/support" className="hover:text-blue-400 transition-colors">
                                    技术支持
                                </Link>
                            </li>
                        </ul>
                    </div>

                    {/* Company */}
                    <div>
                        <h4 className="font-semibold text-white mb-6 text-sm uppercase tracking-wider">
                            公司
                        </h4>
                        <ul className="space-y-3 text-gray-400 text-sm">
                            <li>
                                <Link href="/about" className="hover:text-blue-400 transition-colors">
                                    关于我们
                                </Link>
                            </li>
                            <li>
                                <Link href="/careers" className="hover:text-blue-400 transition-colors">
                                    加入我们
                                </Link>
                            </li>
                            <li>
                                <Link href="/contact" className="hover:text-blue-400 transition-colors">
                                    联系方式
                                </Link>
                            </li>
                            <li>
                                <Link href="/privacy" className="hover:text-blue-400 transition-colors">
                                    隐私政策
                                </Link>
                            </li>
                            <li>
                                <Link href="/terms" className="hover:text-blue-400 transition-colors">
                                    服务条款
                                </Link>
                            </li>
                        </ul>
                    </div>
                </div>
            </div>

            {/* Bottom Bar */}
            <div className="border-t border-gray-800">
                <div className="landing-container py-6">
                    <div className="flex flex-col md:flex-row items-center justify-between gap-4">
                        <div className="text-gray-500 text-sm">
                            © {new Date().getFullYear()} GradeOS. All rights reserved.
                        </div>
                        <div className="flex items-center gap-6 text-gray-500 text-sm">
                            <Link href="/privacy" className="hover:text-white transition-colors">
                                隐私
                            </Link>
                            <Link href="/terms" className="hover:text-white transition-colors">
                                条款
                            </Link>
                            <Link href="/cookies" className="hover:text-white transition-colors">
                                Cookies
                            </Link>
                        </div>
                    </div>
                </div>
            </div>
        </footer>
    );
};

export default PageFooter;
