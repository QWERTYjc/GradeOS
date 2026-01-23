'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { I18N } from '../constants';
import { EnhancedChatMessage, Language } from '../types';
import { assistantApi } from '@/services/api';
import { useAuthStore } from '@/store/authStore';
import FocusMode from './FocusMode';
import MasteryIndicator from './MasteryIndicator';
import ConceptBreakdown from './ConceptBreakdown';

interface Props {
  lang?: Language;
}

const AIChat: React.FC<Props> = ({ lang }) => {
  const resolvedLang = useMemo<Language>(() => {
    if (lang) return lang;
    if (typeof navigator !== 'undefined') {
      return navigator.language.toLowerCase().startsWith('zh') ? 'zh' : 'en';
    }
    return 'en';
  }, [lang]);

  const t = I18N[resolvedLang];
  const [messages, setMessages] = useState<EnhancedChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [focusModeActive, setFocusModeActive] = useState(false);
  const [currentFocusQuestion, setCurrentFocusQuestion] = useState('');
  const { user } = useAuthStore();

  useEffect(() => {
    setMessages([
      {
        role: 'assistant',
        content: t.chatIntro.replace(/[*#]/g, ''),
        timestamp: new Date(),
      },
    ]);
  }, [resolvedLang, t.chatIntro]);

  const handleSend = async (userMsgContent: string) => {
    if (!userMsgContent.trim() || isStreaming) return;
    if (!user?.id) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: t.brainFreeze, timestamp: new Date() },
      ]);
      return;
    }

    setInput('');
    setIsStreaming(true);

    setMessages((prev) => [
      ...prev,
      { role: 'user', content: userMsgContent, timestamp: new Date() },
    ]);

    try {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: '', timestamp: new Date() },
      ]);

      const history: Array<{ role: 'user' | 'assistant'; content: string }> = [
        ...messages,
        { role: 'user' as const, content: userMsgContent, timestamp: new Date() },
      ]
        .filter((msg) => msg.content)
        .slice(-6)
        .map((msg) => ({ role: msg.role as 'user' | 'assistant', content: msg.content }));

      const response = await assistantApi.chat({
        student_id: user.id,
        class_id: user.classIds?.[0],
        message: userMsgContent,
        history,
        session_mode: 'learning',
      });

      setMessages((prev) => {
        const next = [...prev];
        const lastMessage = next[next.length - 1] as EnhancedChatMessage;
        if (lastMessage.role === 'assistant') {
          lastMessage.content = response.content;
          lastMessage.mastery = response.mastery;
          lastMessage.conceptBreakdown = response.concept_breakdown;
          lastMessage.nextQuestion = response.next_question;
          lastMessage.focusMode = response.focus_mode;
          lastMessage.responseType = response.response_type as any;
        }
        return next;
      });

      if (response.focus_mode && response.next_question) {
        setTimeout(() => {
          setCurrentFocusQuestion(response.next_question!);
          setFocusModeActive(true);
        }, 1500);
      } else {
        setFocusModeActive(false);
      }
    } catch (error) {
      console.error('Chat Error:', error);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: t.brainFreeze, timestamp: new Date() },
      ]);
    } finally {
      setIsStreaming(false);
    }
  };

  const handleInputSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSend(input);
  };

  const latestAssistant = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i].role === 'assistant') return messages[i];
    }
    return undefined;
  }, [messages]);

  const latestUser = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i].role === 'user') return messages[i];
    }
    return undefined;
  }, [messages]);

  const progressSnapshots = useMemo(
    () => messages.filter((msg) => msg.role === 'assistant' && msg.mastery).slice(-6),
    [messages],
  );

  const displayContent =
    latestAssistant?.content?.trim() || (isStreaming ? 'Thinking...' : t.chatIntro.replace(/[*#]/g, ''));

  return (
    <div className="relative min-h-[calc(100vh-12rem)] bg-white text-black overflow-hidden">
      <div className="assistant-grid absolute inset-0" aria-hidden="true" />
      <div className="assistant-halo absolute -top-24 left-1/2 h-[420px] w-[420px] -translate-x-1/2" aria-hidden="true" />
      <div className="assistant-scanline absolute inset-x-0 top-0" aria-hidden="true" />

      {focusModeActive && (
        <FocusMode
          question={currentFocusQuestion}
          onAnswer={(ans) => {
            setFocusModeActive(false);
            handleSend(ans);
          }}
          onExit={() => setFocusModeActive(false)}
          isLoading={isStreaming}
        />
      )}

      <div className="relative z-10 flex min-h-[calc(100vh-12rem)] flex-col py-10">
        <div className="flex flex-wrap items-center justify-between gap-4 text-[10px] font-semibold uppercase tracking-[0.45em] text-black/60">
          <span>GradeOS Socratic Agent</span>
          <span className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${isStreaming ? 'bg-black animate-pulse' : 'bg-black/40'}`} />
            {isStreaming ? 'Thinking' : 'Ready'}
          </span>
        </div>

        <div className="mt-10 grid flex-1 items-start gap-10 lg:grid-cols-[minmax(0,1fr)_280px]">
          <section className="flex h-full flex-col items-center justify-center text-center">
            {latestUser && (
              <div className="max-w-2xl text-black/50">
                <div className="text-[10px] font-semibold uppercase tracking-[0.4em]">You asked</div>
                <div className="mt-3 text-sm leading-relaxed text-black/70">{latestUser.content}</div>
              </div>
            )}

            <div className="mt-6 max-w-3xl text-3xl font-light leading-relaxed md:text-4xl">
              {displayContent}
            </div>

            {latestAssistant?.nextQuestion && !latestAssistant.focusMode && (
              <div className="mt-8 w-full max-w-2xl rounded-2xl border border-black/10 bg-white/80 px-6 py-4 text-left shadow-sm">
                <div className="text-[10px] font-semibold uppercase tracking-[0.4em] text-black/50">
                  Socratic prompt
                </div>
                <div className="mt-3 text-lg font-medium text-black">
                  {latestAssistant.nextQuestion}
                </div>
              </div>
            )}

            {isStreaming && (
              <div className="mt-6 text-[10px] font-semibold uppercase tracking-[0.4em] text-black/40">
                Processing
              </div>
            )}
          </section>

          <aside className="space-y-6">
            <div className="rounded-2xl border border-black/10 bg-white/80 p-4 shadow-sm">
              <div className="text-[10px] font-semibold uppercase tracking-[0.4em] text-black/50">
                Mastery snapshot
              </div>
              <div className="mt-4 flex min-h-[160px] items-center justify-center">
                {latestAssistant?.mastery ? (
                  <MasteryIndicator
                    {...latestAssistant.mastery}
                    size="sm"
                    showDetails={true}
                  />
                ) : (
                  <p className="text-sm text-black/40 text-center">
                    Share a concept to begin tracking mastery.
                  </p>
                )}
              </div>
            </div>

            {latestAssistant?.conceptBreakdown && latestAssistant.conceptBreakdown.length > 0 ? (
              <ConceptBreakdown
                concepts={latestAssistant.conceptBreakdown}
                title="First Principles Map"
              />
            ) : (
              <div className="rounded-2xl border border-black/10 bg-white/80 p-4 text-sm text-black/40 shadow-sm">
                First principles map will appear after the next explanation.
              </div>
            )}

            <div className="rounded-2xl border border-black/10 bg-white/80 p-4 shadow-sm">
              <div className="text-[10px] font-semibold uppercase tracking-[0.4em] text-black/50">
                Progress trace
              </div>
              <div className="mt-4 flex h-20 items-end gap-3">
                {progressSnapshots.length > 0 ? (
                  progressSnapshots.map((snapshot, idx) => {
                    const score = snapshot.mastery?.score ?? 0;
                    const height = Math.max(12, Math.min(72, Math.round(score * 0.7)));
                    return (
                      <div key={`${snapshot.timestamp.getTime()}-${idx}`} className="flex flex-col items-center gap-2">
                        <div
                          className="w-2 rounded-full bg-black/80 transition-all"
                          style={{ height }}
                        />
                        <div className="text-[10px] text-black/40">{score}</div>
                      </div>
                    );
                  })
                ) : (
                  <div className="text-sm text-black/40">No mastery snapshots yet.</div>
                )}
              </div>
            </div>
          </aside>
        </div>

        <form onSubmit={handleInputSubmit} className="mt-10">
          <div className="flex flex-col gap-3 rounded-2xl border border-black/10 bg-white/80 px-4 py-3 shadow-sm md:flex-row md:items-center">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={t.chatPlaceholder}
              className="flex-1 bg-transparent text-base text-black placeholder:text-black/40 focus:outline-none"
              disabled={isStreaming}
            />
            <button
              type="submit"
              disabled={!input.trim() || isStreaming}
              className={`rounded-xl px-6 py-2 text-sm font-semibold uppercase tracking-[0.25em] transition-all ${
                input.trim() && !isStreaming
                  ? 'bg-black text-white hover:bg-black/90'
                  : 'bg-black/10 text-black/30'
              }`}
            >
              {isStreaming ? 'Thinking' : 'Send'}
            </button>
          </div>
          <div className="mt-3 text-[10px] uppercase tracking-[0.3em] text-black/40">
            {t.disclaimer}
          </div>
        </form>
      </div>
    </div>
  );
};

export default AIChat;
