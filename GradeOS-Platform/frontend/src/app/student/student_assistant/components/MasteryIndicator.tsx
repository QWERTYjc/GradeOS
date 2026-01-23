'use client';

import React, { useEffect, useState } from 'react';

interface MasteryIndicatorProps {
    score: number; // 0-100
    level: string; // beginner / developing / proficient / mastery
    analysis?: string;
    evidence?: string[];
    suggestions?: string[];
    showDetails?: boolean;
    size?: 'sm' | 'md' | 'lg';
}

/**
 * 掌握度可视化组件
 * 圆形进度条显示掌握度百分比，带颜色编码和动画效果
 */
const MasteryIndicator: React.FC<MasteryIndicatorProps> = ({
    score,
    level,
    analysis,
    evidence = [],
    suggestions = [],
    showDetails = false,
    size = 'md'
}) => {
    const [animatedScore, setAnimatedScore] = useState(0);
    const [expanded, setExpanded] = useState(showDetails);

    // 动画效果
    useEffect(() => {
        const duration = 1000;
        const steps = 60;
        const increment = score / steps;
        let current = 0;

        const timer = setInterval(() => {
            current += increment;
            if (current >= score) {
                setAnimatedScore(score);
                clearInterval(timer);
            } else {
                setAnimatedScore(Math.round(current));
            }
        }, duration / steps);

        return () => clearInterval(timer);
    }, [score]);

    // 根据分数获取颜色
    const getColor = (s: number) => {
        if (s >= 76) return { primary: '#10B981', secondary: '#D1FAE5', text: '掌握' }; // green
        if (s >= 51) return { primary: '#3B82F6', secondary: '#DBEAFE', text: '熟练' }; // blue
        if (s >= 26) return { primary: '#F59E0B', secondary: '#FEF3C7', text: '发展中' }; // yellow
        return { primary: '#EF4444', secondary: '#FEE2E2', text: '初学' }; // red
    };

    const colors = getColor(animatedScore);

    // 尺寸配置
    const sizeConfig = {
        sm: { container: 80, stroke: 6, fontSize: 'text-lg', labelSize: 'text-xs' },
        md: { container: 120, stroke: 8, fontSize: 'text-2xl', labelSize: 'text-sm' },
        lg: { container: 160, stroke: 10, fontSize: 'text-4xl', labelSize: 'text-base' }
    };

    const config = sizeConfig[size];
    const radius = (config.container - config.stroke) / 2;
    const circumference = 2 * Math.PI * radius;
    const strokeDashoffset = circumference - (animatedScore / 100) * circumference;

    // 获取等级图标
    const getLevelIcon = () => {
        switch (level) {
            case 'mastery': return '🏆';
            case 'proficient': return '⭐';
            case 'developing': return '📈';
            default: return '🌱';
        }
    };

    return (
        <div className="flex flex-col items-center gap-4">
            {/* 圆形进度条 */}
            <div
                className="relative cursor-pointer transition-transform hover:scale-105"
                style={{ width: config.container, height: config.container }}
                onClick={() => setExpanded(!expanded)}
            >
                <svg
                    width={config.container}
                    height={config.container}
                    className="transform -rotate-90"
                >
                    {/* 背景圆 */}
                    <circle
                        cx={config.container / 2}
                        cy={config.container / 2}
                        r={radius}
                        fill="none"
                        stroke={colors.secondary}
                        strokeWidth={config.stroke}
                    />
                    {/* 进度圆 */}
                    <circle
                        cx={config.container / 2}
                        cy={config.container / 2}
                        r={radius}
                        fill="none"
                        stroke={colors.primary}
                        strokeWidth={config.stroke}
                        strokeDasharray={circumference}
                        strokeDashoffset={strokeDashoffset}
                        strokeLinecap="round"
                        className="transition-all duration-1000 ease-out"
                    />
                </svg>

                {/* 中心文字 */}
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className={`${config.fontSize} font-bold`} style={{ color: colors.primary }}>
                        {animatedScore}
                    </span>
                    <span className={`${config.labelSize} text-gray-500`}>掌握度</span>
                </div>
            </div>

            {/* 等级标签 */}
            <div
                className="flex items-center gap-2 px-4 py-2 rounded-full"
                style={{ backgroundColor: colors.secondary }}
            >
                <span>{getLevelIcon()}</span>
                <span className={`font-medium ${config.labelSize}`} style={{ color: colors.primary }}>
                    {colors.text}
                </span>
            </div>

            {/* 展开详情 */}
            {expanded && (analysis || evidence.length > 0 || suggestions.length > 0) && (
                <div className="w-full max-w-sm p-4 bg-gray-50 rounded-xl space-y-4 animate-fadeIn">
                    {/* 分析说明 */}
                    {analysis && (
                        <div>
                            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">分析</h4>
                            <p className="text-sm text-gray-700">{analysis}</p>
                        </div>
                    )}

                    {/* 证据列表 */}
                    {evidence.length > 0 && (
                        <div>
                            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">已掌握</h4>
                            <ul className="space-y-1">
                                {evidence.map((item, idx) => (
                                    <li key={idx} className="flex items-start gap-2 text-sm text-gray-700">
                                        <span className="text-green-500 mt-0.5">✓</span>
                                        {item}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {/* 改进建议 */}
                    {suggestions.length > 0 && (
                        <div>
                            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">建议</h4>
                            <ul className="space-y-1">
                                {suggestions.map((item, idx) => (
                                    <li key={idx} className="flex items-start gap-2 text-sm text-gray-700">
                                        <span className="text-blue-500 mt-0.5">→</span>
                                        {item}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>
            )}

            {/* 展开/收起提示 */}
            {(analysis || evidence.length > 0 || suggestions.length > 0) && (
                <button
                    onClick={() => setExpanded(!expanded)}
                    className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
                >
                    {expanded ? '收起详情 ▲' : '查看详情 ▼'}
                </button>
            )}

            <style jsx>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fadeIn {
          animation: fadeIn 0.3s ease-out;
        }
      `}</style>
        </div>
    );
};

export default MasteryIndicator;
