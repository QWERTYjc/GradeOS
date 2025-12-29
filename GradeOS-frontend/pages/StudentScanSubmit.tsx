import React, { useState, useEffect } from 'react';
import { Card, Button, Steps, Select, message, Modal, Spin, Result } from 'antd';
import { CameraOutlined, FileImageOutlined, SendOutlined, ArrowLeftOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { Scanner, ImageGallery, ScannedImage, mergeImagesToSubmission } from '../components/bookscan';
import { useStore } from '../store/useStore';
import { api } from '../services/api';
import { Homework } from '../types';

type ViewMode = 'scan' | 'gallery';

export const StudentScanSubmit: React.FC = () => {
  const { user } = useStore();
  const navigate = useNavigate();
  
  const [currentStep, setCurrentStep] = useState(0);
  const [viewMode, setViewMode] = useState<ViewMode>('scan');
  const [images, setImages] = useState<ScannedImage[]>([]);
  
  // 作业选择
  const [homeworks, setHomeworks] = useState<Homework[]>([]);
  const [selectedHomeworkId, setSelectedHomeworkId] = useState<string>('');
  const [loadingHw, setLoadingHw] = useState(false);
  
  // 提交状态
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<{ success: boolean; score?: number; feedback?: string } | null>(null);

  // 加载待提交作业
  useEffect(() => {
    const fetchHomeworks = async () => {
      if (!user) return;
      setLoadingHw(true);
      try {
        const res = await api.get('/homework', { params: { studentId: user.id } });
        // 只显示未提交的作业
        const pending = res.data.filter((h: any) => h.status === 'pending');
        setHomeworks(pending);
        if (pending.length > 0) {
          setSelectedHomeworkId(pending[0].id);
        }
      } catch (e) {
        message.error('加载作业列表失败');
      } finally {
        setLoadingHw(false);
      }
    };
    fetchHomeworks();
  }, [user]);

  // 添加扫描图片
  const handleCapture = (newImages: ScannedImage[]) => {
    setImages(prev => [...prev, ...newImages]);
    message.success(`已添加 ${newImages.length} 张`);
  };

  // 删除图片
  const handleDelete = (ids: string[]) => {
    setImages(prev => prev.filter(img => !ids.includes(img.id)));
  };

  // 重排图片
  const handleReorder = (fromIndex: number, toIndex: number) => {
    setImages(prev => {
      const newArr = [...prev];
      const [moved] = newArr.splice(fromIndex, 1);
      newArr.splice(toIndex, 0, moved);
      return newArr;
    });
  };

  // 提交作业
  const handleSubmit = async () => {
    if (!selectedHomeworkId) {
      message.warning('请选择要提交的作业');
      return;
    }
    if (images.length === 0) {
      message.warning('请先扫描或上传作业图片');
      return;
    }

    setSubmitting(true);
    try {
      // 压缩图片并转为提交格式
      const imageData = await mergeImagesToSubmission(images);
      
      // 调用提交 API
      const res = await api.post('/homework/submit', {
        homeworkId: selectedHomeworkId,
        studentId: user?.id,
        studentName: user?.name,
        content: `[扫描提交] ${images.length} 张图片`,
        images: imageData // 图片数据
      });

      setSubmitResult({
        success: true,
        score: res.data.score,
        feedback: res.data.aiFeedback
      });
      setCurrentStep(2);
    } catch (e: any) {
      message.error('提交失败: ' + (e.message || '未知错误'));
      setSubmitResult({ success: false });
    } finally {
      setSubmitting(false);
    }
  };

  // 确认提交
  const confirmSubmit = () => {
    Modal.confirm({
      title: '确认提交',
      content: (
        <div>
          <p>作业: {homeworks.find(h => h.id === selectedHomeworkId)?.title}</p>
          <p>图片数量: {images.length} 张</p>
          <p className="text-orange-500 mt-2">提交后将由 AI 自动批改，无法撤回</p>
        </div>
      ),
      okText: '确认提交',
      cancelText: '取消',
      onOk: handleSubmit
    });
  };

  const selectedHomework = homeworks.find(h => h.id === selectedHomeworkId);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 顶部导航 */}
      <div className="bg-white border-b px-4 py-3 flex items-center justify-between sticky top-0 z-20">
        <div className="flex items-center gap-3">
          <Button 
            icon={<ArrowLeftOutlined />} 
            onClick={() => navigate('/student/dashboard')}
          />
          <h1 className="text-lg font-bold">扫描提交作业</h1>
        </div>
        {images.length > 0 && currentStep < 2 && (
          <Button 
            type="primary" 
            icon={<SendOutlined />}
            onClick={() => setCurrentStep(1)}
            disabled={!selectedHomeworkId}
          >
            下一步 ({images.length})
          </Button>
        )}
      </div>

      {/* 步骤条 */}
      <div className="bg-white px-4 py-3 border-b">
        <Steps
          current={currentStep}
          size="small"
          items={[
            { title: '扫描作业' },
            { title: '确认提交' },
            { title: '批改结果' }
          ]}
        />
      </div>

      {/* 步骤 0: 扫描 */}
      {currentStep === 0 && (
        <div className="flex flex-col" style={{ height: 'calc(100vh - 140px)' }}>
          {/* 作业选择 */}
          <div className="bg-white p-4 border-b">
            <div className="flex items-center gap-3">
              <span className="text-gray-500">选择作业:</span>
              <Select
                value={selectedHomeworkId}
                onChange={setSelectedHomeworkId}
                loading={loadingHw}
                placeholder="请选择要提交的作业"
                className="flex-1"
                options={homeworks.map(h => ({
                  value: h.id,
                  label: `${h.title} (截止: ${h.deadline})`
                }))}
              />
            </div>
            {selectedHomework && (
              <p className="text-sm text-gray-400 mt-2 truncate">
                {selectedHomework.description}
              </p>
            )}
          </div>

          {/* 视图切换 */}
          <div className="bg-white px-4 py-2 border-b flex gap-2">
            <Button
              type={viewMode === 'scan' ? 'primary' : 'default'}
              icon={<CameraOutlined />}
              onClick={() => setViewMode('scan')}
            >
              扫描
            </Button>
            <Button
              type={viewMode === 'gallery' ? 'primary' : 'default'}
              icon={<FileImageOutlined />}
              onClick={() => setViewMode('gallery')}
            >
              已扫描 ({images.length})
            </Button>
          </div>

          {/* 内容区 */}
          <div className="flex-1 overflow-hidden">
            {viewMode === 'scan' ? (
              <Scanner onCapture={handleCapture} />
            ) : (
              <ImageGallery
                images={images}
                onDelete={handleDelete}
                onReorder={handleReorder}
              />
            )}
          </div>
        </div>
      )}

      {/* 步骤 1: 确认 */}
      {currentStep === 1 && (
        <div className="p-4 max-w-2xl mx-auto">
          <Card title="提交预览" className="mb-4">
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-500">作业名称</span>
                <span className="font-bold">{selectedHomework?.title}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">截止日期</span>
                <span>{selectedHomework?.deadline}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">图片数量</span>
                <span>{images.length} 张</span>
              </div>
            </div>
          </Card>

          {/* 图片预览 */}
          <Card title="图片预览" className="mb-4">
            <div className="grid grid-cols-4 gap-2">
              {images.map((img, i) => (
                <div key={img.id} className="aspect-[3/4] bg-gray-100 rounded overflow-hidden relative">
                  <img src={img.url} alt="" className="w-full h-full object-cover" />
                  <span className="absolute bottom-1 right-1 bg-black/50 text-white text-xs px-1 rounded">
                    {i + 1}
                  </span>
                </div>
              ))}
            </div>
          </Card>

          <div className="flex gap-3">
            <Button block onClick={() => setCurrentStep(0)}>
              返回修改
            </Button>
            <Button 
              type="primary" 
              block 
              loading={submitting}
              onClick={confirmSubmit}
            >
              确认提交
            </Button>
          </div>
        </div>
      )}

      {/* 步骤 2: 结果 */}
      {currentStep === 2 && submitResult && (
        <div className="p-4 max-w-2xl mx-auto">
          {submitResult.success ? (
            <Result
              status="success"
              icon={<CheckCircleOutlined className="text-green-500" />}
              title="提交成功！"
              subTitle="AI 已完成批改"
              extra={[
                <Card key="score" className="text-left mb-4">
                  <div className="text-center mb-4">
                    <div className="text-5xl font-bold text-blue-500">{submitResult.score}</div>
                    <div className="text-gray-400">分数</div>
                  </div>
                  <div>
                    <div className="text-gray-500 mb-1">AI 反馈:</div>
                    <div className="bg-gray-50 p-3 rounded">{submitResult.feedback}</div>
                  </div>
                </Card>,
                <Button key="back" type="primary" onClick={() => navigate('/student/dashboard')}>
                  返回首页
                </Button>
              ]}
            />
          ) : (
            <Result
              status="error"
              title="提交失败"
              subTitle="请稍后重试"
              extra={
                <Button type="primary" onClick={() => setCurrentStep(1)}>
                  重新提交
                </Button>
              }
            />
          )}
        </div>
      )}

      {/* 提交中遮罩 */}
      {submitting && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="text-center">
            <Spin size="large" />
            <p className="mt-4 text-gray-600">正在提交并等待 AI 批改...</p>
            <p className="text-sm text-gray-400">这可能需要几秒钟</p>
          </Card>
        </div>
      )}
    </div>
  );
};
