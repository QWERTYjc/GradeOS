'use client';

import React, { useMemo, useState, useEffect, useRef } from 'react';
import clsx from 'clsx';
import { useConsoleStore } from '@/store/consoleStore';
import { GlassCard } from '@/components/design-system/GlassCard';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, Terminal, Activity, BrainCircuit, X } from 'lucide-react';

type StreamTab = 'output' | 'thinking';

const tabLabels: Record<StreamTab, string> = {
  output: 'Output',
  thinking: 'Thinking',
};

interface LLMThoughtsPanelProps {
  className?: string;
  onClose?: () => void;
}

export default function LLMThoughtsPanel({ className, onClose }: LLMThoughtsPanelProps) {
  const llmThoughts = useConsoleStore((state) => state.llmThoughts);
  const selectedAgentId = useConsoleStore((state) => state.selectedAgentId);
  const selectedNodeId = useConsoleStore((state) => state.selectedNodeId);
  const workflowNodes = useConsoleStore((state) => state.workflowNodes);
  const [activeTab, setActiveTab] = useState<StreamTab>('output');
  const scrollRef = useRef<HTMLDivElement>(null);

  const activeLabel = useMemo(() => {
    if (!selectedAgentId && !selectedNodeId) return 'All Streams';
    if (selectedAgentId) {
      const agentNode = workflowNodes.find((node) =>
        node.children?.some((agent) => agent.id === selectedAgentId)
      );
      const agent = agentNode?.children?.find((item) => item.id === selectedAgentId);
      return agent?.label || selectedAgentId;
    }
    const node = workflowNodes.find((item) => item.id === selectedNodeId);
    return node?.label || selectedNodeId || 'All Streams';
  }, [selectedAgentId, selectedNodeId, workflowNodes]);

  const thoughts = useMemo(() => {
    const filteredByTarget = llmThoughts.filter((t) => {
      if (selectedAgentId) {
        return t.agentId === selectedAgentId;
      }
      if (selectedNodeId) {
        return t.nodeId === selectedNodeId;
      }
      return true;
    });
    const filteredByTab = filteredByTarget.filter((t) => (t.streamType || 'output') === activeTab);
    const ordered = filteredByTab.sort((a, b) => a.timestamp - b.timestamp);
    return ordered.slice(-40);
  }, [llmThoughts, activeTab, selectedAgentId, selectedNodeId]);

  const totalCount = llmThoughts.length;

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [thoughts]);

  return (
    <GlassCard
      className={clsx("h-full min-h-0 flex flex-col p-0 overflow-hidden", className)}
      hoverEffect={false}
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 bg-white/50 backdrop-blur-md z-10">
        <div>
          <div className="flex items-center gap-2 mb-0.5">
            <Activity className="w-3 h-3 text-indigo-500" />
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">AI Live Stream</p>
          </div>
          <p className="text-sm font-bold text-slate-800 flex items-center gap-2">
            {activeLabel}
            {totalCount > 0 && (
              <span className="bg-slate-100 text-slate-500 text-[10px] px-1.5 py-0.5 rounded font-mono">
                {totalCount}
              </span>
            )}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex rounded-lg bg-slate-100/80 p-1 relative">
            {(Object.keys(tabLabels) as StreamTab[]).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={clsx(
                  'relative px-3 py-1 text-xs font-bold rounded-md transition-all z-10',
                  activeTab === tab ? 'text-indigo-600' : 'text-slate-500 hover:text-slate-700'
                )}
              >
                {activeTab === tab && (
                  <motion.div
                    layoutId="activeTab"
                    className="absolute inset-0 bg-white rounded-md shadow-sm border border-slate-200/50"
                    transition={{ type: "spring", stiffness: 400, damping: 30 }}
                  />
                )}
                <span className="relative z-10 flex items-center gap-1.5">
                  {tab === 'thinking' ? <BrainCircuit className="w-3 h-3" /> : <Terminal className="w-3 h-3" />}
                  {tabLabels[tab]}
                </span>
              </button>
            ))}
          </div>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              aria-label="Close stream panel"
              className="h-8 w-8 rounded-lg border border-slate-200/60 bg-white/70 text-slate-400 transition-colors hover:text-slate-700 hover:bg-white"
            >
              <X className="w-4 h-4 mx-auto" />
            </button>
          )}
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto px-4 py-3 space-y-3 custom-scrollbar bg-slate-50/30">
        <AnimatePresence initial={false}>
          {thoughts.length === 0 ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="h-full flex flex-col items-center justify-center text-slate-400 gap-2"
            >
              <Sparkles className="w-8 h-8 opacity-30" />
              <span className="text-xs font-medium italic">No signal yet...</span>
            </motion.div>
          ) : (
            thoughts.map((thought) => (
              <motion.div
                key={thought.id}
                initial={{ opacity: 0, y: 10, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                className="rounded-xl border border-white bg-white/60 shadow-sm p-3 hover:bg-white/80 transition-colors"
              >
                <div className="flex items-center justify-between text-[11px] text-slate-400 mb-2 font-mono">
                  <span className="font-bold text-indigo-600/80 bg-indigo-50 px-1.5 py-0.5 rounded">
                    {thought.nodeName || thought.nodeId}
                  </span>
                  <span>{new Date(thought.timestamp).toLocaleTimeString()}</span>
                </div>
                <div className="text-xs leading-relaxed text-slate-700 font-mono whitespace-pre-wrap break-words">
                  {thought.content}
                </div>
                {!thought.isComplete && (
                  <div className="mt-2 flex items-center gap-2 text-[10px] text-indigo-500 font-bold uppercase tracking-wider">
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
                    </span>
                    Streaming...
                  </div>
                )}
              </motion.div>
            ))
          )}
        </AnimatePresence>
      </div>
    </GlassCard>
  );
}
