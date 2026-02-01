'use client';

import React, { useEffect, useState, useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import { FileText, Users, Clock, Award, Workflow, Cpu, GitBranch, ShieldCheck } from 'lucide-react';

// 技术特性展示
const techFeatures = [
  {
    icon: Workflow,
    label: "LangGraph",
    value: "工作流编排",
    desc: "多智能体协作",
    color: "#3b82f6"
  },
  {
    icon: Cpu,
    label: "Gemini 3.0",
    value: "Vision原生",
    desc: "视觉理解模型",
    color: "#06b6d4"
  },
  {
    icon: GitBranch,
    label: "并行处理",
    value: "批量批改",
    desc: "多学生同时处理",
    color: "#8b5cf6"
  },
  {
    icon: ShieldCheck,
    label: "人机协同",
    value: "审核机制",
    desc: "可介入审核修改",
    color: "#10b981"
  },
];

// 统计数据
const stats = [
  {
    icon: FileText,
    value: 50000,
    suffix: '+',
    label: '已批改试卷',
    color: '#3b82f6'
  },
  {
    icon: Users,
    value: 1200,
    suffix: '+',
    label: '教师用户',
    color: '#06b6d4'
  },
  {
    icon: Clock,
    value: 90,
    suffix: 's',
    label: '平均批改时间',
    color: '#8b5cf6'
  },
  {
    icon: Award,
    value: 98,
    suffix: '%',
    label: '准确率',
    color: '#10b981'
  },
];

// 数字计数动画组件
const CountUp = ({
  end,
  suffix,
  duration = 2000
}: {
  end: number;
  suffix: string;
  duration?: number;
}) => {
  const [count, setCount] = useState(0);
  const countRef = useRef(0);
  const startTimeRef = useRef<number | null>(null);

  useEffect(() => {
    const animate = (timestamp: number) => {
      if (!startTimeRef.current) startTimeRef.current = timestamp;
      const progress = timestamp - startTimeRef.current;
      const percentage = Math.min(progress / duration, 1);

      // 使用缓动函数
      const easeOutQuart = 1 - Math.pow(1 - percentage, 4);
      const currentCount = Math.floor(easeOutQuart * end);

      if (currentCount !== countRef.current) {
        countRef.current = currentCount;
        setCount(currentCount);
      }

      if (percentage < 1) {
        requestAnimationFrame(animate);
      } else {
        setCount(end);
      }
    };

    requestAnimationFrame(animate);

    return () => {
      startTimeRef.current = null;
    };
  }, [end, duration]);

  return (
    <span>
      {count.toLocaleString()}{suffix}
    </span>
  );
};

// 统计卡片组件
const StatCard = ({ stat, index, isInView }: { stat: typeof stats[0]; index: number; isInView: boolean }) => {
  const Icon = stat.icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ delay: index * 0.1, duration: 0.5 }}
      className="relative group"
    >
      <div className="relative bg-white rounded-2xl p-6 border border-gray-100 shadow-sm hover:shadow-lg transition-all duration-300 hover:-translate-y-1">
        {/* 图标 */}
        <div
          className="w-12 h-12 rounded-xl flex items-center justify-center mb-4 transition-transform group-hover:scale-110"
          style={{ background: `${stat.color}15` }}
        >
          <Icon className="w-6 h-6" style={{ color: stat.color }} />
        </div>

        {/* 数值 */}
        <div
          className="text-4xl font-bold mb-2"
          style={{ color: stat.color }}
        >
          {isInView ? (
            <CountUp end={stat.value} suffix={stat.suffix} />
          ) : (
            `0${stat.suffix}`
          )}
        </div>

        {/* 标签 */}
        <div className="text-gray-600 text-sm">{stat.label}</div>

        {/* 悬停装饰 */}
        <div
          className="absolute bottom-0 left-0 right-0 h-1 rounded-b-2xl opacity-0 group-hover:opacity-100 transition-opacity"
          style={{ background: `linear-gradient(to right, ${stat.color}, ${stat.color}80)` }}
        />
      </div>
    </motion.div>
  );
};

// 技术特性卡片
const TechFeatureCard = ({ feature, index }: { feature: typeof techFeatures[0]; index: number }) => {
  const Icon = feature.icon;
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-50px" });

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 20 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ delay: index * 0.1 }}
      whileHover={{ y: -5, transition: { duration: 0.2 } }}
      className="group cursor-default"
    >
      <div
        className="flex items-center gap-4 p-4 rounded-xl bg-white border transition-all duration-300 hover:shadow-md"
        style={{ borderColor: `${feature.color}20` }}
      >
        {/* 图标 */}
        <div
          className="w-12 h-12 rounded-lg flex items-center justify-center transition-all duration-300"
          style={{ background: `${feature.color}15` }}
        >
          <Icon className="w-6 h-6" style={{ color: feature.color }} />
        </div>

        {/* 内容 */}
        <div className="flex-1">
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-0.5">
            {feature.label}
          </div>
          <div
            className="text-lg font-bold text-gray-900 transition-colors"
            style={{ color: feature.color }}
          >
            {feature.value}
          </div>
          <div className="text-xs text-gray-500">
            {feature.desc}
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export const StatsRow = () => {
  const sectionRef = useRef(null);
  const isInView = useInView(sectionRef, { once: true, margin: "-100px" });

  return (
    <section ref={sectionRef} className="py-20 bg-gradient-to-b from-white to-blue-50/30">
      <div className="landing-container">
        {/* 技术特性 */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          className="mb-16"
        >
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {techFeatures.map((feature, idx) => (
              <TechFeatureCard key={idx} feature={feature} index={idx} />
            ))}
          </div>
        </motion.div>


      </div>
    </section>
  );
};

export default StatsRow;
