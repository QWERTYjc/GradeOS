import React from 'react';

const stats = [
    { value: "50k+", label: "Papers Graded" },
    { value: "99.8%", label: "Accuracy Rate" },
    { value: "100hrs", label: "Saved Monthly" },
    { value: "24/7", label: "Availability" },
];

export const StatsRow = () => {
    return (
        <section className="py-12 border-b border-white/5 bg-slate-950/50">
            <div className="landing-container">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
                    {stats.map((stat, idx) => (
                        <div key={idx} className="text-center group cursor-default">
                            <div className="text-3xl md:text-5xl font-bold font-display text-white mb-2 group-hover:text-blue-400 transition-colors">
                                {stat.value}
                            </div>
                            <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold group-hover:text-slate-400 transition-colors">
                                {stat.label}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
};
