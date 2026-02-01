'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useAuthStore } from '@/store/authStore';
import { Homework, ClassEntity } from '@/types';
import { classApi, homeworkApi, gradingApi, GradingImportRecord, GradingImportItem } from '@/services/api';

type HomeworkWithGrading = Homework & { 
  status: string; 
  score?: number; 
  feedback?: string;
  gradingImportId?: string;  // 关联的批改记录 ID
  gradingResult?: GradingImportItem;  // 完整的批改结果
};

export default function StudentDashboard() {
  const { user, updateUser } = useAuthStore();
  const router = useRouter();
  const [inviteCode, setInviteCode] = useState('');
  const [joining, setJoining] = useState(false);
  const [myClasses, setMyClasses] = useState<ClassEntity[]>([]);
  const [homeworks, setHomeworks] = useState<HomeworkWithGrading[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitModalOpen, setSubmitModalOpen] = useState(false);
  const [activeHw, setActiveHw] = useState<Homework | null>(null);
  const [submissionContent, setSubmissionContent] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [gradingRecords, setGradingRecords] = useState<GradingImportRecord[]>([]);

  useEffect(() => {
    if (!user?.id) {
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    const load = async () => {
      try {
        const [classes, homeworkList] = await Promise.all([
          classApi.getMyClasses(user.id),
          homeworkApi.getList({ student_id: user.id }),
        ]);

        const mappedClasses = classes.map((cls) => ({
          id: cls.class_id,
          name: cls.class_name,
          teacherId: cls.teacher_id,
          inviteCode: cls.invite_code,
          studentCount: cls.student_count,
        }));

        // 获取作业提交状态
        const submissionsList = await Promise.all(
          homeworkList.map((hw) => homeworkApi.getSubmissions(hw.homework_id).catch(() => []))
        );

        // 获取批改历史记录（用于关联完整批改结果）
        let allGradingRecords: GradingImportRecord[] = [];
        const gradingItemsMap = new Map<string, { importId: string; item: GradingImportItem }>();
        
        try {
          const gradingHistory = await gradingApi.getGradingHistory();
          allGradingRecords = gradingHistory.records || [];
          setGradingRecords(allGradingRecords);
          
          // 获取每个批改记录的详情，找到当前学生的批改结果
          const userName = user.name || user.username || '';
          const normalizedUserName = userName.trim().toLowerCase();
          
          await Promise.all(
            allGradingRecords.map(async (record) => {
              try {
                const detail = await gradingApi.getGradingHistoryDetail(record.import_id);
                
                // 多种匹配方式查找当前学生的结果
                const studentItem = detail.items.find(item => {
                  // 1. 优先匹配 student_id
                  if (item.student_id && item.student_id === user.id) {
                    return true;
                  }
                  // 2. 匹配学生姓名
                  if (normalizedUserName && item.student_name) {
                    const normalizedItemName = item.student_name.trim().toLowerCase();
                    if (normalizedItemName === normalizedUserName) {
                      return true;
                    }
                  }
                  // 3. 匹配 result 中的 studentName
                  if (normalizedUserName && item.result) {
                    const resultStudentName = (item.result as Record<string, unknown>).studentName || 
                                              (item.result as Record<string, unknown>).student_name;
                    if (typeof resultStudentName === 'string') {
                      const normalizedResultName = resultStudentName.trim().toLowerCase();
                      if (normalizedResultName === normalizedUserName) {
                        return true;
                      }
                    }
                  }
                  return false;
                });
                
                // 如果没找到匹配的，且只有一个学生结果，直接使用（单人批改场景）
                const finalStudentItem = studentItem || (detail.items.length === 1 ? detail.items[0] : null);
                
                if (finalStudentItem) {
                  // 用 class_id + assignment_id 作为 key 来匹配作业
                  const key = `${record.class_id}_${record.assignment_id || ''}`;
                  gradingItemsMap.set(key, { importId: record.import_id, item: finalStudentItem });
                  // 也用 import_id 作为备用 key
                  gradingItemsMap.set(record.import_id, { importId: record.import_id, item: finalStudentItem });
                }
              } catch (err) {
                console.warn('Failed to load grading detail:', record.import_id, err);
              }
            })
          );
        } catch (err) {
          console.warn('Failed to load grading history:', err);
        }

        const mappedHomeworks: HomeworkWithGrading[] = homeworkList.map((hw, index) => {
          const submissions = submissionsList[index] || [];
          const submission = submissions.find((item) => item.student_id === user.id);
          
          // 尝试匹配批改结果
          const gradingKey = `${hw.class_id}_${hw.homework_id}`;
          const gradingData = gradingItemsMap.get(gradingKey);
          
          // 从批改结果中提取分数
          let gradingScore: number | undefined;
          let gradingFeedback: string | undefined;
          if (gradingData?.item?.result) {
            const result = gradingData.item.result as Record<string, unknown>;
            gradingScore = typeof result.totalScore === 'number' ? result.totalScore : 
                          typeof result.total_score === 'number' ? result.total_score :
                          typeof result.score === 'number' ? result.score : undefined;
            gradingFeedback = typeof result.feedback === 'string' ? result.feedback : undefined;
          }
          
          return {
            id: hw.homework_id,
            classId: hw.class_id,
            className: hw.class_name,
            title: hw.title,
            description: hw.description,
            deadline: hw.deadline,
            createdAt: hw.created_at,
            status: submission || gradingData ? 'submitted' : 'pending',
            score: gradingScore ?? submission?.score,
            feedback: gradingFeedback ?? submission?.feedback,
            gradingImportId: gradingData?.importId,
            gradingResult: gradingData?.item,
          };
        });

        if (!active) return;
        setMyClasses(mappedClasses);
        setHomeworks(mappedHomeworks);
      } catch (error) {
        console.error('Failed to load student dashboard data', error);
        if (active) {
          setMyClasses([]);
          setHomeworks([]);
        }
      } finally {
        if (active) setLoading(false);
      }
    };

    load();
    return () => {
      active = false;
    };
  }, [user]);

  const handleJoinClass = async () => {
    if (!inviteCode || inviteCode.length < 6) return;
    setJoining(true);
    if (!user?.id) {
      setJoining(false);
      return;
    }
    try {
      const result = await classApi.joinClass(inviteCode.toUpperCase(), user.id);
      const classInfo = result.class;
      const newClass: ClassEntity = {
        id: classInfo.id,
        name: classInfo.name,
        teacherId: '',
        inviteCode: inviteCode.toUpperCase(),
        studentCount: 0,
      };
      setMyClasses((prev) => [...prev, newClass]);
      updateUser({ classIds: [...(user?.classIds || []), newClass.id] });
      setInviteCode('');
    } catch (error) {
      console.error('Failed to join class', error);
    } finally {
      setJoining(false);
    }
  };

  const handleSubmit = async () => {
    if (!submissionContent.trim()) return;
    setIsSubmitting(true);
    if (!user?.id || !activeHw) {
      setIsSubmitting(false);
      return;
    }
    try {
      const response = await homeworkApi.submit({
        homework_id: activeHw.id,
        student_id: user.id,
        student_name: user.name || user.username || user.id,
        content: submissionContent,
      });
      setHomeworks(homeworks.map(hw =>
        hw.id === activeHw?.id
          ? { ...hw, status: 'submitted', score: response.score, feedback: response.feedback }
          : hw
      ));
      setSubmitModalOpen(false);
      setSubmissionContent('');
    } catch (error) {
      console.error('Failed to submit homework', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  // No classes view
  if (!user?.classIds || user.classIds.length === 0) {
    return (
      <DashboardLayout>
        <div className="max-w-xl mx-auto mt-20">
          <div className="bg-white rounded-2xl p-12 text-center border border-slate-200 shadow-lg">
            <div className="text-5xl mb-4">🚀</div>
            <h2 className="text-2xl font-bold text-slate-800 mb-2">Join Your First Class</h2>
            <p className="text-slate-500 mb-8">Enter the 6-character code from your teacher</p>
            <input
              type="text"
              value={inviteCode}
              onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
              placeholder="CODE"
              maxLength={6}
              className="w-full text-center text-3xl font-mono font-bold tracking-[0.5em] px-4 py-4 border-2 border-slate-200 rounded-xl mb-4 focus:outline-none focus:border-blue-500"
            />
            <button
              onClick={handleJoinClass}
              disabled={inviteCode.length < 6 || joining}
              className="w-full py-4 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {joining ? 'Joining...' : 'Connect to Class'}
            </button>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="bg-white p-6 rounded-xl border border-slate-200 flex justify-between items-center">
          <div>
            <h1 className="text-xl font-bold text-slate-800">My Assignments</h1>
            <p className="text-slate-500 text-sm">All courses unified</p>
          </div>
          <div className="flex gap-2">
            {myClasses.map(cls => (
              <span key={cls.id} className="px-3 py-1 bg-blue-50 text-blue-600 rounded-full text-sm font-medium">
                {cls.name}
              </span>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="text-center py-20 text-slate-400">Loading...</div>
        ) : (
          <div className="space-y-4">
            {homeworks.map(hw => (
              <div key={hw.id} className="bg-white rounded-xl border border-slate-200 p-6 hover:shadow-md transition-all">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="font-bold text-slate-800 flex items-center gap-2">
                      📄 {hw.title}
                    </h3>
                    <p className="text-xs text-slate-400 mt-1">{hw.className}</p>
                  </div>
                  {hw.status === 'submitted' ? (
                    <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm font-medium">
                      ✓ Complete
                    </span>
                  ) : (
                    <span className="px-3 py-1 bg-orange-100 text-orange-700 rounded-full text-sm font-medium">
                      Pending
                    </span>
                  )}
                </div>
                <p className="text-slate-600 text-sm mb-4">{hw.description}</p>
                <div className="flex justify-between items-center pt-4 border-t border-slate-100">
                  <span className="text-xs text-slate-400">Due: {hw.deadline}</span>
                  {hw.status === 'submitted' ? (
                    <div className="flex items-center gap-3">
                      {hw.score !== undefined && (
                        <span className="text-lg font-bold text-blue-600">
                          {hw.score}分
                        </span>
                      )}
                      {hw.gradingImportId ? (
                        <button
                          onClick={() => router.push(`/student/grading/${hw.gradingImportId}`)}
                          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
                        >
                          🤖 查看完整批改
                        </button>
                      ) : (
                        <span className="px-4 py-2 text-slate-400 text-sm">
                          等待批改中...
                        </span>
                      )}
                    </div>
                  ) : (
                    <div className="flex gap-2">
                      <button
                        onClick={() => router.push(`/student/scan?homeworkId=${hw.id}`)}
                        className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors text-sm font-medium"
                      >
                        📸 扫描提交
                      </button>
                      <button
                        onClick={() => { setActiveHw(hw); setSubmitModalOpen(true); }}
                        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
                      >
                        文字提交 →
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Submit Modal */}
        {submitModalOpen && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl p-6 w-full max-w-lg mx-4">
              <h2 className="font-bold text-slate-800 mb-4">Submit: {activeHw?.title}</h2>
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4 flex items-center gap-2">
                <span>🤖</span>
                <span className="text-sm text-blue-700">AI Auto-Grading Active</span>
              </div>
              <textarea
                value={submissionContent}
                onChange={(e) => setSubmissionContent(e.target.value)}
                placeholder="Enter your response..."
                rows={6}
                className="w-full px-4 py-3 border border-slate-200 rounded-lg mb-4 focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
              />
              <div className="flex gap-2">
                <button
                  onClick={() => setSubmitModalOpen(false)}
                  className="flex-1 py-3 text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={isSubmitting}
                  className="flex-1 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {isSubmitting ? 'Analyzing...' : 'Submit for Analysis'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 批改历史快捷入口 */}
        {gradingRecords.length > 0 && (
          <div className="bg-white p-6 rounded-xl border border-slate-200">
            <h2 className="text-lg font-bold text-slate-800 mb-4">📊 我的批改记录</h2>
            <div className="space-y-2">
              {gradingRecords.slice(0, 5).map((record) => (
                <button
                  key={record.import_id}
                  onClick={() => router.push(`/student/grading/${record.import_id}`)}
                  className="w-full flex items-center justify-between p-3 rounded-lg border border-slate-100 hover:border-blue-200 hover:bg-blue-50 transition-all text-left"
                >
                  <div>
                    <div className="font-medium text-slate-700">{record.class_name || '批改记录'}</div>
                    <div className="text-xs text-slate-400">{record.created_at}</div>
                  </div>
                  <span className="text-blue-600 text-sm">查看详情 →</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
