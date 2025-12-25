import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from "@/components/ui/button";
import { BrandRadarChart, ScoreCard, CompetitionAnalysis, TrademarkRiskTable, DomainAvailabilityCard, FinalAssessmentCard, VisibilityAnalysisCard, AlternativeNamesCard, MultiDomainCard, SocialAvailabilityCard } from '../components/AnalysisComponents';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Printer, ArrowLeft, CheckCircle2, XCircle, Star, Shield, Globe, Menu, LayoutDashboard, Lock, Sparkles, LogIn } from "lucide-react";

// Helper function to parse markdown bold (**text**) into JSX
const parseMarkdownBold = (text) => {
    if (!text) return text;
    const parts = text.split(/(\*\*[^*]+\*\*)/g);
    return parts.map((part, index) => {
        if (part.startsWith('**') && part.endsWith('**')) {
            return <strong key={index} className="font-bold text-slate-800">{part.slice(2, -2)}</strong>;
        }
        return part;
    });
};

// Locked Section Component with blur and teaser
const LockedSection = ({ title, teaser, icon: Icon, onUnlock }) => (
    <div className="relative overflow-hidden rounded-2xl border-2 border-dashed border-slate-200 bg-gradient-to-br from-slate-50 to-white">
        {/* Blurred preview content */}
        <div className="p-8 filter blur-sm opacity-50 pointer-events-none select-none">
            <div className="h-4 w-3/4 bg-slate-200 rounded mb-3"></div>
            <div className="h-4 w-1/2 bg-slate-200 rounded mb-3"></div>
            <div className="h-20 w-full bg-slate-100 rounded mb-3"></div>
            <div className="grid grid-cols-2 gap-4">
                <div className="h-16 bg-slate-100 rounded"></div>
                <div className="h-16 bg-slate-100 rounded"></div>
            </div>
        </div>
        
        {/* Lock overlay */}
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/80 backdrop-blur-[2px]">
            <div className="text-center px-6 py-8 max-w-sm">
                <div className="w-16 h-16 mx-auto mb-4 bg-gradient-to-br from-violet-100 to-fuchsia-100 rounded-2xl flex items-center justify-center">
                    <Lock className="w-8 h-8 text-violet-600" />
                </div>
                <h3 className="text-xl font-black text-slate-900 mb-2 flex items-center justify-center gap-2">
                    {Icon && <Icon className="w-5 h-5 text-violet-500" />}
                    {title}
                </h3>
                <p className="text-sm text-slate-500 mb-6 leading-relaxed">
                    {teaser}
                </p>
                <Button 
                    onClick={onUnlock}
                    className="bg-gradient-to-r from-violet-600 via-fuchsia-500 to-orange-500 hover:from-violet-700 hover:via-fuchsia-600 hover:to-orange-600 text-white font-bold shadow-lg shadow-violet-200 rounded-xl px-6"
                >
                    <Sparkles className="w-4 h-4 mr-2" />
                    Register to Unlock
                </Button>
            </div>
        </div>
    </div>
);

// Register CTA Banner
const RegisterCTABanner = ({ onRegister }) => (
    <div className="bg-gradient-to-r from-violet-600 via-fuchsia-500 to-orange-500 rounded-2xl p-6 text-white mb-8 shadow-xl shadow-violet-200/50">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center">
                    <Lock className="w-6 h-6" />
                </div>
                <div>
                    <h3 className="text-lg font-black">Unlock Your Full Report</h3>
                    <p className="text-sm text-white/80">Register for free to see detailed analysis, risk matrix, and more</p>
                </div>
            </div>
            <Button 
                onClick={onRegister}
                className="bg-white text-violet-700 hover:bg-slate-100 font-bold shadow-lg rounded-xl px-6 whitespace-nowrap"
            >
                <LogIn className="w-4 h-4 mr-2" />
                Register Now — It's Free
            </Button>
        </div>
    </div>
);

const StickyHeader = ({ brandName, score, verdict, isVisible, isAuthenticated, onRegister }) => (
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
                {isAuthenticated ? (
                    <Button size="sm" onClick={() => window.print()} variant="outline">Export</Button>
                ) : (
                    <Button size="sm" onClick={onRegister} className="bg-violet-600 hover:bg-violet-700 text-white">
                        <Lock className="w-3 h-3 mr-1" /> Unlock Full
                    </Button>
                )}
            </div>
        </div>
    </div>
);

const Dashboard = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, openAuthModal } = useAuth();
  const [scrolled, setScrolled] = useState(false);
  const [reportData, setReportData] = useState(null);
  const [queryData, setQueryData] = useState(null);
  const [loading, setLoading] = useState(true);
  
  // Check if user is authenticated
  const isAuthenticated = !!user;

  // Load report data from location.state or localStorage
  useEffect(() => {
    const loadReportData = async () => {
      // First, try to get from location.state
      if (location.state?.data) {
        setReportData(location.state.data);
        setQueryData(location.state.query);
        // Save to localStorage for persistence
        localStorage.setItem('current_report', JSON.stringify(location.state.data));
        localStorage.setItem('current_query', JSON.stringify(location.state.query));
        if (location.state.data.report_id) {
          localStorage.setItem('pending_report_id', location.state.data.report_id);
        }
        setLoading(false);
        return;
      }
      
      // If no location.state, try localStorage
      const savedReport = localStorage.getItem('current_report');
      const savedQuery = localStorage.getItem('current_query');
      
      if (savedReport && savedQuery) {
        try {
          setReportData(JSON.parse(savedReport));
          setQueryData(JSON.parse(savedQuery));
          setLoading(false);
          return;
        } catch (e) {
          console.error('Error parsing saved report:', e);
        }
      }
      
      // No data available
      setLoading(false);
    };
    
    loadReportData();
  }, [location.state]);

  useEffect(() => {
    const handleScroll = () => {
        setScrolled(window.scrollY > 400);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const handleRegister = () => {
    // Save return URL for Google auth flow
    localStorage.setItem('auth_return_url', '/dashboard');
    openAuthModal(reportData?.report_id);
  };

  if (loading) {
    return (
        <div className="min-h-screen flex items-center justify-center flex-col bg-slate-50">
            <div className="p-8 bg-white rounded-2xl shadow-lg text-center">
                <div className="w-8 h-8 border-4 border-violet-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                <h2 className="text-xl font-bold text-slate-800">Loading Report...</h2>
            </div>
        </div>
    );
  }

  if (!reportData) {
    return (
        <div className="min-h-screen flex items-center justify-center flex-col bg-slate-50">
            <div className="p-8 bg-white rounded-2xl shadow-lg text-center">
                <h2 className="text-xl mb-4 font-bold text-slate-800">Session Expired</h2>
                <Button onClick={() => navigate('/')}>Return Home</Button>
            </div>
        </div>
    );
  }

  const data = reportData;
  const query = queryData || {};
  const activeBrand = data.brand_scores[0]; 

  // Teaser texts for locked sections
  const lockedSections = {
    strategy: {
        title: "Strategy Snapshot",
        teaser: "Discover your brand's strategic classification, key strengths, and potential risks identified by our AI analysis...",
        icon: LayoutDashboard
    },
    dimensions: {
        title: "Dimensions Analysis",
        teaser: "See how your brand scores across 8 key frameworks including distinctiveness, cultural resonance, and trust curve...",
        icon: Shield
    },
    trademark: {
        title: "Legal Risk Matrix",
        teaser: "Understand potential trademark conflicts, genericness risk, and rebranding probability with detailed risk scoring...",
        icon: Shield
    },
    domain: {
        title: "Digital Presence Check",
        teaser: "Check domain availability across multiple TLDs and social media handle availability on major platforms...",
        icon: Globe
    },
    competitor: {
        title: "Competitive Landscape",
        teaser: "See who you're competing against in your market, with intent matching and customer overlap analysis...",
        icon: Globe
    },
    cultural: {
        title: "Cultural Fit Analysis",
        teaser: "Understand how your brand name resonates across different cultures and languages in your target markets...",
        icon: Globe
    },
    finalAssessment: {
        title: "Final Assessment & Roadmap",
        teaser: "Get actionable recommendations and a strategic roadmap for your brand launch...",
        icon: Star
    }
  };

  return (
    <div className="min-h-screen bg-[#f8fafc] text-slate-900 font-sans selection:bg-violet-100 pb-24 print:bg-white print:pb-0">
      
      <StickyHeader 
        brandName={activeBrand.brand_name} 
        score={activeBrand.namescore} 
        verdict={activeBrand.verdict}
        isVisible={scrolled}
        isAuthenticated={isAuthenticated}
        onRegister={handleRegister}
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
            {isAuthenticated ? (
                <Button onClick={() => window.print()} variant="outline" className="gap-2 rounded-lg border-slate-200 hover:border-slate-300">
                    <Printer className="h-4 w-4" />
                    <span className="hidden sm:inline">Export PDF</span>
                </Button>
            ) : (
                <Button onClick={handleRegister} className="gap-2 rounded-lg bg-violet-600 hover:bg-violet-700 text-white">
                    <Lock className="h-4 w-4" />
                    <span className="hidden sm:inline">Unlock Full Report</span>
                </Button>
            )}
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
        
        {/* Show CTA Banner for non-authenticated users */}
        {!isAuthenticated && <RegisterCTABanner onRegister={handleRegister} />}

        {data.brand_scores.map((brand, idx) => (
            <div key={idx} className="space-y-12 animate-in fade-in duration-500 print:space-y-8">
                
                {/* 1. HERO + THE ANSWER - ALWAYS VISIBLE */}
                <section className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
                    
                    {/* Left: Brand & Verdict */}
                    <div className="lg:col-span-5 flex flex-col gap-6">
                        <div className="print:hidden">
                            <h1 className="text-5xl md:text-6xl font-black text-slate-900 tracking-tight mb-4">
                                {brand.brand_name}
                            </h1>
                            <div className="flex flex-wrap gap-3">
                                <Badge className="bg-slate-900 text-white px-3 py-1 text-sm font-bold border-0">
                                    {brand.verdict}
                                </Badge>
                                <Badge variant="outline" className="text-slate-500 border-slate-200">
                                    {brand.positioning_fit} positioning
                                </Badge>
                                {!isAuthenticated && (
                                    <Badge className="bg-amber-100 text-amber-700 border-amber-200">
                                        <Lock className="w-3 h-3 mr-1" /> Preview Mode
                                    </Badge>
                                )}
                            </div>
                        </div>
                        
                        {/* Executive Summary - ALWAYS VISIBLE */}
                        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm print:border-l-4 print:border-l-violet-600 print:border-y-0 print:border-r-0 print:rounded-none flex-grow">
                            <h3 className="text-xs font-bold uppercase tracking-widest text-violet-600 mb-2 flex items-center gap-2">
                                <Star className="w-4 h-4" /> Executive Summary
                            </h3>
                            <p className="text-base font-medium text-slate-700 leading-relaxed text-justify">
                                {data.executive_summary}
                            </p>
                        </div>
                    </div>

                    {/* Middle: Score Card - ALWAYS VISIBLE */}
                    <div className="lg:col-span-3">
                         <ScoreCard 
                            title="Rightname™ Index" 
                            score={brand.namescore} 
                            verdict={brand.verdict}
                            subtitle="Composite Consulting Grade"
                            className="h-full shadow-lg shadow-slate-200/50"
                        />
                    </div>

                    {/* Right: Dimensions Quick View - ALWAYS VISIBLE */}
                    <div className="lg:col-span-4">
                        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-lg h-full">
                            <div className="flex items-center gap-2 mb-4">
                                <Shield className="w-4 h-4 text-violet-500" />
                                <p className="text-xs font-bold uppercase tracking-widest text-violet-600">Quick Dimensions</p>
                            </div>
                            <div className="space-y-3">
                                {brand.dimensions.slice(0, 6).map((dim, i) => (
                                    <div key={i} className="group">
                                        <div className="flex items-center justify-between mb-1">
                                            <span className="text-xs font-semibold text-slate-600 truncate max-w-[140px]">{dim.name}</span>
                                            <span className="text-xs font-bold text-slate-800 bg-slate-100 px-2 py-0.5 rounded-full">{dim.score}/10</span>
                                        </div>
                                        <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                                            <div 
                                                className="h-full rounded-full transition-all duration-1000 ease-out"
                                                style={{ 
                                                    width: `${dim.score * 10}%`,
                                                    background: dim.score >= 8 
                                                        ? 'linear-gradient(90deg, #10b981, #059669)' 
                                                        : dim.score >= 6 
                                                            ? 'linear-gradient(90deg, #8b5cf6, #d946ef)' 
                                                            : 'linear-gradient(90deg, #f59e0b, #ef4444)'
                                                }}
                                            />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </section>

                {/* 2. FINAL ASSESSMENT - GATED */}
                {brand.final_assessment && (
                    <section className="print:mt-4">
                        {isAuthenticated ? (
                            <FinalAssessmentCard assessment={brand.final_assessment} />
                        ) : (
                            <LockedSection {...lockedSections.finalAssessment} onUnlock={handleRegister} />
                        )}
                    </section>
                )}

                {/* 2.5 PLAN B - Alternative Names - GATED */}
                {brand.alternative_names && isAuthenticated && (
                    <section className="print:mt-4">
                        <AlternativeNamesCard alternatives={brand.alternative_names} verdict={brand.verdict} />
                    </section>
                )}

                <Separator className="bg-slate-200/60 print:hidden" />

                {/* 3. STRATEGY & RADAR - GATED */}
                <section className="grid grid-cols-1 lg:grid-cols-12 gap-8 print:break-before-page">
                    <div className="lg:col-span-7 space-y-6 print:mb-6">
                        <div className="flex items-center gap-3 mb-2">
                            <div className="p-2 bg-emerald-100 rounded-lg print:hidden">
                                <LayoutDashboard className="w-5 h-5 text-emerald-600" />
                            </div>
                            <h3 className="text-2xl font-bold text-slate-900">Strategy Snapshot</h3>
                        </div>

                        {isAuthenticated ? (
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
                        ) : (
                            <LockedSection {...lockedSections.strategy} onUnlock={handleRegister} />
                        )}
                    </div>

                    <div className="lg:col-span-5 flex flex-col">
                        <div className="flex items-center gap-3 mb-8 print:mb-2">
                            <div className="p-2 bg-violet-100 rounded-lg print:hidden">
                                <Shield className="w-5 h-5 text-violet-600" />
                            </div>
                            <h3 className="text-2xl font-bold text-slate-900">Dimensions Analysis</h3>
                        </div>
                        
                        {isAuthenticated ? (
                            <Card className="bg-white border border-slate-200 shadow-sm rounded-2xl flex-grow flex flex-col items-center justify-center p-4 print:border-slate-300">
                                <div className="w-full text-center mb-4 hidden print:block">
                                    <h4 className="text-sm font-bold uppercase tracking-widest text-slate-500">Performance Radar</h4>
                                    <p className="text-xs text-slate-400">Scores across 6 key frameworks</p>
                                </div>
                                <BrandRadarChart data={brand.dimensions} />
                            </Card>
                        ) : (
                            <LockedSection {...lockedSections.dimensions} onUnlock={handleRegister} />
                        )}
                    </div>
                </section>

                {/* 4.6 DETAILED ANALYSIS - GATED */}
                {isAuthenticated && (
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
                                            {parseMarkdownBold(dim.reasoning)}
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    </section>
                )}

                {/* 4.7 DOMAIN & SOCIAL AVAILABILITY - GATED */}
                {(brand.multi_domain_availability || brand.social_availability) && (
                    <section className="print:break-inside-avoid">
                        <h3 className="text-xl font-bold text-slate-900 mb-6 flex items-center gap-2">
                            <Globe className="w-5 h-5 text-blue-500" /> Digital Presence Check
                        </h3>
                        {isAuthenticated ? (
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                {brand.multi_domain_availability && (
                                    <MultiDomainCard data={brand.multi_domain_availability} />
                                )}
                                {brand.social_availability && (
                                    <SocialAvailabilityCard data={brand.social_availability} />
                                )}
                            </div>
                        ) : (
                            <LockedSection {...lockedSections.domain} onUnlock={handleRegister} />
                        )}
                    </section>
                )}

                {/* 5. MARKET INTELLIGENCE - GATED */}
                <section className="print:break-before-page">
                    <h3 className="text-xl font-bold text-slate-900 mb-6 flex items-center gap-2">
                        <Globe className="w-5 h-5 text-slate-400" /> Market Intelligence
                    </h3>
                    {isAuthenticated ? (
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
                    ) : (
                        <LockedSection {...lockedSections.cultural} onUnlock={handleRegister} />
                    )}
                </section>

                {/* 5. COMPETITION & RISK - GATED */}
                {brand.competitor_analysis && (
                    <section className="print:break-inside-avoid">
                        <h3 className="text-xl font-bold text-slate-900 mb-6">Competitive Landscape</h3>
                        {isAuthenticated ? (
                            <CompetitionAnalysis data={brand.competitor_analysis} verdict={brand.verdict} />
                        ) : (
                            <LockedSection {...lockedSections.competitor} onUnlock={handleRegister} />
                        )}
                    </section>
                )}

                {brand.trademark_matrix && (
                    <section className="print:break-before-page">
                        <h3 className="text-xl font-bold text-slate-900 mb-6">Legal Risk Matrix</h3>
                        {isAuthenticated ? (
                            <TrademarkRiskTable 
                                matrix={brand.trademark_matrix} 
                                trademarkClasses={brand.trademark_classes} 
                            />
                        ) : (
                            <LockedSection {...lockedSections.trademark} onUnlock={handleRegister} />
                        )}
                    </section>
                )}

            </div>
        ))}

        {/* Bottom CTA for non-authenticated users */}
        {!isAuthenticated && (
            <div className="mt-16 text-center">
                <div className="inline-block p-8 bg-white rounded-2xl border-2 border-dashed border-violet-200 shadow-lg">
                    <Lock className="w-12 h-12 mx-auto mb-4 text-violet-400" />
                    <h3 className="text-2xl font-black text-slate-900 mb-2">Want the full picture?</h3>
                    <p className="text-slate-500 mb-6 max-w-md">
                        Register for free to unlock all sections including trademark analysis, competitor insights, and strategic recommendations.
                    </p>
                    <Button 
                        onClick={handleRegister}
                        size="lg"
                        className="bg-gradient-to-r from-violet-600 via-fuchsia-500 to-orange-500 hover:from-violet-700 hover:via-fuchsia-600 hover:to-orange-600 text-white font-bold shadow-xl shadow-violet-200 rounded-xl px-8"
                    >
                        <Sparkles className="w-5 h-5 mr-2" />
                        Unlock Full Report — Free
                    </Button>
                </div>
            </div>
        )}
      </main>
    </div>
  );
};

export default Dashboard;
