
import React from 'react';
import { Link, useLocation } from 'react-router-dom';

const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();
  const isActive = (path: string) => location.pathname === path;

  const navItems = [
    { path: '/', label: '首页控制台', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
    { path: '/analysis', label: '智能诊断', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01' },
    { path: '/error-book', label: '个人错题本', icon: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253' },
  ];

  return (
    <div className="flex min-h-screen bg-white">
      {/* Sidebar */}
      <aside className="w-64 border-r border-slate-100 bg-mist flex-shrink-0">
        <div className="p-8">
          <div className="flex items-center gap-3 mb-12">
            <div className="w-10 h-10 bg-blue-600 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-100">
              <span className="text-white font-black text-xl">I</span>
            </div>
            <h1 className="text-xl font-black tracking-tighter text-slate-900">IntelliLearn</h1>
          </div>
          
          <nav className="space-y-2">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-5 py-4 rounded-2xl transition-all duration-300 ${
                  isActive(item.path)
                    ? 'bg-white shadow-xl shadow-slate-200/50 text-blue-600 border border-slate-100'
                    : 'text-slate-400 hover:bg-slate-100 hover:text-slate-900'
                }`}
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={isActive(item.path) ? 2.5 : 2} d={item.icon} />
                </svg>
                <span className="font-bold text-sm tracking-tight">{item.label}</span>
              </Link>
            ))}
          </nav>

          <div className="mt-20 p-6 bg-slate-900 rounded-[32px] text-white">
             <p className="text-[10px] font-black text-white/30 uppercase tracking-widest mb-4">当前班级</p>
             <h4 className="text-sm font-black mb-1">初三 (2) 班</h4>
             <p className="text-[10px] text-white/50 font-medium">班主任：刘老师</p>
             <div className="mt-6 flex justify-between items-end">
                <span className="text-xs font-black text-blue-400">排名 05</span>
                <span className="text-[10px] font-bold text-white/20">A+</span>
             </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 bg-white">
        <header className="h-20 border-b border-slate-50 flex items-center justify-between px-10 bg-white/80 backdrop-blur-md sticky top-0 z-50">
          <div className="flex items-center gap-6 text-xs text-slate-400 font-black tracking-widest uppercase">
            <span className="bg-slate-50 px-3 py-1 rounded-full border border-slate-100">Student ID: S20240101</span>
          </div>
          <div className="flex items-center gap-6">
            <button className="relative w-10 h-10 flex items-center justify-center bg-slate-50 rounded-full text-slate-400 hover:text-blue-600 transition-colors">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" /></svg>
              <span className="absolute top-2.5 right-2.5 w-2 h-2 bg-blue-600 rounded-full border-2 border-white"></span>
            </button>
            <div className="flex items-center gap-3 border-l border-slate-100 pl-6">
               <div className="text-right">
                  <p className="text-xs font-black text-slate-900">张同学</p>
               </div>
               <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center text-white font-black">张</div>
            </div>
          </div>
        </header>
        
        <div className="p-10 overflow-y-auto blueprint-grid flex-1">
          {children}
        </div>
      </main>
    </div>
  );
};

export default Layout;
