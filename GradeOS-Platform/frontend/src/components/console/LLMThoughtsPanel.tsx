'use client';

import React, { useMemo, useState, useEffect, useRef, useCallback } from 'react';
import clsx from 'clsx';
import { useConsoleStore } from '@/store/consoleStore';
import { motion, AnimatePresence } from 'framer-motion';
import { Radio, Sparkles, ChevronDown, Pause, Play } from 'lucide-react';

interface LLMThoughtsPanelProps {
  className?: string;
  onClose?: () => void;
}

export default function LLMThoughtsPanel({ className, onClose }: LLMThoughtsPanelProps) {
  const llmThoughts = useConsoleStore((state) => state.llmThoughts);
  const selectedNodeId = useConsoleStore((state) => state.selectedNodeId);
  const workflowNodes = useConsoleStore((state) => state.workflowNodes);
  
  const [autoScroll, setAutoScroll] = useState(true);
  const [selectedStudent, setSelectedStudent] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const lastScrollHeight = useRef(0);

  // 获取当前节点的显示名称
  const currentNodeName = useMemo(() => {
    if (!selectedNodeId) return 'AI Stream';
    const node = workflowNodes.find((n) => n.id === selectedNodeId);
    return node?.label || selectedNodeId;
  }, [selectedNodeId, workflowNodes]);

  // 过滤当前节点的思维流
  const filteredThoughts = useMemo(() => {
    let thoughts = llmThoughts;
    
    // 按节点过滤
    if (selectedNodeId) {
      thoughts = thoughts.filter((t) => t.nodeId === selectedNodeId);
    }
    
    // 按学生过滤
    if (selectedStudent) {
      thoughts = thoughts.filter((t) => {
        const label = t.agentLabel || t.agentId || '';
        return label === selectedStudent || label.startsWith(`${selectedStudent} -`);
      });
    }
    
    // 只显示 output 类型（主要内容）
    return thoughts
      .filter((t) => (t.streamType || 'output') === 'output')
      .sort((a, b) => a.timestamp - b.timestamp);
  }, [llmThoughts, selectedNodeId, selectedStudent]);

  // 提取学生列表
  const students = useMemo(() => {
    const studentSet = new Set<string>();
    llmThoughts
      .filter((t) => !selectedNodeId || t.nodeId === selectedNodeId)
      .forEach((t) => {
        const label = t.agentLabel || t.agentId;
        if (label) {
          // 提取学生名（去掉页码后缀）
          const match = label.match(/^(.+?)\s*(?:-\s*P\d+)?$/);
          if (match) studentSet.add(match[1]);
        }
      });
    return Array.from(studentSet).sort();
  }, [llmThoughts, selectedNodeId]);

  // 检查是否有正在进行的流
  const hasActiveStream = useMemo(() => {
    return filteredThoughts.some((t) => !t.isComplete);
  }, [filteredThoughts]);

  // 自动滚动到底部
  const scrollToBottom = useCallback(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, []);

  // 监听内容变化，自动滚动
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      const newHeight = scrollRef.current.scrollHeight;
      if (newHeight !== lastScrollHeight.current) {
        scrollToBottom();
        lastScrollHeight.current = newHeight;
      }
    }
  }, [filteredThoughts, autoScroll, scrollToBottom]);

  // 处理滚动事件
  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 50;
    setAutoScroll(isNearBottom);
  }, []);

  return (
    <div className={clsx(
      "h-full flex flex-col bg-gradient-to-b from-slate-900 to-slate-950 rounded-xl overflow-hidden border border-slate-800/50",
      className
    )}>
      {/* Header */}
      <div className="flex-shrink-0 px-4 py-3 border-b border-slate-800/50 bg-slate-900/80 backdrop-blur-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative">
              <Radio className="w-4 h-4 text-emerald-400" />
              {hasActiveStream && (
                <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-emerald-400 rounded-full animate-ping" />
              )}
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">{currentNodeName}</h3>
              <p className="text-[10px] text-slate-500 uppercase tracking-wider">
                {hasActiveStream ? 'Live Stream' : 'Stream Complete'}
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            {/* 自动滚动控制 */}
            <button
              type="button"
              onClick={() => {
                setAutoScroll(!autoScroll);
                if (!autoScroll) scrollToBottom();
              }}
              className={clsx(
                "p-1.5 rounded-lg transition-all",
                autoScroll 
                  ? "bg-emerald-500/20 text-emerald-400" 
                  : "bg-slate-800 text-slate-500 hover:text-slate-300"
              )}
              title={autoScroll ? "Auto-scroll ON" : "Auto-scroll OFF"}
            >
              {autoScroll ? <ChevronDown className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
            </button>
            
            {/* 关闭按钮 */}
            {onClose && (
              <button
                type="button"
                onClick={onClose}
                className="p-1.5 rounded-lg bg-slate-800 text-slate-500 hover:text-slate-300 hover:bg-slate-700 transition-all"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
        </div>
        
        {/* 学生筛选器 */}
        {students.length > 1 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => setSelectedStudent(null)}
              className={clsx(
                "px-2.5 py-1 rounded-full text-[10px] font-semibold transition-all",
                !selectedStudent
                  ? "bg-indigo-500 text-white"
                  : "bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700"
              )}
            >
              All
            </button>
            {students.map((student) => (
              <button
                key={student}
                type="button"
                onClick={() => setSelectedStudent(student)}
                className={clsx(
                  "px-2.5 py-1 rounded-full text-[10px] font-semibold transition-all",
                  selectedStudent === student
                    ? "bg-indigo-500 text-white"
                    : "bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700"
                )}
              >
                {student}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Content */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden p-4 space-y-3"
        style={{ scrollBehavior: autoScroll ? 'smooth' : 'auto' }}
      >
        <AnimatePresence initial={false}>
          {filteredThoughts.length === 0 ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="h-full flex flex-col items-center justify-center text-slate-600 gap-3 py-12"
            >
              <Sparkles className="w-10 h-10 opacity-30" />
              <p className="text-sm font-medium">Waiting for AI stream...</p>
            </motion.div>
          ) : (
            filteredThoughts.map((thought, index) => (
              <motion.div
                key={thought.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
                className="group"
              >
                {/* 消息头 */}
                <div className="flex items-center gap-2 mb-1.5">
                  {thought.agentLabel && (
                    <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 text-[10px] font-semibold">
                      {thought.agentLabel}
                    </span>
                  )}
                  <span className="text-[10px] text-slate-600 font-mono">
                    {new Date(thought.timestamp).toLocaleTimeString()}
                  </span>
                  {!thought.isComplete && (
                    <span className="flex items-center gap-1 text-[10px] text-amber-400 font-semibold">
                      <span className="w-1.5 h-1.5 bg-amber-400 rounded-full animate-pulse" />
                      streaming
                    </span>
                  )}
                </div>
                
                {/* 消息内容 */}
                <div className={clsx(
                  "rounded-lg p-3 text-sm leading-relaxed font-mono transition-all",
                  "bg-slate-800/50 text-slate-300 border border-slate-700/50",
                  !thought.isComplete && "border-amber-500/30"
                )}>
                  <pre className="whitespace-pre-wrap break-words text-xs">
                    {thought.content}
                  </pre>
                </div>
              </motion.div>
            ))
          )}
        </AnimatePresence>
        
        {/* 滚动到底部的指示器 */}
        {!autoScroll && filteredThoughts.length > 0 && (
          <motion.button
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            type="button"
            onClick={() => {
              setAutoScroll(true);
              scrollToBottom();
            }}
            className="sticky bottom-2 left-1/2 -translate-x-1/2 px-4 py-2 rounded-full bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-500/25 hover:bg-indigo-400 transition-all flex items-center gap-2"
          >
            <ChevronDown className="w-4 h-4" />
            Jump to latest
          </motion.button>
        )}
      </div>
      
      {/* Footer 状态栏 */}
      <div className="flex-shrink-0 px-4 py-2 border-t border-slate-800/50 bg-slate-900/50">
        <div className="flex items-center justify-between text-[10px] text-slate-500">
          <span>{filteredThoughts.length} messages</span>
          {hasActiveStream && (
            <span className="flex items-center gap-1.5 text-emerald-400">
              <Play className="w-3 h-3" />
              Receiving...
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
