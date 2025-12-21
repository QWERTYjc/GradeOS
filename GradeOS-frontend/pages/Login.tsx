import React, { useState } from 'react';
import { Card, Form, Input, Button, message, Alert } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { api } from '../services/api';
import { useStore } from '../store/useStore';
import { useNavigate } from 'react-router-dom';
import { Role } from '../types';

export const Login: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const { login } = useStore();
  const navigate = useNavigate();

  const onFinish = async (values: any) => {
    setLoading(true);
    try {
      const response = await api.post('/auth/login', values);
      const user = response.data;
      login(user);
      message.success(`Welcome back, ${user.name}!`);
      
      if (user.role === Role.Teacher) {
        navigate('/teacher/dashboard');
      } else {
        navigate('/student/dashboard');
      }
    } catch (error: any) {
      message.error(error.response?.data?.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-mist tech-grid p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
           <div className="inline-flex items-center justify-center w-12 h-12 bg-gradient-to-br from-azure to-cyan rounded-xl shadow-glow mb-4">
             <span className="text-white font-bold text-xl">AI</span>
           </div>
           <h2 className="text-3xl font-bold text-ink tracking-tight">EduPlatform</h2>
           <p className="text-ink/50 mt-2">Next Gen Learning Management</p>
        </div>

        <Card 
          className="shadow-xl border-t-4 border-t-azure" 
          bordered={false}
          style={{ borderRadius: '16px' }}
        >
          <Alert
            message="Demo Access"
            description={
              <div className="flex justify-between text-xs mt-1 gap-4">
                <div className="bg-mist p-2 rounded w-full border border-line">
                  <span className="font-bold text-azure block">Teacher</span>
                  <span className="font-mono text-ink">teacher / 123456</span>
                </div>
                <div className="bg-mist p-2 rounded w-full border border-line">
                  <span className="font-bold text-neon block">Student</span>
                  <span className="font-mono text-ink">student / 123456</span>
                </div>
              </div>
            }
            type="info"
            showIcon={false}
            className="mb-6 border-none bg-transparent p-0"
          />

          <Form
            name="login"
            initialValues={{ remember: true }}
            onFinish={onFinish}
            layout="vertical"
            size="large"
          >
            <Form.Item
              name="username"
              rules={[{ required: true, message: 'Required' }]}
            >
              <Input prefix={<UserOutlined className="text-azure" />} placeholder="Username" className="rounded-lg" />
            </Form.Item>
            <Form.Item
              name="password"
              rules={[{ required: true, message: 'Required' }]}
            >
              <Input.Password prefix={<LockOutlined className="text-azure" />} placeholder="Password" className="rounded-lg" />
            </Form.Item>

            <Form.Item className="mb-0">
              <Button type="primary" htmlType="submit" loading={loading} block className="h-12 rounded-lg font-semibold bg-azure hover:bg-neon border-none shadow-glow">
                Sign In
              </Button>
            </Form.Item>
          </Form>
        </Card>
        
        <div className="text-center mt-8 text-ink/30 text-sm">
           &copy; 2024 AI EduPlatform. Secure & Fast.
        </div>
      </div>
    </div>
  );
};