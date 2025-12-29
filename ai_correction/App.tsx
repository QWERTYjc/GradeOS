import React, { useState, useEffect } from 'react';
import { HashRouter as Router, Routes, Route, Link, useLocation, Navigate } from 'react-router-dom';
import { Images, Wand2, Menu, X, ScanLine } from 'lucide-react';
import Scanner from './components/Scanner';
import Gallery from './components/Gallery';
import ImageGenerator from './components/ImageGenerator';
import { Session, ScannedImage } from './types';

export const AppContext = React.createContext<{
  sessions: Session[];
  currentSessionId: string | null;
  createNewSession: (name?: string) => void;
  addImageToSession: (img: ScannedImage) => void;
  addImagesToSession: (imgs: ScannedImage[]) => void;
  deleteSession: (id: string) => void;
  deleteImages: (sessionId: string, imageIds: string[]) => void;
  setCurrentSessionId: (id: string) => void;
  updateImage: (sessionId: string, imageId: string, newUrl: string, isOptimizing?: boolean) => void;
  reorderImages: (sessionId: string, fromIndex: number, toIndex: number) => void;
} | null>(null);

const Layout = ({ children }: React.PropsWithChildren<{}>) => {
  const location = useLocation();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const navItems = [
    { path: '/', label: '扫描引擎', icon: <ScanLine size={18} /> },
    { path: '/gallery', label: '图库', icon: <Images size={18} /> },
    { path: '/generate', label: 'AI 工作室', icon: <Wand2 size={18} /> },
  ];

  return (
    <div className="flex h-screen bg-[#F5F7FB] overflow-hidden text-[#0B0F17]">
      <aside className="hidden md:flex flex-col w-64 bg-white border-r border-slate-100 shadow-sm">
        <div className="p-8 pb-10">
          <div className="flex items-center gap-3 text-[#2563EB]">
            <ScanLine className="stroke-[3px]" size={28} />
            <h1 className="text-xl font-black tracking-tighter">BOOKSCAN</h1>
          </div>
        </div>
        <nav className="flex-1 px-4 space-y-1">
          {navItems.map((item) => (
            <Link key={item.path} to={item.path} className={`flex items-center gap-4 px-6 py-4 rounded-2xl transition-all duration-300 font-bold text-xs tracking-wider uppercase ${location.pathname === item.path ? 'bg-[#2563EB] text-white shadow-xl shadow-blue-100' : 'text-slate-400 hover:bg-slate-50 hover:text-slate-600'}`}>
              {item.icon} {item.label}
            </Link>
          ))}
        </nav>
        <div className="p-8 border-t border-slate-50 text-[10px] font-black text-slate-200 uppercase tracking-widest">
          Azure Edition v1.2
        </div>
      </aside>

      <div className="md:hidden fixed top-0 left-0 right-0 h-16 bg-white/80 backdrop-blur-md border-b border-slate-100 z-50 flex items-center justify-between px-6">
        <div className="font-black text-[#2563EB] flex items-center gap-2 text-sm"><ScanLine size={16}/> BOOKSCAN</div>
        <button onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)} className="p-2 text-slate-400"><Menu size={20}/></button>
      </div>

      {isMobileMenuOpen && (
        <div className="md:hidden fixed inset-0 z-40 bg-white pt-20 animate-in fade-in slide-in-from-top-4">
          <nav className="p-8 space-y-4">
            {navItems.map((item) => (
              <Link key={item.path} to={item.path} onClick={() => setIsMobileMenuOpen(false)} className={`flex items-center gap-4 px-6 py-5 rounded-2xl text-lg font-black ${location.pathname === item.path ? 'bg-[#2563EB] text-white' : 'text-slate-600'}`}>
                {item.icon} {item.label}
              </Link>
            ))}
          </nav>
        </div>
      )}

      <main className="flex-1 flex flex-col overflow-hidden relative pt-16 md:pt-0">
        {children}
      </main>
    </div>
  );
};

export default function App() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem('bookscan_v1.2_azure');
    if (saved) {
      const parsed = JSON.parse(saved);
      setSessions(parsed);
      if (parsed.length > 0) setCurrentSessionId(parsed[0].id);
    } else createNewSession('默认扫描会话');
  }, []);

  useEffect(() => {
    if (sessions.length > 0) localStorage.setItem('bookscan_v1.2_azure', JSON.stringify(sessions));
  }, [sessions]);

  const createNewSession = (name?: string) => {
    const s = { id: crypto.randomUUID(), name: name || `扫描 ${new Date().toLocaleTimeString()}`, createdAt: Date.now(), images: [] };
    setSessions(prev => [s, ...prev]);
    setCurrentSessionId(s.id);
  };

  const addImageToSession = (img: ScannedImage) => {
    if (!currentSessionId) return;
    setSessions(prev => prev.map(s => s.id === currentSessionId ? { ...s, images: [...s.images, img] } : s));
  };

  const addImagesToSession = (imgs: ScannedImage[]) => {
    if (!currentSessionId) return;
    setSessions(prev => prev.map(s => s.id === currentSessionId ? { ...s, images: [...s.images, ...imgs] } : s));
  };

  const deleteSession = (id: string) => {
    setSessions(prev => {
      const filtered = prev.filter(s => s.id !== id);
      if (currentSessionId === id) setCurrentSessionId(filtered.length > 0 ? filtered[0].id : null);
      return filtered;
    });
  };

  const deleteImages = (sessionId: string, imageIds: string[]) => {
    setSessions(prev => prev.map(s => s.id === sessionId ? { ...s, images: s.images.filter(img => !imageIds.includes(img.id)) } : s));
  };

  const updateImage = (sessionId: string, imageId: string, newUrl: string, isOptimizing: boolean = false) => {
     setSessions(prev => prev.map(s => s.id === sessionId ? { ...s, images: s.images.map(img => img.id === imageId ? { ...img, url: newUrl, isOptimizing: isOptimizing } : img) } : s));
  }

  const reorderImages = (sessionId: string, fromIndex: number, toIndex: number) => {
    setSessions(prev => prev.map(s => {
      if (s.id === sessionId) {
        const imgs = [...s.images];
        const [moved] = imgs.splice(fromIndex, 1);
        imgs.splice(toIndex, 0, moved);
        return { ...s, images: imgs };
      }
      return s;
    }));
  };

  return (
    <AppContext.Provider value={{ sessions, currentSessionId, createNewSession, addImageToSession, addImagesToSession, deleteSession, deleteImages, setCurrentSessionId, updateImage, reorderImages }}>
      <Router>
        <Layout>
          <Routes>
            <Route path="/" element={<Scanner />} />
            <Route path="/gallery" element={<Gallery />} />
            <Route path="/generate" element={<ImageGenerator />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Layout>
      </Router>
    </AppContext.Provider>
  );
}