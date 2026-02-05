'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useAuthStore } from '@/store/authStore';
import { Forum, ForumSearchResult } from '@/types';
import { openboardApi } from '@/services/api';

export default function TeacherSearchPage() {
  const router = useRouter();
  const { user } = useAuthStore();
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get('q') || '';

  const [query, setQuery] = useState(initialQuery);
  const [results, setResults] = useState<ForumSearchResult[]>([]);
  const [forums, setForums] = useState<Forum[]>([]);
  const [selectedForum, setSelectedForum] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  useEffect(() => {
    loadForums();
    if (initialQuery) {
      handleSearch();
    }
  }, []);

  const loadForums = async () => {
    try {
      const data = await openboardApi.getForums();
      setForums(data);
    } catch (error) {
      console.error('加载论坛列表失败', error);
    }
  };

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const data = await openboardApi.searchPosts(query, selectedForum || undefined);
      setResults(data);
    } catch (error) {
      console.error('搜索失败', error);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  const handleDeletePost = async (postId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!user?.id) return;
    if (!confirm('确定要删除这个帖子吗？')) return;
    try {
      await openboardApi.deletePost(postId, user.id, '管理员删除');
      setResults(results.filter(r => r.post_id !== postId));
    } catch (error) {
      console.error('删除失败', error);
      alert('删除失败');
    }
  };

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'numeric',
      day: 'numeric',
    });
  };

  const highlightKeyword = (text: string, keyword: string) => {
    if (!keyword) return text;
    const regex = new RegExp(`(${keyword})`, 'gi');
    const parts = text.split(regex);
    return parts.map((part, i) =>
      regex.test(part) ? (
        <mark key={i} className="bg-yellow-200 px-0.5 rounded">
          {part}
        </mark>
      ) : (
        part
      )
    );
  };

  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-6">
        {/* 返回按钮 */}
        <button
          onClick={() => router.push('/teacher/openboard')}
          className="text-slate-500 hover:text-slate-700 flex items-center gap-1 cursor-pointer"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          返回论坛
        </button>

        {/* 搜索框 */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h1 className="text-xl font-bold text-slate-800 mb-4">搜索帖子</h1>
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="输入关键词搜索..."
                className="w-full px-4 py-3 pl-10 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <svg className="absolute left-3 top-3.5 w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <select
              value={selectedForum}
              onChange={(e) => setSelectedForum(e.target.value)}
              className="px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white cursor-pointer"
            >
              <option value="">全部论坛</option>
              {forums.map((forum) => (
                <option key={forum.forum_id} value={forum.forum_id}>
                  {forum.name}
                </option>
              ))}
            </select>
            <button
              onClick={handleSearch}
              disabled={!query.trim() || loading}
              className="px-6 py-3 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-50 transition-colors cursor-pointer"
            >
              {loading ? '搜索中...' : '搜索'}
            </button>
          </div>
        </div>

        {/* 搜索结果 */}
        {loading ? (
          <div className="text-center py-16 text-slate-400">搜索中...</div>
        ) : searched && results.length === 0 ? (
          <div className="text-center py-16 bg-white rounded-xl border border-slate-200">
            <div className="text-5xl mb-4">🔍</div>
            <p className="text-slate-500">未找到相关帖子</p>
            <p className="text-slate-400 text-sm mt-1">试试其他关键词？</p>
          </div>
        ) : results.length > 0 ? (
          <div className="space-y-3">
            <div className="text-sm text-slate-500 mb-2">
              找到 {results.length} 条结果
            </div>
            {results.map((result) => (
              <div
                key={result.post_id}
                className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md hover:border-indigo-200 transition-all"
              >
                <div className="flex justify-between items-start">
                  <div
                    className="flex-1 cursor-pointer"
                    onClick={() => router.push(`/teacher/openboard/post/${result.post_id}`)}
                  >
                    <div className="flex items-center gap-2 text-xs text-indigo-600 mb-2">
                      <span className="px-2 py-0.5 bg-indigo-50 rounded">{result.forum_name}</span>
                    </div>
                    <h3 className="text-lg font-semibold text-slate-800 mb-2 hover:text-indigo-600 transition-colors">
                      {highlightKeyword(result.title, query)}
                    </h3>
                    <p className="text-slate-500 text-sm mb-3">
                      {highlightKeyword(result.content_snippet, query)}
                    </p>
                    <div className="flex items-center gap-3 text-xs text-slate-400">
                      <span>{result.author_name}</span>
                      <span>•</span>
                      <span>{formatTime(result.created_at)}</span>
                    </div>
                  </div>
                  {/* 管理员删除按钮 */}
                  <button
                    onClick={(e) => handleDeletePost(result.post_id, e)}
                    className="ml-4 px-3 py-1.5 text-red-500 hover:bg-red-50 rounded-lg text-sm transition-colors cursor-pointer"
                  >
                    删除
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </DashboardLayout>
  );
}
