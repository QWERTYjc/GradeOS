import React from 'react';
import Link from 'next/link';
import { Github, Twitter, Linkedin } from 'lucide-react';

export const PageFooter = () => {
    return (
        <footer className="border-t border-slate-800 bg-slate-950 pt-16 pb-8">
            <div className="landing-container">
                <div className="grid md:grid-cols-4 gap-12 mb-12">
                    <div className="md:col-span-2">
                        <div className="flex items-center gap-2 mb-6">
                            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-white font-display">
                                G
                            </div>
                            <span className="text-xl font-bold text-white font-display">GradeOS</span>
                        </div>
                        <p className="text-slate-400 max-w-sm">
                            The futuristic grading platform for modern educators.
                            Automate your workflow and focus on what matters most—teaching.
                        </p>
                    </div>

                    <div>
                        <h4 className="font-bold text-white mb-6 uppercase tracking-wider text-sm">Product</h4>
                        <ul className="space-y-4 text-slate-400">
                            <li><Link href="#features" className="hover:text-blue-400 transition-colors">Features</Link></li>
                            <li><Link href="#pricing" className="hover:text-blue-400 transition-colors">Pricing</Link></li>
                            <li><Link href="/console" className="hover:text-blue-400 transition-colors">Console</Link></li>
                            <li><Link href="/changelog" className="hover:text-blue-400 transition-colors">Changelog</Link></li>
                        </ul>
                    </div>

                    <div>
                        <h4 className="font-bold text-white mb-6 uppercase tracking-wider text-sm">Company</h4>
                        <ul className="space-y-4 text-slate-400">
                            <li><Link href="/about" className="hover:text-blue-400 transition-colors">About</Link></li>
                            <li><Link href="/careers" className="hover:text-blue-400 transition-colors">Careers</Link></li>
                            <li><Link href="/blog" className="hover:text-blue-400 transition-colors">Blog</Link></li>
                            <li><Link href="/contact" className="hover:text-blue-400 transition-colors">Contact</Link></li>
                        </ul>
                    </div>
                </div>

                <div className="border-t border-slate-900 pt-8 flex flex-col md:flex-row items-center justify-between gap-4">
                    <div className="text-slate-500 text-sm">
                        © {new Date().getFullYear()} GradeOS Platform. All rights reserved.
                    </div>

                    <div className="flex items-center gap-6">
                        <a href="#" className="text-slate-500 hover:text-white transition-colors"><Github className="w-5 h-5" /></a>
                        <a href="#" className="text-slate-500 hover:text-white transition-colors"><Twitter className="w-5 h-5" /></a>
                        <a href="#" className="text-slate-500 hover:text-white transition-colors"><Linkedin className="w-5 h-5" /></a>
                    </div>
                </div>
            </div>
        </footer>
    );
};
