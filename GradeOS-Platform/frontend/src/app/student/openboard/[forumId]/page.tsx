'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useAuthStore } from '@/store/authStore';
import { Forum, ForumPost } from '@/types';
import { openboardApi } from '@/services/api';

export default function ForumDetailPage() {
  const { user } = useAuthStore();
  const router = useRouter();
  const params = useParams();
  const forumId = params.forumId as string;
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [forum, setForum] = useState<Forum | null>(null);
  const [posts, setPosts] = useState<ForumPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [createPostOpen, setCreatePostOpen] = useState(false);
  const [newPost, setNewPost] = useState({ title: '', content: '' });
  const [postImages, setPostImages] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);
  const [page, setPage] = useState(1);

  useEffect(() => {
    if (forumId) {
      loadForumData();
    }
  }, [forumId, page]);

  const loadForumData = async () => {
    try {
      setLoading(true);
      const [forumsData, postsData] = await Promise.all([
        openboardApi.getForums(),
        openboardApi.getForumPosts(forumId, page),
      ]);
      const currentForum = forumsData.find(f => f.forum_id === forumId);
      setForum(currentForum || null);
      setPosts(postsData);
    } catch (error) {
      console.error('加载论坛数据失败', error);
    } finally {
      setLoading(false);
    }
  };

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    const remainingSlots = 9 - postImages.length;
    const filesToProcess = Array.from(files).slice(0, remainingSlots);

    filesToProcess.forEach(file => {
      if (file.size > 5 * 1024 * 1024) {
        alert(`图片 ${file.name} 超过5MB限制`);
        return;
      }

      const reader = new FileReader();
      reader.onload = (event) => {
        const base64 = event.target?.result as string;
        setPostImages(prev => [...prev, base64]);
      };
      reader.readAsDataURL(file);
    });

    // 清空 input 以便重复选择同一文件
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeImage = (index: number) => {
    setPostImages(prev => prev.filter((_, i) => i !== index));
  };

  const handleCreatePost = async () => {
    if (!newPost.title.trim() || !newPost.content.trim() || !user?.id) return;
    setCreating(true);
    try {
      await openboardApi.createPost({
        forum_id: forumId,
        title: newPost.title,
        content: newPost.content,
        author_id: user.id,
        images: postImages,
      });
      setCreatePostOpen(false);
      setNewPost({ title: '', content: '' });
      setPostImages([]);
      loadForumData();
    } catch (error: any) {
      if (error.message?.includes('403') || error.message?.includes('禁言')) {
        alert('您已被禁言，无法发帖');
      } else {
        console.error('发帖失败', error);
        alert('发帖失败，请重试');
      }
    } finally {
      setCreating(false);
    }
  };

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
      month: 'numeric',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="text-center py-20 text-slate-400">加载中...</div>
      </DashboardLayout>
    );
  }

  if (!forum) {
    return (
      <DashboardLayout>
        <div className="text-center py-20">
          <div className="text-6xl mb-4">😕</div>
          <p className="text-slate-500">论坛不存在或未通过审核</p>
          <button
            onClick={() => router.push('/student/openboard')}
            className="mt-4 px-6 py-2 bg-indigo-600 text-white rounded-lg"
          >
            返回论坛列表
          </button>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-6">
        {/* 论坛头部 */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <button
            onClick={() => router.push('/student/openboard')}
            className="text-slate-500 hover:text-slate-700 mb-4 flex items-center gap-1 cursor-pointer"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            返回列表
          </button>
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
                <span className="text-3xl">📚</span>
                {forum.name}
              </h1>
              <p className="text-slate-500 mt-2">{forum.description || '暂无描述'}</p>
              <div className="flex items-center gap-4 mt-4 text-sm text-slate-400">
                <span>创建者: {forum.creator_name || '匿名'}</span>
                <span>•</span>
                <span>{forum.post_count} 帖子</span>
                <span>•</span>
                <span>{forum.reply_count} 回复</span>
              </div>
            </div>
            <button
              onClick={() => setCreatePostOpen(true)}
              className="px-6 py-3 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition-colors font-medium cursor-pointer"
            >
              + 发帖
            </button>
          </div>
        </div>

        {/* 帖子列表 */}
        {posts.length === 0 ? (
          <div className="text-center py-16 bg-white rounded-xl border border-slate-200">
            <div className="text-5xl mb-4">📝</div>
            <p className="text-slate-500">暂无帖子</p>
            <p className="text-slate-400 text-sm mt-1">快来发布第一个帖子吧！</p>
          </div>
        ) : (
          <div className="space-y-3">
            {posts.map((post) => (
              <div
                key={post.post_id}
                onClick={() => router.push(`/student/openboard/post/${post.post_id}`)}
                className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md hover:border-indigo-200 transition-all cursor-pointer"
              >
                <h3 className="text-lg font-semibold text-slate-800 mb-2 hover:text-indigo-600">
                  {post.title}
                </h3>
                <p className="text-slate-500 text-sm line-clamp-2 mb-3">
                  {post.content.slice(0, 150)}{post.content.length > 150 ? '...' : ''}
                </p>
                {/* 显示图片缩略图 */}
                {post.images && post.images.length > 0 && (
                  <div className="flex gap-2 mb-3 flex-wrap">
                    {post.images.slice(0, 3).map((img, idx) => (
                      <div key={idx} className="w-16 h-16 rounded-lg overflow-hidden bg-slate-100">
                        <img src={img} alt="" className="w-full h-full object-cover" />
                      </div>
                    ))}
                    {post.images.length > 3 && (
                      <div className="w-16 h-16 rounded-lg bg-slate-100 flex items-center justify-center text-slate-500 text-sm">
                        +{post.images.length - 3}
                      </div>
                    )}
                  </div>
                )}
                <div className="flex items-center justify-between text-sm text-slate-400">
                  <div className="flex items-center gap-3">
                    <span>{post.author_name || '匿名用户'}</span>
                    <span>•</span>
                    <span>{formatTime(post.created_at)}</span>
                    {post.images && post.images.length > 0 && (
                      <>
                        <span>•</span>
                        <span className="text-indigo-400">{post.images.length}张图</span>
                      </>
                    )}
                  </div>
                  <div className="flex items-center gap-1 text-indigo-500">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                    <span>{post.reply_count} 回复</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 发帖弹窗 */}
        {createPostOpen && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-2xl p-8 w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
              <h2 className="text-2xl font-bold text-slate-800 mb-6">发布新帖子</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    标题 *
                  </label>
                  <input
                    type="text"
                    value={newPost.title}
                    onChange={(e) => setNewPost({ ...newPost, title: e.target.value })}
                    placeholder="请输入帖子标题"
                    maxLength={200}
                    className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    内容 *
                  </label>
                  <textarea
                    value={newPost.content}
                    onChange={(e) => setNewPost({ ...newPost, content: e.target.value })}
                    placeholder="分享你的想法..."
                    rows={8}
                    className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                  />
                </div>

                {/* 图片上传区域 */}
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    添加图片（最多9张，每张不超过5MB）
                  </label>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    multiple
                    onChange={handleImageUpload}
                    className="hidden"
                  />
                  <div className="grid grid-cols-3 gap-3">
                    {postImages.map((img, idx) => (
                      <div key={idx} className="relative aspect-square rounded-xl overflow-hidden bg-slate-100 group">
                        <img src={img} alt="" className="w-full h-full object-cover" />
                        <button
                          onClick={() => removeImage(idx)}
                          className="absolute top-2 right-2 w-6 h-6 bg-red-500 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                        >
                          ×
                        </button>
                      </div>
                    ))}
                    {postImages.length < 9 && (
                      <button
                        onClick={() => fileInputRef.current?.click()}
                        className="aspect-square rounded-xl border-2 border-dashed border-slate-300 flex flex-col items-center justify-center text-slate-400 hover:border-indigo-400 hover:text-indigo-500 transition-colors cursor-pointer"
                      >
                        <svg className="w-8 h-8 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                        </svg>
                        <span className="text-sm">添加图片</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex gap-3 mt-6">
                <button
                  onClick={() => {
                    setCreatePostOpen(false);
                    setNewPost({ title: '', content: '' });
                    setPostImages([]);
                  }}
                  className="flex-1 py-3 text-slate-600 hover:bg-slate-100 rounded-xl transition-colors cursor-pointer"
                >
                  取消
                </button>
                <button
                  onClick={handleCreatePost}
                  disabled={!newPost.title.trim() || !newPost.content.trim() || creating}
                  className="flex-1 py-3 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
                >
                  {creating ? '发布中...' : '发布帖子'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
