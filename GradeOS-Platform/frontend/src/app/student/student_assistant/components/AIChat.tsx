import React, { useState, useRef, useEffect } from 'react';
import { ICONS, I18N } from '../constants';
import { EnhancedChatMessage, Language } from '../types';
import { assistantApi } from '@/services/api';
import { useAuthStore } from '@/store/authStore';
import FocusMode from './FocusMode';
import MasteryIndicator from './MasteryIndicator';
import ConceptBreakdown from './ConceptBreakdown';

interface Props {
  lang: Language;
}

const AIChat: React.FC<Props> = ({ lang }) => {
  const t = I18N[lang];
  const [messages, setMessages] = useState<EnhancedChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [focusModeActive, setFocusModeActive] = useState(false);
  const [currentFocusQuestion, setCurrentFocusQuestion] = useState('');
  const { user } = useAuthStore();

  const scrollRef = useRef<HTMLDivElement>(null);

  // Initialize with welcome message
  useEffect(() => {
    setMessages([{
      role: 'assistant',
      content: t.chatIntro.replace(/[*#]/g, ''),
      timestamp: new Date()
    }]);
  }, [lang, t.chatIntro]);

  // Auto-scroll
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isStreaming, focusModeActive]);

  const handleSend = async (userMsgContent: string) => {
    if (!userMsgContent.trim() || isStreaming) return;
    if (!user?.id) {
      setMessages(prev => [...prev, { role: 'assistant', content: t.brainFreeze, timestamp: new Date() }]);
      return;
    }

    // 如果在专注模式，先暂时退出
    // setFocusModeActive(false); 
    // 保持专注模式逻辑：如果在专注模式回答，保持专注还是退出？
    // 这里设计为：回答后退出专注模式，等待AI响应，如果AI再次触发专注模式则再次进入

    setInput('');
    setIsStreaming(true);

    // Add User Message
    setMessages(prev => [...prev, { role: 'user', content: userMsgContent, timestamp: new Date() }]);

    try {
      // Add placeholder Assistant Message for streaming
      setMessages(prev => [...prev, { role: 'assistant', content: '', timestamp: new Date() }]);

      const history: Array<{ role: 'user' | 'assistant'; content: string }> = [...messages, { role: 'user' as const, content: userMsgContent, timestamp: new Date() }]
        .filter((msg) => msg.content)
        .slice(-6)
        .map((msg) => ({ role: msg.role as 'user' | 'assistant', content: msg.content }));

      const response = await assistantApi.chat({
        student_id: user.id,
        class_id: user.classIds?.[0],
        message: userMsgContent,
        history,
        session_mode: 'learning', // 默认学习模式
      });

      setMessages(prev => {
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

      // 处理专注模式触发
      if (response.focus_mode && response.next_question) {
        // 延迟一点触发，让用户先看到回答
        setTimeout(() => {
          setCurrentFocusQuestion(response.next_question!);
          setFocusModeActive(true);
        }, 3000);
      } else {
        setFocusModeActive(false);
      }

    } catch (error) {
      console.error('Chat Error:', error);
      setMessages(prev => [...prev, { role: 'assistant', content: t.brainFreeze, timestamp: new Date() }]);
    } finally {
      setIsStreaming(false);
    }
  };

  const handleInputSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSend(input);
  };

  // 渲染消息内容（支持增强组件）
  const renderMessageContent = (msg: EnhancedChatMessage) => {
    return (
      <div className="space-y-4">
        {/* 文本内容 */}
        <div className="prose prose-slate max-w-none break-words leading-7 text-[15px]">
          {msg.content}
        </div>

        {/* 掌握度展示 */}
        {msg.mastery && (
          <div className="mt-4 p-4 bg-gray-50 rounded-xl border border-gray-100">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">本次掌握度评估</span>
            </div>
            <div className="flex justify-center py-2">
              <MasteryIndicator {...msg.mastery} size="sm" showDetails={true} />
            </div>
          </div>
        )}

        {/* 概念分解 */}
        {msg.conceptBreakdown && msg.conceptBreakdown.length > 0 && (
          <div className="mt-4">
            <ConceptBreakdown concepts={msg.conceptBreakdown} />
          </div>
        )}

        {/* 苏格拉底式追问 */}
        {msg.nextQuestion && !msg.focusMode && (
          <div className="mt-4 p-3 bg-blue-50 border border-blue-100 rounded-lg flex items-start gap-3">
            <div className="text-blue-500 mt-1">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <div className="text-xs font-bold text-blue-600 mb-1">思考一下</div>
              <div className="text-sm text-blue-900 font-medium">{msg.nextQuestion}</div>
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] bg-white relative">

      {/* 专注模式 */}
      {focusModeActive && (
        <FocusMode
          question={currentFocusQuestion}
          onAnswer={(ans) => {
            setFocusModeActive(false); // 退出专注模式
            handleSend(ans); // 发送回答
          }}
          onExit={() => setFocusModeActive(false)}
          isLoading={isStreaming}
        />
      )}

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto w-full" ref={scrollRef}>
        <div className="max-w-3xl mx-auto w-full pb-32 pt-8 px-4">

          {/* Header/Intro */}
          {messages.length <= 1 && (
            <div className="flex flex-col items-center justify-center mb-12 opacity-50">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center text-blue-600 mb-4">
                <ICONS.Chat className="w-8 h-8" />
              </div>
              <h3 className="text-xl font-bold text-gray-800">{t.appName} AI</h3>
              <p className="text-sm text-gray-500 mt-2">Your Socratic Study Companion</p>
            </div>
          )}

          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`group w-full text-gray-800 border-b border-black/5 dark:border-white/5 bg-transparent`}
            >
              <div className="text-base gap-4 md:gap-6 md:max-w-2xl lg:max-w-3xl xl:max-w-3xl p-4 md:py-6 flex lg:px-0 m-auto">

                {/* Avatar */}
                <div className="flex-shrink-0 flex flex-col relative items-end">
                  <div className={`w-8 h-8 rounded-sm flex items-center justify-center ${msg.role === 'assistant'
                    ? 'bg-gradient-to-br from-blue-500 to-cyan-400 shadow-sm'
                    : 'bg-gray-200'
                    }`}>
                    {msg.role === 'assistant' ? (
                      <ICONS.Chat className="w-5 h-5 text-white" />
                    ) : (
                      <div className="w-5 h-5 bg-gray-400 rounded-sm" />
                    )}
                  </div>
                </div>

                {/* Content */}
                <div className="relative flex-1 overflow-hidden">
                  <div className="font-semibold text-xs text-gray-400 mb-1 uppercase tracking-wide">
                    {msg.role === 'assistant' ? 'AI Assistant' : 'You'}
                  </div>

                  {msg.role === 'user' ? (
                    <div className="prose prose-slate max-w-none break-words leading-7 text-[15px]">
                      {msg.content}
                    </div>
                  ) : (
                    msg.content || (isStreaming && idx === messages.length - 1) ?
                      renderMessageContent(msg) :
                      <span className="inline-block w-2 h-4 bg-gray-400 animate-pulse ml-1" />
                  )}

                  {isStreaming && idx === messages.length - 1 && !msg.content && (
                    <span className="inline-block w-2 h-4 bg-gray-400 animate-pulse ml-1" />
                  )}
                </div>
              </div>
            </div>
          ))}

          {isStreaming && messages.length > 0 && messages[messages.length - 1].role !== 'assistant' && (
            <div className="group w-full text-gray-800 border-b border-black/5">
              <div className="text-base gap-4 md:gap-6 md:max-w-2xl lg:max-w-3xl xl:max-w-3xl p-4 md:py-6 flex lg:px-0 m-auto">
                <div className="flex-shrink-0 flex flex-col relative items-end">
                  <div className="w-8 h-8 rounded-sm flex items-center justify-center bg-gradient-to-br from-blue-500 to-cyan-400 shadow-sm">
                    <ICONS.Chat className="w-5 h-5 text-white" />
                  </div>
                </div>
                <div className="relative flex-1 overflow-hidden">
                  <div className="font-semibold text-xs text-gray-400 mb-1 uppercase tracking-wide">AI Assistant</div>
                  <div className="flex gap-1">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Input Area */}
      <div className="absolute bottom-0 left-0 w-full bg-gradient-to-t from-white via-white to-transparent pt-10 pb-6 px-4">
        <div className="max-w-3xl mx-auto">
          <form onSubmit={handleInputSubmit} className="relative shadow-xl shadow-blue-900/5 rounded-2xl bg-white border border-gray-200 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100 transition-all">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={t.chatPlaceholder}
              className="w-full pl-5 pr-12 py-4 bg-transparent border-none focus:outline-none text-base text-gray-800 placeholder:text-gray-400 rounded-2xl"
              disabled={isStreaming}
            />
            <button
              type="submit"
              disabled={!input.trim() || isStreaming}
              className={`absolute right-3 top-1/2 -translate-y-1/2 p-2 rounded-xl transition-all ${input.trim() && !isStreaming
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-gray-100 text-gray-300'
                }`}
            >
              {isStreaming ? (
                <div className="w-5 h-5 border-2 border-white/50 border-t-white rounded-full animate-spin" />
              ) : (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-5 h-5">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              )}
            </button>
          </form>
          <div className="text-center mt-3">
            <p className="text-[10px] text-gray-400">
              {t.disclaimer}
            </p>
          </div>
        </div>
      </div>

    </div>
  );
};

export default AIChat;
