'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useAuthStore } from '@/store/authStore';
import { Forum, ForumPost } from '@/types';
import { openboardApi } from '@/services/api';

export default function TeacherForumDetailPage() {
  const { user } = useAuthStore();
  const router = useRouter();
  const params = useParams();
  const forumId = params.forumId as string;

  const [forum, setForum] = useState<Forum | null>(null);
  const [posts, setPosts] = useState<ForumPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreatePost, setShowCreatePost] = useState(false);
  const [newPostTitle, setNewPostTitle] = useState('');
  const [newPostContent, setNewPostContent] = useState('');
  const [newPostImages, setNewPostImages] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (forumId) {
      loadForumData();
    }
  }, [forumId]);

  const loadForumData = async () => {
    try {
      setLoading(true);
      const [forumsData, postsData] = await Promise.all([
        openboardApi.getForums(false),
        openboardApi.getForumPosts(forumId),
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

    const maxImages = 9;
    const maxSize = 5 * 1024 * 1024;

    Array.from(files).forEach((file) => {
      if (newPostImages.length >= maxImages) {
        alert(`最多只能上传 ${maxImages} 张图片`);
        return;
      }
      if (file.size > maxSize) {
        alert(`图片 ${file.name} 超过 5MB 限制`);
        return;
      }
      const reader = new FileReader();
      reader.onload = (ev) => {
        const base64 = ev.target?.result as string;
        setNewPostImages((prev) => {
          if (prev.length >= maxImages) return prev;
          return [...prev, base64];
        });
      };
      reader.readAsDataURL(file);
    });
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const removeImage = (index: number) => {
    setNewPostImages((prev) => prev.filter((_, i) => i !== index));
  };

  const handleCreatePost = async () => {
    if (!newPostTitle.trim() || !newPostContent.trim() || !user?.id) return;
    setCreating(true);
    try {
      const newPost = await openboardApi.createPost({
        forum_id: forumId,
        title: newPostTitle,
        content: newPostContent,
        author_id: user.id,
        images: newPostImages,
      });
      setPosts([newPost, ...posts]);
      setShowCreatePost(false);
      setNewPostTitle('');
      setNewPostContent('');
      setNewPostImages([]);
    } catch (error: any) {
      if (error.message?.includes('403') || error.message?.includes('禁言')) {
        alert('您已被禁言，无法发帖');
      } else {
        alert('发帖失败，请重试');
      }
    } finally {
      setCreating(false);
    }
  };

  const handleDeletePost = async (postId: string) => {
    if (!user?.id) return;
    if (!confirm('确定要删除这个帖子吗？')) return;
    try {
      await openboardApi.deletePost(postId, user.id, '管理员删除');
      setPosts(posts.filter(p => p.post_id !== postId));
    } catch (error) {
      console.error('删除失败', error);
      alert('删除失败');
    }
  };

  const formatTime = (dateStr: string) => {
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
            onClick={() => router.push('/teacher/openboard')}
            className="mt-4 px-6 py-2 bg-indigo-600 text-white rounded-lg cursor-pointer"
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
        <div className="bg-gradient-to-r from-indigo-500 to-purple-500 rounded-2xl p-8 text-white">
          <button
            onClick={() => router.push('/teacher/openboard')}
            className="text-white/80 hover:text-white flex items-center gap-1 mb-4 cursor-pointer"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            返回论坛列表
          </button>
          <h1 className="text-3xl font-bold mb-2">{forum.name}</h1>
          <p className="text-indigo-100 mb-4">{forum.description || '暂无描述'}</p>
          <div className="flex items-center gap-6 text-sm text-indigo-200">
            <span>帖子: {forum.post_count}</span>
            <span>回复: {forum.reply_count}</span>
            <span>创建者: {forum.creator_name || '未知'}</span>
          </div>
        </div>

        {/* 发帖按钮 */}
        <div className="flex justify-end">
          <button
            onClick={() => setShowCreatePost(true)}
            className="px-6 py-3 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition-colors flex items-center gap-2 cursor-pointer"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            发表新帖
          </button>
        </div>

        {/* 帖子列表 */}
        {posts.length === 0 ? (
          <div className="text-center py-16 bg-white rounded-xl border border-slate-200">
            <div className="text-5xl mb-4">📝</div>
            <p className="text-slate-500 mb-4">这个论坛还没有帖子</p>
            <button
              onClick={() => setShowCreatePost(true)}
              className="px-6 py-2 bg-indigo-600 text-white rounded-lg cursor-pointer"
            >
              发表第一个帖子
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {posts.map((post) => (
              <div
                key={post.post_id}
                className="bg-white rounded-xl border border-slate-200 p-6 hover:shadow-md transition-shadow"
              >
                <div className="flex justify-between items-start">
                  <div
                    className="flex-1 cursor-pointer"
                    onClick={() => router.push(`/teacher/openboard/post/${post.post_id}`)}
                  >
                    <h3 className="text-lg font-bold text-slate-800 mb-2 hover:text-indigo-600 transition-colors">
                      {post.title}
                    </h3>
                    <p className="text-slate-500 text-sm line-clamp-2 mb-3">{post.content}</p>
                    {post.images && post.images.length > 0 && (
                      <div className="flex gap-2 mb-3">
                        {post.images.slice(0, 3).map((img, idx) => (
                          <div key={idx} className="w-16 h-16 rounded-lg overflow-hidden bg-slate-100">
                            <img src={img} alt="" className="w-full h-full object-cover" />
                          </div>
                        ))}
                        {post.images.length > 3 && (
                          <div className="w-16 h-16 rounded-lg bg-slate-100 flex items-center justify-center text-slate-400 text-sm">
                            +{post.images.length - 3}
                          </div>
                        )}
                      </div>
                    )}
                    <div className="flex items-center gap-4 text-xs text-slate-400">
                      <span>{post.author_name || '匿名用户'}</span>
                      <span>{formatTime(post.created_at)}</span>
                      <span>{post.reply_count} 回复</span>
                    </div>
                  </div>
                  {/* 管理员删除按钮 */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeletePost(post.post_id);
                    }}
                    className="ml-4 px-3 py-1.5 text-red-500 hover:bg-red-50 rounded-lg text-sm transition-colors cursor-pointer"
                  >
                    删除
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 发帖弹窗 */}
      {showCreatePost && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-8 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <h2 className="text-xl font-bold text-slate-800 mb-6">发表新帖</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">标题</label>
                <input
                  type="text"
                  value={newPostTitle}
                  onChange={(e) => setNewPostTitle(e.target.value)}
                  placeholder="输入帖子标题"
                  className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">内容</label>
                <textarea
                  value={newPostContent}
                  onChange={(e) => setNewPostContent(e.target.value)}
                  placeholder="写下你想分享的内容..."
                  rows={6}
                  className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">图片（可选，最多9张）</label>
                {newPostImages.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-3">
                    {newPostImages.map((img, idx) => (
                      <div key={idx} className="relative w-20 h-20 rounded-lg overflow-hidden bg-slate-100">
                        <img src={img} alt={`预览 ${idx + 1}`} className="w-full h-full object-cover" />
                        <button
                          onClick={() => removeImage(idx)}
                          className="absolute top-1 right-1 w-5 h-5 bg-black/60 text-white rounded-full flex items-center justify-center text-xs cursor-pointer hover:bg-black/80"
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={handleImageUpload}
                  className="hidden"
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={newPostImages.length >= 9}
                  className="flex items-center gap-2 px-4 py-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-50 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  添加图片 ({newPostImages.length}/9)
                </button>
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => {
                  setShowCreatePost(false);
                  setNewPostTitle('');
                  setNewPostContent('');
                  setNewPostImages([]);
                }}
                className="flex-1 py-3 border border-slate-200 rounded-xl text-slate-600 hover:bg-slate-50 transition-colors cursor-pointer"
              >
                取消
              </button>
              <button
                onClick={handleCreatePost}
                disabled={!newPostTitle.trim() || !newPostContent.trim() || creating}
                className="flex-1 py-3 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-50 transition-colors cursor-pointer"
              >
                {creating ? '发布中...' : '发布帖子'}
              </button>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
