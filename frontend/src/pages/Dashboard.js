import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Button } from "@/components/ui/button";
import { BrandRadarChart, ScoreCard, CompetitionAnalysis, TrademarkRiskTable, DomainAvailabilityCard, FinalAssessmentCard } from '../components/AnalysisComponents';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Printer, ArrowLeft, CheckCircle2, XCircle, Star, Shield, Globe } from "lucide-react";

const Dashboard = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { data, query } = location.state || {};

  if (!data) {
    return (
        <div className="min-h-screen flex items-center justify-center flex-col bg-slate-50">
            <h2 className="text-xl mb-4 font-bold text-slate-800">No data found</h2>
            <Button onClick={() => navigate('/')}>Go Back</Button>
        </div>
    );
  }

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="min-h-screen bg-[#f8fafc] text-slate-900 pb-20 print:bg-white font-sans selection:bg-violet-200">
      {/* Navbar - Hidden on Print */}
      <div className="sticky top-0 z-50 bg-white/80 backdrop-blur-xl border-b border-slate-200/60 px-6 py-4 flex justify-between items-center print:hidden shadow-sm">
        <div className="flex items-center space-x-4">
            <Button variant="ghost" size="icon" onClick={() => navigate('/')} className="hover:bg-violet-50 hover:text-violet-600 rounded-full">
                <ArrowLeft className="h-5 w-5" />
            </Button>
            <h1 className="text-xl font-extrabold bg-clip-text text-transparent bg-gradient-to-r from-violet-600 to-fuchsia-600">RIGHTNAME</h1>
        </div>
        <Button onClick={handlePrint} variant="outline" className="gap-2 rounded-full border-2 hover:bg-slate-50">
            <Printer className="h-4 w-4" />
            Export PDF
        </Button>
      </div>

      <div className="max-w-7xl mx-auto px-4 md:px-6 py-12 space-y-20">
        
        {/* Brand Details Loop */}
        {data.brand_scores.map((brand, idx) => (
            <div key={idx} className="space-y-16 break-inside-avoid">
                
                {/* HERO SECTION: NameScore + Executive Summary */}
                <section className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-stretch">
                    {/* Left: Score Card (Hero) */}
                    <div className="lg:col-span-4 flex flex-col h-full">
                         <ScoreCard 
                            title="NameScore™ Index" 
                            score={brand.namescore} 
                            verdict={brand.verdict}
                            subtitle="Composite Consulting Grade"
                            className="h-full shadow-xl shadow-violet-100 border-l-8"
                        />
                    </div>

                    {/* Right: Brand Title & Executive Summary */}
                    <div className="lg:col-span-8 flex flex-col space-y-6">
                        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                            <div>
                                <Badge className="mb-2 bg-violet-100 text-violet-700 hover:bg-violet-200 border-0 px-3 py-1 text-xs tracking-wider font-bold">PROJECT: {query.category}</Badge>
                                <h1 className="text-5xl md:text-6xl font-black text-slate-900 tracking-tighter flex items-center gap-4">
                                    {brand.brand_name}
                                </h1>
                            </div>
                            <div className="text-right hidden md:block">
                                <p className="text-xs text-slate-400 font-bold uppercase tracking-widest mb-1">Market</p>
                                <p className="font-bold text-lg text-slate-700">{query.market_scope}</p>
                            </div>
                        </div>

                        <Card className="playful-card bg-gradient-to-br from-slate-900 to-slate-800 text-white border-none shadow-xl flex-grow">
                            <CardContent className="pt-8 pb-8 px-8 flex flex-col justify-center h-full">
                                <h3 className="text-xs font-black uppercase tracking-widest text-violet-300 mb-4 flex items-center gap-2">
                                    <Star className="w-4 h-4" /> Executive Summary
                                </h3>
                                <p className="text-lg md:text-xl font-medium leading-relaxed opacity-95 text-slate-100">
                                    {data.executive_summary}
                                </p>
                            </CardContent>
                        </Card>
                    </div>
                </section>

                {/* 1. Strategy Section */}
                <section>
                    <div className="flex items-center space-x-4 mb-8">
                         <div className="h-10 w-1.5 bg-gradient-to-b from-emerald-500 to-teal-500 rounded-full"></div>
                         <div>
                            <h3 className="text-2xl font-black text-slate-900">Strategy Snapshot</h3>
                            <p className="text-slate-500 font-medium">Positioning & Trade-offs</p>
                         </div>
                    </div>

                    <Card className="playful-card bg-white border-0 ring-1 ring-slate-100">
                        <CardContent className="pt-8">
                            <h3 className="text-2xl md:text-3xl font-bold text-slate-900 mb-8 flex items-center gap-3">
                                <span className="text-violet-500">❝</span>
                                {brand.strategic_classification || "Analysis unavailable"}
                            </h3>
                            
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 lg:gap-12">
                                <div className="bg-emerald-50/50 p-6 md:p-8 rounded-3xl border border-emerald-100">
                                    <h4 className="flex items-center text-sm font-black text-emerald-700 uppercase mb-4 tracking-wide">
                                        <CheckCircle2 className="w-5 h-5 mr-2" />
                                        Delivers
                                    </h4>
                                    <ul className="space-y-4">
                                        {brand.pros && brand.pros.map((pro, i) => (
                                            <li key={i} className="flex items-start text-base text-slate-700 font-medium">
                                                <span className="mr-3 text-emerald-500 font-bold">•</span>
                                                {pro}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                                
                                <div className="bg-rose-50/50 p-6 md:p-8 rounded-3xl border border-rose-100">
                                    <h4 className="flex items-center text-sm font-black text-rose-700 uppercase mb-4 tracking-wide">
                                        <XCircle className="w-5 h-5 mr-2" />
                                        Sacrifices
                                    </h4>
                                    <ul className="space-y-4">
                                        {brand.cons && brand.cons.map((con, i) => (
                                            <li key={i} className="flex items-start text-base text-slate-700 font-medium">
                                                <span className="mr-3 text-rose-500 font-bold">•</span>
                                                {con}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </section>

                {/* 2. Deep Dive Metrics (Radar, Domain, Cultural) */}
                <section>
                    <div className="flex items-center space-x-4 mb-8">
                         <div className="h-10 w-1.5 bg-gradient-to-b from-blue-500 to-cyan-500 rounded-full"></div>
                         <div>
                            <h3 className="text-2xl font-black text-slate-900">Brand Dimensions</h3>
                            <p className="text-slate-500 font-medium">Analysis on 6 Core Frameworks</p>
                         </div>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
                        {/* Domain (Left - 4 cols) */}
                        <div className="lg:col-span-4 flex flex-col">
                            {brand.domain_analysis && (
                                <DomainAvailabilityCard analysis={brand.domain_analysis} />
                            )}
                        </div>

                        {/* Radar (Middle - 4 cols) */}
                        <div className="lg:col-span-4 playful-card p-4 flex items-center justify-center bg-white h-full">
                            <BrandRadarChart data={brand.dimensions} />
                        </div>

                        {/* Cultural/Positioning (Right - 4 cols) */}
                        <div className="lg:col-span-4 flex flex-col space-y-6">
                            <Card className="playful-card border-l-4 border-l-cyan-400 flex-grow">
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-xs font-bold uppercase text-cyan-500 tracking-widest">Positioning Fit</CardTitle>
                                </CardHeader>
                                <CardContent className="pt-4">
                                    <p className="text-base font-medium text-slate-700 leading-relaxed">{brand.positioning_fit}</p>
                                </CardContent>
                            </Card>

                             <Card className="playful-card border-l-4 border-l-fuchsia-400 flex-grow">
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-xs font-bold uppercase text-fuchsia-500 tracking-widest flex items-center gap-2">
                                        <Globe className="w-3 h-3" /> Cultural Resonance
                                    </CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-4 pt-4">
                                    {brand.cultural_analysis.map((c, i) => (
                                        <div key={i} className="bg-fuchsia-50/50 p-4 rounded-xl">
                                            <div className="flex justify-between font-bold text-base mb-2 text-slate-800">
                                                <span>{c.country}</span>
                                                <span className="text-fuchsia-600">{c.cultural_resonance_score}/10</span>
                                            </div>
                                            <p className="text-sm text-slate-600 font-medium">{c.cultural_notes}</p>
                                        </div>
                                    ))}
                                </CardContent>
                            </Card>
                        </div>
                    </div>
                </section>

                {/* 3. Competitor Analysis */}
                {brand.competitor_analysis && (
                    <section>
                         <div className="flex items-center space-x-4 mb-8">
                             <div className="h-10 w-1.5 bg-gradient-to-b from-orange-500 to-amber-500 rounded-full"></div>
                             <div>
                                <h3 className="text-2xl font-black text-slate-900">Competition</h3>
                                <p className="text-slate-500 font-medium">Market Landscape & Pricing</p>
                             </div>
                        </div>
                        <CompetitionAnalysis data={brand.competitor_analysis} />
                    </section>
                )}
                
                {/* 4. Legal Risk - Full Width Container */}
                {brand.trademark_matrix && (
                    <section className="w-full">
                        <div className="flex items-center space-x-4 mb-8">
                            <div className="h-10 w-1.5 bg-gradient-to-b from-rose-500 to-pink-500 rounded-full"></div>
                            <div>
                                <h3 className="text-2xl font-black text-slate-900">Legal Risk Analysis</h3>
                                <p className="text-slate-500 font-medium">Detailed breakdown of potential IP conflicts</p>
                            </div>
                        </div>
                        <div className="w-full overflow-hidden">
                            <TrademarkRiskTable matrix={brand.trademark_matrix} />
                        </div>
                    </section>
                )}

                {/* 5. Final Assessment & Recommendations - NEW SECTION */}
                {brand.final_assessment && (
                    <section className="w-full">
                        <div className="flex items-center space-x-4 mb-8">
                            <div className="h-10 w-1.5 bg-gradient-to-b from-indigo-500 to-violet-500 rounded-full"></div>
                            <div>
                                <h3 className="text-2xl font-black text-slate-900">Final Recommendation</h3>
                                <p className="text-slate-500 font-medium">Executive Verdict & Next Steps</p>
                            </div>
                        </div>
                        <div className="w-full">
                            <FinalAssessmentCard assessment={brand.final_assessment} />
                        </div>
                    </section>
                )}

                {/* 6. Detailed Cards */}
                <section>
                     <div className="flex items-center space-x-4 mb-8">
                         <div className="h-10 w-1.5 bg-gradient-to-b from-violet-500 to-indigo-500 rounded-full"></div>
                         <div>
                            <h3 className="text-2xl font-black text-slate-900">Deep Dive Analysis</h3>
                            <p className="text-slate-500 font-medium">Detailed 6-Factor Framework Breakdown</p>
                         </div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                        {brand.dimensions.map((dim, i) => (
                            <Card key={i} className="playful-card border-slate-100 hover:translate-y-[-4px] transition-transform duration-300">
                                <CardHeader className="bg-slate-50/50 border-b border-slate-100 pb-4">
                                    <div className="flex justify-between items-start">
                                        <CardTitle className="text-lg font-bold text-slate-800">{dim.name}</CardTitle>
                                        <Badge variant="outline" className="bg-white text-violet-600 font-black border-slate-200 text-lg px-3">
                                            {dim.score}
                                        </Badge>
                                    </div>
                                </CardHeader>
                                <CardContent className="pt-6">
                                    <div className="text-sm text-slate-600 leading-loose whitespace-pre-wrap font-medium">
                                        {dim.reasoning}
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </section>

            </div>
        ))}
      </div>
    </div>
  );
};

export default Dashboard;
