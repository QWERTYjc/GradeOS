'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, Settings, BarChart3, FileCheck } from 'lucide-react';

const steps = [
    { id: 'upload', label: '1. 上传数据', icon: Upload },
    { id: 'config', label: '2. 选择标准', icon: Settings },
    { id: 'result', label: '3. 生成结果', icon: BarChart3 },
];

export default function DemoDock() {
    const [activeStep, setActiveStep] = useState('upload');

    return (
        <div className="w-full max-w-5xl mx-auto bg-white rounded-2xl shadow-xl border border-gray-100 overflow-hidden flex flex-col md:flex-row h-[600px]">
            {/* Sidebar / Stepper */}
            <div className="w-full md:w-64 bg-gray-50 p-6 flex flex-col gap-2 border-r border-gray-100">
                <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4">Interactive Demo</h3>
                {steps.map((step) => (
                    <button
                        key={step.id}
                        onClick={() => setActiveStep(step.id)}
                        className={`flex items-center gap-3 p-3 rounded-lg text-sm font-medium transition-all ${activeStep === step.id
                                ? 'bg-white text-azure shadow-sm ring-1 ring-gray-100'
                                : 'text-gray-500 hover:bg-gray-100'
                            }`}
                    >
                        <step.icon size={18} />
                        {step.label}
                    </button>
                ))}
            </div>

            {/* Main Content Area */}
            <div className="flex-1 relative p-8 bg-white overflow-hidden">
                <AnimatePresence mode="wait">
                    {activeStep === 'upload' && (
                        <motion.div
                            key="upload"
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            className="h-full flex flex-col items-center justify-center border-2 border-dashed border-gray-200 rounded-xl bg-gray-50/50"
                        >
                            <div className="w-20 h-20 bg-blue-50 rounded-full flex items-center justify-center mb-4 animate-pulse">
                                <Upload size={32} className="text-azure" />
                            </div>
                            <h4 className="text-lg font-semibold text-ink">拖拽文件到这里</h4>
                            <p className="text-sm text-gray-400 mt-2">支持 PDF, JPG, PNG (自动识别手写体)</p>
                        </motion.div>
                    )}

                    {activeStep === 'config' && (
                        <motion.div
                            key="config"
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            className="h-full flex flex-col gap-6"
                        >
                            <h3 className="text-xl font-bold text-ink">配置评分标准</h3>
                            <div className="space-y-4">
                                {['严格模式 (Strict)', '宽松模式 (Lenient)', '仅纠错 (Correction Only)'].map((mode, i) => (
                                    <div key={i} className="p-4 border border-gray-200 rounded-lg hover:border-azure cursor-pointer transition-colors flex items-center gap-4 group">
                                        <div className={`w-4 h-4 rounded-full border-2 border-gray-300 group-hover:border-azure ${i === 0 ? 'bg-azure border-azure' : ''}`} />
                                        <span className="text-gray-700 font-medium">{mode}</span>
                                    </div>
                                ))}
                            </div>
                        </motion.div>
                    )}

                    {activeStep === 'result' && (
                        <motion.div
                            key="result"
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            className="h-full flex flex-col"
                        >
                            <div className="flex items-end gap-4 mb-8">
                                <div className="text-6xl font-bold text-ink tracking-tighter">
                                    92<span className="text-2xl text-gray-400 font-normal">/100</span>
                                </div>
                                <div className="mb-2 px-2 py-1 bg-green-100 text-green-700 text-xs font-bold rounded">A GRADE</div>
                            </div>

                            <div className="space-y-3">
                                <div className="flex items-start gap-3 p-3 bg-red-50 rounded-lg border border-red-100">
                                    <AlertCircle size={16} className="text-red-500 mt-1 shrink-0" />
                                    <div>
                                        <div className="text-sm font-bold text-red-800">计算错误 (-5)</div>
                                        <div className="text-xs text-red-600 mt-1">第 3 题步骤正确，但最终数值计算有误。</div>
                                    </div>
                                </div>
                                <div className="flex items-start gap-3 p-3 bg-blue-50 rounded-lg border border-blue-100">
                                    <FileCheck size={16} className="text-blue-500 mt-1 shrink-0" />
                                    <div>
                                        <div className="text-sm font-bold text-blue-800">逻辑清晰 (+2)</div>
                                        <div className="text-xs text-blue-600 mt-1">解题思路非常清晰，步骤完整。</div>
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
}

// Helper icon
function AlertCircle({ size, className }: { size: number, className: string }) {
    return (
        <svg
            width={size}
            height={size}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={className}
        >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
    );
}
