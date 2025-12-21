import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Button } from "@/components/ui/button";
import { BrandRadarChart, ScoreCard } from '../components/AnalysisComponents';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Printer, ArrowLeft, CheckCircle2, XCircle } from "lucide-react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";

const Dashboard = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { data, query } = location.state || {};

  if (!data) {
    return (
        <div className="min-h-screen flex items-center justify-center flex-col">
            <h2 className="text-xl mb-4">No data found</h2>
            <Button onClick={() => navigate('/')}>Go Back</Button>
        </div>
    );
  }

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 pb-20 print:bg-white">
      {/* Navbar - Hidden on Print */}
      <div className="sticky top-0 z-50 bg-white/80 backdrop-blur border-b border-slate-200 px-6 py-4 flex justify-between items-center print:hidden">
        <div className="flex items-center space-x-4">
            <Button variant="ghost" size="icon" onClick={() => navigate('/')}>
                <ArrowLeft className="h-5 w-5" />
            </Button>
            <h1 className="text-xl font-serif font-bold">RIGHTNAME Analysis</h1>
        </div>
        <Button onClick={handlePrint} variant="outline" className="gap-2">
            <Printer className="h-4 w-4" />
            Export PDF
        </Button>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8 space-y-12">
        
        {/* Header Section */}
        <section className="space-y-4">
            <div className="flex items-baseline justify-between">
                <h1 className="text-4xl font-serif font-bold text-slate-900">Executive Report</h1>
                <div className="text-right">
                    <p className="text-sm text-slate-500 uppercase tracking-widest">Project</p>
                    <p className="font-semibold">{query.category} • {query.market_scope}</p>
                </div>
            </div>
            <Card className="bg-slate-900 text-white border-none">
                <CardContent className="pt-6">
                    <h3 className="text-sm uppercase tracking-widest text-slate-400 mb-2">Executive Summary</h3>
                    <p className="text-lg font-light leading-relaxed opacity-90">
                        {data.executive_summary}
                    </p>
                </CardContent>
            </Card>
        </section>

        {/* Comparison Verdict */}
        {data.brand_scores.length > 1 && (
            <section>
                <div className="flex items-center space-x-2 mb-4">
                     <Separator className="w-10 bg-blue-600 h-1" />
                     <h2 className="text-2xl font-serif font-bold">Verdict</h2>
                </div>
                <p className="text-xl text-slate-700 italic border-l-4 border-blue-600 pl-4 py-2 bg-white shadow-sm">
                    {data.comparison_verdict}
                </p>
            </section>
        )}

        {/* Brand Details */}
        <div className="grid grid-cols-1 gap-16">
            {data.brand_scores.map((brand, idx) => (
                <div key={idx} className="space-y-8 break-inside-avoid">
                    <div className="flex items-center justify-between border-b pb-4 border-slate-200">
                        <h2 className="text-5xl font-serif font-bold text-slate-900">{brand.brand_name}</h2>
                         <Badge variant={brand.verdict === 'GO' ? 'default' : 'secondary'} className="text-lg px-4 py-1">
                            {brand.verdict}
                         </Badge>
                    </div>

                    {/* Overall Strategic Verdict Section */}
                    <Card className="border-l-4 border-l-slate-900">
                        <CardHeader>
                            <CardTitle className="text-sm uppercase text-slate-500 tracking-widest">Overall Strategic Verdict</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <h3 className="text-xl font-serif font-semibold text-slate-900 mb-6 italic">
                                "{brand.strategic_classification || "Analysis unavailable"}"
                            </h3>
                            
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                <div>
                                    <h4 className="flex items-center text-sm font-bold text-emerald-700 uppercase mb-4">
                                        <CheckCircle2 className="w-4 h-4 mr-2" />
                                        What the Name Delivers
                                    </h4>
                                    <ul className="space-y-3">
                                        {brand.pros && brand.pros.map((pro, i) => (
                                            <li key={i} className="flex items-start text-sm text-slate-700">
                                                <span className="mr-2 text-emerald-500">✓</span>
                                                {pro}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                                
                                <div>
                                    <h4 className="flex items-center text-sm font-bold text-red-700 uppercase mb-4">
                                        <XCircle className="w-4 h-4 mr-2" />
                                        What the Name Sacrifices
                                    </h4>
                                    <ul className="space-y-3">
                                        {brand.cons && brand.cons.map((con, i) => (
                                            <li key={i} className="flex items-start text-sm text-slate-700">
                                                <span className="mr-2 text-red-500">×</span>
                                                {con}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                        {/* Left Column: Scores */}
                        <div className="space-y-6">
                            <ScoreCard 
                                title="NameScore™ Index" 
                                score={brand.namescore} 
                                verdict={brand.verdict}
                                subtitle="Composite Consulting Grade"
                            />
                            
                            <Card>
                                <CardHeader><CardTitle className="text-sm uppercase text-slate-500">Trademark Risk</CardTitle></CardHeader>
                                <CardContent>
                                    <div className="flex justify-between items-center mb-2">
                                        <span className="font-bold text-xl">{brand.trademark_risk.risk_level}</span>
                                        <span className="text-sm text-slate-400">Score: {brand.trademark_risk.score}/10</span>
                                    </div>
                                    <p className="text-sm text-slate-600 mb-4">{brand.trademark_risk.summary}</p>
                                    <div className="space-y-2">
                                        {brand.trademark_risk.details.map((d, i) => (
                                            <div key={i} className="flex justify-between text-xs border-b border-slate-100 pb-1">
                                                <span>{d.country}</span>
                                                <span className={d.risk === 'High' ? 'text-red-500 font-bold' : 'text-slate-600'}>{d.risk}</span>
                                            </div>
                                        ))}
                                    </div>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Middle Column: Radar */}
                        <div className="bg-white p-6 rounded-lg border shadow-sm">
                            <BrandRadarChart data={brand.dimensions} />
                        </div>

                         {/* Right Column: Cultural & Positioning */}
                         <div className="space-y-6">
                            <Card>
                                <CardHeader><CardTitle className="text-sm uppercase text-slate-500">Positioning Fit</CardTitle></CardHeader>
                                <CardContent>
                                    <p className="text-sm leading-relaxed">{brand.positioning_fit}</p>
                                </CardContent>
                            </Card>

                             <Card>
                                <CardHeader><CardTitle className="text-sm uppercase text-slate-500">Cultural Analysis</CardTitle></CardHeader>
                                <CardContent className="space-y-4">
                                    {brand.cultural_analysis.map((c, i) => (
                                        <div key={i}>
                                            <div className="flex justify-between font-semibold text-sm mb-1">
                                                <span>{c.country}</span>
                                                <span>{c.cultural_resonance_score}/10</span>
                                            </div>
                                            <p className="text-xs text-slate-600">{c.cultural_notes}</p>
                                        </div>
                                    ))}
                                </CardContent>
                            </Card>
                         </div>
                    </div>

                    {/* Detailed Framework Analysis */}
                    <div className="mt-8">
                        <h3 className="text-2xl font-serif font-bold text-slate-900 mb-6">Detailed Framework Analysis</h3>
                        <Accordion type="single" collapsible className="w-full bg-white rounded-lg border shadow-sm px-6">
                            {brand.dimensions.map((dim, i) => (
                                <AccordionItem key={i} value={`item-${i}`} className="border-b-slate-100 last:border-0">
                                    <AccordionTrigger className="hover:no-underline py-4">
                                        <div className="flex justify-between w-full items-center pr-4">
                                            <span className="font-serif font-medium text-lg">{dim.name}</span>
                                            <div className="flex items-center space-x-2">
                                                <span className="text-sm text-slate-400 uppercase tracking-widest text-xs">Score</span>
                                                <span className="font-bold text-primary">{dim.score}/10</span>
                                            </div>
                                        </div>
                                    </AccordionTrigger>
                                    <AccordionContent className="text-slate-600 leading-relaxed pb-6 whitespace-pre-wrap">
                                        {dim.reasoning}
                                    </AccordionContent>
                                </AccordionItem>
                            ))}
                        </Accordion>
                    </div>

                </div>
            ))}
        </div>

      </div>
    </div>
  );
};

export default Dashboard;
