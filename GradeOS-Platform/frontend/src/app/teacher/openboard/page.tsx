'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useAuthStore } from '@/store/authStore';
import { Forum, ForumUserStatus, ForumModLog } from '@/types';
import { openboardApi } from '@/services/api';

type TabType = 'browse' | 'pending' | 'users' | 'logs';

export default function TeacherOpenBoardPage() {
  const { user } = useAuthStore();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabType>('browse');
  const [forums, setForums] = useState<Forum[]>([]);
  const [pendingForums, setPendingForums] = useState<Forum[]>([]);
  const [modLogs, setModLogs] = useState<ForumModLog[]>([]);
  const [loading, setLoading] = useState(true);
  
  // 创建论坛
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newForumName, setNewForumName] = useState('');
  const [newForumDesc, setNewForumDesc] = useState('');
  const [creating, setCreating] = useState(false);
  
  // 用户管理
  const [searchUserId, setSearchUserId] = useState('');
  const [userStatus, setUserStatus] = useState<ForumUserStatus | null>(null);
  const [searchingUser, setSearchingUser] = useState(false);

  useEffect(() => {
    loadData();
  }, [activeTab]);

  const loadData = async () => {
    setLoading(true);
    try {
      if (activeTab === 'browse') {
        const data = await openboardApi.getForums(false);
        setForums(data);
      } else if (activeTab === 'pending') {
        const data = await openboardApi.getPendingForums();
        setPendingForums(data);
      } else if (activeTab === 'logs') {
        const data = await openboardApi.getModLogs();
        setModLogs(data);
      }
    } catch (error) {
      console.error('加载数据失败', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateForum = async () => {
    if (!newForumName.trim() || !user?.id) return;
    setCreating(true);
    try {
      await openboardApi.createForum({
        name: newForumName,
        description: newForumDesc,
        creator_id: user.id,
      });
      setShowCreateModal(false);
      setNewForumName('');
      setNewForumDesc('');
      alert('论坛创建申请已提交，等待审核');
    } catch (error: any) {
      if (error.message?.includes('403') || error.message?.includes('禁言')) {
        alert('您已被禁言，无法创建论坛');
      } else {
        alert('创建失败，请重试');
      }
    } finally {
      setCreating(false);
    }
  };

  const handleApproveForum = async (forumId: string, approved: boolean, reason?: string) => {
    if (!user?.id) return;
    try {
      await openboardApi.approveForum(forumId, {
        approved,
        reason,
        moderator_id: user.id,
      });
      setPendingForums(pendingForums.filter(f => f.forum_id !== forumId));
    } catch (error) {
      console.error('审核失败', error);
    }
  };

  const handleSearchUser = async () => {
    if (!searchUserId.trim()) return;
    setSearchingUser(true);
    try {
      const data = await openboardApi.getUserStatus(searchUserId);
      setUserStatus(data);
    } catch (error) {
      console.error('查询用户失败', error);
      setUserStatus(null);
    } finally {
      setSearchingUser(false);
    }
  };

  const handleBanUser = async (userId: string, banned: boolean) => {
    if (!user?.id) return;
    try {
      await openboardApi.banUser({
        user_id: userId,
        moderator_id: user.id,
        banned,
      });
      if (userStatus) {
        setUserStatus({ ...userStatus, is_banned: banned });
      }
    } catch (error) {
      console.error('操作失败', error);
    }
  };

  const formatTime = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('zh-CN');
  };

  const getActionText = (action: string) => {
    const actionMap: Record<string, string> = {
      approve_forum: '通过论坛',
      reject_forum: '拒绝论坛',
      delete_post: '删除帖子',
      ban_user: '封禁用户',
      unban_user: '解封用户',
    };
    return actionMap[action] || action;
  };

  return (
    <DashboardLayout>
      <div className="max-w-5xl mx-auto space-y-6">
        {/* 头部 */}
        <div className="bg-gradient-to-r from-rose-500 to-orange-500 rounded-2xl p-8 text-white">
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-3xl font-bold mb-2">OpenBoard 论坛</h1>
              <p className="text-rose-100">浏览论坛、发帖交流、管理社区</p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => router.push('/teacher/openboard/search')}
                className="px-5 py-2.5 bg-white/20 hover:bg-white/30 rounded-xl font-medium transition-colors cursor-pointer flex items-center gap-2"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                搜索帖子
              </button>
              <button
                onClick={() => setShowCreateModal(true)}
                className="px-5 py-2.5 bg-white/20 hover:bg-white/30 rounded-xl font-medium transition-colors cursor-pointer"
              >
                + 申请创建论坛
              </button>
            </div>
          </div>
        </div>

        {/* 标签页 */}
        <div className="flex gap-2 bg-white rounded-xl p-2 border border-slate-200">
          <button
            onClick={() => setActiveTab('browse')}
            className={`flex-1 py-3 rounded-lg font-medium transition-colors cursor-pointer ${
              activeTab === 'browse'
                ? 'bg-indigo-600 text-white'
                : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            浏览论坛
          </button>
          <button
            onClick={() => setActiveTab('pending')}
            className={`flex-1 py-3 rounded-lg font-medium transition-colors cursor-pointer ${
              activeTab === 'pending'
                ? 'bg-indigo-600 text-white'
                : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            待审核 ({pendingForums.length})
          </button>
          <button
            onClick={() => setActiveTab('users')}
            className={`flex-1 py-3 rounded-lg font-medium transition-colors cursor-pointer ${
              activeTab === 'users'
                ? 'bg-indigo-600 text-white'
                : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            用户管理
          </button>
          <button
            onClick={() => setActiveTab('logs')}
            className={`flex-1 py-3 rounded-lg font-medium transition-colors cursor-pointer ${
              activeTab === 'logs'
                ? 'bg-indigo-600 text-white'
                : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            操作日志
          </button>
        </div>

        {/* 内容区域 */}
        {loading ? (
          <div className="text-center py-16 text-slate-400">加载中...</div>
        ) : (
          <>
            {/* 浏览论坛 */}
            {activeTab === 'browse' && (
              <div className="space-y-4">
                {forums.length === 0 ? (
                  <div className="text-center py-16 bg-white rounded-xl border border-slate-200">
                    <div className="text-5xl mb-4">📭</div>
                    <p className="text-slate-500">暂无论坛</p>
                    <button
                      onClick={() => setShowCreateModal(true)}
                      className="mt-4 px-6 py-2 bg-indigo-600 text-white rounded-lg cursor-pointer"
                    >
                      创建第一个论坛
                    </button>
                  </div>
                ) : (
                  <div className="grid gap-4">
                    {forums.map((forum) => (
                      <div
                        key={forum.forum_id}
                        onClick={() => router.push(`/teacher/openboard/${forum.forum_id}`)}
                        className="bg-white rounded-xl border border-slate-200 p-6 hover:shadow-lg hover:border-indigo-200 transition-all cursor-pointer"
                      >
                        <div className="flex justify-between items-start">
                          <div className="flex-1">
                            <h3 className="text-lg font-bold text-slate-800 mb-1">{forum.name}</h3>
                            <p className="text-slate-500 text-sm mb-3">{forum.description || '暂无描述'}</p>
                            <div className="flex items-center gap-4 text-xs text-slate-400">
                              <span>创建者: {forum.creator_name || '未知'}</span>
                              <span>帖子: {forum.post_count}</span>
                              <span>回复: {forum.reply_count}</span>
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-xs text-slate-400">
                              {forum.last_activity_at ? `最近活动: ${formatTime(forum.last_activity_at)}` : '暂无活动'}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* 待审核论坛 */}
            {activeTab === 'pending' && (
              <div className="space-y-4">
                {pendingForums.length === 0 ? (
                  <div className="text-center py-16 bg-white rounded-xl border border-slate-200">
                    <div className="text-5xl mb-4">✅</div>
                    <p className="text-slate-500">暂无待审核的论坛</p>
                  </div>
                ) : (
                  pendingForums.map((forum) => (
                    <div key={forum.forum_id} className="bg-white rounded-xl border border-slate-200 p-6">
                      <div className="flex justify-between items-start">
                        <div>
                          <h3 className="text-lg font-bold text-slate-800 mb-1">{forum.name}</h3>
                          <p className="text-slate-500 text-sm mb-2">{forum.description || '暂无描述'}</p>
                          <div className="text-xs text-slate-400">
                            申请人: {forum.creator_name || forum.creator_id} · {formatTime(forum.created_at)}
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => {
                              const reason = prompt('请输入拒绝原因（可选）');
                              handleApproveForum(forum.forum_id, false, reason || undefined);
                            }}
                            className="px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors cursor-pointer"
                          >
                            拒绝
                          </button>
                          <button
                            onClick={() => handleApproveForum(forum.forum_id, true)}
                            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors cursor-pointer"
                          >
                            通过
                          </button>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* 用户管理 */}
            {activeTab === 'users' && (
              <div className="space-y-4">
                <div className="bg-white rounded-xl border border-slate-200 p-6">
                  <h3 className="font-bold text-slate-800 mb-4">查询用户</h3>
                  <div className="flex gap-3">
                    <input
                      type="text"
                      value={searchUserId}
                      onChange={(e) => setSearchUserId(e.target.value)}
                      placeholder="输入用户ID"
                      className="flex-1 px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                    <button
                      onClick={handleSearchUser}
                      disabled={!searchUserId.trim() || searchingUser}
                      className="px-6 py-3 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-50 transition-colors cursor-pointer"
                    >
                      {searchingUser ? '查询中...' : '查询'}
                    </button>
                  </div>
                </div>

                {userStatus && (
                  <div className="bg-white rounded-xl border border-slate-200 p-6">
                    <div className="flex justify-between items-start mb-4">
                      <div>
                        <h3 className="text-lg font-bold text-slate-800">{userStatus.name}</h3>
                        <p className="text-sm text-slate-400">ID: {userStatus.user_id}</p>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                          userStatus.is_banned
                            ? 'bg-red-100 text-red-700'
                            : 'bg-green-100 text-green-700'
                        }`}>
                          {userStatus.is_banned ? '已封禁' : '正常'}
                        </span>
                        <button
                          onClick={() => handleBanUser(userStatus.user_id, !userStatus.is_banned)}
                          className={`px-4 py-2 rounded-lg transition-colors cursor-pointer ${
                            userStatus.is_banned
                              ? 'bg-green-600 text-white hover:bg-green-700'
                              : 'bg-red-600 text-white hover:bg-red-700'
                          }`}
                        >
                          {userStatus.is_banned ? '解除封禁' : '封禁用户'}
                        </button>
                      </div>
                    </div>
                    
                    {userStatus.is_banned && userStatus.ban_reason && (
                      <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 text-sm text-red-700">
                        封禁原因: {userStatus.ban_reason}
                      </div>
                    )}

                    <h4 className="font-medium text-slate-700 mb-3">发帖记录</h4>
                    {userStatus.posts.length === 0 ? (
                      <p className="text-slate-400 text-sm">暂无发帖记录</p>
                    ) : (
                      <div className="space-y-2">
                        {userStatus.posts.map((post) => (
                          <div key={post.post_id} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                            <div>
                              <span className={post.is_deleted ? 'line-through text-slate-400' : 'text-slate-700'}>
                                {post.title}
                              </span>
                              <span className="text-xs text-slate-400 ml-2">{post.forum_name}</span>
                            </div>
                            <span className="text-xs text-slate-400">{formatTime(post.created_at)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* 操作日志 */}
            {activeTab === 'logs' && (
              <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                {modLogs.length === 0 ? (
                  <div className="text-center py-16 text-slate-400">暂无操作日志</div>
                ) : (
                  <table className="w-full">
                    <thead className="bg-slate-50 border-b border-slate-200">
                      <tr>
                        <th className="text-left px-6 py-3 text-sm font-medium text-slate-600">时间</th>
                        <th className="text-left px-6 py-3 text-sm font-medium text-slate-600">操作人</th>
                        <th className="text-left px-6 py-3 text-sm font-medium text-slate-600">操作</th>
                        <th className="text-left px-6 py-3 text-sm font-medium text-slate-600">目标</th>
                        <th className="text-left px-6 py-3 text-sm font-medium text-slate-600">原因</th>
                      </tr>
                    </thead>
                    <tbody>
                      {modLogs.map((log) => (
                        <tr key={log.log_id} className="border-b border-slate-100 hover:bg-slate-50">
                          <td className="px-6 py-4 text-sm text-slate-500">{formatTime(log.created_at)}</td>
                          <td className="px-6 py-4 text-sm text-slate-700">{log.moderator_name || log.moderator_id}</td>
                          <td className="px-6 py-4">
                            <span className="px-2 py-1 bg-indigo-50 text-indigo-700 rounded text-xs font-medium">
                              {getActionText(log.action)}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-sm text-slate-500">{log.target_type}: {log.target_id}</td>
                          <td className="px-6 py-4 text-sm text-slate-400">{log.reason || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* 创建论坛弹窗 */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-8 w-full max-w-md mx-4">
            <h2 className="text-xl font-bold text-slate-800 mb-6">申请创建论坛</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">论坛名称</label>
                <input
                  type="text"
                  value={newForumName}
                  onChange={(e) => setNewForumName(e.target.value)}
                  placeholder="输入论坛名称"
                  className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">论坛描述（可选）</label>
                <textarea
                  value={newForumDesc}
                  onChange={(e) => setNewForumDesc(e.target.value)}
                  placeholder="简单描述这个论坛的主题"
                  rows={3}
                  className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowCreateModal(false)}
                className="flex-1 py-3 border border-slate-200 rounded-xl text-slate-600 hover:bg-slate-50 transition-colors cursor-pointer"
              >
                取消
              </button>
              <button
                onClick={handleCreateForum}
                disabled={!newForumName.trim() || creating}
                className="flex-1 py-3 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-50 transition-colors cursor-pointer"
              >
                {creating ? '提交中...' : '提交申请'}
              </button>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
