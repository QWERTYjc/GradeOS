'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useAuthStore } from '@/store/authStore';
import { Homework, Submission, ClassEntity } from '@/types';
import dayjs from 'dayjs';

export default function TeacherHomework() {
  const { user } = useAuthStore();
  const router = useRouter();
  const [classes, setClasses] = useState<ClassEntity[]>([]);
  const [homeworks, setHomeworks] = useState<Homework[]>([]);
  const [selectedClass, setSelectedClass] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [currentHw, setCurrentHw] = useState<Homework | null>(null);
  const [submissions, setSubmissions] = useState<Submission[]>([]);

  // Form state
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [deadline, setDeadline] = useState('');

  useEffect(() => {
    setTimeout(() => {
      const mockClasses: ClassEntity[] = [
        { id: '1', name: 'Advanced Physics 2024', teacherId: user?.id || '', inviteCode: 'PHY24A', studentCount: 32 },
        { id: '2', name: 'Mathematics Grade 11', teacherId: user?.id || '', inviteCode: 'MTH11B', studentCount: 28 },
      ];
      setClasses(mockClasses);
      if (mockClasses.length > 0) {
        setSelectedClass(mockClasses[0].id);
      }
      setLoading(false);
    }, 300);
  }, [user]);

  useEffect(() => {
    if (selectedClass) {
      // Mock homeworks
      setHomeworks([
        {
          id: '1',
          classId: selectedClass,
          className: classes.find(c => c.id === selectedClass)?.name,
          title: 'Newton\'s Laws Problem Set',
          description: 'Complete problems 1-10 from Chapter 5',
          deadline: '2024-12-30',
          createdAt: new Date().toISOString()
        },
        {
          id: '2',
          classId: selectedClass,
          className: classes.find(c => c.id === selectedClass)?.name,
          title: 'Energy Conservation Quiz',
          description: 'Online quiz covering kinetic and potential energy',
          deadline: '2024-12-28',
          createdAt: new Date().toISOString()
        }
      ]);
    }
  }, [selectedClass, classes]);

  const handleCreate = () => {
    if (!title || !description || !deadline) return;
    const newHw: Homework = {
      id: Date.now().toString(),
      classId: selectedClass,
      className: classes.find(c => c.id === selectedClass)?.name,
      title,
      description,
      deadline,
      createdAt: new Date().toISOString()
    };
    setHomeworks([newHw, ...homeworks]);
    setTitle('');
    setDescription('');
    setDeadline('');
    setIsCreateOpen(false);
  };

  const openSubmissions = (hw: Homework) => {
    setCurrentHw(hw);
    setIsDrawerOpen(true);
    // Mock submissions
    setSubmissions([
      { id: '1', homeworkId: hw.id, studentId: 's1', studentName: 'Alice Chen', content: 'My answer...', submittedAt: new Date().toISOString(), status: 'graded', score: 92, aiFeedback: 'Excellent work! Clear understanding of concepts.' },
      { id: '2', homeworkId: hw.id, studentId: 's2', studentName: 'Bob Wang', content: 'Solution...', submittedAt: new Date().toISOString(), status: 'graded', score: 78, aiFeedback: 'Good effort. Review section 5.3 for improvement.' },
      { id: '3', homeworkId: hw.id, studentId: 's3', studentName: 'Carol Liu', content: 'Answer...', submittedAt: new Date().toISOString(), status: 'graded', score: 85, aiFeedback: 'Well done! Minor calculation errors in Q3.' },
    ]);
  };

  const getScoreColor = (score: number) => {
    if (score >= 90) return 'bg-green-100 text-green-700';
    if (score >= 80) return 'bg-blue-100 text-blue-700';
    if (score >= 60) return 'bg-yellow-100 text-yellow-700';
    return 'bg-red-100 text-red-700';
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex justify-between items-start bg-white p-6 rounded-xl border border-slate-200">
          <div className="flex gap-4 items-start">
            <button
              onClick={() => router.push('/teacher/dashboard')}
              className="mt-1 p-2 hover:bg-slate-100 rounded-lg transition-colors"
            >
              ←
            </button>
            <div>
              <h1 className="text-xl font-bold text-slate-800">Assignment Manager</h1>
              {classes.length > 0 && (
                <div className="flex gap-2 mt-3 flex-wrap">
                  {classes.map(cls => (
                    <button
                      key={cls.id}
                      onClick={() => setSelectedClass(cls.id)}
                      className={`px-3 py-1 rounded-full text-sm transition-all ${
                        selectedClass === cls.id
                          ? 'bg-blue-600 text-white'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      }`}
                    >
                      {cls.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
          <button
            onClick={() => setIsCreateOpen(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            + New Assignment
          </button>
        </div>

        {/* Homework List */}
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-6 py-3 text-sm font-medium text-slate-600">Title</th>
                <th className="text-left px-6 py-3 text-sm font-medium text-slate-600">Deadline</th>
                <th className="text-left px-6 py-3 text-sm font-medium text-slate-600">Created</th>
                <th className="text-right px-6 py-3 text-sm font-medium text-slate-600">Action</th>
              </tr>
            </thead>
            <tbody>
              {homeworks.map(hw => (
                <tr key={hw.id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-6 py-4 font-medium text-slate-800">{hw.title}</td>
                  <td className="px-6 py-4 text-slate-600 font-mono text-sm">{hw.deadline}</td>
                  <td className="px-6 py-4 text-slate-400 text-sm">{dayjs(hw.createdAt).format('MM-DD HH:mm')}</td>
                  <td className="px-6 py-4 text-right">
                    <button
                      onClick={() => openSubmissions(hw)}
                      className="px-3 py-1 text-sm text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                    >
                      View Grades
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {homeworks.length === 0 && (
            <div className="text-center py-12 text-slate-400">No assignments yet</div>
          )}
        </div>

        {/* Create Modal */}
        {isCreateOpen && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl p-6 w-full max-w-md mx-4">
              <h2 className="text-xl font-bold text-slate-800 mb-4">Create Assignment</h2>
              <div className="space-y-4">
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Title"
                  className="w-full px-4 py-3 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Instructions"
                  rows={3}
                  className="w-full px-4 py-3 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <input
                  type="date"
                  value={deadline}
                  onChange={(e) => setDeadline(e.target.value)}
                  className="w-full px-4 py-3 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div className="flex gap-2 mt-6">
                <button
                  onClick={() => setIsCreateOpen(false)}
                  className="flex-1 py-2 text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreate}
                  className="flex-1 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Create
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Submissions Drawer */}
        {isDrawerOpen && (
          <div className="fixed inset-0 bg-black/50 flex justify-end z-50">
            <div className="bg-white w-full max-w-2xl h-full overflow-y-auto">
              <div className="sticky top-0 bg-white border-b border-slate-200 p-4 flex justify-between items-center">
                <div>
                  <h2 className="font-bold text-slate-800">🤖 AI Gradebook: {currentHw?.title}</h2>
                </div>
                <button
                  onClick={() => setIsDrawerOpen(false)}
                  className="p-2 hover:bg-slate-100 rounded-lg"
                >
                  ✕
                </button>
              </div>
              <div className="p-6 space-y-4">
                {submissions.map(sub => (
                  <div key={sub.id} className="bg-slate-50 rounded-xl p-4 border border-slate-200">
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <span className="font-bold text-slate-800">{sub.studentName}</span>
                        <span className="text-xs text-slate-400 ml-2">
                          {dayjs(sub.submittedAt).format('MM-DD HH:mm')}
                        </span>
                      </div>
                      <span className={`px-3 py-1 rounded-full text-sm font-bold ${getScoreColor(sub.score || 0)}`}>
                        {sub.score}
                      </span>
                    </div>
                    <p className="text-sm text-slate-600">{sub.aiFeedback}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
