'use client';

import React, { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { I18N } from '../constants';
import { ConceptNode, EnhancedChatMessage, Language } from '../types';
import { assistantApi, AssistantProgressResponse } from '@/services/api';
import { useAuthStore } from '@/store/authStore';
import FocusMode from './FocusMode';
import MasteryIndicator from './MasteryIndicator';
import ConceptBreakdown from './ConceptBreakdown';

interface Props {
  lang?: Language;
}

type ProgressSnapshot = {
  score: number;
  level: string;
  analysis?: string;
  evidence: string[];
  suggestions: string[];
  timestamp: Date;
};

type PersistedMessage = Omit<EnhancedChatMessage, 'timestamp'> & { timestamp: string };

type PersistedState = {
  messages?: PersistedMessage[];
  activePage?: 'question' | 'explanation';
  highlightEnabled?: boolean;
  selectedConceptId?: string | null;
  selectedConceptLabel?: string | null;
};

// 错题上下文类型
type WrongQuestionContext = {
  questionId: string;
  score: number;
  maxScore: number;
  feedback?: string;
  studentAnswer?: string;
  scoringPointResults?: Array<{
    point_id?: string;
    description?: string;
    awarded: number;
    max_points?: number;
    evidence: string;
  }>;
  subject?: string;
  topic?: string;
  images?: string[];
  timestamp: string;
};

const STORAGE_KEY = 'gradeos.student-assistant-ui';
const WRONG_QUESTION_CONTEXT_KEY = 'gradeos.wrong-question-context';
const WRONG_QUESTION_PROCESSED_KEY = 'gradeos.wrong-question-processed';
const WRONG_QUESTION_STATE_KEY = 'gradeos.wrong-question-state'; // 用于 Fast Refresh 恢复
const MAX_PERSISTED_MESSAGES = 12;

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

const AIChat: React.FC<Props> = ({ lang }) => {
  const resolvedLang = useMemo<Language>(() => {
    if (lang) return lang;
    if (typeof navigator !== 'undefined') {
      return navigator.language.toLowerCase().startsWith('zh') ? 'zh' : 'en';
    }
    return 'en';
  }, [lang]);

  const t = I18N[resolvedLang];
  const searchParams = useSearchParams();
  const [messages, setMessages] = useState<EnhancedChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [focusModeActive, setFocusModeActive] = useState(false);
  const [currentFocusQuestion, setCurrentFocusQuestion] = useState('');
  const [sidebarsCollapsed, setSidebarsCollapsed] = useState(false);
  const [progressData, setProgressData] = useState<AssistantProgressResponse | null>(null);
  const [progressLoading, setProgressLoading] = useState(false);
  const [activePage, setActivePage] = useState<'question' | 'explanation'>('question');
  const [highlightEnabled, setHighlightEnabled] = useState(true);
  const [selectedConceptId, setSelectedConceptId] = useState<string | null>(null);
  const [selectedConceptLabel, setSelectedConceptLabel] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [wrongQuestionProcessed, setWrongQuestionProcessed] = useState(false);
  const { user } = useAuthStore();
  const activeClassId = user?.classIds?.[0];
  const router = useRouter();
  const timelineRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // 用于存储 handleSendWithContext 函数引用，以便在 effect 中使用
  const handleSendWithContextRef = useRef<((msg: string, ctx?: WrongQuestionContext | null) => void) | null>(null);
  
  // 使用 ref 来同步跟踪错题上下文是否已处理（避免 React Strict Mode 双重执行问题）
  const wrongQuestionProcessedRef = useRef(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) {
      try {
        const parsed = JSON.parse(raw) as PersistedState;
        if (parsed.messages && parsed.messages.length > 0) {
          const restored = parsed.messages.map((msg) => ({
            ...msg,
            timestamp: new Date(msg.timestamp),
          }));
          setMessages(restored);
        }
        if (parsed.activePage) setActivePage(parsed.activePage);
        if (typeof parsed.highlightEnabled === 'boolean') setHighlightEnabled(parsed.highlightEnabled);
        if (parsed.selectedConceptId) setSelectedConceptId(parsed.selectedConceptId);
        if (parsed.selectedConceptLabel) setSelectedConceptLabel(parsed.selectedConceptLabel);
      } catch (error) {
        console.warn('Assistant UI cache restore failed:', error);
      }
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    if (messages.length === 0) {
      setMessages([
        {
          role: 'assistant',
          content: t.chatIntro.replace(/[*#]/g, ''),
          timestamp: new Date(),
        },
      ]);
    }
  }, [hydrated, messages.length, resolvedLang, t.chatIntro]);

  // 存储待处理的错题上下文（用于传递给 API）
  const [activeWrongQuestionContext, setActiveWrongQuestionContext] = useState<WrongQuestionContext | null>(null);
  // 存储待发送的图片预览
  const [pendingImages, setPendingImages] = useState<string[]>([]);

  // 处理从错题本跳转过来的深究请求 - 填充到输入框而不是自动发送
  useEffect(() => {
    // 确保在客户端运行
    if (typeof window === 'undefined') {
      console.log('[AIChat] Not in browser, skipping wrongbook check');
      return;
    }
    
    if (!hydrated) {
      console.log('[AIChat] Not hydrated yet, skipping wrongbook check');
      return;
    }
    
    // 使用 ref 进行同步检查，避免 React Strict Mode 双重执行问题
    if (wrongQuestionProcessedRef.current) {
      console.log('[AIChat] Already processed wrongbook context (ref check)');
      return;
    }
    
    if (wrongQuestionProcessed) {
      console.log('[AIChat] Already processed wrongbook context (state check)');
      return;
    }
    
    // 检查 URL 参数 - 使用 window.location 作为备选
    let fromParam = searchParams?.get('from');
    if (!fromParam && typeof window !== 'undefined') {
      const urlParams = new URLSearchParams(window.location.search);
      fromParam = urlParams.get('from');
    }
    
    console.log('[AIChat] Checking wrongbook context:', {
      from: fromParam,
      hydrated,
      processed: wrongQuestionProcessed,
      processedRef: wrongQuestionProcessedRef.current,
      url: typeof window !== 'undefined' ? window.location.href : 'N/A',
      searchParamsAvailable: !!searchParams
    });
    
    if (fromParam !== 'wrongbook') {
      console.log('[AIChat] Not from wrongbook, skipping');
      return;
    }
    
    // 读取错题上下文
    const contextRaw = window.localStorage.getItem(WRONG_QUESTION_CONTEXT_KEY);
    console.log('[AIChat] Context raw:', contextRaw ? 'found (' + contextRaw.length + ' chars)' : 'not found');
    
    if (!contextRaw) {
      // 检查是否是 Fast Refresh 导致的重复执行（上下文已被处理但状态被重置）
      const lastProcessedTime = window.sessionStorage.getItem(WRONG_QUESTION_PROCESSED_KEY);
      if (lastProcessedTime) {
        const timeDiff = Date.now() - parseInt(lastProcessedTime, 10);
        // 如果在 10 秒内处理过，说明是 Fast Refresh，尝试恢复状态
        if (timeDiff < 10000) {
          console.log('[AIChat] Fast Refresh detected, timeDiff:', timeDiff);
          
          // 尝试从 sessionStorage 恢复状态
          const savedState = window.sessionStorage.getItem(WRONG_QUESTION_STATE_KEY);
          if (savedState) {
            try {
              const state = JSON.parse(savedState);
              console.log('[AIChat] Restoring state from sessionStorage:', state);
              
              if (state.context) {
                setActiveWrongQuestionContext(state.context);
              }
              if (state.images && state.images.length > 0) {
                setPendingImages(state.images);
              }
              if (state.input) {
                setInput(state.input);
              }
            } catch (e) {
              console.error('[AIChat] Failed to restore state:', e);
            }
          }
          
          wrongQuestionProcessedRef.current = true;
          setWrongQuestionProcessed(true);
          return;
        }
      }
      console.warn('[AIChat] No wrong question context found in localStorage');
      setWrongQuestionProcessed(true);
      return;
    }
    
    // 立即标记为已处理（同步），防止重复执行
    wrongQuestionProcessedRef.current = true;
    // 记录处理时间，用于检测 Fast Refresh
    window.sessionStorage.setItem(WRONG_QUESTION_PROCESSED_KEY, Date.now().toString());
    
    try {
      const context: WrongQuestionContext = JSON.parse(contextRaw);
      console.log('[AIChat] Parsed wrong question context:', {
        questionId: context.questionId,
        score: context.score,
        maxScore: context.maxScore,
        imagesCount: context.images?.length || 0
      });
      
      // 清除 localStorage 中的上下文，避免重复处理
      window.localStorage.removeItem(WRONG_QUESTION_CONTEXT_KEY);
      
      // 存储错题上下文
      setActiveWrongQuestionContext(context);
      console.log('[AIChat] Set activeWrongQuestionContext');
      
      // 设置待发送的图片
      if (context.images && context.images.length > 0) {
        setPendingImages(context.images);
        console.log('[AIChat] Set pendingImages:', context.images.length);
      }
      
      // 构建预填充的消息内容
      const prefillMessage = `请帮我深究这道错题 Q${context.questionId}，我得了 ${context.score}/${context.maxScore} 分。`;
      setInput(prefillMessage);
      console.log('[AIChat] Set input:', prefillMessage);
      
      // 保存状态到 sessionStorage，用于 Fast Refresh 恢复
      window.sessionStorage.setItem(WRONG_QUESTION_STATE_KEY, JSON.stringify({
        context,
        images: context.images || [],
        input: prefillMessage
      }));
      
      setWrongQuestionProcessed(true);
    } catch (err) {
      console.error('[AIChat] Failed to parse wrong question context:', err);
      setWrongQuestionProcessed(true);
    }
  }, [hydrated, wrongQuestionProcessed, searchParams]);

  useEffect(() => {
    if (!hydrated || typeof window === 'undefined') return;
    const payload: PersistedState = {
      messages: messages.slice(-MAX_PERSISTED_MESSAGES).map((msg) => ({
        ...msg,
        timestamp:
          msg.timestamp instanceof Date
            ? msg.timestamp.toISOString()
            : new Date(msg.timestamp).toISOString(),
      })),
      activePage,
      highlightEnabled,
      selectedConceptId,
      selectedConceptLabel,
    };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  }, [activePage, highlightEnabled, hydrated, messages, selectedConceptId, selectedConceptLabel]);

  useEffect(() => {
    if (!user?.id) {
      setProgressData(null);
      setProgressLoading(false);
      return;
    }

    let active = true;
    const loadProgress = async () => {
      setProgressLoading(true);
      try {
        const data = await assistantApi.getProgress(user.id, activeClassId);
        if (active) {
          setProgressData(data);
        }
      } catch (error) {
        console.error('Assistant progress load failed:', error);
        if (active) {
          setProgressData(null);
        }
      } finally {
        if (active) {
          setProgressLoading(false);
        }
      }
    };

    loadProgress();

    return () => {
      active = false;
    };
  }, [user?.id, activeClassId]);

  useEffect(() => {
    const timeline = timelineRef.current;
    if (timeline) {
      timeline.scrollTop = timeline.scrollHeight;
    }
  }, [messages]);

  // 带错题上下文的发送函数
  const handleSendWithContext = useCallback(async (
    userMsgContent: string, 
    wrongContext?: WrongQuestionContext | null
  ) => {
    console.log('[AIChat] handleSendWithContext called:', {
      message: userMsgContent.substring(0, 50),
      hasContext: !!wrongContext,
      contextImages: wrongContext?.images?.length || 0,
      userId: user?.id,
      isStreaming
    });
    
    if (!userMsgContent.trim() || isStreaming) return;
    if (!user?.id) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: '请先登录后再使用学习助手功能。点击左上角返回后登录。', timestamp: new Date() },
      ]);
      return;
    }

    setInput('');
    setIsStreaming(true);
    setActivePage('explanation');

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
        .slice(-16)  // 增加到 16 条历史消息
        .map((msg) => ({ role: msg.role as 'user' | 'assistant', content: msg.content }));

      // 构建 API 请求，包含错题上下文和图片
      const isManualImageUpload = wrongContext?.questionId === 'manual';
      const chatRequest: Parameters<typeof assistantApi.chat>[0] = {
        student_id: user.id,
        class_id: activeClassId,
        message: userMsgContent,
        history,
        session_mode: wrongContext && !isManualImageUpload ? 'wrong_question_review' : 'learning',
      };

      // 如果有错题上下文（非手动上传），添加到请求中
      if (wrongContext && !isManualImageUpload) {
        chatRequest.wrong_question_context = {
          questionId: wrongContext.questionId,
          score: wrongContext.score,
          maxScore: wrongContext.maxScore,
          feedback: wrongContext.feedback,
          studentAnswer: wrongContext.studentAnswer,
          scoringPointResults: wrongContext.scoringPointResults,
          subject: wrongContext.subject,
          topic: wrongContext.topic,
        };
      }
      
      // 如果有图片（无论是错题还是手动上传），都传递给后端
      if (wrongContext?.images && wrongContext.images.length > 0) {
        chatRequest.images = wrongContext.images;
        console.log('[AIChat] Adding images to request:', wrongContext.images.length);
      }

      console.log('[AIChat] Sending chat request:', {
        student_id: chatRequest.student_id,
        session_mode: chatRequest.session_mode,
        hasWrongContext: !!chatRequest.wrong_question_context,
        imagesCount: chatRequest.images?.length || 0,
      });

      const response = await assistantApi.chat(chatRequest);
      console.log('[AIChat] Received response:', {
        contentLength: response.content?.length || 0,
        hasNextQuestion: !!response.next_question,
        responseType: response.response_type,
      });

      setMessages((prev) => {
        const next = [...prev];
        const lastMessage = next[next.length - 1] as EnhancedChatMessage;
        if (lastMessage.role === 'assistant') {
          lastMessage.content = response.content;
          lastMessage.mastery = response.mastery;
          lastMessage.conceptBreakdown = response.concept_breakdown;
          lastMessage.nextQuestion = response.next_question;
          lastMessage.questionOptions = response.question_options;
          lastMessage.focusMode = response.focus_mode;
          lastMessage.responseType = response.response_type as 'text' | 'question' | 'diagram' | 'code';
        }
        return next;
      });

      if (response.next_question) {
        setCurrentFocusQuestion(response.next_question);
      }
      setFocusModeActive(false);
    } catch (error) {
      console.error('Chat Error:', error);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: t.brainFreeze, timestamp: new Date() },
      ]);
    } finally {
      setIsStreaming(false);
    }
  }, [isStreaming, user?.id, t.brainFreeze, messages, activeClassId]);

  // 普通发送函数（不带错题上下文）
  const handleSend = useCallback((userMsgContent: string) => {
    handleSendWithContext(userMsgContent, null);
  }, [handleSendWithContext]);

  // 同步更新 ref（不使用 useEffect 以避免时序问题）
  handleSendWithContextRef.current = handleSendWithContext;

  // 处理表单提交 - 如果有错题上下文和图片，一起发送
  const handleInputSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    
    // 如果有错题上下文，使用带上下文的发送
    if (activeWrongQuestionContext) {
      // 如果有待发送的图片，添加到上下文中
      const contextWithImages: WrongQuestionContext = {
        ...activeWrongQuestionContext,
        images: pendingImages.length > 0 ? pendingImages : activeWrongQuestionContext.images,
      };
      handleSendWithContext(input, contextWithImages);
      // 清除上下文和图片
      setActiveWrongQuestionContext(null);
      setPendingImages([]);
    } else if (pendingImages.length > 0) {
      // 手动上传图片的情况（无错题上下文）
      const manualImageContext: WrongQuestionContext = {
        questionId: 'manual',
        score: 0,
        maxScore: 0,
        images: pendingImages,
        timestamp: new Date().toISOString(),
      };
      handleSendWithContext(input, manualImageContext);
      setPendingImages([]);
    } else {
      handleSend(input);
    }
  };

  // 移除待发送的图片
  const removePendingImage = (index: number) => {
    setPendingImages(prev => prev.filter((_, i) => i !== index));
  };

  // 清除错题上下文
  const clearWrongQuestionContext = () => {
    setActiveWrongQuestionContext(null);
    setPendingImages([]);
    setInput('');
  };

  // 处理文件上传 - 将图片转换为 base64
  const handleFileUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    
    Array.from(files).forEach((file) => {
      if (!file.type.startsWith('image/')) {
        console.warn('[AIChat] Skipping non-image file:', file.name);
        return;
      }
      
      const reader = new FileReader();
      reader.onload = () => {
        const base64 = reader.result as string;
        setPendingImages((prev) => [...prev, base64]);
        console.log('[AIChat] Added image:', file.name, 'Total:', pendingImages.length + 1);
      };
      reader.onerror = () => {
        console.error('[AIChat] Failed to read file:', file.name);
      };
      reader.readAsDataURL(file);
    });
    
    // 清除 input 以便可以重复选择同一文件
    e.target.value = '';
  }, [pendingImages.length]);

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

  const toSafeDate = (value: string) => {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? new Date() : parsed;
  };

  const messageSnapshots = useMemo<ProgressSnapshot[]>(
    () =>
      messages
        .filter((msg) => msg.role === 'assistant' && msg.mastery)
        .map((msg) => ({
          score: msg.mastery?.score ?? 0,
          level: msg.mastery?.level ?? 'developing',
          analysis: msg.mastery?.analysis,
          evidence: msg.mastery?.evidence ?? [],
          suggestions: msg.mastery?.suggestions ?? [],
          timestamp: msg.timestamp,
        })),
    [messages],
  );

  const storedSnapshots = useMemo<ProgressSnapshot[]>(
    () =>
      (progressData?.mastery_history ?? []).map((item) => ({
        score: item.score,
        level: item.level,
        analysis: item.analysis,
        evidence: item.evidence ?? [],
        suggestions: item.suggestions ?? [],
        timestamp: toSafeDate(item.created_at),
      })),
    [progressData],
  );

  const progressSnapshots = useMemo(() => {
    const combined = [...storedSnapshots, ...messageSnapshots];
    const unique = new Map<string, ProgressSnapshot>();
    combined.forEach((snapshot) => {
      const key = `${snapshot.timestamp.toISOString()}-${snapshot.score}-${snapshot.level}`;
      unique.set(key, snapshot);
    });
    return Array.from(unique.values())
      .sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())
      .slice(-6);
  }, [storedSnapshots, messageSnapshots]);

  const latestProgressSnapshot = progressSnapshots[progressSnapshots.length - 1];
  const conceptBreakdown =
    latestAssistant?.conceptBreakdown && latestAssistant.conceptBreakdown.length > 0
      ? latestAssistant.conceptBreakdown
      : progressData?.concept_breakdown ?? [];

  const flattenConcepts = (concepts: ConceptNode[] = []): ConceptNode[] => {
    const queue = [...concepts];
    const flattened: ConceptNode[] = [];
    while (queue.length) {
      const current = queue.shift();
      if (!current) continue;
      flattened.push(current);
      if (current.children?.length) {
        queue.push(...current.children);
      }
    }
    return flattened;
  };

  const knowledgeGaps = useMemo(() => {
    if (!conceptBreakdown.length) return [];
    return flattenConcepts(conceptBreakdown).filter((node) => node.understood !== true);
  }, [conceptBreakdown]);

  const focusAreas = useMemo(() => {
    const latestSuggestions = latestAssistant?.mastery?.suggestions ?? [];
    if (latestSuggestions.length > 0) {
      return latestSuggestions;
    }
    return latestProgressSnapshot?.suggestions ?? [];
  }, [latestAssistant, latestProgressSnapshot]);

  const masteryDisplay =
    latestAssistant?.mastery ??
    (latestProgressSnapshot
      ? {
          score: latestProgressSnapshot.score,
          level: latestProgressSnapshot.level,
          analysis: latestProgressSnapshot.analysis,
          evidence: latestProgressSnapshot.evidence,
          suggestions: latestProgressSnapshot.suggestions,
        }
      : undefined);

  const displayContent =
    latestAssistant?.content?.trim() || (isStreaming ? 'Thinking...' : t.chatIntro.replace(/[*#]/g, ''));

  const conceptStats = useMemo(() => {
    const flattened = flattenConcepts(conceptBreakdown);
    const total = flattened.length;
    const mastered = flattened.filter((node) => node.understood).length;
    return { total, mastered };
  }, [conceptBreakdown]);

  const scoreDelta = useMemo(() => {
    if (progressSnapshots.length < 2) return 0;
    const latest = progressSnapshots[progressSnapshots.length - 1]?.score ?? 0;
    const previous = progressSnapshots[progressSnapshots.length - 2]?.score ?? 0;
    return latest - previous;
  }, [progressSnapshots]);

  const selectedConcept = useMemo(() => {
    if (!selectedConceptId) return null;
    const flattened = flattenConcepts(conceptBreakdown);
    return flattened.find((node) => (node.id || node.name) === selectedConceptId) ?? null;
  }, [conceptBreakdown, selectedConceptId]);

  useEffect(() => {
    if (!selectedConceptId) return;
    if (selectedConcept && selectedConcept.name !== selectedConceptLabel) {
      setSelectedConceptLabel(selectedConcept.name);
    }
  }, [selectedConcept, selectedConceptId, selectedConceptLabel]);

  const selectedConceptName = selectedConcept?.name ?? selectedConceptLabel;

  const questionContent = useMemo(() => {
    const fallback = 'Ask a question, or choose a concept from the knowledge map to begin.';
    return (
      latestAssistant?.nextQuestion?.trim() ||
      currentFocusQuestion ||
      latestUser?.content?.trim() ||
      fallback
    );
  }, [currentFocusQuestion, latestAssistant, latestUser]);


  const explanationContent = displayContent || 'Explanation will appear here.';

  const highlightTerms = useMemo(() => {
    const terms = new Set<string>();
    focusAreas.forEach((item) => {
      if (item) terms.add(item.trim());
    });
    knowledgeGaps.forEach((node) => {
      if (node.name) terms.add(node.name.trim());
    });
    flattenConcepts(conceptBreakdown).forEach((node) => {
      if (node.name) terms.add(node.name.trim());
    });
    return Array.from(terms)
      .filter((term) => term.length >= 2)
      .slice(0, 12);
  }, [conceptBreakdown, focusAreas, knowledgeGaps]);

  const highlightLookup = useMemo(
    () => new Set(highlightTerms.map((term) => term.toLowerCase())),
    [highlightTerms],
  );

  const highlightRegex = useMemo(() => {
    if (!highlightEnabled || highlightTerms.length === 0) return null;
    const pattern = highlightTerms.map(escapeRegExp).join('|');
    return pattern ? new RegExp(`(${pattern})`, 'gi') : null;
  }, [highlightEnabled, highlightTerms]);

  const renderHighlightedLine = (line: string) => {
    if (!highlightRegex) return line;
    return line.split(highlightRegex).map((part, idx) => {
      if (!part) return null;
      const key = `${part}-${idx}`;
      if (highlightLookup.has(part.toLowerCase())) {
        return (
          <mark key={key} className="assistant-highlight">
            {part}
          </mark>
        );
      }
      return <span key={key}>{part}</span>;
    });
  };

  const renderHighlightedContent = (text: string) =>
    text.split('\n').map((line, idx) => (
      <p key={`line-${idx}`} className="whitespace-pre-line leading-relaxed">
        {line ? renderHighlightedLine(line) : <span className="block h-4" />}
      </p>
    ));

  const labels = useMemo(
    () => ({
      history: 'History',
      focus: 'Focus cues',
      analytics: 'Learning progress',
      knowledgeMap: 'Knowledge map',
      question: 'Question',
      explanation: 'Explanation',
      highlight: 'Highlight',
      progressTrace: 'Progress',
    }),
    [],
  );


  const shouldShowSidebars = !sidebarsCollapsed;

  const handleConceptSelect = (node: ConceptNode) => {
    if (!node.name) return;
    const key = node.id || node.name;
    setSelectedConceptId(key);
    setSelectedConceptLabel(node.name);
    setActivePage('question');
    const prompt = `Explain "${node.name}" from first principles, then ask me a diagnostic question.`;
    handleSend(prompt);
  };


  const activePageIndex = activePage === 'question' ? 0 : 1;
  const pageCount = 2;

  return (
    <div className="relative min-h-screen bg-white text-black overflow-hidden">
      <div className="assistant-grid absolute inset-0" aria-hidden="true" />
      <div
        className="assistant-halo absolute -top-24 left-1/2 h-[420px] w-[420px] -translate-x-1/2"
        aria-hidden="true"
      />
      <div className="assistant-scanline absolute inset-x-0 top-0" aria-hidden="true" />
      <div className="assistant-orb assistant-orb--left absolute -bottom-20 -left-10 h-56 w-56" aria-hidden="true" />
      <div className="assistant-orb assistant-orb--right absolute -top-10 right-10 h-40 w-40" aria-hidden="true" />

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

      <div className="relative z-10 flex min-h-screen flex-col px-6 py-10 md:px-12">
        <div className="flex flex-wrap items-center justify-between gap-4 text-[10px] font-semibold uppercase tracking-[0.45em] text-black/60">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => router.push('/student/dashboard')}
              className="border border-black/20 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.3em] text-black/60 transition hover:border-black/40"
            >Back to courses</button>
            <span>GradeOS Socratic Agent</span>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setSidebarsCollapsed((prev) => !prev)}
              className="border border-black/20 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.3em] text-black/60 transition hover:border-black/40"
            >
              {sidebarsCollapsed ? 'Show sidebars' : 'Hide sidebars'}
            </button>
            <span className="flex items-center gap-2">
              <span
                className={`h-2 w-2 rounded-full ${isStreaming ? 'bg-black animate-pulse' : 'bg-black/40'}`}
              />
              {isStreaming ? 'Thinking' : 'Ready'}
            </span>
          </div>
        </div>

        <div
          className={`mt-10 grid flex-1 items-start gap-10 ${
            sidebarsCollapsed ? 'lg:grid-cols-[minmax(0,1fr)]' : 'lg:grid-cols-[280px_minmax(0,1fr)_320px]'
          }`}
        >
          {shouldShowSidebars && (
            <aside className="space-y-6 border-r border-black/10 pr-6">
              <div className="flex items-center justify-between text-[10px] font-semibold uppercase tracking-[0.4em] text-black/50">
                <span>{labels.history}</span>
                <span className="text-black/30">{messages.length}</span>
              </div>

              <div
                ref={timelineRef}
                className="max-h-[520px] space-y-4 overflow-y-auto pr-2 text-sm leading-relaxed text-black/80 custom-scrollbar"
              >
                {messages.map((msg, idx) => {
                  const isAssistant = msg.role === 'assistant';
                  const content = msg.content?.trim()
                    ? msg.content
                    : isAssistant && isStreaming && idx === messages.length - 1
                      ? 'Thinking...'
                      : '';
                  if (!content) return null;
                  return (
                    <div
                      key={`${msg.role}-${msg.timestamp.getTime()}-${idx}`}
                      className={`border-l-2 pl-4 ${isAssistant ? 'ml-2 border-black/20' : 'ml-6 border-black/50'}`}
                    >
                      <div className="text-[10px] uppercase tracking-[0.3em] text-black/30">
                        {isAssistant ? 'Assistant' : 'You'}
                      </div>
                      <div className="mt-2 whitespace-pre-line text-xs text-black/70">{content}</div>
                    </div>
                  );
                })}
                {!messages.length && (
                  <div className="text-sm text-black/40">Start a conversation to see history here.</div>
                )}
              </div>

              <div className="border-t border-black/10 pt-4">
                <div className="text-[10px] font-semibold uppercase tracking-[0.4em] text-black/50">
                  {labels.focus}
                </div>
                <div className="mt-3 space-y-2">
                  {focusAreas.length > 0 ? (
                    focusAreas.slice(0, 6).map((item, idx) => (
                      <button
                        key={`focus-${idx}`}
                        type="button"
                        onClick={() => setInput(item)}
                        className="w-full border-l-2 border-black/10 pl-3 text-left text-xs text-black/70 transition hover:border-black/40"
                      >
                        {item}
                      </button>
                    ))
                  ) : (
                    <div className="text-sm text-black/40">Waiting for the next mastery update.</div>
                  )}
                </div>
              </div>
            </aside>
          )}

          <section className="flex h-full flex-col gap-6">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-black/10 pb-4">
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.4em] text-black/50">
                  Learning flow
                </div>
                {selectedConceptName && (
                  <div className="mt-2 flex items-center gap-3 text-sm text-black/70">
                    <span className="border-l-2 border-black/60 pl-3 text-[10px] font-semibold uppercase tracking-[0.3em] text-black/50">
                      Focus
                    </span>
                    <span className="font-medium text-black">{selectedConceptName}</span>
                  </div>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-3 text-[10px] font-semibold uppercase tracking-[0.3em] text-black/50">
                <button
                  type="button"
                  onClick={() => setHighlightEnabled((prev) => !prev)}
                  className={`border px-3 py-1 transition ${
                    highlightEnabled
                      ? 'border-amber-400 text-amber-700'
                      : 'border-black/20 text-black/40'
                  }`}
                >
                  {labels.highlight} {highlightEnabled ? 'ON' : 'OFF'}
                </button>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 text-[10px] font-semibold uppercase tracking-[0.35em] text-black/50">
              <div className="flex items-center gap-4">
                <button
                  type="button"
                  onClick={() => setActivePage('question')}
                  className={`border-b-2 pb-1 transition ${
                    activePage === 'question' ? 'border-black text-black' : 'border-transparent text-black/40'
                  }`}
                >
                  {labels.question}
                </button>
                <button
                  type="button"
                  onClick={() => setActivePage('explanation')}
                  className={`border-b-2 pb-1 transition ${
                    activePage === 'explanation' ? 'border-black text-black' : 'border-transparent text-black/40'
                  }`}
                >
                  {labels.explanation}
                </button>
              </div>
              <div className="flex items-center gap-2 text-black/40">
                <span>
                  {activePageIndex + 1}/{pageCount}
                </span>
                <button
                  type="button"
                  onClick={() => setActivePage('question')}
                  disabled={activePage === 'question'}
                  className="border border-black/20 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.3em] text-black/60 transition disabled:cursor-not-allowed disabled:border-black/10 disabled:text-black/20"
                >
                  Prev
                </button>
                <button
                  type="button"
                  onClick={() => setActivePage('explanation')}
                  disabled={activePage === 'explanation'}
                  className="border border-black/20 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.3em] text-black/60 transition disabled:cursor-not-allowed disabled:border-black/10 disabled:text-black/20"
                >
                  Next
                </button>
              </div>
            </div>

            <div className="min-h-[420px] border-y border-black/10 py-6">
              <div className="text-[10px] font-semibold uppercase tracking-[0.4em] text-black/50">
                {activePage === 'question' ? labels.question : labels.explanation}
              </div>
              <div className="mt-6 max-h-[520px] overflow-y-auto pr-2 custom-scrollbar">
                {activePage === 'question' ? (
                  <div className="space-y-6">
                    <div className="text-2xl font-light leading-relaxed text-black">
                      {questionContent}
                    </div>
                    {latestAssistant?.questionOptions && latestAssistant.questionOptions.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {latestAssistant.questionOptions.map((option) => (
                          <button
                            key={option}
                            type="button"
                            onClick={() => handleSend(option)}
                            className="border border-black/20 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-black/70 transition hover:border-black/40 hover:text-black"
                          >
                            {option}
                          </button>
                        ))}
                      </div>
                    )}
                    {latestAssistant?.focusMode && (
                      <div>
                        <button
                          type="button"
                          onClick={() => {
                            if (currentFocusQuestion) {
                              setFocusModeActive(true);
                            }
                          }}
                          disabled={!currentFocusQuestion}
                          className={`border px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.2em] transition ${
                            currentFocusQuestion
                              ? 'border-black text-black hover:bg-black hover:text-white'
                              : 'border-black/10 text-black/30 cursor-not-allowed'
                          }`}
                        >Enter focus mode</button>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="space-y-5 text-base text-black/80">
                    {renderHighlightedContent(explanationContent)}
                    {highlightEnabled && highlightTerms.length > 0 && (
                      <div className="mt-6 border-l-2 border-amber-400 bg-amber-50/60 px-4 py-3 text-xs text-amber-900">
                        <div className="text-[10px] font-semibold uppercase tracking-[0.3em] text-amber-700">
                          {labels.highlight}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {highlightTerms.slice(0, 6).map((term) => (
                            <span
                              key={term}
                              className="border border-amber-200 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-amber-700"
                            >
                              {term}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {isStreaming && (
              <div className="text-[10px] font-semibold uppercase tracking-[0.4em] text-black/40">
                Processing
              </div>
            )}
          </section>

          {shouldShowSidebars && (
            <aside className="flex flex-col gap-8 border-l border-black/10 pl-6">
              <div className="space-y-4">
                <div className="text-[10px] font-semibold uppercase tracking-[0.4em] text-black/50">
                  {labels.analytics}
                </div>
                <div className="grid grid-cols-2 gap-4 text-xs text-black/60">
                  <div className="border-b border-black/10 pb-2">
                    <div className="text-[10px] uppercase tracking-[0.3em] text-black/40">Mastery</div>
                    <div className="mt-1 text-2xl font-semibold text-black">
                      {masteryDisplay?.score ?? '--'}
                    </div>
                    <div className="text-[10px] uppercase tracking-[0.2em] text-black/40">
                      {masteryDisplay?.level ?? '--'}
                    </div>
                  </div>
                  <div className="border-b border-black/10 pb-2">
                    <div className="text-[10px] uppercase tracking-[0.3em] text-black/40">Trend</div>
                    <div
                      className={`mt-1 text-2xl font-semibold ${
                        scoreDelta >= 0 ? 'text-emerald-600' : 'text-rose-600'
                      }`}
                    >
                      {scoreDelta >= 0 ? `+${scoreDelta}` : scoreDelta}
                    </div>
                    <div className="text-[10px] uppercase tracking-[0.2em] text-black/40">Last 2</div>
                  </div>
                  <div className="border-b border-black/10 pb-2">
                    <div className="text-[10px] uppercase tracking-[0.3em] text-black/40">Nodes</div>
                    <div className="mt-1 text-xl font-semibold text-black">
                      {conceptStats.mastered}/{conceptStats.total || '--'}
                    </div>
                    <div className="text-[10px] uppercase tracking-[0.2em] text-black/40">
                      {conceptStats.total
                        ? `${Math.round((conceptStats.mastered / conceptStats.total) * 100)}%`
                        : '--'}
                    </div>
                  </div>
                  <div className="border-b border-black/10 pb-2">
                    <div className="text-[10px] uppercase tracking-[0.3em] text-black/40">Gaps</div>
                    <div className="mt-1 text-xl font-semibold text-black">{knowledgeGaps.length}</div>
                    <div className="text-[10px] uppercase tracking-[0.2em] text-black/40">Review</div>
                  </div>
                </div>

                <div className="flex min-h-[160px] items-center justify-center">
                  {masteryDisplay ? (
                    <MasteryIndicator {...masteryDisplay} size="sm" showDetails={true} />
                  ) : (
                    <p className="text-sm text-black/40 text-center">
                      Share a concept to begin tracking mastery.
                    </p>
                  )}
                </div>

                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-[0.4em] text-black/50">
                    {labels.progressTrace}
                  </div>
                  <div className="mt-4 flex h-20 items-end gap-3">
                    {progressSnapshots.length > 0 ? (
                      progressSnapshots.map((snapshot, idx) => {
                        const score = snapshot.score ?? 0;
                        const height = Math.max(12, Math.min(72, Math.round(score * 0.7)));
                        return (
                          <div key={`${snapshot.timestamp.getTime()}-${idx}`} className="flex flex-col items-center gap-2">
                            <div className="w-2 bg-black/80 transition-all" style={{ height }} />
                            <div className="text-[10px] text-black/40">{score}</div>
                          </div>
                        );
                      })
                    ) : (
                      <div className="text-sm text-black/40">
                        {progressLoading ? 'Loading progress...' : 'No mastery snapshots yet.'}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                {conceptBreakdown.length > 0 ? (
                  <ConceptBreakdown
                    concepts={conceptBreakdown}
                    title={labels.knowledgeMap}
                    onSelect={handleConceptSelect}
                    selectedId={selectedConceptId ?? undefined}
                  />
                ) : (
                  <div className="text-sm text-black/40">
                    {progressLoading
                      ? 'Loading progress map...'
                      : 'Knowledge map will appear after the next explanation.'}
                  </div>
                )}
              </div>
            </aside>
          )}
        </div>

        <form onSubmit={handleInputSubmit} className="mt-10 border-t border-black/10 pt-6">
          {/* Debug 信息 - 开发时显示 */}
          {process.env.NODE_ENV === 'development' && (
            <div className="mb-4 p-2 bg-gray-100 rounded text-xs font-mono">
              <div>hydrated: {String(hydrated)}</div>
              <div>wrongQuestionProcessed: {String(wrongQuestionProcessed)}</div>
              <div>activeWrongQuestionContext: {activeWrongQuestionContext ? `Q${activeWrongQuestionContext.questionId}` : 'null'}</div>
              <div>pendingImages: {pendingImages.length}</div>
              <div>input: {input.substring(0, 30)}...</div>
            </div>
          )}
          
          {/* 错题上下文和图片预览 */}
          {(activeWrongQuestionContext || pendingImages.length > 0) && (
            <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50/50 p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="text-[10px] font-semibold uppercase tracking-[0.3em] text-amber-700">
                  错题深究模式
                </div>
                <button
                  type="button"
                  onClick={clearWrongQuestionContext}
                  className="text-amber-600 hover:text-amber-800 text-xs"
                >
                  ✕ 取消
                </button>
              </div>
              
              {activeWrongQuestionContext && (
                <div className="mb-3 text-sm text-amber-900">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium">题目 Q{activeWrongQuestionContext.questionId}</span>
                    <span className="text-amber-600">
                      得分: {activeWrongQuestionContext.score}/{activeWrongQuestionContext.maxScore}
                    </span>
                  </div>
                  {activeWrongQuestionContext.feedback && (
                    <div className="text-xs text-amber-700 mt-1 line-clamp-2">
                      反馈: {activeWrongQuestionContext.feedback}
                    </div>
                  )}
                </div>
              )}
              
              {/* 图片预览 */}
              {pendingImages.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {pendingImages.map((img, idx) => (
                    <div key={idx} className="relative group">
                      <img
                        src={img}
                        alt={`错题图片 ${idx + 1}`}
                        className="h-20 w-20 object-cover rounded-lg border border-amber-200"
                      />
                      <button
                        type="button"
                        onClick={() => removePendingImage(idx)}
                        className="absolute -top-2 -right-2 w-5 h-5 bg-amber-500 text-white rounded-full text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              )}
              
              <div className="mt-3 text-[10px] text-amber-600">
                点击发送按钮，AI 将分析你的错题并提供苏格拉底式引导
              </div>
            </div>
          )}
          
          {/* 普通图片上传预览（非错题模式） */}
          {!activeWrongQuestionContext && pendingImages.length > 0 && (
            <div className="mb-4 flex flex-wrap gap-2">
              {pendingImages.map((img, idx) => (
                <div key={idx} className="relative group">
                  <img
                    src={img}
                    alt={`上传图片 ${idx + 1}`}
                    className="h-16 w-16 object-cover rounded-lg border border-black/20"
                  />
                  <button
                    type="button"
                    onClick={() => removePendingImage(idx)}
                    className="absolute -top-2 -right-2 w-5 h-5 bg-black text-white rounded-full text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
          
          <div className="flex flex-col gap-3 md:flex-row md:items-center">
            {/* 图片上传按钮 */}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              accept="image/*"
              multiple
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isStreaming}
              className="border border-black/20 px-3 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-black/60 transition hover:border-black/40 disabled:opacity-50"
              title="上传图片"
            >
              📷 {pendingImages.length > 0 ? `(${pendingImages.length})` : ''}
            </button>
            
            <div className="flex-1 border-b border-black/20 pb-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={activeWrongQuestionContext ? '输入你对这道题的疑问，或直接点击发送...' : (pendingImages.length > 0 ? '描述图片中的问题...' : t.chatPlaceholder)}
                className="w-full bg-transparent text-base text-black placeholder:text-black/40 focus:outline-none"
                disabled={isStreaming}
              />
            </div>
            <button
              type="submit"
              disabled={!input.trim() || isStreaming}
              className={`border px-6 py-2 text-xs font-semibold uppercase tracking-[0.25em] transition-all ${
                input.trim() && !isStreaming
                  ? 'border-black text-black hover:bg-black hover:text-white'
                  : 'border-black/10 text-black/30'
              }`}
            >
              {isStreaming ? 'Thinking' : (activeWrongQuestionContext ? '深究分析' : 'Send')}
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
