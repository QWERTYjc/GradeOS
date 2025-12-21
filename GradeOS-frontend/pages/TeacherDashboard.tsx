import React, { useEffect, useState } from 'react';
import { Card, Button, Modal, Form, Input, Empty, message, Typography } from 'antd';
import { PlusOutlined, TeamOutlined, CopyOutlined, RightOutlined } from '@ant-design/icons';
import { api } from '../services/api';
import { useStore } from '../store/useStore';
import { ClassEntity } from '../types';
import { useNavigate } from 'react-router-dom';

const { Title, Text } = Typography;

export const TeacherDashboard: React.FC = () => {
  const { user } = useStore();
  const [classes, setClasses] = useState<ClassEntity[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [form] = Form.useForm();
  const navigate = useNavigate();

  const fetchClasses = async () => {
    try {
      setLoading(true);
      const res = await api.get('/teacher/classes', { params: { teacherId: user?.id } });
      setClasses(res.data);
    } catch (e) {
      message.error('Failed to load classes');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClasses();
  }, []);

  const handleCreateClass = async (values: any) => {
    try {
      await api.post('/teacher/classes', {
        name: values.name,
        teacherId: user?.id
      });
      message.success('Class created successfully!');
      setIsModalOpen(false);
      form.resetFields();
      fetchClasses(); 
    } catch (e) {
      message.error('Failed to create class');
    }
  };

  const copyCode = (code: string) => {
    navigator.clipboard.writeText(code);
    message.success('Code copied!');
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <div>
           <Title level={2} className="text-ink mb-1 !font-bold">My Classes</Title>
           <Text className="text-ink/50">Manage your classrooms and students</Text>
        </div>
        <Button 
          type="primary" 
          icon={<PlusOutlined />} 
          size="large"
          onClick={() => setIsModalOpen(true)}
          className="bg-azure hover:bg-neon shadow-glow border-none"
        >
          Create Class
        </Button>
      </div>

      {loading ? (
        <div className="text-center py-20 text-azure/50">Loading interface...</div>
      ) : classes.length === 0 ? (
        <Empty 
          description={<span className="text-ink/50">No classes active.</span>} 
          className="mt-10 bg-paper p-10 rounded-2xl shadow-sm border border-line"
        >
          <Button type="primary" onClick={() => setIsModalOpen(true)}>Initialize Class</Button>
        </Empty>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {classes.map(cls => (
            <Card 
              key={cls.id}
              hoverable
              className="group border border-line shadow-tech hover:shadow-glow hover:border-neon transition-all duration-300"
              style={{ borderRadius: '12px' }}
              actions={[
                <Button type="text" className="text-ink/60 hover:text-azure" onClick={() => navigate(`/teacher/class/${cls.id}`)}>Students</Button>,
                <Button type="link" className="text-azure font-medium" onClick={() => navigate(`/teacher/homework`)}>Assignments <RightOutlined /></Button>
              ]}
            >
              <div className="flex justify-between items-start mb-4">
                 <h3 className="text-lg font-bold text-ink group-hover:text-azure transition-colors">{cls.name}</h3>
                 <div className="bg-mist px-2 py-1 rounded text-xs font-mono text-ink/50 border border-line">ID: {cls.id}</div>
              </div>
              
              <div className="mt-4 space-y-4">
                 <div className="bg-mist p-4 rounded-lg flex justify-between items-center border border-line group-hover:bg-white group-hover:border-azure/20 transition-all">
                    <div>
                      <Text type="secondary" className="text-[10px] uppercase font-bold tracking-widest text-ink/40">Invite Code</Text>
                      <div className="text-2xl font-mono font-bold text-ink tracking-widest mt-1">{cls.inviteCode}</div>
                    </div>
                    <Button 
                      type="text"
                      icon={<CopyOutlined />} 
                      onClick={() => copyCode(cls.inviteCode)}
                      className="text-azure hover:bg-blue-50"
                    />
                 </div>
                 <div className="flex items-center gap-2 text-ink/60 text-sm">
                    <TeamOutlined className="text-azure" />
                    <span><span className="font-bold text-ink">{cls.studentCount}</span> Active Students</span>
                 </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal
        title="Initialize New Class"
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        footer={null}
        className="rounded-xl overflow-hidden"
      >
        <Form form={form} onFinish={handleCreateClass} layout="vertical" className="pt-4">
          <Form.Item 
            name="name" 
            label="Class Name" 
            rules={[{ required: true, message: 'Required' }]}
          >
            <Input placeholder="e.g. Advanced Physics 2024" size="large" />
          </Form.Item>
          <Form.Item className="mb-0 text-right">
             <Button onClick={() => setIsModalOpen(false)} className="mr-2">Cancel</Button>
             <Button type="primary" htmlType="submit" size="large" className="bg-azure">Create System</Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};