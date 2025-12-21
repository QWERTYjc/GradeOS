import React, { useState, useEffect, useMemo } from 'react';
import { Table, Button, Modal, Form, Input, DatePicker, message, Card, Tag, Drawer, Typography, Descriptions, Empty, Tooltip, InputNumber, Upload, Steps } from 'antd';
import { PlusOutlined, RobotOutlined, EyeOutlined, ArrowLeftOutlined, DownloadOutlined, BarChartOutlined, EditOutlined, UploadOutlined, FileExcelOutlined, CalculatorOutlined } from '@ant-design/icons';
import { useStore } from '../store/useStore';
import { api } from '../services/api';
import { ClassEntity, Homework, Submission } from '../types';
import dayjs from 'dayjs';
import { useNavigate } from 'react-router-dom';

const { Title, Text } = Typography;
const { TextArea } = Input;

// Helper for Quantile Calculation
const quantile = (arr: number[], q: number) => {
    const sorted = [...arr].sort((a, b) => a - b);
    const pos = (sorted.length - 1) * q;
    const base = Math.floor(pos);
    const rest = pos - base;
    if (sorted[base + 1] !== undefined) {
        return Math.round((sorted[base] + rest * (sorted[base + 1] - sorted[base])) * 10) / 10;
    } else {
        return sorted[base];
    }
};

export const TeacherHomework: React.FC = () => {
  const { user } = useStore();
  const [classes, setClasses] = useState<ClassEntity[]>([]);
  const [homeworks, setHomeworks] = useState<Homework[]>([]);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  
  const [loading, setLoading] = useState(false);
  const [selectedClass, setSelectedClass] = useState<string>('');
  
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [currentHw, setCurrentHw] = useState<Homework | null>(null);

  // Edit State
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editingSubmission, setEditingSubmission] = useState<Submission | null>(null);

  // Stats / Merge State
  const [isStatsOpen, setIsStatsOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [externalFileContent, setExternalFileContent] = useState<string>('');
  const [isMerging, setIsMerging] = useState(false);
  const [statsData, setStatsData] = useState<{ students: any[], columns: string[] } | null>(null);
  const [weights, setWeights] = useState<Record<string, number>>({});
  
  const [form] = Form.useForm();
  const [editForm] = Form.useForm();
  const navigate = useNavigate();

  useEffect(() => {
    const init = async () => {
      const res = await api.get('/teacher/classes', { params: { teacherId: user?.id } });
      setClasses(res.data);
      if (res.data.length > 0) {
        setSelectedClass(res.data[0].id);
      }
    };
    init();
  }, [user]);

  useEffect(() => {
    if (selectedClass) {
      fetchHomeworks();
    }
  }, [selectedClass]);

  const fetchHomeworks = async () => {
    setLoading(true);
    try {
      const res = await api.get('/homework', { params: { classId: selectedClass } });
      setHomeworks(res.data.reverse()); 
    } catch (e) {
      message.error('Failed to load homeworks');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (values: any) => {
    if (!selectedClass) {
        message.error('No class selected');
        return;
    }
    try {
      await api.post('/homework', {
        ...values,
        deadline: values.deadline.format('YYYY-MM-DD'),
        classId: selectedClass,
        className: classes.find(c => c.id === selectedClass)?.name
      });
      message.success('Assignment created!');
      setIsCreateOpen(false);
      form.resetFields();
      fetchHomeworks();
    } catch (e) {
      message.error('Creation failed');
    }
  };

  const openSubmissions = async (hw: Homework) => {
    setCurrentHw(hw);
    setIsDrawerOpen(true);
    setSubmissions([]); // Clear previous
    try {
      const res = await api.get('/homework/submissions', { params: { homeworkId: hw.id } });
      setSubmissions(res.data);
    } catch (e) {
      message.error('Could not load submissions');
    }
  };

  const openEdit = (sub: Submission) => {
      setEditingSubmission(sub);
      editForm.setFieldsValue({
          score: sub.score,
          feedback: sub.aiFeedback
      });
      setIsEditOpen(true);
  };

  const handleUpdateGrade = async (values: any) => {
      if (!editingSubmission) return;
      try {
          await api.patch('/submission/update', {
              id: editingSubmission.id,
              score: values.score,
              feedback: values.feedback
          });
          message.success('Grade updated');
          setIsEditOpen(false);
          // Refresh submissions
          if (currentHw) openSubmissions(currentHw);
      } catch (e) {
          message.error('Failed to update grade');
      }
  };

  // 1. Export CSV Feature
  const handleExportCSV = () => {
    if (submissions.length === 0) {
        message.warning('No data to export');
        return;
    }

    const headers = "Student ID,Student Name,Submitted At,Score,Feedback\n";
    const rows = submissions.map(sub => {
        const cleanFeedback = (sub.aiFeedback || '').replace(/"/g, '""');
        return [
            sub.studentId,
            `"${sub.studentName}"`,
            dayjs(sub.submittedAt).format('YYYY-MM-DD HH:mm'),
            sub.score || 0,
            `"${cleanFeedback}"`
        ].join(",");
    });

    const csvContent = "data:text/csv;charset=utf-8," + headers + rows.join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `${currentHw?.title.replace(/\s+/g, '_')}_grades.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // 2. Statistics Calculation for Box Plot
  const stats = useMemo(() => {
    const scores = submissions
        .map(s => s.score)
        .filter((s): s is number => s !== undefined && s !== null)
        .sort((a, b) => a - b);
    
    if (scores.length < 2) return null;

    return {
        min: scores[0],
        max: scores[scores.length - 1],
        q1: quantile(scores, 0.25),
        median: quantile(scores, 0.5),
        q3: quantile(scores, 0.75),
        average: Math.round(scores.reduce((a, b) => a + b, 0) / scores.length * 10) / 10
    };
  }, [submissions]);

  // 3. Stats Merge Handler
  const handleFileUpload = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
        const text = e.target?.result as string;
        setExternalFileContent(text);
        message.success(`Loaded: ${file.name}`);
    };
    reader.readAsText(file);
    return false; // Prevent upload
  };

  const handleProcessStats = async () => {
      setIsMerging(true);
      try {
          // Trigger Backend Merge (Mock uses Gemini to parse, but returns RAW data)
          const res = await api.post('/teacher/statistics/merge', {
              classId: selectedClass,
              externalData: externalFileContent
          });

          const { students, internalAssignments, externalAssignments } = res.data;
          const allCols = [...internalAssignments, ...externalAssignments];
          
          setStatsData({
              students,
              columns: allCols
          });
          
          // Initialize Weights equally
          const initialWeights: Record<string, number> = {};
          allCols.forEach((col: string) => {
             initialWeights[col] = Math.floor(100 / allCols.length);
          });
          setWeights(initialWeights);

          setCurrentStep(1); // Move to config step

      } catch (e) {
          message.error("Data processing failed.");
      } finally {
          setIsMerging(false);
      }
  };

  const calculateWeightedScore = (studentScores: Record<string, number>) => {
      let total = 0;
      let totalWeight = 0;
      
      Object.keys(weights).forEach(col => {
          const w = weights[col] || 0;
          const s = studentScores[col] || 0;
          total += s * (w / 100);
          totalWeight += w;
      });

      return Math.round(total * 100) / 100;
  };

  const handleExportFinalStats = () => {
    if (!statsData) return;
    
    // Header
    const colKeys = statsData.columns;
    let csv = "Student Name,Student ID," + colKeys.map(c => `"${c} (${weights[c]}%)"`).join(",") + ",Semester Total\n";
    
    // Rows
    csv += statsData.students.map(s => {
        const scores = colKeys.map(k => s.scores[k] || 0).join(",");
        const total = calculateWeightedScore(s.scores);
        return `"${s.name}",${s.id},${scores},${total}`;
    }).join("\n");

    const csvContent = "data:text/csv;charset=utf-8," + encodeURI(csv);
    const link = document.createElement("a");
    link.setAttribute("href", csvContent);
    link.setAttribute("download", `Semester_Report_${classes.find(c => c.id === selectedClass)?.name.replace(/\s/g, '_')}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    setIsStatsOpen(false);
    setCurrentStep(0);
  };

  const columns = [
    { title: 'Title', dataIndex: 'title', key: 'title', render: (t: string) => <span className="font-bold text-ink">{t}</span> },
    { title: 'Deadline', dataIndex: 'deadline', key: 'deadline', render: (t: string) => <span className="font-mono text-ink/70">{t}</span> },
    { title: 'Created', dataIndex: 'createdAt', key: 'createdAt', render: (d: string) => <span className="text-ink/50 text-xs">{dayjs(d).format('MM-DD HH:mm')}</span> },
    { 
      title: 'Action', 
      key: 'action', 
      render: (_: any, record: Homework) => (
        <Button size="small" icon={<EyeOutlined />} onClick={() => openSubmissions(record)} className="text-azure border-azure hover:bg-azure hover:text-white">View Grades</Button>
      ) 
    }
  ];

  const submissionColumns = [
    { title: 'Student', dataIndex: 'studentName', key: 'studentName', render: (t: string) => <span className="font-bold">{t}</span> },
    { title: 'Submitted', dataIndex: 'submittedAt', key: 'submitted', render: (d: string) => <span className="font-mono text-xs">{dayjs(d).format('MM-DD HH:mm')}</span> },
    { 
      title: 'Score', 
      dataIndex: 'score', 
      key: 'score',
      sorter: (a: Submission, b: Submission) => (a.score || 0) - (b.score || 0),
      render: (score: number) => {
        let color = score >= 90 ? 'green' : score >= 80 ? 'blue' : score >= 60 ? 'orange' : 'red';
        return <Tag color={color} className="font-bold min-w-[60px] text-center">{score}</Tag>;
      }
    },
    {
      title: 'Feedback',
      dataIndex: 'aiFeedback',
      key: 'feedback',
      width: '35%',
      render: (text: string) => <span className="text-ink/60 text-sm line-clamp-2" title={text}>{text}</span>
    },
    {
      title: '',
      key: 'actions',
      render: (_: any, record: Submission) => (
          <Button size="small" type="text" icon={<EditOutlined />} onClick={() => openEdit(record)} className="text-ink/40 hover:text-azure" />
      )
    }
  ];

  // Stats Table Columns Generator
  const statsTableColumns = useMemo(() => {
      if (!statsData) return [];
      
      const cols: any[] = [
          { title: 'Name', dataIndex: 'name', key: 'name', fixed: 'left', width: 120 },
      ];

      statsData.columns.forEach(col => {
          cols.push({
              title: (
                  <div className="flex flex-col items-center">
                      <span className="text-xs mb-1 text-ink/70 truncate w-24 text-center" title={col}>{col}</span>
                      <InputNumber 
                        size="small" 
                        min={0} max={100}
                        value={weights[col]}
                        onChange={(val) => setWeights(prev => ({ ...prev, [col]: val || 0 }))}
                        formatter={value => `${value}%`}
                        parser={value => value!.replace('%', '') as unknown as number}
                        className="w-16 text-xs"
                      />
                  </div>
              ),
              dataIndex: ['scores', col],
              key: col,
              align: 'center',
              width: 130,
              render: (score: number) => <span className="text-ink/60">{score || 0}</span>
          });
      });

      cols.push({
          title: <span className="text-azure font-bold">Semester Total</span>,
          key: 'total',
          fixed: 'right',
          width: 100,
          align: 'center',
          render: (_: any, record: any) => {
              const total = calculateWeightedScore(record.scores);
              const color = total >= 90 ? 'green' : total >= 60 ? 'blue' : 'red';
              return <Tag color={color} className="font-bold">{total}</Tag>;
          }
      });

      return cols;
  }, [statsData, weights]);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-start bg-paper p-5 rounded-2xl shadow-sm border border-line">
        <div className="flex gap-4 items-start">
           <Button 
             icon={<ArrowLeftOutlined />} 
             onClick={() => navigate('/teacher/dashboard')} 
             className="mt-1 border-line shadow-sm text-ink/70 hover:text-azure hover:border-azure"
             shape="circle"
           />
           <div>
             <Title level={4} style={{ margin: 0 }} className="text-ink">Assignment Manager</Title>
             
             {classes.length > 0 ? (
                <div className="flex gap-2 mt-3 overflow-x-auto pb-1 max-w-2xl">
                    {classes.map(cls => (
                        <Tag.CheckableTag 
                        key={cls.id} 
                        checked={selectedClass === cls.id} 
                        onChange={() => setSelectedClass(cls.id)}
                        className={`border px-3 py-1 rounded-full transition-all cursor-pointer ${selectedClass === cls.id ? 'bg-azure text-white border-azure shadow-glow' : 'bg-mist text-ink/60 border-line hover:border-azure'}`}
                        >
                        {cls.name}
                        </Tag.CheckableTag>
                    ))}
                </div>
             ) : (
                 <div className="mt-2 text-ink/40 text-sm">No active classes found.</div>
             )}
           </div>
        </div>
        
        <div className="flex gap-2">
            <Button 
                icon={<BarChartOutlined />} 
                onClick={() => { setIsStatsOpen(true); setCurrentStep(0); }}
                disabled={classes.length === 0}
                className="text-azure border-azure/20 hover:border-azure hover:text-azure"
            >
                Semester Stats
            </Button>
            <Button 
                type="primary" 
                icon={<PlusOutlined />} 
                onClick={() => setIsCreateOpen(true)} 
                disabled={classes.length === 0}
                className="bg-azure shadow-glow border-none"
            >
                New Assignment
            </Button>
        </div>
      </div>

      <Card className="shadow-tech border border-line rounded-xl" bordered={false}>
        {classes.length === 0 ? (
            <Empty 
                image={Empty.PRESENTED_IMAGE_SIMPLE} 
                description={
                    <div className="text-center">
                        <Text className="text-ink/50 block mb-2">You need to create a class before assigning homework.</Text>
                        <Button type="link" onClick={() => navigate('/teacher/dashboard')}>Go to Dashboard</Button>
                    </div>
                } 
            />
        ) : (
            <Table 
            dataSource={homeworks} 
            columns={columns} 
            rowKey="id" 
            loading={loading}
            locale={{ emptyText: <div className="text-ink/40 py-10">No assignments found for this class</div> }}
            />
        )}
      </Card>

      {/* Create Modal */}
      <Modal 
        title="Create New Assignment" 
        open={isCreateOpen} 
        onCancel={() => setIsCreateOpen(false)}
        footer={null}
      >
        <Form form={form} onFinish={handleCreate} layout="vertical" className="pt-4">
          <Form.Item label="Target Class">
             <Input value={classes.find(c => c.id === selectedClass)?.name} disabled className="bg-mist text-ink" />
          </Form.Item>
          <Form.Item name="title" label="Title" rules={[{ required: true }]}>
            <Input placeholder="Assignment Title" />
          </Form.Item>
          <Form.Item name="description" label="Instructions" rules={[{ required: true }]}>
            <TextArea rows={4} placeholder="Detailed instructions..." />
          </Form.Item>
          <Form.Item name="deadline" label="Due Date" rules={[{ required: true }]}>
            <DatePicker className="w-full" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block className="bg-azure h-10 shadow-glow border-none">Publish Assignment</Button>
        </Form>
      </Modal>

      {/* Submissions Drawer */}
      <Drawer
        title={
          <div className="flex items-center justify-between w-full pr-4">
              <div className="flex items-center gap-2 text-azure">
                <RobotOutlined />
                <span className="font-bold">AI Gradebook: {currentHw?.title}</span>
              </div>
              <Button 
                icon={<DownloadOutlined />} 
                onClick={handleExportCSV} 
                disabled={submissions.length === 0} 
                size="small"
                className="text-azure border-azure hover:bg-azure hover:text-white"
              >
                Export CSV
              </Button>
          </div>
        }
        placement="right"
        width={800}
        onClose={() => setIsDrawerOpen(false)}
        open={isDrawerOpen}
        headerStyle={{ borderBottom: '1px solid #E5E7EB' }}
      >
        {currentHw && (
          <>
            <div className="mb-6 bg-mist p-5 rounded-xl border border-line">
                <Descriptions size="small" column={1}>
                    <Descriptions.Item label={<span className="text-ink/50 uppercase text-xs font-bold">Instructions</span>}>
                        <span className="text-ink">{currentHw.description}</span>
                    </Descriptions.Item>
                    <Descriptions.Item label={<span className="text-ink/50 uppercase text-xs font-bold">Due</span>}>
                        <span className="font-mono text-azure">{currentHw.deadline}</span>
                    </Descriptions.Item>
                </Descriptions>
            </div>

            {/* Statistics Visualization (Box Plot) */}
            {stats && (
                <div className="mb-8 p-6 border border-line rounded-xl bg-white shadow-sm">
                    <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2 text-ink">
                            <BarChartOutlined className="text-azure" />
                            <span className="font-bold">Score Distribution (Interquartile)</span>
                        </div>
                        <span className="text-xs text-ink/40 bg-mist px-2 py-1 rounded">Avg: {stats.average}</span>
                    </div>
                    
                    <div className="relative h-24 w-full mt-6 select-none px-4">
                        {/* Scale Base */}
                        <div className="absolute top-10 left-4 right-4 h-0.5 bg-gray-200"></div>
                        <div className="absolute top-14 left-4 text-xs text-gray-400 font-mono">0</div>
                        <div className="absolute top-14 right-4 text-xs text-gray-400 font-mono">100</div>

                        {/* Chart Area */}
                        <div className="absolute top-0 bottom-0 left-4 right-4">
                            {/* Whiskers (Range Line) */}
                            <div 
                                className="absolute top-10 h-0.5 bg-azure/40" 
                                style={{ left: `${stats.min}%`, width: `${stats.max - stats.min}%` }}
                            ></div>
                            
                            {/* Min Tick */}
                            <Tooltip title={`Min: ${stats.min}`}>
                                <div className="absolute top-8 h-4 w-0.5 bg-azure/60 cursor-help" style={{ left: `${stats.min}%` }}></div>
                            </Tooltip>

                            {/* Max Tick */}
                            <Tooltip title={`Max: ${stats.max}`}>
                                <div className="absolute top-8 h-4 w-0.5 bg-azure/60 cursor-help" style={{ left: `${stats.max}%` }}></div>
                            </Tooltip>

                            {/* IQR Box (Q1 to Q3) */}
                            <Tooltip title={`Q1: ${stats.q1} - Q3: ${stats.q3}`}>
                                <div 
                                    className="absolute top-6 h-8 bg-azure/10 border border-azure cursor-help flex items-center justify-center transition-all hover:bg-azure/20"
                                    style={{ left: `${stats.q1}%`, width: `${stats.q3 - stats.q1}%` }}
                                >
                                </div>
                            </Tooltip>

                            {/* Median Line */}
                            <Tooltip title={`Median: ${stats.median}`}>
                                <div 
                                    className="absolute top-6 h-8 w-1 bg-azure cursor-help z-10 shadow-glow" 
                                    style={{ left: `${stats.median}%`, transform: 'translateX(-50%)' }}
                                ></div>
                            </Tooltip>

                             {/* Average Dot */}
                            <Tooltip title={`Average: ${stats.average}`}>
                                <div className="absolute top-[38px] w-2 h-2 rounded-full bg-orange-400 z-20 border border-white" style={{ left: `${stats.average}%`, transform: 'translateX(-50%)' }}></div>
                            </Tooltip>
                        </div>
                    </div>
                    <div className="flex justify-between text-[10px] text-ink/40 mt-6 px-4 font-mono">
                        <span>Min: {stats.min}</span>
                        <span>Q1: {stats.q1}</span>
                        <span className="text-azure font-bold">Median: {stats.median}</span>
                        <span>Q3: {stats.q3}</span>
                        <span>Max: {stats.max}</span>
                    </div>
                </div>
            )}

            <Table 
              dataSource={submissions} 
              columns={submissionColumns} 
              rowKey="id" 
              pagination={false}
              size="small"
              expandable={{
                expandedRowRender: record => (
                  <div className="p-4 bg-mist rounded border border-line mx-4 mb-4">
                    <p className="font-bold text-ink/50 text-xs uppercase mb-2">Student Response:</p>
                    <p className="font-mono bg-paper p-3 border border-line rounded text-ink/80 text-sm">{record.content}</p>
                  </div>
                )
              }}
            />
          </>
        )}
      </Drawer>

      {/* Edit Grade Modal */}
      <Modal
        title="Edit Grade & Feedback"
        open={isEditOpen}
        onCancel={() => setIsEditOpen(false)}
        footer={null}
      >
          <Form form={editForm} onFinish={handleUpdateGrade} layout="vertical">
              <Form.Item name="score" label="Score (0-100)" rules={[{ required: true }]}>
                  <InputNumber min={0} max={100} className="w-full" />
              </Form.Item>
              <Form.Item name="feedback" label="Feedback" rules={[{ required: true }]}>
                  <TextArea rows={4} />
              </Form.Item>
              <div className="flex justify-end gap-2">
                  <Button onClick={() => setIsEditOpen(false)}>Cancel</Button>
                  <Button type="primary" htmlType="submit" className="bg-azure">Save Changes</Button>
              </div>
          </Form>
      </Modal>

      {/* Semester Statistics Modal */}
      <Modal
          title={
              <div className="flex items-center gap-2 text-azure">
                  <BarChartOutlined />
                  <span>Semester Statistics Manager</span>
              </div>
          }
          open={isStatsOpen}
          onCancel={() => setIsStatsOpen(false)}
          footer={null}
          width={900}
      >
          <div className="pt-2">
              <Steps 
                current={currentStep} 
                size="small"
                className="mb-8"
                items={[
                    { title: 'Data Source', description: 'Internal & Uploads' },
                    { title: 'Configuration', description: 'Weights & Preview' },
                ]}
              />

              {currentStep === 0 && (
                  <div className="space-y-6 animate-fade-in">
                      <div className="bg-mist p-6 rounded-xl border border-line">
                          <Title level={5}>1. External Data Source (Optional)</Title>
                          <Text className="text-ink/60 block mb-4">
                             Upload a CSV/Text file containing offline grades (e.g., Midterms). 
                             Our AI will automatically match names to student IDs.
                          </Text>
                          <Upload 
                              beforeUpload={handleFileUpload} 
                              maxCount={1} 
                              onRemove={() => setExternalFileContent('')}
                              accept=".csv,.txt"
                              className="w-full"
                          >
                              <Button icon={<UploadOutlined />} block className="h-12 border-dashed border-2">Click to Upload CSV</Button>
                          </Upload>
                          {externalFileContent && <div className="text-sm text-green-600 mt-2 font-bold flex items-center gap-2"><div className="w-2 h-2 bg-green-500 rounded-full"></div> File Ready</div>}
                      </div>

                      <div className="flex justify-end">
                        <Button 
                            type="primary" 
                            size="large"
                            onClick={handleProcessStats}
                            loading={isMerging}
                            className="bg-azure h-10 shadow-glow px-8"
                        >
                            Next: Configure Weights
                        </Button>
                      </div>
                  </div>
              )}

              {currentStep === 1 && statsData && (
                  <div className="space-y-4">
                      <div className="flex justify-between items-center bg-mist p-4 rounded-lg border border-line">
                         <div className="text-sm">
                            <span className="font-bold text-azure">{statsData.columns.length} Assignments</span> Found.
                            Adjust weights below to calculate the semester total.
                         </div>
                         <div className="text-xs text-ink/50">
                             Total Weight: <span className={Object.values(weights).reduce((a,b)=>a+b,0) === 100 ? 'text-green-600 font-bold' : 'text-orange-500 font-bold'}>
                                 {Object.values(weights).reduce((a,b)=>a+b,0)}%
                             </span>
                         </div>
                      </div>

                      <Table 
                        dataSource={statsData.students} 
                        columns={statsTableColumns} 
                        rowKey="id"
                        scroll={{ x: 'max-content', y: 400 }}
                        pagination={false}
                        size="small"
                        bordered
                      />

                      <div className="flex justify-between pt-4 border-t border-line">
                          <Button onClick={() => setCurrentStep(0)}>Back</Button>
                          <Button 
                              type="primary" 
                              icon={<FileExcelOutlined />}
                              onClick={handleExportFinalStats}
                              className="bg-green-600 hover:bg-green-500 border-none shadow-md"
                          >
                              Export Final CSV Report
                          </Button>
                      </div>
                  </div>
              )}
          </div>
      </Modal>
    </div>
  );
};