'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { UserPlus, GraduationCap, Building2, ArrowRight } from 'lucide-react';
import { authApi } from '@/services/api';
import { useAuthStore } from '@/store/authStore';
import { Role, User } from '@/types';

export default function RegisterPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<Role>(Role.Teacher);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const router = useRouter();
  const { login } = useAuthStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const response = await authApi.register({
        username,
        password,
        role: role === Role.Student ? 'student' : 'teacher',
      });
      const user: User = {
        id: response.user_id,
        name: response.name,
        username: response.username,
        role: response.user_type as Role,
        classIds: response.class_ids || [],
      };
      login(user);
      if (user.role === Role.Teacher || user.role === Role.Admin) {
        router.push('/teacher/dashboard');
      } else {
        router.push('/student/dashboard');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Registration failed';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white relative overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(34,197,94,0.2),_transparent_55%)]" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_bottom,_rgba(14,165,233,0.25),_transparent_55%)]" />
      <div className="absolute inset-0 bg-[linear-gradient(130deg,_rgba(15,23,42,0.95),_rgba(15,23,42,0.72),_rgba(15,23,42,0.95))]" />

      <div className="relative z-10 min-h-screen flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-4xl grid lg:grid-cols-[1fr_0.9fr] gap-8">
          <div className="rounded-3xl border border-slate-800 bg-slate-900/70 backdrop-blur-xl p-10 shadow-2xl">
            <div className="flex items-center gap-3 mb-10">
              <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-emerald-400 to-cyan-400 flex items-center justify-center">
                <UserPlus className="h-6 w-6 text-white" />
              </div>
              <div>
                <div className="text-sm uppercase tracking-[0.3em] text-slate-400">GradeOS</div>
                <h1 className="text-3xl font-semibold tracking-tight">Create workspace</h1>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-6">
              <div className="text-xs uppercase tracking-[0.3em] text-slate-500">Roles</div>
              <div className="mt-4 grid gap-4">
                <button
                  type="button"
                  onClick={() => setRole(Role.Teacher)}
                  className={`flex items-center justify-between rounded-xl border px-4 py-4 text-left transition ${
                    role === Role.Teacher
                      ? 'border-emerald-400 bg-emerald-500/10 text-emerald-200'
                      : 'border-slate-800 text-slate-300 hover:border-slate-600'
                  }`}
                >
                  <div>
                    <div className="flex items-center gap-2 text-sm font-semibold">
                      <Building2 className="h-4 w-4" />
                      Teacher
                    </div>
                    <div className="mt-1 text-xs text-slate-400">Manage classes and grading pipelines</div>
                  </div>
                  <div className="font-mono text-xs">T</div>
                </button>
                <button
                  type="button"
                  onClick={() => setRole(Role.Student)}
                  className={`flex items-center justify-between rounded-xl border px-4 py-4 text-left transition ${
                    role === Role.Student
                      ? 'border-cyan-400 bg-cyan-500/10 text-cyan-200'
                      : 'border-slate-800 text-slate-300 hover:border-slate-600'
                  }`}
                >
                  <div>
                    <div className="flex items-center gap-2 text-sm font-semibold">
                      <GraduationCap className="h-4 w-4" />
                      Student
                    </div>
                    <div className="mt-1 text-xs text-slate-400">Track mistakes and request help</div>
                  </div>
                  <div className="font-mono text-xs">S</div>
                </button>
              </div>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-800 bg-white/95 text-slate-900 shadow-2xl p-10">
            <div>
              <div className="text-xs uppercase tracking-[0.3em] text-slate-400">Register</div>
              <h2 className="mt-3 text-2xl font-semibold text-slate-900">Create account</h2>
              <p className="mt-2 text-sm text-slate-500">Use a unique username to join GradeOS.</p>
            </div>

            <form onSubmit={handleSubmit} className="mt-8 space-y-4">
              <div>
                <label className="text-xs font-semibold text-slate-500">Username</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Choose username"
                  className="mt-2 w-full px-4 py-3 rounded-xl border border-slate-200 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
                  required
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-500">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Create password"
                  className="mt-2 w-full px-4 py-3 rounded-xl border border-slate-200 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
                  required
                />
              </div>

              {error && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-600">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 rounded-xl bg-slate-900 text-white font-semibold shadow-lg hover:shadow-xl transition disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {loading ? 'Creating...' : 'Create account'}
                <ArrowRight className="h-4 w-4" />
              </button>
            </form>

            <div className="mt-6 flex items-center justify-between text-xs text-slate-400">
              <span>Already have an account?</span>
              <Link
                href="/login"
                className="text-slate-900 font-semibold hover:text-blue-600 transition-colors"
              >
                Sign in
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
