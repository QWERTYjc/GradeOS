'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useAuthStore } from '@/store/authStore';
import { ClassEntity } from '@/types';
import { classApi } from '@/services/api';

export default function TeacherDashboard() {
  const { user } = useAuthStore();
  const router = useRouter();
  const [classes, setClasses] = useState<ClassEntity[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newClassName, setNewClassName] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user?.id) {
      setClasses([]);
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    classApi.getTeacherClasses(user.id)
      .then((items) => {
        if (!active) return;
        const mapped = items.map((cls) => ({
          id: cls.class_id,
          name: cls.class_name,
          teacherId: cls.teacher_id,
          inviteCode: cls.invite_code,
          studentCount: cls.student_count,
        }));
        setClasses(mapped);
      })
      .catch((error) => {
        console.error('Failed to load classes', error);
        setClasses([]);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [user]);

  const handleCreateClass = async () => {
    if (!newClassName.trim()) return;
    if (!user?.id) return;
    try {
      const created = await classApi.createClass(newClassName, user.id);
      const newClass: ClassEntity = {
        id: created.class_id,
        name: created.class_name,
        teacherId: created.teacher_id,
        inviteCode: created.invite_code,
        studentCount: created.student_count,
      };
      setClasses((prev) => [...prev, newClass]);
      setNewClassName('');
      setIsModalOpen(false);
    } catch (error) {
      console.error('Failed to create class', error);
    }
  };

  const copyCode = (code: string) => {
    navigator.clipboard.writeText(code);
    alert('Code copied!');
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">My Classes</h1>
            <p className="text-slate-500">Manage your classrooms and students</p>
          </div>
          <button
            onClick={() => setIsModalOpen(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2"
          >
            <span>+</span> Create Class
          </button>
        </div>

        {loading ? (
          <div className="text-center py-20 text-slate-400">Loading...</div>
        ) : classes.length === 0 ? (
          <div className="text-center py-20 bg-white rounded-xl border border-slate-200">
            <p className="text-slate-500 mb-4">No classes yet</p>
            <button
              onClick={() => setIsModalOpen(true)}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg"
            >
              Create Your First Class
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {classes.map((cls) => (
              <div
                key={cls.id}
                className="bg-white rounded-xl border border-slate-200 p-6 hover:shadow-lg hover:border-blue-200 transition-all"
              >
                <div className="flex justify-between items-start mb-4">
                  <h3 className="text-lg font-bold text-slate-800">{cls.name}</h3>
                  <span className="text-xs bg-slate-100 px-2 py-1 rounded text-slate-500">
                    ID: {cls.id}
                  </span>
                </div>

                <div className="bg-slate-50 p-4 rounded-lg mb-4">
                  <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Invite Code</p>
                  <div className="flex justify-between items-center">
                    <span className="text-2xl font-mono font-bold text-slate-800 tracking-widest">
                      {cls.inviteCode}
                    </span>
                    <button
                      onClick={() => copyCode(cls.inviteCode)}
                      className="text-blue-600 hover:bg-blue-50 p-2 rounded-lg transition-colors"
                    >
                      📋
                    </button>
                  </div>
                </div>

                <div className="flex items-center gap-2 text-slate-600 text-sm mb-4">
                  <span>👥</span>
                  <span><strong>{cls.studentCount}</strong> Students</span>
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => router.push(`/teacher/class/${cls.id}`)}
                    className="flex-1 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                  >
                    Students
                  </button>
                  <button
                    onClick={() => router.push('/teacher/homework')}
                    className="flex-1 py-2 text-sm text-blue-600 hover:bg-blue-50 rounded-lg transition-colors font-medium"
                  >
                    Assignments →
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Create Class Modal */}
        {isModalOpen && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl p-6 w-full max-w-md mx-4">
              <h2 className="text-xl font-bold text-slate-800 mb-4">Create New Class</h2>
              <input
                type="text"
                value={newClassName}
                onChange={(e) => setNewClassName(e.target.value)}
                placeholder="Class Name (e.g. Advanced Physics 2024)"
                className="w-full px-4 py-3 border border-slate-200 rounded-lg mb-4 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <div className="flex gap-2">
                <button
                  onClick={() => setIsModalOpen(false)}
                  className="flex-1 py-2 text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreateClass}
                  className="flex-1 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Create
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
