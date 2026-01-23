'use client';

import React, { useState, useEffect, useRef } from 'react';
import { COLORS } from '../constants';

interface FocusModeProps {
    question: string;
    onAnswer: (answer: string) => void;
    onExit: () => void;
    isLoading?: boolean;
}

/**
 * 专注模式组件
 * 全屏白底黑字设计，帮助学生集中注意力回答问题
 */
const FocusMode: React.FC<FocusModeProps> = ({
    question,
    onAnswer,
    onExit,
    isLoading = false
}) => {
    const [answer, setAnswer] = useState('');
    const [showHint, setShowHint] = useState(false);
    const inputRef = useRef<HTMLTextAreaElement>(null);

    // 自动聚焦输入框
    useEffect(() => {
        if (inputRef.current) {
            inputRef.current.focus();
        }
    }, []);

    // ESC 键退出专注模式
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                onExit();
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [onExit]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (answer.trim() && !isLoading) {
            onAnswer(answer.trim());
            setAnswer('');
        }
    };

    return (
        <div className="fixed inset-0 z-[100] bg-white flex flex-col items-center justify-center p-8 animate-fadeIn">
            {/* 退出按钮 */}
            <button
                onClick={onExit}
                className="absolute top-6 right-6 p-2 text-gray-400 hover:text-gray-600 transition-colors group"
                title="按 ESC 退出专注模式"
            >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
                <span className="absolute -bottom-8 right-0 text-xs text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                    ESC 退出
                </span>
            </button>

            {/* 专注模式标识 */}
            <div className="absolute top-6 left-6 flex items-center gap-2 text-gray-400">
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
                <span className="text-xs font-medium tracking-widest uppercase">专注模式</span>
            </div>

            {/* 问题区域 */}
            <div className="max-w-3xl w-full text-center mb-16">
                <div className="text-4xl md:text-5xl font-light text-gray-900 leading-relaxed tracking-wide">
                    {question}
                </div>
            </div>

            {/* 输入区域 */}
            <form onSubmit={handleSubmit} className="max-w-2xl w-full">
                <div className="relative">
                    <textarea
                        ref={inputRef}
                        value={answer}
                        onChange={(e) => setAnswer(e.target.value)}
                        placeholder="在此输入你的思考..."
                        className="w-full min-h-[120px] p-6 text-xl text-gray-800 bg-gray-50 border-2 border-gray-200 rounded-2xl 
                       focus:outline-none focus:border-blue-400 focus:bg-white transition-all duration-300
                       placeholder:text-gray-400 resize-none"
                        disabled={isLoading}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                handleSubmit(e);
                            }
                        }}
                    />

                    {/* 提交按钮 */}
                    <button
                        type="submit"
                        disabled={!answer.trim() || isLoading}
                        className={`absolute bottom-4 right-4 px-6 py-2 rounded-xl font-medium transition-all duration-300
              ${answer.trim() && !isLoading
                                ? 'bg-gray-900 text-white hover:bg-gray-800'
                                : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                            }`}
                    >
                        {isLoading ? (
                            <div className="flex items-center gap-2">
                                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                <span>思考中...</span>
                            </div>
                        ) : (
                            '提交回答'
                        )}
                    </button>
                </div>

                {/* 提示信息 */}
                <div className="mt-4 text-center">
                    <button
                        type="button"
                        onClick={() => setShowHint(!showHint)}
                        className="text-sm text-gray-400 hover:text-gray-600 transition-colors"
                    >
                        {showHint ? '隐藏提示' : '需要提示？'}
                    </button>

                    {showHint && (
                        <div className="mt-4 p-4 bg-blue-50 rounded-xl text-blue-800 text-sm animate-fadeIn">
                            💡 试着用自己的话解释这个概念。不要担心答错，思考的过程比答案更重要！
                        </div>
                    )}
                </div>
            </form>

            {/* 底部提示 */}
            <div className="absolute bottom-8 text-xs text-gray-400">
                按 <kbd className="px-2 py-1 bg-gray-100 rounded border border-gray-300 font-mono">Shift + Enter</kbd> 换行，
                按 <kbd className="px-2 py-1 bg-gray-100 rounded border border-gray-300 font-mono">Enter</kbd> 提交
            </div>

        </div>
    );
};

export default FocusMode;
