'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useAuthStore } from '@/store/authStore';
import { ForumPost, ForumReply } from '@/types';
import { openboardApi } from '@/services/api';

export default function PostDetailPage() {
  const { user } = useAuthStore();
  const router = useRouter();
  const params = useParams();
  const postId = params.postId as string;

  const [post, setPost] = useState<ForumPost | null>(null);
  const [replies, setReplies] = useState<ForumReply[]>([]);
  const [loading, setLoading] = useState(true);
  const [replyContent, setReplyContent] = useState('');
  const [replyImages, setReplyImages] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [lightboxImage, setLightboxImage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (postId) {
      loadPostData();
    }
  }, [postId]);

  const loadPostData = async () => {
    try {
      setLoading(true);
      const data = await openboardApi.getPostDetail(postId);
      setPost(data.post);
      setReplies(data.replies);
    } catch (error) {
      console.error('加载帖子失败', error);
    } finally {
      setLoading(false);
    }
  };

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    const maxImages = 5;
    const maxSize = 5 * 1024 * 1024; // 5MB

    Array.from(files).forEach((file) => {
      if (replyImages.length >= maxImages) {
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
        setReplyImages((prev) => {
          if (prev.length >= maxImages) return prev;
          return [...prev, base64];
        });
      };
      reader.readAsDataURL(file);
    });
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const removeImage = (index: number) => {
    setReplyImages((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmitReply = async () => {
    if ((!replyContent.trim() && replyImages.length === 0) || !user?.id) return;
    setSubmitting(true);
    try {
      const newReply = await openboardApi.createReply(postId, {
        content: replyContent,
        author_id: user.id,
        images: replyImages,
      });
      setReplies([...replies, newReply]);
      setReplyContent('');
      setReplyImages([]);
      if (post) {
        setPost({ ...post, reply_count: post.reply_count + 1 });
      }
    } catch (error: any) {
      if (error.message?.includes('403') || error.message?.includes('禁言')) {
        alert('您已被禁言，无法回复');
      } else {
        console.error('回复失败', error);
        alert('回复失败，请重试');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: 'numeric',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // 渲染图片网格
  const renderImages = (images: string[] | undefined) => {
    if (!images || images.length === 0) return null;
    return (
      <div className={`mt-4 grid gap-2 ${
        images.length === 1 ? 'grid-cols-1 max-w-xs' :
        images.length === 2 ? 'grid-cols-2 max-w-sm' :
        'grid-cols-3 max-w-md'
      }`}>
        {images.map((img, idx) => (
          <div
            key={idx}
            onClick={() => setLightboxImage(img)}
            className="aspect-square rounded-lg overflow-hidden bg-slate-100 cursor-pointer hover:opacity-90 transition-opacity"
          >
            <img src={img} alt={`图片 ${idx + 1}`} className="w-full h-full object-cover" />
          </div>
        ))}
      </div>
    );
  };

  // 渲染楼层
  const renderFloor = (
    floorNumber: number,
    authorName: string,
    authorId: string,
    content: string,
    images: string[] | undefined,
    createdAt: string,
    isOP: boolean = false
  ) => (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      {/* 楼层头部 */}
      <div className="flex items-center justify-between px-6 py-4 bg-slate-50 border-b border-slate-100">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold ${
            isOP ? 'bg-indigo-100 text-indigo-600' : 'bg-slate-200 text-slate-600'
          }`}>
            {(authorName || '匿')[0]}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-medium text-slate-800">{authorName || '匿名用户'}</span>
              {isOP && (
                <span className="px-2 py-0.5 bg-indigo-500 text-white text-xs rounded-full">楼主</span>
              )}
            </div>
            <div className="text-xs text-slate-400">{formatTime(createdAt)}</div>
          </div>
        </div>
        <div className={`px-3 py-1 rounded-full text-sm font-medium ${
          isOP ? 'bg-indigo-100 text-indigo-600' : 'bg-slate-100 text-slate-500'
        }`}>
          {floorNumber === 1 ? '楼主' : `${floorNumber}楼`}
        </div>
      </div>
      {/* 楼层内容 */}
      <div className="px-6 py-5">
        <p className="whitespace-pre-wrap text-slate-700 leading-relaxed">{content}</p>
        {renderImages(images)}
      </div>
    </div>
  );

  if (loading) {
    return (
      <DashboardLayout>
        <div className="text-center py-20 text-slate-400">加载中...</div>
      </DashboardLayout>
    );
  }

  if (!post) {
    return (
      <DashboardLayout>
        <div className="text-center py-20">
          <div className="text-6xl mb-4">😕</div>
          <p className="text-slate-500">帖子不存在或已被删除</p>
          <button
            onClick={() => router.push('/student/openboard')}
            className="mt-4 px-6 py-2 bg-indigo-600 text-white rounded-lg cursor-pointer"
          >
            返回论坛
          </button>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-4">
        {/* 返回按钮和标题 */}
        <div className="flex items-center justify-between">
          <button
            onClick={() => router.push(`/student/openboard/${post.forum_id}`)}
            className="text-slate-500 hover:text-slate-700 flex items-center gap-1 cursor-pointer"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            返回 {post.forum_name || '论坛'}
          </button>
          <div className="text-sm text-slate-400">
            共 {replies.length + 1} 层
          </div>
        </div>

        {/* 帖子标题 */}
        <div className="bg-gradient-to-r from-indigo-500 to-purple-500 rounded-xl px-6 py-4 text-white">
          <h1 className="text-xl font-bold">{post.title}</h1>
        </div>

        {/* 1楼：楼主帖子 */}
        {renderFloor(1, post.author_name || '匿名用户', post.author_id, post.content, post.images, post.created_at, true)}

        {/* 回复楼层 */}
        {replies.map((reply, index) => (
          <div key={reply.reply_id}>
            {renderFloor(
              index + 2,
              reply.author_name || '匿名用户',
              reply.author_id,
              reply.content,
              reply.images,
              reply.created_at,
              reply.author_id === post.author_id
            )}
          </div>
        ))}

        {/* 回复输入区域 */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h3 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
            <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
            发表回复
          </h3>
          
          <textarea
            value={replyContent}
            onChange={(e) => setReplyContent(e.target.value)}
            placeholder="写下你的回复..."
            rows={4}
            className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none mb-3"
          />

          {/* 图片预览 */}
          {replyImages.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {replyImages.map((img, idx) => (
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

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
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
                disabled={replyImages.length >= 5}
                className="flex items-center gap-1 px-3 py-2 text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                <span className="text-sm">添加图片</span>
              </button>
              <span className="text-xs text-slate-400">
                {replyImages.length}/5 张
              </span>
            </div>
            <button
              onClick={handleSubmitReply}
              disabled={(!replyContent.trim() && replyImages.length === 0) || submitting}
              className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
            >
              {submitting ? '发送中...' : '发表回复'}
            </button>
          </div>
        </div>
      </div>

      {/* 图片灯箱 */}
      {lightboxImage && (
        <div
          className="fixed inset-0 bg-black/90 flex items-center justify-center z-50 cursor-pointer"
          onClick={() => setLightboxImage(null)}
        >
          <button
            className="absolute top-4 right-4 text-white text-4xl hover:text-slate-300 cursor-pointer"
            onClick={() => setLightboxImage(null)}
          >
            ×
          </button>
          <img
            src={lightboxImage}
            alt="大图预览"
            className="max-w-[90vw] max-h-[90vh] object-contain"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </DashboardLayout>
  );
}
