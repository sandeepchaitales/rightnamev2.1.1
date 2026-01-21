import React, { useState, useEffect } from 'react';
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Star, Shield, Globe, TrendingUp, Lock, Sparkles, CheckCircle2, BarChart3, AlertTriangle, Users, Zap, ChevronLeft, ChevronRight } from "lucide-react";

// Sample full report data for carousel
const sampleReport = {
    brandName: "TechNova",
    score: 87,
    verdict: "GO",
    executiveSummary: "TechNova presents a strong, distinctive brand identity with excellent trademark clearance and high memorability scores. Strategic positioning aligns perfectly with the premium tech market. The name carries a futuristic connotation while maintaining accessibility.",
    dimensions: [
        { name: "Distinctiveness", score: 9.2, color: "emerald" },
        { name: "Memorability", score: 8.8, color: "violet" },
        { name: "Trust Curve", score: 8.5, color: "blue" },
        { name: "Cultural Fit", score: 9.0, color: "fuchsia" },
        { name: "Phonetic Appeal", score: 8.7, color: "orange" },
        { name: "Digital Presence", score: 7.9, color: "cyan" },
    ],
    strengths: ["Unique phonetic structure", "Strong tech association", "Available .com domain", "No trademark conflicts"],
    risks: ["Similar to 'Nova' brands in aerospace", "May need education in non-English markets"],
    competitors: [
        { name: "TechCore", similarity: 45, intent: "Low" },
        { name: "NovaTech Systems", similarity: 72, intent: "Medium" },
        { name: "Innovate Labs", similarity: 38, intent: "Low" },
    ],
    domains: [
        { domain: "technova.com", status: "Available", price: "$2,500" },
        { domain: "technova.io", status: "Available", price: "$49/yr" },
        { domain: "technova.ai", status: "Taken", alternative: "gettechnova.ai" },
    ],
    cultural: [
        { country: "USA", score: 9.2, note: "Strong tech connotation" },
        { country: "India", score: 8.8, note: "Positive innovation association" },
        { country: "Germany", score: 8.5, note: "Professional sound" },
    ],
    trademarkRisk: "LOW",
    finalVerdict: "PROCEED WITH CONFIDENCE"
};

// Slide 1: Score & Summary
const SlideScoreSummary = () => (
    <div className="bg-white rounded-2xl p-8 h-full">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 h-full">
            {/* Score Card */}
            <div className="bg-gradient-to-br from-emerald-50 to-white border-2 border-emerald-200 rounded-2xl p-6 flex flex-col items-center justify-center">
                <p className="text-xs font-bold uppercase tracking-widest text-emerald-600 mb-2">RIGHTNAME™ INDEX</p>
                <div className="text-7xl font-black text-emerald-600">{sampleReport.score}</div>
                <div className="text-xl text-slate-400 font-bold">/100</div>
                <Badge className="mt-4 bg-emerald-500 text-white font-bold px-6 py-2 text-lg">
                    {sampleReport.verdict}
                </Badge>
            </div>
            
            {/* Summary */}
            <div className="flex flex-col justify-center">
                <h3 className="text-4xl font-black text-slate-900 mb-4">{sampleReport.brandName}</h3>
                <div className="flex items-center gap-2 mb-4">
                    <Star className="w-5 h-5 text-amber-500" />
                    <span className="text-sm font-bold uppercase text-amber-600">Executive Summary</span>
                </div>
                <p className="text-slate-600 leading-relaxed">{sampleReport.executiveSummary}</p>
            </div>
        </div>
    </div>
);

// Slide 2: Dimensions Analysis
const SlideDimensions = () => (
    <div className="bg-white rounded-2xl p-8 h-full">
        <div className="flex items-center gap-2 mb-6">
            <BarChart3 className="w-5 h-5 text-violet-500" />
            <h3 className="text-xl font-bold text-slate-900">Dimensions Analysis</h3>
            <Badge variant="outline" className="ml-auto">6 Frameworks</Badge>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {sampleReport.dimensions.map((dim, i) => (
                <div key={i} className="bg-slate-50 rounded-xl p-4">
                    <div className="flex items-center justify-between mb-2">
                        <span className="font-bold text-slate-700">{dim.name}</span>
                        <span className="text-lg font-black text-slate-900">{dim.score}/10</span>
                    </div>
                    <div className="h-3 bg-slate-200 rounded-full overflow-hidden">
                        <div 
                            className="h-full rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500 transition-all duration-1000"
                            style={{ width: `${dim.score * 10}%` }}
                        />
                    </div>
                </div>
            ))}
        </div>
    </div>
);

// Slide 3: Strengths & Risks
const SlideStrengthsRisks = () => (
    <div className="bg-white rounded-2xl p-8 h-full">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 h-full">
            {/* Strengths */}
            <div className="bg-emerald-50 rounded-xl p-6">
                <div className="flex items-center gap-2 mb-4">
                    <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                    <h4 className="font-bold text-emerald-700">Key Strengths</h4>
                </div>
                <ul className="space-y-3">
                    {sampleReport.strengths.map((s, i) => (
                        <li key={i} className="flex items-start gap-2 text-slate-700">
                            <span className="w-2 h-2 rounded-full bg-emerald-500 mt-2 flex-shrink-0"></span>
                            {s}
                        </li>
                    ))}
                </ul>
            </div>
            
            {/* Risks */}
            <div className="bg-amber-50 rounded-xl p-6">
                <div className="flex items-center gap-2 mb-4">
                    <AlertTriangle className="w-5 h-5 text-amber-600" />
                    <h4 className="font-bold text-amber-700">Potential Risks</h4>
                </div>
                <ul className="space-y-3">
                    {sampleReport.risks.map((r, i) => (
                        <li key={i} className="flex items-start gap-2 text-slate-700">
                            <span className="w-2 h-2 rounded-full bg-amber-500 mt-2 flex-shrink-0"></span>
                            {r}
                        </li>
                    ))}
                </ul>
            </div>
        </div>
    </div>
);

// Slide 4: Competitor Analysis
const SlideCompetitors = () => (
    <div className="bg-white rounded-2xl p-8 h-full">
        <div className="flex items-center gap-2 mb-6">
            <Users className="w-5 h-5 text-blue-500" />
            <h3 className="text-xl font-bold text-slate-900">Competitor Analysis</h3>
        </div>
        <div className="space-y-4">
            {sampleReport.competitors.map((comp, i) => (
                <div key={i} className="bg-slate-50 rounded-xl p-4 flex items-center justify-between">
                    <div>
                        <h4 className="font-bold text-slate-800">{comp.name}</h4>
                        <p className="text-sm text-slate-500">Market overlap: {comp.similarity}%</p>
                    </div>
                    <Badge className={comp.intent === 'Low' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}>
                        {comp.intent} Risk
                    </Badge>
                </div>
            ))}
        </div>
        <div className="mt-6 p-4 bg-blue-50 rounded-xl">
            <p className="text-sm text-blue-700">
                <strong>Analysis:</strong> No direct competitors with identical positioning. Market differentiation opportunity is strong.
            </p>
        </div>
    </div>
);

// Slide 5: Domain & Digital
const SlideDomains = () => (
    <div className="bg-white rounded-2xl p-8 h-full">
        <div className="flex items-center gap-2 mb-6">
            <Globe className="w-5 h-5 text-cyan-500" />
            <h3 className="text-xl font-bold text-slate-900">Domain Availability</h3>
        </div>
        <div className="space-y-4">
            {sampleReport.domains.map((d, i) => (
                <div key={i} className="bg-slate-50 rounded-xl p-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className={`w-3 h-3 rounded-full ${d.status === 'Available' ? 'bg-emerald-500' : 'bg-red-500'}`}></div>
                        <span className="font-mono font-bold text-slate-800">{d.domain}</span>
                    </div>
                    <div className="text-right">
                        <Badge className={d.status === 'Available' ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}>
                            {d.status}
                        </Badge>
                        <p className="text-xs text-slate-500 mt-1">{d.price || d.alternative}</p>
                    </div>
                </div>
            ))}
        </div>
    </div>
);

// Slide 6: Cultural Analysis
const SlideCultural = () => (
    <div className="bg-white rounded-2xl p-8 h-full">
        <div className="flex items-center gap-2 mb-6">
            <Globe className="w-5 h-5 text-fuchsia-500" />
            <h3 className="text-xl font-bold text-slate-900">Cultural Resonance</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {sampleReport.cultural.map((c, i) => (
                <div key={i} className="bg-gradient-to-br from-fuchsia-50 to-white border border-fuchsia-200 rounded-xl p-5 text-center">
                    <div className="text-3xl mb-2">
                        {c.country === 'USA' ? '🇺🇸' : c.country === 'India' ? '🇮🇳' : '🇩🇪'}
                    </div>
                    <h4 className="font-bold text-slate-800 mb-1">{c.country}</h4>
                    <div className="text-2xl font-black text-fuchsia-600 mb-2">{c.score}/10</div>
                    <p className="text-xs text-slate-500">{c.note}</p>
                </div>
            ))}
        </div>
    </div>
);

// Slide 7: Final Verdict
const SlideFinalVerdict = () => (
    <div className="bg-gradient-to-br from-emerald-500 via-teal-500 to-cyan-500 rounded-2xl p-8 h-full text-white">
        <div className="flex flex-col items-center justify-center h-full text-center">
            <Zap className="w-16 h-16 mb-4 opacity-90" />
            <h3 className="text-3xl font-black mb-2">Final Verdict</h3>
            <div className="text-5xl font-black mb-4">{sampleReport.finalVerdict}</div>
            <div className="flex items-center gap-4 mb-6">
                <div className="bg-white/20 rounded-xl px-4 py-2">
                    <span className="text-sm opacity-80">Trademark Risk</span>
                    <div className="font-bold">{sampleReport.trademarkRisk}</div>
                </div>
                <div className="bg-white/20 rounded-xl px-4 py-2">
                    <span className="text-sm opacity-80">Score</span>
                    <div className="font-bold">{sampleReport.score}/100</div>
                </div>
            </div>
            <p className="text-white/80 max-w-md">
                This brand name has passed all critical checks and is ready for market launch.
            </p>
        </div>
    </div>
);

// All slides
const slides = [
    { component: SlideScoreSummary, title: "Score & Summary" },
    { component: SlideDimensions, title: "Dimensions" },
    { component: SlideStrengthsRisks, title: "Analysis" },
    { component: SlideCompetitors, title: "Competitors" },
    { component: SlideDomains, title: "Domains" },
    { component: SlideCultural, title: "Cultural" },
    { component: SlideFinalVerdict, title: "Verdict" },
];

// Main Auto-Sliding Carousel
export const ReportCarousel = () => {
    const [currentSlide, setCurrentSlide] = useState(0);
    const [isPaused, setIsPaused] = useState(false);

    useEffect(() => {
        if (isPaused) return;
        
        const interval = setInterval(() => {
            setCurrentSlide((prev) => (prev + 1) % slides.length);
        }, 4000);
        
        return () => clearInterval(interval);
    }, [isPaused]);

    const goToSlide = (index) => {
        setCurrentSlide(index);
    };

    const prevSlide = () => {
        setCurrentSlide((prev) => (prev - 1 + slides.length) % slides.length);
    };

    const nextSlide = () => {
        setCurrentSlide((prev) => (prev + 1) % slides.length);
    };

    const CurrentSlideComponent = slides[currentSlide].component;

    return (
        <div className="py-16 px-4 bg-gradient-to-b from-slate-50 to-white">
            <div className="max-w-5xl mx-auto">
                {/* Header */}
                <div className="text-center mb-10">
                    <Badge className="bg-violet-100 text-violet-700 font-bold mb-4">
                        <Sparkles className="w-3 h-3 mr-1" /> SAMPLE REPORT
                    </Badge>
                    <h2 className="text-3xl md:text-4xl font-black text-slate-900 mb-3">
                        What You'll Get
                    </h2>
                    <p className="text-slate-500 max-w-lg mx-auto">
                        Full analysis for <span className="font-bold text-violet-600">"{sampleReport.brandName}"</span> — auto-playing preview
                    </p>
                </div>

                {/* Carousel Container */}
                <div 
                    className="relative"
                    onMouseEnter={() => setIsPaused(true)}
                    onMouseLeave={() => setIsPaused(false)}
                >
                    {/* Navigation Arrows */}
                    <button 
                        onClick={prevSlide}
                        className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-4 z-10 w-10 h-10 bg-white rounded-full shadow-lg flex items-center justify-center hover:bg-slate-50 transition-colors"
                    >
                        <ChevronLeft className="w-5 h-5 text-slate-600" />
                    </button>
                    <button 
                        onClick={nextSlide}
                        className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-4 z-10 w-10 h-10 bg-white rounded-full shadow-lg flex items-center justify-center hover:bg-slate-50 transition-colors"
                    >
                        <ChevronRight className="w-5 h-5 text-slate-600" />
                    </button>

                    {/* Slide Content */}
                    <div className="bg-gradient-to-br from-violet-100 via-fuchsia-50 to-orange-50 rounded-3xl p-4 shadow-xl shadow-violet-200/30 min-h-[400px]">
                        <div className="transition-all duration-500 ease-in-out">
                            <CurrentSlideComponent />
                        </div>
                    </div>

                    {/* Progress Bar */}
                    <div className="mt-4 h-1 bg-slate-200 rounded-full overflow-hidden">
                        <div 
                            className="h-full bg-gradient-to-r from-violet-500 to-fuchsia-500 transition-all duration-300"
                            style={{ width: `${((currentSlide + 1) / slides.length) * 100}%` }}
                        />
                    </div>

                    {/* Slide Indicators */}
                    <div className="flex justify-center gap-2 mt-6">
                        {slides.map((slide, index) => (
                            <button
                                key={index}
                                onClick={() => goToSlide(index)}
                                className={`px-3 py-1.5 rounded-full text-xs font-bold transition-all ${
                                    currentSlide === index 
                                        ? 'bg-violet-600 text-white shadow-lg' 
                                        : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                                }`}
                            >
                                {slide.title}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Lock indicator */}
                <div className="mt-8 text-center">
                    <div className="inline-flex items-center gap-2 px-4 py-2 bg-slate-100 rounded-full text-sm text-slate-500">
                        <Lock className="w-4 h-4" />
                        <span>Get your comprehensive brand report</span>
                    </div>
                </div>
            </div>
        </div>
    );
};

// Compact Preview for Auth Modal (keeping the old one)
export const ReportPreviewCompact = () => (
    <div className="bg-gradient-to-br from-slate-50 to-white rounded-xl p-4 mb-6 border border-slate-100">
        <div className="flex items-center gap-2 mb-3">
            <Sparkles className="w-4 h-4 text-violet-500" />
            <span className="text-xs font-bold text-slate-600">SAMPLE REPORT PREVIEW</span>
        </div>
        
        <div className="flex items-center gap-4 mb-3">
            <div className="flex-shrink-0">
                <div className="w-16 h-16 bg-gradient-to-br from-emerald-100 to-emerald-50 rounded-xl flex flex-col items-center justify-center border border-emerald-200">
                    <span className="text-xl font-black text-emerald-600">87</span>
                    <span className="text-[8px] text-emerald-500 font-bold">SCORE</span>
                </div>
            </div>
            <div className="flex-1 min-w-0">
                <h4 className="font-bold text-slate-900 text-sm">{sampleReport.brandName}</h4>
                <p className="text-xs text-slate-500 line-clamp-2 mt-1">
                    Strong brand identity with excellent trademark clearance...
                </p>
            </div>
            <Badge className="bg-emerald-500 text-white text-xs font-bold flex-shrink-0">GO</Badge>
        </div>

        {/* Mini dimension bars */}
        <div className="grid grid-cols-2 gap-2">
            {sampleReport.dimensions.slice(0, 2).map((dim, i) => (
                <div key={i} className="flex items-center gap-2">
                    <span className="text-[10px] text-slate-500 w-16 truncate">{dim.name}</span>
                    <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div 
                            className="h-full bg-violet-500 rounded-full"
                            style={{ width: `${dim.score * 10}%` }}
                        />
                    </div>
                </div>
            ))}
        </div>

        <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-center gap-1 text-xs text-slate-400">
            <Lock className="w-3 h-3" />
            <span>Register to unlock full analysis</span>
        </div>
    </div>
);

export default ReportCarousel;
