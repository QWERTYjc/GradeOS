'use client';

import React from 'react';
import { useConsoleStore, StudentResult } from '@/store/consoleStore';
import clsx from 'clsx';
import { Trophy, TrendingUp, Users, Award, ArrowLeft } from 'lucide-react';

interface ResultCardProps {
    result: StudentResult;
    rank: number;
}

const ResultCard: React.FC<ResultCardProps> = ({ result, rank }) => {
    const percentage = (result.score / result.maxScore) * 100;

    let gradeColor = 'from-gray-400 to-gray-500';
    let gradeBg = 'bg-gray-50';
    let gradeLabel = '待提升';

    if (percentage >= 85) {
        gradeColor = 'from-green-400 to-emerald-500';
        gradeBg = 'bg-green-50';
        gradeLabel = '优秀';
    } else if (percentage >= 70) {
        gradeColor = 'from-blue-400 to-indigo-500';
        gradeBg = 'bg-blue-50';
        gradeLabel = '良好';
    } else if (percentage >= 60) {
        gradeColor = 'from-yellow-400 to-orange-500';
        gradeBg = 'bg-yellow-50';
        gradeLabel = '及格';
    } else {
        gradeColor = 'from-red-400 to-rose-500';
        gradeBg = 'bg-red-50';
        gradeLabel = '不及格';
    }

    return (
        <div className={clsx(
            'rounded-2xl p-6 transition-all duration-300 hover:shadow-lg hover:scale-[1.02]',
            gradeBg
        )}>
            <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                    {rank <= 3 && (
                        <div className={clsx(
                            'w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-sm',
                            rank === 1 ? 'bg-gradient-to-br from-yellow-400 to-amber-500' :
                                rank === 2 ? 'bg-gradient-to-br from-gray-300 to-gray-400' :
                                    'bg-gradient-to-br from-orange-300 to-orange-400'
                        )}>
                            {rank}
                        </div>
                    )}
                    <div>
                        <h3 className="font-semibold text-gray-800 text-lg">{result.studentName}</h3>
                        <span className={clsx(
                            'text-xs px-2 py-0.5 rounded-full font-medium',
                            percentage >= 60 ? 'bg-white/50 text-gray-600' : 'bg-red-100 text-red-600'
                        )}>
                            {gradeLabel}
                        </span>
                    </div>
                </div>
            </div>

            {/* Score Display */}
            <div className="flex items-baseline gap-2 mb-3">
                <span className={clsx(
                    'text-4xl font-bold bg-gradient-to-r bg-clip-text text-transparent',
                    gradeColor
                )}>
                    {result.score}
                </span>
                <span className="text-gray-400 text-lg">/ {result.maxScore}</span>
            </div>

            {/* Progress Bar */}
            <div className="w-full bg-white/50 rounded-full h-2.5 overflow-hidden">
                <div
                    className={clsx('h-full rounded-full bg-gradient-to-r transition-all duration-500', gradeColor)}
                    style={{ width: `${percentage}%` }}
                />
            </div>
            <p className="text-right text-xs text-gray-500 mt-1">{percentage.toFixed(1)}%</p>
        </div>
    );
};

export const ResultsView: React.FC = () => {
    const { finalResults, setCurrentTab, workflowNodes } = useConsoleStore();

    // 从 workflowNodes 中获取所有 Agent 的详细结果（如果 finalResults 为空）
    const gradingNode = workflowNodes.find(n => n.id === 'grading');
    const agentResults = gradingNode?.children?.filter(c => c.status === 'completed' && c.output) || [];

    // 优先使用 finalResults，否则从 agents 构建
    const results: StudentResult[] = finalResults.length > 0
        ? finalResults
        : agentResults.map(agent => ({
            studentName: agent.label,
            score: agent.output?.score || 0,
            maxScore: agent.output?.maxScore || 100
        }));

    // 按分数排序
    const sortedResults = [...results].sort((a, b) => b.score - a.score);

    // 统计信息
    const totalStudents = sortedResults.length;
    const avgScore = totalStudents > 0
        ? sortedResults.reduce((sum, r) => sum + r.score, 0) / totalStudents
        : 0;
    const maxScore = sortedResults.length > 0 ? sortedResults[0].maxScore : 100;
    const highestScore = sortedResults.length > 0 ? sortedResults[0].score : 0;
    const passCount = sortedResults.filter(r => (r.score / r.maxScore) >= 0.6).length;

    if (results.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
                <Trophy className="w-16 h-16 mb-4 opacity-30" />
                <p>暂无批改结果</p>
                <button
                    onClick={() => setCurrentTab('process')}
                    className="mt-4 text-blue-500 hover:underline flex items-center gap-1"
                >
                    <ArrowLeft className="w-4 h-4" />
                    返回批改过程
                </button>
            </div>
        );
    }

    return (
        <div className="h-full overflow-y-auto p-6 space-y-6">
            {/* Header with Back Button */}
            <div className="flex items-center justify-between">
                <h2 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
                    <Trophy className="w-6 h-6 text-yellow-500" />
                    批改结果
                </h2>
                <button
                    onClick={() => setCurrentTab('process')}
                    className="text-sm text-gray-500 hover:text-blue-600 flex items-center gap-1 transition-colors"
                >
                    <ArrowLeft className="w-4 h-4" />
                    返回批改过程
                </button>
            </div>

            {/* Statistics Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-4 text-center">
                    <Users className="w-5 h-5 text-blue-500 mx-auto mb-1" />
                    <div className="text-2xl font-bold text-blue-600">{totalStudents}</div>
                    <div className="text-xs text-gray-500">总人数</div>
                </div>
                <div className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-xl p-4 text-center">
                    <TrendingUp className="w-5 h-5 text-green-500 mx-auto mb-1" />
                    <div className="text-2xl font-bold text-green-600">{avgScore.toFixed(1)}</div>
                    <div className="text-xs text-gray-500">平均分</div>
                </div>
                <div className="bg-gradient-to-br from-yellow-50 to-amber-50 rounded-xl p-4 text-center">
                    <Award className="w-5 h-5 text-yellow-500 mx-auto mb-1" />
                    <div className="text-2xl font-bold text-yellow-600">{highestScore}</div>
                    <div className="text-xs text-gray-500">最高分</div>
                </div>
                <div className="bg-gradient-to-br from-purple-50 to-pink-50 rounded-xl p-4 text-center">
                    <Trophy className="w-5 h-5 text-purple-500 mx-auto mb-1" />
                    <div className="text-2xl font-bold text-purple-600">
                        {totalStudents > 0 ? ((passCount / totalStudents) * 100).toFixed(0) : 0}%
                    </div>
                    <div className="text-xs text-gray-500">及格率</div>
                </div>
            </div>

            {/* Results Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {sortedResults.map((result, index) => (
                    <ResultCard
                        key={result.studentName}
                        result={result}
                        rank={index + 1}
                    />
                ))}
            </div>
        </div>
    );
};

export default ResultsView;
