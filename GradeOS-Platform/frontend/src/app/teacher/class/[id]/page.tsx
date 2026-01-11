'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';

interface Student {
  id: string;
  name: string;
  username: string;
  avgScore?: number;
  submissionRate?: number;
}

interface ClassDetail {
  class_id: string;
  class_name: string;
  invite_code: string;
  student_count: number;
  students: Student[];
}

export default function ClassDetailPage() {
  const params = useParams();
  const router = useRouter();
  const classId = params.id as string;

  const [classDetail, setClassDetail] = useState<ClassDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'students' | 'homework' | 'grading_history' | 'stats'>('students');
  const [showInviteModal, setShowInviteModal] = useState(false);

  useEffect(() => {
    // Mock data - 实际应调用 API
    setTimeout(() => {
      setClassDetail({
        class_id: classId,
        class_name: 'Advanced Physics 2024',
        invite_code: 'PHY24A',
        student_count: 32,
        students: [
          { id: 's-001', name: 'Alice Chen', username: 'alice', avgScore: 92, submissionRate: 100 },
          { id: 's-002', name: 'Bob Wang', username: 'bob', avgScore: 78, submissionRate: 95 },
          { id: 's-003', name: 'Carol Liu', username: 'carol', avgScore: 85, submissionRate: 100 },
          { id: 's-004', name: 'David Zhang', username: 'david', avgScore: 88, submissionRate: 90 },
          { id: 's-005', name: 'Eva Li', username: 'eva', avgScore: 95, submissionRate: 100 },
        ],
      });
      setLoading(false);
    }, 500);
  }, [classId]);

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      </DashboardLayout>
    );
  }

  if (!classDetail) {
    return (
      <DashboardLayout>
        <div className="text-center py-12">
          <p className="text-slate-500">班级不存在</p>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <button
              onClick={() => router.back()}
              className="text-slate-500 hover:text-slate-700 mb-2 flex items-center gap-1"
            >
              ← 返回
            </button>
            <h1 className="text-2xl font-bold text-slate-800">{classDetail.class_name}</h1>
            <p className="text-slate-500">{classDetail.student_count} 名学生</p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => {
                // TODO: 需选择作业，此处暂时硬编码示例 ID
                router.push(`/console?classId=${classDetail.class_id}&homeworkId=homework-1`);
              }}
              className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 flex items-center gap-2"
            >
              <span>✨</span>
              Start Grading
            </button>
            <button
              onClick={() => setShowInviteModal(true)}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Invite Students
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="border-b border-slate-200">
          <nav className="flex gap-8">
            {[
              { key: 'students', label: '学生列表' },
              { key: 'homework', label: '作业管理' },
              { key: 'grading_history', label: '批改历史' },
              { key: 'stats', label: '班级统计' },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key as typeof activeTab)}
                className={`pb-3 text-sm font-medium border-b-2 transition-colors ${activeTab === tab.key
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
                  }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        {activeTab === 'students' && (
          <div className="bg-white rounded-xl shadow-sm overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase">学生</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase">用户名</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase">平均分</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase">提交率</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {classDetail.students.map((student) => (
                  <tr key={student.id} className="hover:bg-slate-50">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                          <span className="text-blue-600 font-medium text-sm">
                            {student.name.charAt(0)}
                          </span>
                        </div>
                        <span className="font-medium text-slate-800">{student.name}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-slate-600">{student.username}</td>
                    <td className="px-6 py-4">
                      <span className={`font-medium ${(student.avgScore || 0) >= 90 ? 'text-green-600' :
                        (student.avgScore || 0) >= 60 ? 'text-blue-600' : 'text-red-600'
                        }`}>
                        {student.avgScore || '-'}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div className="w-24 h-2 bg-slate-200 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-green-500 rounded-full"
                            style={{ width: `${student.submissionRate || 0}%` }}
                          />
                        </div>
                        <span className="text-sm text-slate-600">{student.submissionRate}%</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <button className="text-blue-600 hover:text-blue-800 text-sm">
                        查看详情
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'homework' && (
          <div className="bg-white rounded-xl shadow-sm p-6">
            <div className="flex justify-between items-center mb-6">
              <h3 className="font-semibold text-slate-800">作业列表</h3>
              <button
                onClick={() => router.push('/teacher/homework')}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
              >
                发布作业
              </button>
            </div>
            <p className="text-slate-500 text-center py-8">
              前往作业管理页面查看和管理作业
            </p>
          </div>
        )}

        {activeTab === 'grading_history' && (
          <div className="bg-white rounded-xl shadow-sm p-6">
            <div className="flex justify-between items-center mb-6">
              <h3 className="font-semibold text-slate-800">批改历史记录</h3>
            </div>
            <div className="space-y-4">
              <div className="text-center py-8 text-slate-400">
                暂无批改记录，使用一键批改功能开始批改。
              </div>
            </div>
          </div>
        )}

        {activeTab === 'stats' && (
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h3 className="font-semibold text-slate-800 mb-6">班级统计</h3>
            <div className="grid grid-cols-4 gap-4">
              <div className="bg-blue-50 rounded-lg p-4">
                <p className="text-sm text-blue-600">学生总数</p>
                <p className="text-2xl font-bold text-blue-700">{classDetail.student_count}</p>
              </div>
              <div className="bg-green-50 rounded-lg p-4">
                <p className="text-sm text-green-600">平均分</p>
                <p className="text-2xl font-bold text-green-700">82.5</p>
              </div>
              <div className="bg-purple-50 rounded-lg p-4">
                <p className="text-sm text-purple-600">及格率</p>
                <p className="text-2xl font-bold text-purple-700">87.5%</p>
              </div>
              <div className="bg-orange-50 rounded-lg p-4">
                <p className="text-sm text-orange-600">作业数</p>
                <p className="text-2xl font-bold text-orange-700">12</p>
              </div>
            </div>
            <div className="mt-6 text-center">
              <button
                onClick={() => router.push('/teacher/statistics')}
                className="text-blue-600 hover:text-blue-800"
              >
                查看详细统计 →
              </button>
            </div>
          </div>
        )}

        {/* Invite Modal */}
        {showInviteModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl p-6 w-full max-w-md">
              <h3 className="text-lg font-semibold text-slate-800 mb-4">邀请学生加入班级</h3>
              <div className="bg-slate-50 rounded-lg p-4 text-center mb-4">
                <p className="text-sm text-slate-500 mb-2">班级邀请码</p>
                <p className="text-3xl font-bold text-blue-600 tracking-wider">
                  {classDetail.invite_code}
                </p>
              </div>
              <p className="text-sm text-slate-500 mb-4">
                学生可以使用此邀请码加入班级，或者您可以分享以下链接：
              </p>
              <div className="bg-slate-100 rounded-lg p-3 text-sm text-slate-600 break-all mb-4">
                https://gradeos.app/join/{classDetail.invite_code}
              </div>
              <button
                onClick={() => setShowInviteModal(false)}
                className="w-full py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200"
              >
                关闭
              </button>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
