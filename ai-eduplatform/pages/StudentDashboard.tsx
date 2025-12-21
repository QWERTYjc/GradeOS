import React, { useState, useEffect } from 'react';
import { Card, Input, Button, message, Result, List, Tag, Empty, Typography, Modal, Alert, Divider } from 'antd';
import { TeamOutlined, FileTextOutlined, SendOutlined, CheckCircleOutlined, RobotOutlined, RocketOutlined, PlusOutlined } from '@ant-design/icons';
import { useStore } from '../store/useStore';
import { api, delay } from '../services/api';
import { Homework, ClassEntity } from '../types';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

export const StudentDashboard: React.FC = () => {
  const { user, updateUser } = useStore();
  const [inviteCode, setInviteCode] = useState('');
  const [joining, setJoining] = useState(false);
  const [joinModalOpen, setJoinModalOpen] = useState(false);
  
  const [homeworks, setHomeworks] = useState<any[]>([]); 
  const [myClasses, setMyClasses] = useState<ClassEntity[]>([]);
  const [loadingHw, setLoadingHw] = useState(false);

  // Submission State
  const [activeHw, setActiveHw] = useState<Homework | null>(null);
  const [submissionContent, setSubmissionContent] = useState('');
  const [isSubmitModalOpen, setIsSubmitModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Feedback View State
  const [feedbackModalOpen, setFeedbackModalOpen] = useState(false);
  const [currentFeedback, setCurrentFeedback] = useState<any>(null);

  const fetchData = async () => {
    if (!user?.id) return;
    setLoadingHw(true);
    try {
      // Fetch classes
      const classRes = await api.get('/student/classes', { params: { studentId: user.id } });
      setMyClasses(classRes.data);

      // Fetch aggregated homeworks (Mock backend handles aggregation based on studentId)
      const hwRes = await api.get('/homework', { params: { studentId: user.id } });
      setHomeworks(hwRes.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingHw(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [user]);

  const handleJoinClass = async () => {
    if (!inviteCode) return message.warning('Please enter a code');
    
    setJoining(true);
    try {
      const res = await api.post('/student/join', {
        code: inviteCode.trim().toUpperCase(),
        studentId: user?.id
      });
      
      message.success(`Successfully joined ${res.data.class.name}!`);
      
      // Update local store with new classId list if needed, or just refresh data
      const currentIds = user?.classIds || [];
      if (!currentIds.includes(res.data.class.id)) {
          updateUser({ classIds: [...currentIds, res.data.class.id] });
      }
      
      setJoinModalOpen(false);
      setInviteCode('');
      fetchData(); // Refresh list
    } catch (error: any) {
      message.error(error.response?.data?.message || 'Failed to join class');
    } finally {
      setJoining(false);
    }
  };

  const openSubmit = (hw: Homework) => {
    setActiveHw(hw);
    setSubmissionContent('');
    setIsSubmitModalOpen(true);
  };

  const handleSubmit = async () => {
    if (!submissionContent.trim()) return message.error('Content cannot be empty');
    
    setIsSubmitting(true);
    try {
      await api.post('/homework/submit', {
        homeworkId: activeHw?.id,
        studentId: user?.id,
        studentName: user?.name,
        content: submissionContent
      });

      await delay(1500); 

      message.success('Assignment submitted & Graded by AI!');
      setIsSubmitModalOpen(false);
      fetchData(); 
    } catch (e) {
      message.error('Submission failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const viewFeedback = (item: any) => {
    setCurrentFeedback(item);
    setFeedbackModalOpen(true);
  };

  // Full Screen Join View if no classes
  if (!user?.classIds || user.classIds.length === 0) {
    return (
      <div className="max-w-xl mx-auto mt-20">
        <Card className="text-center shadow-lg border-t-4 border-t-azure py-12 rounded-2xl bg-paper">
          <Result
            icon={<RocketOutlined className="text-azure" style={{ fontSize: '48px' }} />}
            title={<span className="text-ink font-bold">Initialize Learning Module</span>}
            subTitle={<span className="text-ink/60">Enter the 6-character access code provided by your instructor to join your first class.</span>}
            extra={
              <div className="max-w-xs mx-auto space-y-4 mt-8">
                <Input 
                  placeholder="CODE" 
                  size="large" 
                  style={{ textAlign: 'center', letterSpacing: '4px', textTransform: 'uppercase', fontSize: '24px', fontWeight: 'bold' }}
                  value={inviteCode}
                  onChange={e => setInviteCode(e.target.value)}
                  maxLength={6}
                  className="font-mono border-2 border-line focus:border-azure"
                />
                <Button 
                  type="primary" 
                  size="large" 
                  block 
                  onClick={handleJoinClass} 
                  loading={joining}
                  disabled={inviteCode.length < 6}
                  className="bg-azure h-12 text-lg shadow-glow"
                >
                  Connect to Class
                </Button>
              </div>
            }
          />
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
       <div className="mb-8 bg-paper p-6 rounded-2xl shadow-sm border border-line flex flex-col md:flex-row items-center justify-between gap-4">
         <div>
            <Title level={3} style={{ marginBottom: 0 }} className="text-ink">My Assignments</Title>
            <Text className="text-ink/50">Unified stream for all your courses.</Text>
         </div>
         <div className="flex flex-col items-end gap-2 w-full md:w-auto">
            <div className="flex flex-wrap gap-2 justify-end">
                {myClasses.map(cls => (
                    <Tag key={cls.id} className="mr-0 px-3 py-1 bg-azure/5 text-azure border-azure/20 font-bold rounded-full">
                        {cls.name}
                    </Tag>
                ))}
                <Button size="small" type="dashed" shape="circle" icon={<PlusOutlined />} onClick={() => setJoinModalOpen(true)} className="border-azure text-azure" />
            </div>
            <div className="text-xs uppercase font-bold text-ink/40 tracking-wider">Active Courses</div>
         </div>
       </div>

       <List
         grid={{ gutter: 16, column: 1 }}
         dataSource={homeworks}
         loading={loadingHw}
         locale={{ emptyText: <Empty description="No active assignments from any class" /> }}
         renderItem={(item) => (
           <List.Item>
             <Card 
                className="shadow-tech rounded-xl border border-line hover:border-azure transition-colors"
                title={
                    <div className="flex flex-col">
                        <span className="flex items-center gap-2 text-ink font-bold"><FileTextOutlined className="text-azure" /> {item.title}</span>
                        <span className="text-xs font-normal text-ink/40 mt-1">{item.className}</span>
                    </div>
                }
                extra={
                    item.status === 'submitted' 
                    ? <Tag color="success" icon={<CheckCircleOutlined />} className="px-3 py-1 rounded-full border-0 bg-green-50 text-green-600 font-bold">COMPLETE</Tag> 
                    : <Tag color="warning" className="px-3 py-1 rounded-full border-0 bg-orange-50 text-orange-600 font-bold">PENDING</Tag>
                }
                actions={[
                    item.status === 'submitted' ? (
                        <Button type="default" onClick={() => viewFeedback(item)} icon={<RobotOutlined />} className="border-azure text-azure hover:text-white hover:bg-azure">
                            AI Analysis Report
                        </Button>
                    ) : (
                        <Button type="primary" onClick={() => openSubmit(item)} icon={<SendOutlined />} className="bg-azure border-none shadow-glow">
                            Start Module
                        </Button>
                    )
                ]}
             >
               <Paragraph ellipsis={{ rows: 2 }} className="text-ink/70">{item.description}</Paragraph>
               <div className="flex justify-between items-center mt-4 pt-4 border-t border-mist">
                  <span className="text-xs text-ink/40 font-mono">DEADLINE</span>
                  <span className="text-sm font-bold text-ink">{item.deadline}</span>
               </div>
             </Card>
           </List.Item>
         )}
       />

       {/* Join Class Modal */}
       <Modal
         title="Join New Class"
         open={joinModalOpen}
         onCancel={() => setJoinModalOpen(false)}
         footer={null}
       >
         <div className="py-6 text-center">
            <Input 
                placeholder="6-DIGIT CODE" 
                size="large" 
                style={{ textAlign: 'center', letterSpacing: '4px', textTransform: 'uppercase', fontSize: '24px', fontWeight: 'bold' }}
                value={inviteCode}
                onChange={e => setInviteCode(e.target.value)}
                maxLength={6}
                className="font-mono border-2 border-line focus:border-azure mb-4"
            />
            <Button 
                type="primary" 
                size="large" 
                block 
                onClick={handleJoinClass} 
                loading={joining}
                disabled={inviteCode.length < 6}
                className="bg-azure shadow-glow"
            >
                Confirm Join
            </Button>
         </div>
       </Modal>

       {/* Submission Modal */}
       <Modal
         title={<span className="text-ink font-bold">Submit: {activeHw?.title}</span>}
         open={isSubmitModalOpen}
         onCancel={() => setIsSubmitModalOpen(false)}
         footer={null}
       >
         <Alert 
            message="AI Auto-Grading Active" 
            description="Your submission will be analyzed by our algorithms instantly."
            type="info" 
            showIcon 
            className="mb-4 border-azure/20 bg-azure/5 text-azure"
            icon={<RobotOutlined />}
         />
         <TextArea 
            rows={8} 
            value={submissionContent} 
            onChange={e => setSubmissionContent(e.target.value)}
            placeholder="Input your response here..."
            className="mb-4 font-mono text-sm bg-mist border-line focus:border-azure"
         />
         <Button type="primary" block size="large" onClick={handleSubmit} loading={isSubmitting} className="bg-azure shadow-glow h-12">
            Submit for Analysis
         </Button>
       </Modal>

       {/* Feedback Modal */}
       <Modal
         title={<div className="text-azure font-bold flex items-center gap-2"><RobotOutlined /> Analysis Result</div>}
         open={feedbackModalOpen}
         onCancel={() => setFeedbackModalOpen(false)}
         footer={[<Button key="close" onClick={() => setFeedbackModalOpen(false)}>Close Report</Button>]}
         width={600}
      >
          {currentFeedback && (
             <div className="text-center py-4">
                <div className="mb-6 relative inline-block">
                   <div className="text-sm uppercase tracking-widest text-ink/40 mb-2">Performance Score</div>
                   <div className="text-7xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-azure to-cyan">
                      {currentFeedback.score}
                   </div>
                   <div className="absolute -inset-4 bg-azure/5 blur-xl rounded-full -z-10"></div>
                </div>
                
                <div className="text-left bg-mist p-6 rounded-xl border border-line">
                   <Text strong className="block mb-3 text-ink uppercase text-xs tracking-wider">System Feedback</Text>
                   <Text className="text-ink/80 leading-relaxed">{currentFeedback.feedback}</Text>
                </div>
             </div>
          )}
       </Modal>
    </div>
  );
};