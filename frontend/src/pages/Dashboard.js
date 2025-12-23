import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Button } from "@/components/ui/button";
import { BrandRadarChart, ScoreCard, CompetitionAnalysis, TrademarkRiskTable, DomainAvailabilityCard, FinalAssessmentCard, VisibilityAnalysisCard, AlternativeNamesCard } from '../components/AnalysisComponents';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Printer, ArrowLeft, CheckCircle2, XCircle, Star, Shield, Globe, Menu, LayoutDashboard } from "lucide-react";

const StickyHeader = ({ brandName, score, verdict, isVisible }) => (
    <div className={`sticky-header fixed top-0 left-0 right-0 bg-white/90 backdrop-blur-md border-b border-slate-200 z-50 transition-all duration-300 transform ${isVisible ? 'translate-y-0 opacity-100' : '-translate-y-full opacity-0'}`}>
        <div className="max-w-7xl mx-auto px-6 py-3 flex justify-between items-center">
            <div className="flex items-center gap-4">
                <h2 className="text-lg font-bold text-slate-900">{brandName}</h2>
                <Badge variant="secondary" className="font-mono font-bold text-xs">{score}/100</Badge>
            </div>
            <div className="flex items-center gap-3">
                <Badge className={
                    verdict === 'GO' ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-700"
                }>{verdict}</Badge>
                <Button size="sm" onClick={() => window.print()} variant="outline">Export</Button>
            </div>
        </div>
    </div>
);

const Dashboard = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { data, query } = location.state || {};
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
        setScrolled(window.scrollY > 400);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  if (!data) {
    return (
        <div className="min-h-screen flex items-center justify-center flex-col bg-slate-50">
            <div className="p-8 bg-white rounded-2xl shadow-lg text-center">
                <h2 className="text-xl mb-4 font-bold text-slate-800">Session Expired</h2>
                <Button onClick={() => navigate('/')}>Return Home</Button>
            </div>
        </div>
    );
  }

  const activeBrand = data.brand_scores[0]; 

  return (
    <div className="min-h-screen bg-[#f8fafc] text-slate-900 font-sans selection:bg-violet-100 pb-24 print:bg-white print:pb-0">
      
      <StickyHeader 
        brandName={activeBrand.brand_name} 
        score={activeBrand.namescore} 
        verdict={activeBrand.verdict}
        isVisible={scrolled}
      />

      {/* Main Navbar */}
      <div className="bg-white border-b border-slate-200 px-6 py-4 flex justify-between items-center print:hidden">
        <div className="flex items-center space-x-4">
            <Button variant="ghost" size="icon" onClick={() => navigate('/')} className="hover:bg-slate-100 rounded-full">
                <ArrowLeft className="h-5 w-5 text-slate-600" />
            </Button>
            <div className="flex flex-col">
                <h1 className="text-lg font-bold text-slate-900 tracking-tight">RIGHTNAME</h1>
                <span className="text-[10px] font-medium text-slate-400 uppercase tracking-widest">Report v2.2</span>
            </div>
        </div>
        <div className="flex items-center gap-3">
            <Badge variant="outline" className="hidden md:flex border-slate-200 text-slate-500 font-medium">
                {query.category} • {query.market_scope}
            </Badge>
            <Button onClick={() => window.print()} variant="outline" className="gap-2 rounded-lg border-slate-200 hover:border-slate-300">
                <Printer className="h-4 w-4" />
                <span className="hidden sm:inline">Export PDF</span>
            </Button>
        </div>
      </div>

      {/* Print-Only Header */}
      <div className="hidden print:block mb-8 border-b-2 border-slate-900 pb-4">
          <div className="flex justify-between items-end">
              <div>
                  <h1 className="text-4xl font-black text-slate-900 mb-2">RIGHTNAME ASSESSMENT</h1>
                  <p className="text-sm text-slate-500 uppercase tracking-widest">Confidential • {new Date().toLocaleDateString()}</p>
              </div>
              <div className="text-right">
                  <h2 className="text-2xl font-bold text-slate-700">{activeBrand.brand_name}</h2>
                  <p className="text-sm text-slate-500">{query.category} | {query.market_scope}</p>
              </div>
          </div>
      </div>

      <main className="max-w-7xl mx-auto px-4 md:px-6 py-10 space-y-12 print:p-0 print:space-y-8">
        
        {data.brand_scores.map((brand, idx) => (
            <div key={idx} className="space-y-12 animate-in fade-in duration-500 print:space-y-8">
                
                {/* 1. HERO + THE ANSWER (Re-ordered for Impact) */}
                <section className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
                    
                    {/* Left: Brand & Verdict */}
                    <div className="lg:col-span-8 flex flex-col gap-6">
                        <div className="print:hidden">
                            <h1 className="text-5xl md:text-7xl font-black text-slate-900 tracking-tight mb-4">
                                {brand.brand_name}
                            </h1>
                            <div className="flex flex-wrap gap-3">
                                <Badge className="bg-slate-900 text-white px-3 py-1 text-sm font-bold border-0">
                                    {brand.verdict}
                                </Badge>
                                <Badge variant="outline" className="text-slate-500 border-slate-200">
                                    {brand.positioning_fit} positioning
                                </Badge>
                            </div>
                        </div>
                        
                        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm print:border-l-4 print:border-l-violet-600 print:border-y-0 print:border-r-0 print:rounded-none">
                            <h3 className="text-xs font-bold uppercase tracking-widest text-violet-600 mb-2 flex items-center gap-2">
                                <Star className="w-4 h-4" /> Executive Summary
                            </h3>
                            <p className="text-lg font-medium text-slate-700 leading-relaxed text-justify">
                                {data.executive_summary}
                            </p>
                        </div>
                    </div>

                    {/* Right: Score Card */}
                    <div className="lg:col-span-4">
                         <ScoreCard 
                            title="Rightname™ Index" 
                            score={brand.namescore} 
                            verdict={brand.verdict}
                            subtitle="Composite Consulting Grade"
                            className="h-full shadow-lg shadow-slate-200/50"
                        />
                    </div>
                </section>

                {/* 2. FINAL ASSESSMENT & ROADMAP (Moved UP for "Answer First") */}
                {brand.final_assessment && (
                    <section className="print:mt-4">
                        <FinalAssessmentCard assessment={brand.final_assessment} />
                    </section>
                )}

                {/* 2.5 PLAN B - Alternative Names for REJECT/NO-GO verdicts */}
                {brand.alternative_names && (
                    <section className="print:mt-4">
                        <AlternativeNamesCard alternatives={brand.alternative_names} verdict={brand.verdict} />
                    </section>
                )}

                <Separator className="bg-slate-200/60 print:hidden" />

                {/* 3. STRATEGY & RADAR */}
                <section className="grid grid-cols-1 lg:grid-cols-12 gap-8 print:break-before-page">
                    <div className="lg:col-span-7 space-y-6 print:mb-6">
                        <div className="flex items-center gap-3 mb-2">
                            <div className="p-2 bg-emerald-100 rounded-lg print:hidden">
                                <LayoutDashboard className="w-5 h-5 text-emerald-600" />
                            </div>
                            <h3 className="text-2xl font-bold text-slate-900">Strategy Snapshot</h3>
                        </div>

                        <Card className="bg-white border border-slate-200 shadow-sm rounded-2xl overflow-hidden print:border-slate-300">
                            <CardContent className="p-8">
                                <h3 className="text-xl font-bold text-slate-900 mb-6 italic border-l-4 border-violet-500 pl-4 py-1">
                                    "{brand.strategic_classification}"
                                </h3>
                                <div className="grid md:grid-cols-2 gap-8">
                                    <div>
                                        <h4 className="text-xs font-bold uppercase text-emerald-600 mb-4 flex items-center gap-2">
                                            <CheckCircle2 className="w-4 h-4" /> Key Strengths
                                        </h4>
                                        <ul className="space-y-3">
                                            {brand.pros.map((pro, i) => (
                                                <li key={i} className="text-sm text-slate-700 font-medium flex items-start gap-2">
                                                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mt-1.5 flex-shrink-0 print:bg-emerald-600"></span>
                                                    {pro}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                    <div>
                                        <h4 className="text-xs font-bold uppercase text-rose-600 mb-4 flex items-center gap-2">
                                            <XCircle className="w-4 h-4" /> Key Risks
                                        </h4>
                                        <ul className="space-y-3">
                                            {brand.cons.map((con, i) => (
                                                <li key={i} className="text-sm text-slate-700 font-medium flex items-start gap-2">
                                                    <span className="w-1.5 h-1.5 rounded-full bg-rose-400 mt-1.5 flex-shrink-0 print:bg-rose-600"></span>
                                                    {con}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </div>

                    <div className="lg:col-span-5 flex flex-col">
                        <div className="flex items-center gap-3 mb-8 print:mb-2">
                            <div className="p-2 bg-violet-100 rounded-lg print:hidden">
                                <Shield className="w-5 h-5 text-violet-600" />
                            </div>
                            <h3 className="text-2xl font-bold text-slate-900">Dimensions Analysis</h3>
                        </div>
                        {/* Radar Chart Container with Print Header */}
                        <Card className="bg-white border border-slate-200 shadow-sm rounded-2xl flex-grow flex flex-col items-center justify-center p-4 print:border-slate-300">
                            <div className="w-full text-center mb-4 hidden print:block">
                                <h4 className="text-sm font-bold uppercase tracking-widest text-slate-500">Performance Radar</h4>
                                <p className="text-xs text-slate-400">Scores across 6 key frameworks</p>
                            </div>
                            <BrandRadarChart data={brand.dimensions} />
                        </Card>
                    </div>
                </section>

                {/* 4. MARKET INTELLIGENCE */}
                <section className="print:break-before-page">
                    <h3 className="text-xl font-bold text-slate-900 mb-6 flex items-center gap-2">
                        <Globe className="w-5 h-5 text-slate-400" /> Market Intelligence
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 print:grid-cols-2">
                        <div className="print:break-inside-avoid">
                            <DomainAvailabilityCard analysis={brand.domain_analysis} />
                        </div>
                        <div className="print:break-inside-avoid">
                            <VisibilityAnalysisCard analysis={brand.visibility_analysis} />
                        </div>
                        
                        <Card className="bg-white border border-slate-200 shadow-sm rounded-2xl flex flex-col print:break-inside-avoid">
                            <CardHeader className="pb-2 pt-5">
                                <CardTitle className="text-xs font-bold uppercase tracking-widest text-fuchsia-500">
                                    Cultural Fit
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="pt-4 space-y-4 flex-grow">
                                {brand.cultural_analysis.map((c, i) => (
                                    <div key={i} className="p-4 bg-fuchsia-50/50 rounded-xl border border-fuchsia-100">
                                        <div className="flex justify-between items-center mb-2">
                                            <span className="font-bold text-slate-800 text-sm">{c.country}</span>
                                            <Badge variant="secondary" className="bg-white text-fuchsia-700 text-xs font-bold border border-fuchsia-200">{c.cultural_resonance_score}/10</Badge>
                                        </div>
                                        <p className="text-xs text-slate-600 font-medium leading-relaxed">{c.cultural_notes}</p>
                                    </div>
                                ))}
                            </CardContent>
                        </Card>
                    </div>
                </section>

                {/* 5. COMPETITION & RISK */}
                {brand.competitor_analysis && (
                    <section className="print:break-inside-avoid">
                        <h3 className="text-xl font-bold text-slate-900 mb-6">Competitive Landscape</h3>
                        <CompetitionAnalysis data={brand.competitor_analysis} />
                    </section>
                )}

                {brand.trademark_matrix && (
                    <section className="print:break-before-page">
                        <h3 className="text-xl font-bold text-slate-900 mb-6">Legal Risk Matrix</h3>
                        <TrademarkRiskTable 
                            matrix={brand.trademark_matrix} 
                            trademarkClasses={brand.trademark_classes} 
                        />
                    </section>
                )}

                {/* 6. DETAILED ANALYSIS - Last Page */}
                <section className="print:break-before-page">
                    <h3 className="text-xl font-bold text-slate-900 mb-6">Detailed Framework Analysis</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 print:grid-cols-2">
                        {brand.dimensions.map((dim, i) => (
                            <Card key={i} className="bg-white border border-slate-200 shadow-sm hover:shadow-md transition-shadow rounded-2xl overflow-hidden group print:break-inside-avoid print:mb-4">
                                <CardHeader className="bg-slate-50/50 border-b border-slate-100 pb-4 group-hover:bg-slate-50 transition-colors">
                                    <div className="flex justify-between items-start">
                                        <CardTitle className="text-base font-bold text-slate-800">{dim.name}</CardTitle>
                                        <Badge className="bg-white text-violet-700 border-slate-200 font-bold border">
                                            {dim.score}/10
                                        </Badge>
                                    </div>
                                </CardHeader>
                                <CardContent className="pt-6">
                                    <div className="text-sm text-slate-600 leading-loose whitespace-pre-wrap font-medium text-justify">
                                        {dim.reasoning}
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </section>

            </div>
        ))}
      </main>
    </div>
  );
};

export default Dashboard;
