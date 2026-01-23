'use client';

import React, { useState } from 'react';

interface ConceptNode {
    id: string;
    name: string;
    description: string;
    understood: boolean;
    children?: ConceptNode[];
}

interface ConceptBreakdownProps {
    concepts: ConceptNode[];
    title?: string;
}

/**
 * 概念分解可视化组件
 * 展示第一性原理的概念树状图
 */
const ConceptBreakdown: React.FC<ConceptBreakdownProps> = ({
    concepts,
    title = '概念分解'
}) => {
    const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

    const toggleNode = (id: string) => {
        const newExpanded = new Set(expandedNodes);
        if (newExpanded.has(id)) {
            newExpanded.delete(id);
        } else {
            newExpanded.add(id);
        }
        setExpandedNodes(newExpanded);
    };

    const renderNode = (node: ConceptNode, depth: number = 0) => {
        const hasChildren = node.children && node.children.length > 0;
        const isExpanded = expandedNodes.has(node.id);

        return (
            <div key={node.id} className="relative">
                {/* 连接线 */}
                {depth > 0 && (
                    <div
                        className="absolute left-0 top-0 w-4 h-full border-l-2 border-gray-200"
                        style={{ left: (depth - 1) * 24 + 8 }}
                    />
                )}

                {/* 节点 */}
                <div
                    className="relative flex items-start gap-3 py-2 group"
                    style={{ paddingLeft: depth * 24 }}
                >
                    {/* 展开/收起按钮或节点指示器 */}
                    <div className="relative z-10 flex-shrink-0">
                        {hasChildren ? (
                            <button
                                onClick={() => toggleNode(node.id)}
                                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold
                  transition-all duration-200 hover:scale-110
                  ${node.understood
                                        ? 'bg-green-100 text-green-600 border-2 border-green-300'
                                        : 'bg-gray-100 text-gray-500 border-2 border-gray-300'
                                    }`}
                            >
                                {isExpanded ? '−' : '+'}
                            </button>
                        ) : (
                            <div
                                className={`w-4 h-4 rounded-full border-2 mt-1
                  ${node.understood
                                        ? 'bg-green-400 border-green-500'
                                        : 'bg-gray-200 border-gray-300'
                                    }`}
                            />
                        )}
                    </div>

                    {/* 节点内容 */}
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                            <h4 className={`font-medium text-sm ${node.understood ? 'text-green-700' : 'text-gray-800'}`}>
                                {node.name}
                            </h4>
                            {node.understood && (
                                <span className="text-green-500 text-xs">✓ 已理解</span>
                            )}
                        </div>
                        <p className="text-xs text-gray-500 mt-0.5 line-clamp-2 group-hover:line-clamp-none transition-all">
                            {node.description}
                        </p>
                    </div>
                </div>

                {/* 子节点 */}
                {hasChildren && isExpanded && (
                    <div className="animate-expandIn">
                        {node.children!.map(child => renderNode(child, depth + 1))}
                    </div>
                )}
            </div>
        );
    };

    // 统计理解进度
    const countNodes = (nodes: ConceptNode[]): { total: number; understood: number } => {
        let total = 0;
        let understood = 0;

        const traverse = (nodeList: ConceptNode[]) => {
            for (const node of nodeList) {
                total++;
                if (node.understood) understood++;
                if (node.children) traverse(node.children);
            }
        };

        traverse(nodes);
        return { total, understood };
    };

    const stats = countNodes(concepts);
    const progress = stats.total > 0 ? Math.round((stats.understood / stats.total) * 100) : 0;

    if (concepts.length === 0) {
        return null;
    }

    return (
        <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            {/* 标题和进度 */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center">
                        <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                    </div>
                    <h3 className="font-semibold text-gray-800">{title}</h3>
                </div>

                <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500">
                        {stats.understood}/{stats.total} 概念
                    </span>
                    <div className="w-20 h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div
                            className="h-full bg-green-500 transition-all duration-500"
                            style={{ width: `${progress}%` }}
                        />
                    </div>
                </div>
            </div>

            {/* 概念树 */}
            <div className="space-y-1">
                {concepts.map(concept => renderNode(concept, 0))}
            </div>

            {/* 图例 */}
            <div className="flex items-center gap-4 mt-4 pt-3 border-t border-gray-100 text-xs text-gray-500">
                <div className="flex items-center gap-1">
                    <div className="w-3 h-3 rounded-full bg-green-400 border-2 border-green-500" />
                    <span>已理解</span>
                </div>
                <div className="flex items-center gap-1">
                    <div className="w-3 h-3 rounded-full bg-gray-200 border-2 border-gray-300" />
                    <span>待掌握</span>
                </div>
            </div>

            <style jsx>{`
        @keyframes expandIn {
          from { opacity: 0; max-height: 0; }
          to { opacity: 1; max-height: 500px; }
        }
        .animate-expandIn {
          animation: expandIn 0.3s ease-out;
          overflow: hidden;
        }
      `}</style>
        </div>
    );
};

export default ConceptBreakdown;
