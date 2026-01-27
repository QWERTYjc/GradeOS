'use client';

import React, { useState } from 'react';
import { ConceptNode } from '../types';

interface ConceptBreakdownProps {
  concepts: ConceptNode[];
  title?: string;
  onSelect?: (node: ConceptNode) => void;
  selectedId?: string;
}

const ConceptBreakdown: React.FC<ConceptBreakdownProps> = ({
  concepts,
  title = 'First Principles Map',
  onSelect,
  selectedId,
}) => {
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

  const toggleNode = (id: string) => {
    const next = new Set(expandedNodes);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    setExpandedNodes(next);
  };

  const renderNode = (node: ConceptNode, depth: number = 0) => {
    const nodeKey = node.id || node.name;
    const hasChildren = node.children && node.children.length > 0;
    const isExpanded = expandedNodes.has(nodeKey);
    const isSelected = selectedId === nodeKey;

    return (
      <div key={nodeKey} className="relative">
        {depth > 0 && (
          <div
            className="absolute left-0 top-0 h-full w-4 border-l border-black/10"
            style={{ left: (depth - 1) * 24 + 8 }}
          />
        )}

        <div
          className={`group relative flex items-start gap-3 py-2 ${
            isSelected ? 'bg-black/5' : ''
          }`}
          style={{ paddingLeft: depth * 24 }}
        >
          <div className="relative z-10 flex-shrink-0">
            {hasChildren ? (
              <button
                onClick={() => toggleNode(nodeKey)}
                aria-expanded={isExpanded}
                className={`flex h-6 w-6 items-center justify-center border text-xs font-bold transition-all duration-200 hover:scale-110 ${
                  node.understood
                    ? 'border-black bg-black text-white'
                    : 'border-black/30 bg-white text-black/60'
                }`}
              >
                {isExpanded ? '-' : '+'}
              </button>
            ) : (
              <div
                className={`mt-1 h-4 w-4 border ${
                  node.understood
                    ? 'border-black bg-black'
                    : 'border-black/20 bg-white'
                }`}
              />
            )}
          </div>

          <button
            type="button"
            onClick={() => onSelect?.(node)}
            className="min-w-0 flex-1 text-left"
          >
            <div className="flex items-center gap-2">
              <h4 className={`text-sm font-medium ${node.understood ? 'text-black' : 'text-black/70'}`}>
                {node.name}
              </h4>
              <span
                className={`text-[10px] uppercase tracking-[0.2em] ${
                  node.understood ? 'text-black/60' : 'text-black/40'
                }`}
              >
                {node.understood ? 'Mastered' : 'Review'}
              </span>
            </div>
            <p className="mt-0.5 text-xs text-black/50 line-clamp-2 transition-all group-hover:line-clamp-none">
              {node.description}
            </p>
          </button>
        </div>

        {hasChildren && isExpanded && (
          <div className="animate-expandIn">
            {node.children!.map((child) => renderNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  const countNodes = (nodes: ConceptNode[]): { total: number; understood: number } => {
    let total = 0;
    let understood = 0;

    const traverse = (nodeList: ConceptNode[]) => {
      for (const node of nodeList) {
        total += 1;
        if (node.understood) understood += 1;
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
    <div className="space-y-4">
      <div className="flex items-center justify-between border-b border-black/10 pb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center border border-black/10 bg-white">
            <svg className="h-4 w-4 text-black/70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
          </div>
          <h3 className="text-sm font-semibold text-black">{title}</h3>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-black/50">
            {stats.understood}/{stats.total} nodes
          </span>
          <div className="h-1 w-24 bg-black/10">
            <div className="h-full bg-black transition-all duration-500" style={{ width: `${progress}%` }} />
          </div>
        </div>
      </div>

      <div className="space-y-1">
        {concepts.map((concept) => renderNode(concept, 0))}
      </div>

      <div className="flex items-center gap-4 border-t border-black/10 pt-3 text-xs text-black/50">
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 bg-black" />
          <span>Mastered</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 border border-black/20 bg-white" />
          <span>Review</span>
        </div>
      </div>
    </div>
  );
};

export default ConceptBreakdown;
