import React, { useState, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
    ArrowLeft, 
    Printer,
    Building2,
    Globe,
    BarChart3,
    Target,
    TrendingUp,
    Users,
    Shield,
    AlertTriangle,
    CheckCircle2,
    XCircle,
    Lightbulb,
    Clock,
    Calendar,
    Star,
    Zap
} from 'lucide-react';

// Logo URL
const LOGO_URL = "https://customer-assets.emergentagent.com/job_naming-hub/artifacts/vj8cw9xx_R.png";

// Verdict colors
const getVerdictColor = (verdict) => {
    switch (verdict?.toUpperCase()) {
        case 'STRONG': return 'bg-emerald-100 text-emerald-700 border-emerald-200';
        case 'MODERATE': return 'bg-amber-100 text-amber-700 border-amber-200';
        case 'WEAK': return 'bg-orange-100 text-orange-700 border-orange-200';
        case 'CRITICAL': return 'bg-red-100 text-red-700 border-red-200';
        default: return 'bg-slate-100 text-slate-700 border-slate-200';
    }
};

// Score color
const getScoreColor = (score) => {
    if (score >= 8) return 'text-emerald-600';
    if (score >= 6) return 'text-amber-600';
    if (score >= 4) return 'text-orange-600';
    return 'text-red-600';
};

// Dimension icons
const DIMENSION_ICONS = {
    'Heritage & Authenticity': '🏛️',
    'Customer Satisfaction': '⭐',
    'Market Positioning': '🎯',
    'Growth Trajectory': '📈',
    'Operational Excellence': '⚙️',
    'Brand Awareness': '📢',
    'Financial Viability': '💰',
    'Digital Presence': '🌐'
};

// Section Header Component
const SectionHeader = ({ icon: Icon, title, subtitle, color = "violet" }) => {
    const colorClasses = {
        violet: "bg-violet-100 text-violet-600",
        emerald: "bg-emerald-100 text-emerald-600",
        amber: "bg-amber-100 text-amber-600",
        red: "bg-red-100 text-red-600",
        blue: "bg-blue-100 text-blue-600"
    };
    
    return (
        <div className="flex items-center gap-3 mb-4">
            <div className={`p-2 rounded-xl ${colorClasses[color]}`}>
                <Icon className="w-5 h-5" />
            </div>
            <div>
                <h2 className="text-xl font-bold text-slate-900">{title}</h2>
                {subtitle && <p className="text-sm text-slate-500">{subtitle}</p>}
            </div>
        </div>
    );
};

// Card Component
const Card = ({ children, className = "" }) => (
    <div className={`bg-white rounded-2xl border border-slate-200 p-6 ${className}`}>
        {children}
    </div>
);

// Radar Chart (Simple CSS-based)
const RadarDisplay = ({ dimensions }) => {
    const avgScore = dimensions.length > 0 
        ? (dimensions.reduce((acc, d) => acc + (d.score || 0), 0) / dimensions.length).toFixed(1)
        : 0;
    
    return (
        <Card>
            <h3 className="font-bold text-slate-900 mb-4">8-Dimension Radar</h3>
            <div className="text-center mb-4">
                <div className="text-4xl font-black text-violet-600">{avgScore}</div>
                <div className="text-sm text-slate-500">Average Score</div>
            </div>
            <div className="space-y-3">
                {dimensions.map((dim, i) => (
                    <div key={i} className="flex items-center gap-3">
                        <span className="text-xl">{DIMENSION_ICONS[dim.name] || '📊'}</span>
                        <div className="flex-1">
                            <div className="flex justify-between mb-1">
                                <span className="text-xs font-medium text-slate-600">{dim.name}</span>
                                <span className={`text-xs font-bold ${getScoreColor(dim.score)}`}>{dim.score}/10</span>
                            </div>
                            <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                                <div 
                                    className={`h-full rounded-full ${dim.score >= 7 ? 'bg-emerald-500' : dim.score >= 5 ? 'bg-amber-500' : 'bg-red-500'}`}
                                    style={{ width: `${dim.score * 10}%` }}
                                />
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </Card>
    );
};

// SWOT Card
const SWOTCard = ({ type, items, icon: Icon, bgColor, textColor }) => (
    <div className={`${bgColor} rounded-xl p-4`}>
        <div className="flex items-center gap-2 mb-3">
            <Icon className={`w-5 h-5 ${textColor}`} />
            <h4 className={`font-bold ${textColor}`}>{type}</h4>
            <Badge variant="outline" className="text-xs">{items?.length || 0}</Badge>
        </div>
        <ul className="space-y-2">
            {items?.slice(0, 5).map((item, i) => (
                <li key={i} className="text-sm text-slate-700 flex items-start gap-2">
                    <span className="mt-1">•</span>
                    <span>{typeof item === 'string' ? item : item.point}</span>
                </li>
            ))}
        </ul>
    </div>
);

// Recommendation Card
const RecommendationCard = ({ rec, index, timeline }) => {
    const timelineColors = {
        'immediate': 'border-l-emerald-500',
        'medium': 'border-l-amber-500',
        'long': 'border-l-violet-500'
    };
    
    return (
        <div className={`bg-white border border-slate-200 rounded-xl p-4 border-l-4 ${timelineColors[timeline]}`}>
            <div className="flex items-start justify-between mb-2">
                <h4 className="font-bold text-slate-900">{rec.title}</h4>
                <Badge variant="outline" className="text-xs">{rec.priority || 'MEDIUM'}</Badge>
            </div>
            <p className="text-sm text-slate-600 mb-2">{rec.recommended_action}</p>
            {rec.expected_outcome && (
                <p className="text-xs text-slate-500">
                    <strong>Expected:</strong> {rec.expected_outcome}
                </p>
            )}
        </div>
    );
};

// Main Dashboard Component
const BrandAuditDashboard = () => {
    const location = useLocation();
    const navigate = useNavigate();
    const reportRef = useRef(null);
    
    const { data, query } = location.state || {};
    
    // Handle missing data
    if (!data) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-slate-50">
                <div className="text-center">
                    <h1 className="text-2xl font-bold text-slate-900 mb-4">No Audit Data</h1>
                    <p className="text-slate-600 mb-6">Please run a brand audit first.</p>
                    <Button onClick={() => navigate('/brand-audit')}>
                        Start Brand Audit
                    </Button>
                </div>
            </div>
        );
    }
    
    const currentDate = new Date().toLocaleDateString('en-US', { 
        year: 'numeric', month: 'long', day: 'numeric' 
    });
    
    const handlePrint = () => {
        window.print();
    };

    return (
        <>
            <Helmet>
                <title>{data.brand_name} Brand Audit | RIGHTNAME</title>
            </Helmet>
            
            <div className="min-h-screen bg-slate-50 text-slate-900 print:bg-white">
                {/* Print Styles */}
                <style>{`
                    @media print {
                        @page { size: A4 portrait; margin: 10mm; }
                        body { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
                        .no-print { display: none !important; }
                        .print-break { page-break-before: always; }
                    }
                `}</style>
                
                {/* Navbar */}
                <div className="bg-white border-b border-slate-200 px-6 py-4 flex justify-between items-center no-print sticky top-0 z-50">
                    <div className="flex items-center gap-4">
                        <Button variant="ghost" size="icon" onClick={() => navigate('/brand-audit')} className="rounded-full">
                            <ArrowLeft className="h-5 w-5" />
                        </Button>
                        <img src={LOGO_URL} alt="RIGHTNAME" className="h-8" />
                        <Badge variant="outline" className="text-violet-600 border-violet-200">Brand Audit</Badge>
                    </div>
                    <div className="flex items-center gap-3">
                        <Button onClick={handlePrint} className="gap-2 bg-violet-600 hover:bg-violet-700 text-white rounded-xl">
                            <Printer className="h-4 w-4" /> Print / Save PDF
                        </Button>
                    </div>
                </div>
                
                {/* Main Content */}
                <main ref={reportRef} className="max-w-6xl mx-auto px-6 py-8 space-y-8 print:px-2 print:py-4">
                    
                    {/* Hero Section */}
                    <section>
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                            {/* Brand Overview */}
                            <div className="lg:col-span-2">
                                <Card>
                                    <div className="flex items-center gap-4 mb-4">
                                        <div className="p-3 bg-violet-100 rounded-xl">
                                            <Building2 className="w-8 h-8 text-violet-600" />
                                        </div>
                                        <div>
                                            <h1 className="text-4xl font-black text-slate-900">{data.brand_name}</h1>
                                            <p className="text-slate-500">{data.brand_website}</p>
                                        </div>
                                    </div>
                                    <div className="flex flex-wrap gap-2 mb-4">
                                        <Badge className={getVerdictColor(data.verdict)}>{data.verdict}</Badge>
                                        <Badge variant="outline">{data.category}</Badge>
                                        <Badge variant="outline">{data.geography}</Badge>
                                    </div>
                                    <div className="flex items-center gap-2 mb-3">
                                        <Star className="w-4 h-4 text-amber-500" />
                                        <span className="text-xs font-bold uppercase tracking-widest text-amber-600">Executive Summary</span>
                                    </div>
                                    <p className="text-slate-700 leading-relaxed">{data.executive_summary}</p>
                                </Card>
                            </div>
                            
                            {/* Score Card */}
                            <div>
                                <Card className="text-center">
                                    <h3 className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-2">Brand Health Score</h3>
                                    <div className={`text-6xl font-black ${data.overall_score >= 70 ? 'text-emerald-600' : data.overall_score >= 50 ? 'text-amber-600' : 'text-red-600'}`}>
                                        {data.overall_score || 0}
                                    </div>
                                    <div className="text-slate-500 mb-4">out of 100</div>
                                    <div className={`inline-flex items-center px-4 py-2 rounded-full font-bold ${getVerdictColor(data.verdict)}`}>
                                        {data.verdict}
                                    </div>
                                </Card>
                            </div>
                        </div>
                    </section>
                    
                    {/* 8-Dimension Analysis */}
                    <section>
                        <SectionHeader icon={BarChart3} title="8-Dimension Brand Analysis" subtitle="Comprehensive scoring breakdown" color="violet" />
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <RadarDisplay dimensions={data.dimensions || []} />
                            <Card>
                                <h3 className="font-bold text-slate-900 mb-4">Dimension Details</h3>
                                <div className="space-y-4">
                                    {data.dimensions?.map((dim, i) => (
                                        <div key={i} className="border-b border-slate-100 pb-3 last:border-0">
                                            <div className="flex justify-between items-center mb-1">
                                                <span className="font-semibold text-slate-800">{DIMENSION_ICONS[dim.name]} {dim.name}</span>
                                                <span className={`font-bold ${getScoreColor(dim.score)}`}>{dim.score}/10</span>
                                            </div>
                                            <p className="text-xs text-slate-600">{dim.reasoning}</p>
                                            <Badge variant="outline" className="text-xs mt-1">{dim.confidence} confidence</Badge>
                                        </div>
                                    ))}
                                </div>
                            </Card>
                        </div>
                    </section>
                    
                    {/* SWOT Analysis */}
                    <section className="print-break">
                        <SectionHeader icon={Target} title="SWOT Analysis" subtitle="Strategic assessment" color="amber" />
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <SWOTCard 
                                type="Strengths" 
                                items={data.swot?.strengths} 
                                icon={CheckCircle2} 
                                bgColor="bg-emerald-50" 
                                textColor="text-emerald-700" 
                            />
                            <SWOTCard 
                                type="Weaknesses" 
                                items={data.swot?.weaknesses} 
                                icon={XCircle} 
                                bgColor="bg-red-50" 
                                textColor="text-red-700" 
                            />
                            <SWOTCard 
                                type="Opportunities" 
                                items={data.swot?.opportunities} 
                                icon={Lightbulb} 
                                bgColor="bg-amber-50" 
                                textColor="text-amber-700" 
                            />
                            <SWOTCard 
                                type="Threats" 
                                items={data.swot?.threats} 
                                icon={AlertTriangle} 
                                bgColor="bg-slate-100" 
                                textColor="text-slate-700" 
                            />
                        </div>
                    </section>
                    
                    {/* Competitive Analysis */}
                    {data.competitors?.length > 0 && (
                        <section>
                            <SectionHeader icon={Users} title="Competitive Landscape" subtitle="Competitor comparison" color="blue" />
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                {data.competitors.map((comp, i) => (
                                    <Card key={i}>
                                        <h4 className="font-bold text-slate-900 mb-2">{comp.name}</h4>
                                        <p className="text-sm text-slate-500 mb-3">{comp.website}</p>
                                        <div className="space-y-2 text-sm">
                                            {comp.founded && <div><strong>Founded:</strong> {comp.founded}</div>}
                                            {comp.outlets && <div><strong>Outlets:</strong> {comp.outlets}</div>}
                                            {comp.rating && <div><strong>Rating:</strong> ⭐ {comp.rating}</div>}
                                            {comp.social_followers && <div><strong>Social:</strong> {comp.social_followers}</div>}
                                        </div>
                                        {comp.key_strength && (
                                            <div className="mt-3 pt-3 border-t border-slate-100">
                                                <p className="text-xs text-emerald-600"><strong>Strength:</strong> {comp.key_strength}</p>
                                                {comp.key_weakness && (
                                                    <p className="text-xs text-red-600 mt-1"><strong>Weakness:</strong> {comp.key_weakness}</p>
                                                )}
                                            </div>
                                        )}
                                    </Card>
                                ))}
                            </div>
                        </section>
                    )}
                    
                    {/* Strategic Recommendations */}
                    <section className="print-break">
                        <SectionHeader icon={Zap} title="Strategic Recommendations" subtitle="Actionable roadmap" color="emerald" />
                        
                        {/* Immediate (0-6 months) */}
                        {data.immediate_recommendations?.length > 0 && (
                            <div className="mb-6">
                                <div className="flex items-center gap-2 mb-3">
                                    <Clock className="w-4 h-4 text-emerald-600" />
                                    <h3 className="font-bold text-slate-800">Immediate (0-6 months)</h3>
                                </div>
                                <div className="space-y-3">
                                    {data.immediate_recommendations.map((rec, i) => (
                                        <RecommendationCard key={i} rec={rec} index={i} timeline="immediate" />
                                    ))}
                                </div>
                            </div>
                        )}
                        
                        {/* Medium-term (6-18 months) */}
                        {data.medium_term_recommendations?.length > 0 && (
                            <div className="mb-6">
                                <div className="flex items-center gap-2 mb-3">
                                    <Calendar className="w-4 h-4 text-amber-600" />
                                    <h3 className="font-bold text-slate-800">Medium-Term (6-18 months)</h3>
                                </div>
                                <div className="space-y-3">
                                    {data.medium_term_recommendations.map((rec, i) => (
                                        <RecommendationCard key={i} rec={rec} index={i} timeline="medium" />
                                    ))}
                                </div>
                            </div>
                        )}
                        
                        {/* Long-term (18-36 months) */}
                        {data.long_term_recommendations?.length > 0 && (
                            <div className="mb-6">
                                <div className="flex items-center gap-2 mb-3">
                                    <TrendingUp className="w-4 h-4 text-violet-600" />
                                    <h3 className="font-bold text-slate-800">Long-Term (18-36 months)</h3>
                                </div>
                                <div className="space-y-3">
                                    {data.long_term_recommendations.map((rec, i) => (
                                        <RecommendationCard key={i} rec={rec} index={i} timeline="long" />
                                    ))}
                                </div>
                            </div>
                        )}
                    </section>
                    
                    {/* Market Data */}
                    {data.market_data && (
                        <section>
                            <SectionHeader icon={TrendingUp} title="Market Intelligence" subtitle="Industry context" color="amber" />
                            <Card>
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                    {data.market_data.market_size && (
                                        <div className="text-center p-4 bg-slate-50 rounded-xl">
                                            <div className="text-2xl font-bold text-slate-900">{data.market_data.market_size}</div>
                                            <div className="text-xs text-slate-500">Market Size</div>
                                        </div>
                                    )}
                                    {data.market_data.cagr && (
                                        <div className="text-center p-4 bg-emerald-50 rounded-xl">
                                            <div className="text-2xl font-bold text-emerald-600">{data.market_data.cagr}</div>
                                            <div className="text-xs text-slate-500">CAGR</div>
                                        </div>
                                    )}
                                </div>
                                {data.market_data.growth_drivers?.length > 0 && (
                                    <div className="mt-4">
                                        <h4 className="font-semibold text-slate-800 mb-2">Growth Drivers</h4>
                                        <div className="flex flex-wrap gap-2">
                                            {data.market_data.growth_drivers.map((driver, i) => (
                                                <Badge key={i} variant="outline">{driver}</Badge>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </Card>
                        </section>
                    )}
                    
                    {/* Research Sources */}
                    {data.search_queries?.length > 0 && (
                        <section className="print-break">
                            <SectionHeader icon={Shield} title="Research Methodology" subtitle="Transparency report" color="violet" />
                            <Card>
                                <h4 className="font-semibold text-slate-800 mb-3">Search Queries Executed ({data.search_queries.length})</h4>
                                <div className="space-y-2">
                                    {data.search_queries.map((query, i) => (
                                        <div key={i} className="text-sm text-slate-600 p-2 bg-slate-50 rounded">
                                            <span className="font-mono text-violet-600">[{i + 1}]</span> {query}
                                        </div>
                                    ))}
                                </div>
                                <div className="mt-4 pt-4 border-t border-slate-200">
                                    <Badge variant="outline">Data Confidence: {data.data_confidence || 'MEDIUM'}</Badge>
                                    <Badge variant="outline" className="ml-2">Processing: {data.processing_time_seconds?.toFixed(1)}s</Badge>
                                </div>
                            </Card>
                        </section>
                    )}
                    
                    {/* Footer */}
                    <footer className="text-center py-8 border-t border-slate-200">
                        <p className="text-sm text-slate-500">
                            Generated by RIGHTNAME Brand Audit • {currentDate} • rightname.ai
                        </p>
                        <p className="text-xs text-slate-400 mt-1">
                            Report ID: {data.report_id}
                        </p>
                    </footer>
                </main>
            </div>
        </>
    );
};

export default BrandAuditDashboard;
