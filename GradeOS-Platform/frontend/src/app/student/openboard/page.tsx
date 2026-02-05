'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useAuthStore } from '@/store/authStore';
import { Forum } from '@/types';
import { openboardApi } from '@/services/api';

export default function OpenBoardPage() {
  const { user } = useAuthStore();
  const router = useRouter();
  const [forums, setForums] = useState<Forum[]>([]);
  const [loading, setLoading] = useState(true);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [newForum, setNewForum] = useState({ name: '', description: '' });
  const [creating, setCreating] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    loadForums();
  }, []);

  const loadForums = async () => {
    try {
      setLoading(true);
      const data = await openboardApi.getForums();
      setForums(data);
    } catch (error) {
      console.error('加载论坛列表失败', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateForum = async () => {
    if (!newForum.name.trim() || !user?.id) return;
    setCreating(true);
    try {
      await openboardApi.createForum({
        name: newForum.name,
        description: newForum.description,
        creator_id: user.id,
      });
      setCreateModalOpen(false);
      setNewForum({ name: '', description: '' });
      loadForums();
    } catch (error) {
      console.error('创建论坛失败', error);
    } finally {
      setCreating(false);
    }
  };

  const formatTime = (dateStr?: string) => {
    if (!dateStr) return '暂无活动';
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    
    if (minutes < 1) return '刚刚';
    if (minutes < 60) return `${minutes}分钟前`;
    if (hours < 24) return `${hours}小时前`;
    if (days < 7) return `${days}天前`;
    return date.toLocaleDateString('zh-CN');
  };

  const filteredForums = forums.filter(f => 
    f.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    f.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <DashboardLayout>
      <div className="max-w-5xl mx-auto space-y-6">
        {/* 头部 */}
        <div className="bg-gradient-to-r from-indigo-500 to-purple-600 rounded-2xl p-8 text-white">
          <h1 className="text-3xl font-bold mb-2">OpenBoard 学习社区</h1>
          <p className="text-indigo-100">分享知识，共同进步</p>
        </div>

        {/* 搜索和操作栏 */}
        <div className="flex gap-4 items-center">
          <div className="flex-1 relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜索论坛..."
              className="w-full px-4 py-3 pl-10 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <svg className="absolute left-3 top-3.5 w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <button
            onClick={() => router.push('/student/openboard/search')}
            className="px-4 py-3 bg-slate-100 text-slate-700 rounded-xl hover:bg-slate-200 transition-colors"
          >
            搜索帖子
          </button>
          <button
            onClick={() => setCreateModalOpen(true)}
            className="px-6 py-3 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition-colors font-medium"
          >
            + 创建论坛
          </button>
        </div>

        {/* 论坛列表 */}
        {loading ? (
          <div className="text-center py-20 text-slate-400">加载中...</div>
        ) : filteredForums.length === 0 ? (
          <div className="text-center py-20">
            <div className="text-6xl mb-4">📭</div>
            <p className="text-slate-500">暂无论坛，快来创建第一个吧！</p>
          </div>
        ) : (
          <div className="grid gap-4">
            {filteredForums.map((forum) => (
              <div
                key={forum.forum_id}
                onClick={() => router.push(`/student/openboard/${forum.forum_id}`)}
                className="bg-white rounded-xl border border-slate-200 p-6 hover:shadow-lg hover:border-indigo-200 transition-all cursor-pointer"
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <h3 className="text-xl font-bold text-slate-800 mb-2 flex items-center gap-2">
                      <span className="text-2xl">📚</span>
                      {forum.name}
                    </h3>
                    <p className="text-slate-500 mb-4 line-clamp-2">
                      {forum.description || '暂无描述'}
                    </p>
                    <div className="flex items-center gap-4 text-sm text-slate-400">
                      <span>创建者: {forum.creator_name || '匿名'}</span>
                      <span>•</span>
                      <span>{forum.post_count} 帖子</span>
                      <span>•</span>
                      <span>{forum.reply_count} 回复</span>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm text-slate-400">
                      最后活动
                    </div>
                    <div className="text-indigo-600 font-medium">
                      {formatTime(forum.last_activity_at)}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 创建论坛弹窗 */}
        {createModalOpen && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-2xl p-8 w-full max-w-md mx-4">
              <h2 className="text-2xl font-bold text-slate-800 mb-6">创建新论坛</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    论坛名称 *
                  </label>
                  <input
                    type="text"
                    value={newForum.name}
                    onChange={(e) => setNewForum({ ...newForum, name: e.target.value })}
                    placeholder="例如：数学好题分享吧"
                    maxLength={100}
                    className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    论坛描述
                  </label>
                  <textarea
                    value={newForum.description}
                    onChange={(e) => setNewForum({ ...newForum, description: e.target.value })}
                    placeholder="简单介绍一下这个论坛的主题..."
                    rows={3}
                    maxLength={500}
                    className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                  />
                </div>
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-700">
                  提示：创建的论坛需要老师审核通过后才能使用
                </div>
              </div>
              <div className="flex gap-3 mt-6">
                <button
                  onClick={() => setCreateModalOpen(false)}
                  className="flex-1 py-3 text-slate-600 hover:bg-slate-100 rounded-xl transition-colors"
                >
                  取消
                </button>
                <button
                  onClick={handleCreateForum}
                  disabled={!newForum.name.trim() || creating}
                  className="flex-1 py-3 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {creating ? '提交中...' : '提交申请'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
