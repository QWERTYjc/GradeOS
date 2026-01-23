import React from 'react';
import { Brain, Zap, Shield, BarChart3, Users, Clock } from 'lucide-react';

const features = [
    {
        icon: Brain,
        title: "Neural Analysis",
        description: "Advanced AI models understand context, handwriting, and complex reasoning in student answers.",
        color: "blue"
    },
    {
        icon: Zap,
        title: "Instant Feedback",
        description: "Reduce grading time from days to seconds with high-throughput parallel processing.",
        color: "amber"
    },
    {
        icon: Shield,
        title: "Bias Elimination",
        description: "Standardized rubric application ensures every student is graded exactly the same way.",
        color: "green"
    },
    {
        icon: BarChart3,
        title: "Deep Analytics",
        description: "Uncover learning gaps and class-wide trends with comprehensive performance dashboards.",
        color: "purple"
    },
    {
        icon: Users,
        title: "Batch Management",
        description: "Effortlessly handle hundreds of submissions. Upload, scan, and grade in bulk.",
        color: "cyan"
    },
    {
        icon: Clock,
        title: "Real-time History",
        description: "Track every grade change and audit the AI's reasoning step-by-step.",
        color: "rose"
    }
];

export const FeatureGrid = () => {
    return (
        <section className="py-24 relative overflow-hidden">
            {/* Section Glow */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-indigo-500/5 blur-[120px] rounded-full pointer-events-none" />

            <div className="landing-container relative z-10">
                <div className="text-center max-w-2xl mx-auto mb-16">
                    <h2 className="landing-display text-3xl md:text-4xl font-bold text-white mb-4">
                        Powering the <span className="text-blue-500">Next Gen</span> Classroom
                    </h2>
                    <p className="text-slate-400">
                        GradeOS combines enterprise-grade reliability with cutting-edge AI to deliver the most accurate grading experience possible.
                    </p>
                </div>

                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {features.map((feature, idx) => (
                        <div
                            key={idx}
                            className="group relative p-6 rounded-2xl border border-slate-800 bg-slate-900/40 hover:bg-slate-900/80 transition-all duration-300 hover:-translate-y-1 hover:border-slate-700"
                        >
                            <div className={`
                w-12 h-12 rounded-lg mb-6 flex items-center justify-center
                bg-${feature.color}-500/10 text-${feature.color}-400
                group-hover:bg-${feature.color}-500/20 group-hover:scale-110 transition-all duration-300
              `}>
                                <feature.icon className="w-6 h-6" />
                            </div>

                            <h3 className="text-xl font-semibold text-white mb-3 font-display">
                                {feature.title}
                            </h3>

                            <p className="text-slate-400 text-sm leading-relaxed">
                                {feature.description}
                            </p>

                            {/* Hover Glow */}
                            <div className={`absolute inset-0 opacity-0 group-hover:opacity-100 bg-gradient-to-br from-${feature.color}-500/5 to-transparent rounded-2xl transition-opacity duration-300 pointer-events-none`} />
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
};
