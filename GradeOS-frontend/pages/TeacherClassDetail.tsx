import React, { useEffect, useState } from 'react';
import { Table, Breadcrumb, Card, Avatar, Tag, Button } from 'antd';
import { UserOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { User, ClassEntity } from '../types';
import { useStore } from '../store/useStore';

export const TeacherClassDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [students, setStudents] = useState<User[]>([]);
  const [currentClass, setCurrentClass] = useState<ClassEntity | null>(null);
  const [loading, setLoading] = useState(true);
  const { user } = useStore();
  const navigate = useNavigate();

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const classRes = await api.get('/teacher/classes', { params: { teacherId: user?.id } });
        const foundClass = classRes.data.find((c: ClassEntity) => c.id === id);
        setCurrentClass(foundClass);

        const studentRes = await api.get('/class/students', { params: { classId: id } });
        setStudents(studentRes.data);
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    };
    if (id) fetchData();
  }, [id, user?.id]);

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => (
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-mist border border-line flex items-center justify-center text-azure">
             <UserOutlined />
          </div>
          <span className="font-bold text-ink">{text}</span>
        </div>
      ),
    },
    {
      title: 'Username',
      dataIndex: 'username',
      key: 'username',
      render: (t: string) => <span className="font-mono text-ink/70">{t}</span>
    },
    {
      title: 'Status',
      dataIndex: 'role',
      key: 'role',
      render: () => <Tag className="bg-cyan/10 text-cyan border-cyan/20 px-2 rounded-full uppercase text-xs font-bold">Active</Tag>,
    },
    {
      title: 'Joined',
      key: 'date',
      render: () => <span className="text-ink/40 text-xs">Recently</span>, 
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/teacher/dashboard')} className="border-none shadow-none bg-transparent hover:bg-mist" />
        <Breadcrumb 
          separator=">"
          items={[
            { title: 'Dashboard', onClick: () => navigate('/teacher/dashboard'), className: 'cursor-pointer hover:text-azure' },
            { title: currentClass?.name || 'Class Details' }
        ]} />
      </div>

      <Card 
        bordered={false}
        title={
          <div className="flex items-center gap-4 py-2">
            <span className="text-xl font-bold text-ink">Student Roster</span>
            <span className="bg-azure/10 text-azure px-3 py-1 rounded-full text-xs font-bold">{students.length} Enrolled</span>
          </div>
        }
        className="shadow-tech rounded-2xl"
      >
        <Table 
          dataSource={students} 
          columns={columns} 
          rowKey="id" 
          loading={loading}
          locale={{ emptyText: 'Awaiting students...' }}
          pagination={false}
        />
      </Card>
    </div>
  );
};