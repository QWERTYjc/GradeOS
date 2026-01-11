'use client';

import React, { useMemo, useState } from 'react';
import clsx from 'clsx';
import { useConsoleStore } from '@/store/consoleStore';

type StreamTab = 'output' | 'thinking';

const tabLabels: Record<StreamTab, string> = {
  output: 'Output',
  thinking: 'Thinking',
};

export default function LLMThoughtsPanel() {
  const llmThoughts = useConsoleStore((state) => state.llmThoughts);
  const [activeTab, setActiveTab] = useState<StreamTab>('output');

  const thoughts = useMemo(() => {
    const filtered = llmThoughts.filter((t) => (t.streamType || 'output') === activeTab);
    return filtered.sort((a, b) => a.timestamp - b.timestamp);
  }, [llmThoughts, activeTab]);

  const totalCount = llmThoughts.length;

  return (
    <div className="h-full flex flex-col rounded-2xl border border-gray-200/70 bg-white/80 backdrop-blur-md shadow-inner">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200/60">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-gray-400">AI Live Streams</p>
          <p className="text-sm font-semibold text-gray-800">
            {totalCount > 0 ? `${totalCount} streams` : 'Waiting for AI streams...'}
          </p>
        </div>
        <div className="flex rounded-full bg-gray-100 p-1 text-xs font-medium">
          {(Object.keys(tabLabels) as StreamTab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={clsx(
                'px-3 py-1 rounded-full transition-colors',
                activeTab === tab ? 'bg-white text-gray-900 shadow' : 'text-gray-500 hover:text-gray-800'
              )}
            >
              {tabLabels[tab]}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 text-sm text-gray-700">
        {thoughts.length === 0 ? (
          <div className="text-gray-400 italic">No stream output yet.</div>
        ) : (
          thoughts.map((thought) => (
            <div key={thought.id} className="rounded-xl border border-gray-200/70 bg-white p-3">
              <div className="flex items-center justify-between text-xs text-gray-500 mb-2">
                <span className="font-medium text-gray-700">{thought.nodeName || thought.nodeId}</span>
                <span>{new Date(thought.timestamp).toLocaleTimeString()}</span>
              </div>
              <div className="whitespace-pre-wrap leading-relaxed text-gray-800">
                {thought.content}
              </div>
              {!thought.isComplete && (
                <div className="mt-2 text-[11px] text-blue-500">Streaming...</div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
