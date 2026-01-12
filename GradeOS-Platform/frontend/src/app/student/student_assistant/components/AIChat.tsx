import React, { useState, useRef, useEffect } from 'react';
import { ICONS, I18N } from '../constants';
import { ChatMessage, Language } from '../types';
import { geminiService } from '../services/gemini';

interface Props {
  lang: Language;
}

const AIChat: React.FC<Props> = ({ lang }) => {
  const t = I18N[lang];
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  
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
  }, [messages, isStreaming]);

  const cleanText = (text: string) => text.replace(/[*#`]/g, '').trim();

  const handleSend = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || isStreaming) return;

    const userMsgContent = input;
    setInput('');
    setIsStreaming(true);

    // Add User Message
    setMessages(prev => [...prev, { role: 'user', content: userMsgContent, timestamp: new Date() }]);

    try {
      // Add placeholder Assistant Message for streaming
      setMessages(prev => [...prev, { role: 'assistant', content: '', timestamp: new Date() }]);
      
      let currentResponse = '';
      
      // Use Gemini streaming response
      await geminiService.generateStreamResponse(userMsgContent, lang, (chunk: string) => {
        currentResponse += chunk;
        setMessages(prev => {
          const newMessages = [...prev];
          const lastMessage = newMessages[newMessages.length - 1];
          if (lastMessage.role === 'assistant') {
            lastMessage.content = cleanText(currentResponse);
          }
          return newMessages;
        });
      });

    } catch (error) {
      console.error('Chat Error:', error);
      setMessages(prev => [...prev, { role: 'assistant', content: t.brainFreeze, timestamp: new Date() }]);
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] bg-white relative">
        
      {/* Chat Area - ChatGPT Style Centered */}
      <div className="flex-1 overflow-y-auto w-full" ref={scrollRef}>
        <div className="max-w-3xl mx-auto w-full pb-32 pt-8 px-4">
            
          {/* Header/Intro (Only show if few messages) */}
          {messages.length <= 1 && (
             <div className="flex flex-col items-center justify-center mb-12 opacity-50">
                <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center text-blue-600 mb-4">
                    <ICONS.Chat className="w-8 h-8" />
                </div>
                <h3 className="text-xl font-bold text-gray-800">{t.appName} AI</h3>
                <p className="text-sm text-gray-500 mt-2">Your Study Companion</p>
             </div>
          )}

          {messages.map((msg, idx) => (
            <div 
              key={idx} 
              className={`group w-full text-gray-800 border-b border-black/5 dark:border-white/5 ${
                msg.role === 'assistant' ? 'bg-transparent' : 'bg-transparent'
              }`}
            >
              <div className="text-base gap-4 md:gap-6 md:max-w-2xl lg:max-w-3xl xl:max-w-3xl p-4 md:py-6 flex lg:px-0 m-auto">
                
                {/* Avatar Column */}
                <div className="flex-shrink-0 flex flex-col relative items-end">
                  <div className={`w-8 h-8 rounded-sm flex items-center justify-center ${
                      msg.role === 'assistant' 
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

                {/* Content Column */}
                <div className="relative flex-1 overflow-hidden">
                    <div className="font-semibold text-xs text-gray-400 mb-1 uppercase tracking-wide">
                        {msg.role === 'assistant' ? 'AI Assistant' : 'You'}
                    </div>
                    <div className="prose prose-slate max-w-none break-words leading-7 text-[15px]">
                        {msg.content || (
                            isStreaming && idx === messages.length - 1 ? (
                                <span className="inline-block w-2 h-4 bg-gray-400 animate-pulse ml-1"/>
                            ) : ''
                        )}
                    </div>
                </div>
              </div>
            </div>
          ))}
          
          {isStreaming && (
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

      {/* Input Area - Fixed Bottom Floating */}
      <div className="absolute bottom-0 left-0 w-full bg-gradient-to-t from-white via-white to-transparent pt-10 pb-6 px-4">
        <div className="max-w-3xl mx-auto">
            <form onSubmit={handleSend} className="relative shadow-xl shadow-blue-900/5 rounded-2xl bg-white border border-gray-200 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100 transition-all">
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
                    className={`absolute right-3 top-1/2 -translate-y-1/2 p-2 rounded-xl transition-all ${
                        input.trim() && !isStreaming 
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