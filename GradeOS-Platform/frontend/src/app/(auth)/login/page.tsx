'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Fira_Code, Fira_Sans } from 'next/font/google';
import { Building2, GraduationCap, ShieldCheck, LockKeyhole, ArrowRight } from 'lucide-react';
import { useAuthStore } from '@/store/authStore';
import { Role, User } from '@/types';
import { authApi } from '@/services/api';

const firaSans = Fira_Sans({
  subsets: ['latin'],
  weight: ['300', '400', '500', '600', '700'],
});

const firaCode = Fira_Code({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
});

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { login } = useAuthStore();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await authApi.login({ username, password });
      const role = response.user_type as Role;
      const user: User = {
        id: response.user_id,
        name: response.name,
        username: response.username,
        role,
        classIds: response.class_ids || [],
      };
      login(user);
      if (role === Role.Teacher || role === Role.Admin) {
        router.push('/teacher/dashboard');
      } else {
        router.push('/student/dashboard');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`${firaSans.className} min-h-screen bg-slate-950 text-white relative overflow-hidden`}>
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.25),_transparent_55%)]" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_bottom,_rgba(15,118,110,0.25),_transparent_55%)]" />
      <div className="absolute inset-0 bg-[linear-gradient(120deg,_rgba(15,23,42,0.96),_rgba(15,23,42,0.72),_rgba(15,23,42,0.96))]" />

      <div className="relative z-10 min-h-screen flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-5xl grid lg:grid-cols-[1.1fr_0.9fr] gap-8">
          <div className="rounded-3xl border border-slate-800 bg-slate-900/70 backdrop-blur-xl p-10 shadow-2xl">
            <div className="flex items-center gap-3 mb-10">
              <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center">
                <span className="text-white font-bold text-xl">G</span>
              </div>
              <div>
                <div className="text-sm uppercase tracking-[0.3em] text-slate-400">GradeOS</div>
                <h1 className="text-3xl font-semibold tracking-tight">Intelligence Console</h1>
              </div>
            </div>

            <div className="space-y-6">
              <div className="grid gap-4 md:grid-cols-3">
                <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
                  <div className="flex items-center justify-between text-xs text-slate-400">
                    <span>Role</span>
                    <ShieldCheck className="h-4 w-4 text-emerald-400" />
                  </div>
                  <div className="mt-3 text-lg font-semibold">Account Segmentation</div>
                  <p className="mt-2 text-sm text-slate-400">Teacher / Student auto-detected</p>
                </div>
                <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
                  <div className="flex items-center justify-between text-xs text-slate-400">
                    <span>Security</span>
                    <LockKeyhole className="h-4 w-4 text-blue-400" />
                  </div>
                  <div className="mt-3 text-lg font-semibold">Credential Access</div>
                  <p className="mt-2 text-sm text-slate-400">Encrypted channel verification</p>
                </div>
                <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
                  <div className="flex items-center justify-between text-xs text-slate-400">
                    <span>Mode</span>
                    <Building2 className="h-4 w-4 text-orange-400" />
                  </div>
                  <div className="mt-3 text-lg font-semibold">Multi-session Ready</div>
                  <p className="mt-2 text-sm text-slate-400">Queue & parallel control</p>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
                <div className="text-xs uppercase tracking-[0.3em] text-slate-500">Demo Accounts</div>
                <div className="mt-4 grid gap-4 md:grid-cols-2 text-sm">
                  <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
                    <div className="flex items-center gap-2 text-blue-300 font-semibold">
                      <Building2 className="h-4 w-4" />
                      Teacher
                    </div>
                    <div className={`${firaCode.className} mt-2 text-slate-300`}>teacher / 123456</div>
                  </div>
                  <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
                    <div className="flex items-center gap-2 text-cyan-300 font-semibold">
                      <GraduationCap className="h-4 w-4" />
                      Student
                    </div>
                    <div className={`${firaCode.className} mt-2 text-slate-300`}>student / 123456</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-800 bg-white/95 text-slate-900 shadow-2xl p-10">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs uppercase tracking-[0.3em] text-slate-400">Sign In</div>
                <h2 className="mt-3 text-2xl font-semibold text-slate-900">Access workspace</h2>
                <p className="mt-2 text-sm text-slate-500">Use account credentials to enter your role.</p>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="mt-8 space-y-4">
              <div>
                <label className="text-xs font-semibold text-slate-500">Username</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter account"
                  className="mt-2 w-full px-4 py-3 rounded-xl border border-slate-200 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
                  required
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-500">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter password"
                  className="mt-2 w-full px-4 py-3 rounded-xl border border-slate-200 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
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
                {loading ? 'Signing in...' : 'Continue'}
                <ArrowRight className="h-4 w-4" />
              </button>
            </form>

            <div className="mt-6 flex items-center justify-between text-xs text-slate-400">
              <span>Need an account?</span>
              <Link
                href="/register"
                className="text-slate-900 font-semibold hover:text-blue-600 transition-colors"
              >
                Create account
              </Link>
            </div>

            <p className="mt-6 text-xs text-slate-400">
              By continuing, you agree to GradeOS operational policies and data handling rules.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
