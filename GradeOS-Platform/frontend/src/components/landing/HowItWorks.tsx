import React from 'react';
import { FileText, Scan, BrainCircuit, CheckCircle2 } from 'lucide-react';

const steps = [
    {
        icon: FileText,
        title: "Upload",
        desc: "Submit PDFs or images of student work in bulk."
    },
    {
        icon: Scan,
        title: "Extract",
        desc: "OCR identifies handwriting and converts it to digital text."
    },
    {
        icon: BrainCircuit,
        title: "Analyze",
        desc: "AI evaluates answers against your specific rubric criteria."
    },
    {
        icon: CheckCircle2,
        title: "Review",
        desc: "Verify grades and export results instantly."
    }
];

export const HowItWorks = () => {
    return (
        <section className="py-24 bg-slate-900/50 border-y border-white/5">
            <div className="landing-container">
                <div className="text-center mb-16">
                    <h2 className="landing-display text-3xl md:text-4xl font-bold text-white mb-4">
                        From Paper to Grade <span className="text-blue-500">in Seconds</span>
                    </h2>
                    <p className="text-slate-400">
                        A seamless pipeline designed for efficiency.
                    </p>
                </div>

                <div className="relative">
                    {/* Connecting Line */}
                    <div className="hidden lg:block absolute top-[60px] left-0 right-0 h-0.5 bg-gradient-to-r from-blue-900 via-blue-500 to-blue-900 opacity-30" />

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
                        {steps.map((step, idx) => (
                            <div key={idx} className="relative group">
                                {/* Step Number Badge */}
                                <div className="absolute -top-4 -right-4 w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-xs font-bold text-slate-400 z-10">
                                    {idx + 1}
                                </div>

                                <div className="bg-slate-950 border border-slate-800 p-8 rounded-2xl relative z-0 hover:border-blue-500/50 transition-colors duration-300">
                                    <div className="w-14 h-14 mx-auto bg-blue-900/20 rounded-xl flex items-center justify-center text-blue-400 mb-6 group-hover:scale-110 transition-transform duration-300 group-hover:bg-blue-600/20 group-hover:text-blue-300">
                                        <step.icon className="w-7 h-7" />
                                    </div>
                                    <h3 className="text-lg font-bold text-white text-center mb-3">{step.title}</h3>
                                    <p className="text-slate-400 text-center text-sm">{step.desc}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </section>
    );
};
