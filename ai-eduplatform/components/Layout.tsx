import React from 'react';
import { Layout, Button, theme } from 'antd';
import { useStore } from '../store/useStore';
import { useNavigate } from 'react-router-dom';
import { LogoutOutlined, UserOutlined } from '@ant-design/icons';

const { Header, Content } = Layout;

export const MainLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, logout } = useStore();
  const navigate = useNavigate();
  const {
    token: { borderRadiusLG },
  } = theme.useToken();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <Layout className="h-screen w-full bg-mist">
      <Header className="flex items-center justify-between px-6 bg-paper border-b border-line shadow-sm z-10 h-16">
        <div className="flex items-center gap-3">
           <div className="w-9 h-9 bg-gradient-to-br from-azure to-cyan rounded-lg flex items-center justify-center shadow-glow">
             <span className="text-white font-bold text-lg tracking-tighter">AI</span>
           </div>
           <h1 className="text-xl font-bold text-ink tracking-tight m-0">EduPlatform</h1>
        </div>
        
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2 text-ink/70 bg-mist px-3 py-1.5 rounded-full border border-line">
            <UserOutlined className="text-azure" />
            <span className="font-medium text-sm">{user?.name} <span className="text-xs text-gray-400">|</span> <span className="uppercase text-xs font-bold tracking-wide text-azure">{user?.role}</span></span>
          </div>
          <Button 
            type="text" 
            danger 
            icon={<LogoutOutlined />} 
            onClick={handleLogout}
            className="hover:bg-red-50"
          >
            Logout
          </Button>
        </div>
      </Header>
      <Content className="p-6 bg-mist overflow-y-auto tech-grid">
        <div 
          className="max-w-6xl mx-auto min-h-full"
          style={{ 
            borderRadius: borderRadiusLG,
          }}
        >
          {children}
        </div>
      </Content>
    </Layout>
  );
};