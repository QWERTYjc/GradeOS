'use client';

import React, { useState } from 'react';
import { useConsoleStore, StudentResult, QuestionResult } from '@/store/consoleStore';
import clsx from 'clsx';
import { Trophy, TrendingUp, Users, Award, ArrowLeft, ChevronDown, ChevronUp, CheckCircle, XCircle, Download } from 'lucide-react';

interface ResultCardProps {
    result: StudentResult;
    rank: number;
    onExpand: () => void;
    isExpanded: boolean;
}

const QuestionDetail: React.FC<{ question: QuestionResult }> = ({ question }) => {
    const percentage = question.maxScore > 0 ? (question.score / question.maxScore) * 100 : 0;
    
    return (
        <div className="border-l-2 border-gray-200 pl-3 py-2">
            <div className="flex items-center justify-between">
                <span className="font-medium text-gray-700">第 {question.questionId} 题</span>
                <span className={clsx(
                    'text-sm font-semibold',
                    percentage >= 60 ? 'text-green-600' : 'text-red-600'
                )}>
                    {question.score} / {question.maxScore}
                </span>
            </div>
            {question.feedback && (
                <p className="text-xs text-gray-500 mt-1">{question.feedback}</p>
            )}
            {question.scoringPoints && question.scoringPoints.length > 0 && (
                <div className="mt-2 space-y-1">
                    {question.scoringPoints.map((sp, idx) => (
                        <div key={idx} className="flex items-start gap-2 text-xs">
                            {sp.isCorrect ? (
                                <CheckCircle className="w-3 h-3 text-green-500 mt-0.5 flex-shrink-0" />
                            ) : (
                                <XCircle className="w-3 h-3 text-red-500 mt-0.5 flex-shrink-0" />
                            )}
                            <div className="flex-1">
                                <span className={clsx(
                                    sp.isCorrect ? 'text-green-700' : 'text-red-700'
                                )}>
                                    [{sp.score}/{sp.maxScore}] {sp.description}
                                </span>
                                {sp.explanation && (
                                    <p className="text-gray-500 mt-0.5">{sp.explanation}</p>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

const ResultCard: React.FC<ResultCardProps> = ({ result, rank, onExpand, isExpanded }) => {
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
            'rounded-2xl p-6 transition-all duration-300 hover:shadow-lg',
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
                {result.questionResults && result.questionResults.length > 0 && (
                    <button
                        onClick={onExpand}
                        className="p-1 hover:bg-white/50 rounded-lg transition-colors"
                    >
                        {isExpanded ? (
                            <ChevronUp className="w-5 h-5 text-gray-500" />
                        ) : (
                            <ChevronDown className="w-5 h-5 text-gray-500" />
                        )}
                    </button>
                )}
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

            {/* Expanded Question Details */}
            {isExpanded && result.questionResults && (
                <div className="mt-4 pt-4 border-t border-gray-200 space-y-3 max-h-[300px] overflow-y-auto">
                    <h4 className="text-sm font-semibold text-gray-600">各题详情</h4>
                    {result.questionResults.map((q, idx) => (
                        <QuestionDetail key={idx} question={q} />
                    ))}
                </div>
            )}
        </div>
    );
};

export const ResultsView: React.FC = () => {
    const { finalResults, setCurrentTab, workflowNodes } = useConsoleStore();
    const [expandedStudent, setExpandedStudent] = useState<string | null>(null);

    // 从 workflowNodes 中获取所有 Agent 的详细结果（如果 finalResults 为空）
    const gradingNode = workflowNodes.find(n => n.id === 'grading');
    const agentResults = gradingNode?.children?.filter(c => c.status === 'completed' && c.output) || [];

    // 优先使用 finalResults，否则从 agents 构建
    const results: StudentResult[] = finalResults.length > 0
        ? finalResults
        : agentResults.map(agent => ({
            studentName: agent.label,
            score: agent.output?.score || 0,
            maxScore: agent.output?.maxScore || 100,
            questionResults: agent.output?.questionResults
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

    // 导出为 CSV
    const handleExportCSV = () => {
        const headers = ['排名', '学生', '得分', '满分', '得分率', '等级'];
        const rows = sortedResults.map((r, idx) => {
            const percentage = (r.score / r.maxScore) * 100;
            let grade = '待提升';
            if (percentage >= 85) grade = '优秀';
            else if (percentage >= 70) grade = '良好';
            else if (percentage >= 60) grade = '及格';
            else grade = '不及格';
            return [idx + 1, r.studentName, r.score, r.maxScore, `${percentage.toFixed(1)}%`, grade];
        });
        
        const csvContent = [headers, ...rows].map(row => row.join(',')).join('\n');
        const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `批改结果_${new Date().toLocaleDateString()}.csv`;
        link.click();
        URL.revokeObjectURL(url);
    };

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
                <div className="flex items-center gap-3">
                    <button
                        onClick={handleExportCSV}
                        className="text-sm text-gray-600 hover:text-green-600 flex items-center gap-1 transition-colors bg-gray-100 hover:bg-green-50 px-3 py-1.5 rounded-lg"
                    >
                        <Download className="w-4 h-4" />
                        导出 CSV
                    </button>
                    <button
                        onClick={() => setCurrentTab('process')}
                        className="text-sm text-gray-500 hover:text-blue-600 flex items-center gap-1 transition-colors"
                    >
                        <ArrowLeft className="w-4 h-4" />
                        返回批改过程
                    </button>
                </div>
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
                        isExpanded={expandedStudent === result.studentName}
                        onExpand={() => setExpandedStudent(
                            expandedStudent === result.studentName ? null : result.studentName
                        )}
                    />
                ))}
            </div>
        </div>
    );
};

export default ResultsView;
