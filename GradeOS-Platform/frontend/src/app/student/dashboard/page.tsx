'use client';

import React, { useState, useEffect } from 'react';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useAuthStore } from '@/store/authStore';
import { Homework, ClassEntity } from '@/types';

export default function StudentDashboard() {
  const { user, updateUser } = useAuthStore();
  const [inviteCode, setInviteCode] = useState('');
  const [joining, setJoining] = useState(false);
  const [myClasses, setMyClasses] = useState<ClassEntity[]>([]);
  const [homeworks, setHomeworks] = useState<(Homework & { status: string; score?: number; feedback?: string })[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitModalOpen, setSubmitModalOpen] = useState(false);
  const [activeHw, setActiveHw] = useState<Homework | null>(null);
  const [submissionContent, setSubmissionContent] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedbackModal, setFeedbackModal] = useState<{ open: boolean; score?: number; feedback?: string }>({ open: false });

  useEffect(() => {
    setTimeout(() => {
      if (user?.classIds && user.classIds.length > 0) {
        setMyClasses([
          { id: '1', name: 'Advanced Physics 2024', teacherId: 't1', inviteCode: 'PHY24A', studentCount: 32 }
        ]);
        setHomeworks([
          { id: '1', classId: '1', className: 'Advanced Physics 2024', title: 'Newton\'s Laws Problem Set', description: 'Complete problems 1-10', deadline: '2024-12-30', createdAt: '', status: 'pending' },
          { id: '2', classId: '1', className: 'Advanced Physics 2024', title: 'Energy Quiz', description: 'Online quiz', deadline: '2024-12-28', createdAt: '', status: 'submitted', score: 88, feedback: 'Great work! Minor errors in Q3.' }
        ]);
      }
      setLoading(false);
    }, 500);
  }, [user]);

  const handleJoinClass = async () => {
    if (!inviteCode || inviteCode.length < 6) return;
    setJoining(true);
    await new Promise(r => setTimeout(r, 1000));
    
    const newClass: ClassEntity = {
      id: Date.now().toString(),
      name: 'New Class',
      teacherId: 't1',
      inviteCode: inviteCode.toUpperCase(),
      studentCount: 25
    };
    
    setMyClasses([...myClasses, newClass]);
    updateUser({ classIds: [...(user?.classIds || []), newClass.id] });
    setInviteCode('');
    setJoining(false);
  };

  const handleSubmit = async () => {
    if (!submissionContent.trim()) return;
    setIsSubmitting(true);
    await new Promise(r => setTimeout(r, 2000));
    
    setHomeworks(homeworks.map(hw => 
      hw.id === activeHw?.id 
        ? { ...hw, status: 'submitted', score: Math.floor(Math.random() * 20) + 80, feedback: 'AI Analysis: Good understanding of core concepts.' }
        : hw
    ));
    
    setIsSubmitting(false);
    setSubmitModalOpen(false);
    setSubmissionContent('');
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
                    <button
                      onClick={() => setFeedbackModal({ open: true, score: hw.score, feedback: hw.feedback })}
                      className="px-4 py-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors text-sm font-medium"
                    >
                      🤖 View AI Analysis
                    </button>
                  ) : (
                    <button
                      onClick={() => { setActiveHw(hw); setSubmitModalOpen(true); }}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
                    >
                      Start →
                    </button>
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

        {/* Feedback Modal */}
        {feedbackModal.open && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl p-6 w-full max-w-md mx-4 text-center">
              <div className="text-6xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-cyan-500 mb-4">
                {feedbackModal.score}
              </div>
              <div className="bg-slate-50 p-4 rounded-lg text-left mb-4">
                <p className="text-sm text-slate-600">{feedbackModal.feedback}</p>
              </div>
              <button
                onClick={() => setFeedbackModal({ open: false })}
                className="px-6 py-2 text-slate-600 hover:bg-slate-100 rounded-lg"
              >
                Close
              </button>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
