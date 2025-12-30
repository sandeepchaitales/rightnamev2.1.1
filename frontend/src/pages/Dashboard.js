import React, { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { 
    Printer, ArrowLeft, CheckCircle2, XCircle, Star, Shield, Globe, 
    Lock, Sparkles, TrendingUp, AlertTriangle, Users, Zap, 
    BarChart3, Target, Award, FileText, Calendar, Lightbulb,
    Rocket, MessageSquare, Scale, Building2, Hash, AtSign,
    CheckCircle, XOctagon, HelpCircle, Map, Briefcase, UserCheck, AlertCircle,
    Download, Loader2
} from "lucide-react";
import { 
    RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, 
    ResponsiveContainer, Tooltip 
} from 'recharts';
import html2pdf from 'html2pdf.js';

// RIGHTNAME Logo URL
const LOGO_URL = "https://customer-assets.emergentagent.com/job_name-radar-1/artifacts/qrfrrizq_R.png";

// Get country name (handles both string and object formats)
const getCountryName = (country) => {
    return typeof country === 'object' ? country?.name : country;
};

// Format countries for display (names only, no flags)
const formatCountriesWithFlags = (countries) => {
    if (!countries || countries.length === 0) return 'Not specified';
    return countries.map(c => getCountryName(c)).join(', ');
};

// ============ PRINT-SAFE CARD WRAPPER ============
const PrintCard = ({ children, className = "" }) => (
    <div className={`print-card break-inside-avoid pdf-no-break ${className}`}>
        {children}
    </div>
);

// ============ SECTION HEADER ============
const SectionHeader = ({ icon: Icon, title, subtitle, color = "violet", badge }) => {
    const colors = {
        violet: "text-violet-600 bg-violet-100",
        emerald: "text-emerald-600 bg-emerald-100",
        fuchsia: "text-fuchsia-600 bg-fuchsia-100",
        amber: "text-amber-600 bg-amber-100",
        blue: "text-blue-600 bg-blue-100",
        red: "text-red-600 bg-red-100",
        cyan: "text-cyan-600 bg-cyan-100",
    };
    
    return (
        <div className="flex items-center justify-between mb-6 print:mb-4">
            <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-xl ${colors[color]} flex items-center justify-center print:w-8 print:h-8`}>
                    <Icon className={`w-5 h-5 ${colors[color].split(' ')[0]} print:w-4 print:h-4`} />
                </div>
                <div>
                    <h2 className="text-xl font-black text-slate-900 print:text-lg">{title}</h2>
                    {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
                </div>
            </div>
            {badge && <Badge variant="outline" className="text-slate-500">{badge}</Badge>}
        </div>
    );
};

// ============ SUB-SECTION HEADER ============
const SubSectionHeader = ({ icon: Icon, title, color = "slate" }) => (
    <div className="flex items-center gap-2 mb-3">
        {Icon && <Icon className={`w-4 h-4 text-${color}-500`} />}
        <h4 className="text-xs font-bold uppercase tracking-widest text-slate-600">{title}</h4>
    </div>
);

// ============ COVER PAGE ============
const CoverPage = ({ brandName, score, verdict, date, query, reportId, forPdf = false }) => {
    // For PDF: always visible. For screen: hidden (only show in print)
    const baseClass = forPdf 
        ? "flex flex-col min-h-[297mm] items-center justify-center bg-white p-8 pdf-cover-page"
        : "hidden print:flex print:flex-col print:min-h-screen print:items-center print:justify-center print:bg-white print:p-8";
    
    return (
        <div className={baseClass} style={forPdf ? { pageBreakAfter: 'always' } : {}}>
            {/* Logo - Decent Size */}
            <div className="mb-6">
                <img src={LOGO_URL} alt="RIGHTNAME" className="h-20 mx-auto" crossOrigin="anonymous" />
            </div>
            
            {/* Brand Name - Large and Bold */}
            <h1 className="text-6xl font-black text-slate-900 mb-4 text-center">{brandName}</h1>
            
            {/* Score Badge */}
            <div className="mb-6">
                <div className={`inline-flex items-center gap-3 px-8 py-4 rounded-full text-2xl font-black ${
                    verdict === 'GO' ? 'bg-emerald-100 text-emerald-700' :
                    verdict === 'CONDITIONAL GO' ? 'bg-amber-100 text-amber-700' :
                    'bg-red-100 text-red-700'
                }`}>
                    {score}/100 • {verdict}
                </div>
            </div>
            
            {/* Industry & Countries */}
            <div className="text-slate-600 space-y-2 text-center mb-4">
                <p className="text-lg font-semibold">
                    {query?.category} • {formatCountriesWithFlags(query?.countries)}
                </p>
                <p className="flex items-center justify-center gap-2 text-slate-500">
                    <Calendar className="w-4 h-4" />{date}
                </p>
            </div>
            
            {/* Gradient Line */}
            <div className="w-40 h-1 bg-gradient-to-r from-violet-500 via-fuchsia-500 to-orange-500 mx-auto my-6 rounded-full"></div>
            
            {/* Report Title */}
            <p className="text-sm text-slate-500 uppercase tracking-[0.3em] font-semibold mb-2">Brand Name Analysis Report</p>
            {reportId && <p className="text-xs text-slate-400 mb-8">Report ID: {reportId}</p>}
            
            {/* Input Summary Table on Cover Page */}
            <div className="w-full max-w-lg mt-4">
                <div className="border border-slate-200 rounded-xl overflow-hidden shadow-sm">
                    <div className="bg-slate-800 px-4 py-3 text-center">
                        <h3 className="text-sm font-bold text-white uppercase tracking-wider">Evaluation Request Summary</h3>
                    </div>
                    <table className="w-full text-sm bg-white">
                        <tbody>
                            <tr className="border-b border-slate-100">
                                <td className="px-4 py-3 text-slate-500 font-medium">Brand Name</td>
                                <td className="px-4 py-3 text-slate-900 font-bold text-right">{brandName}</td>
                            </tr>
                            {query?.industry && (
                                <tr className="border-b border-slate-100">
                                    <td className="px-4 py-3 text-slate-500 font-medium">Industry</td>
                                    <td className="px-4 py-3 text-slate-900 font-semibold text-right">{query.industry}</td>
                                </tr>
                            )}
                            <tr className="border-b border-slate-100">
                                <td className="px-4 py-3 text-slate-500 font-medium">Category</td>
                                <td className="px-4 py-3 text-slate-900 font-semibold text-right">{query?.category || 'N/A'}</td>
                            </tr>
                            {query?.product_type && (
                                <tr className="border-b border-slate-100">
                                    <td className="px-4 py-3 text-slate-500 font-medium">Product Type</td>
                                    <td className="px-4 py-3 text-slate-900 font-semibold text-right">{query.product_type}</td>
                                </tr>
                            )}
                            <tr className="border-b border-slate-100">
                                <td className="px-4 py-3 text-slate-500 font-medium">Positioning</td>
                                <td className="px-4 py-3 text-slate-900 font-semibold text-right">{query?.positioning || 'N/A'}</td>
                            </tr>
                            <tr className="border-b border-slate-100">
                                <td className="px-4 py-3 text-slate-500 font-medium">Market Scope</td>
                                <td className="px-4 py-3 text-slate-900 font-semibold text-right">{query?.market_scope || 'N/A'}</td>
                            </tr>
                            <tr>
                                <td className="px-4 py-3 text-slate-500 font-medium">Target Countries</td>
                                <td className="px-4 py-3 text-slate-900 font-semibold text-right">
                                    {formatCountriesWithFlags(query?.countries)}
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
            
            {/* Footer */}
            <div className="mt-auto pt-8 text-center">
                <p className="text-xs text-slate-400">https://rightname.ai</p>
            </div>
        </div>
    );
};

// ============ INPUT SUMMARY SECTION (For Screen View) ============
const InputSummarySection = ({ query, brandName, reportId, date }) => {
    return (
        <PrintCard>
            <div className="bg-gradient-to-br from-slate-50 to-slate-100 rounded-2xl border border-slate-200 overflow-hidden">
                <div className="bg-slate-800 px-6 py-3 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-slate-300" />
                        <h3 className="text-sm font-bold text-white uppercase tracking-wider">Evaluation Request Summary</h3>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-slate-400">
                        <span className="flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            {date}
                        </span>
                        {reportId && (
                            <span className="flex items-center gap-1">
                                <Hash className="w-3 h-3" />
                                {reportId}
                            </span>
                        )}
                    </div>
                </div>
                <div className="p-6 print:p-4">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 print:grid-cols-4">
                        <div className="space-y-1">
                            <p className="text-xs text-slate-500 uppercase tracking-wide font-medium">Brand Name</p>
                            <p className="text-sm font-bold text-slate-900">{brandName}</p>
                        </div>
                        {query?.industry && (
                            <div className="space-y-1">
                                <p className="text-xs text-slate-500 uppercase tracking-wide font-medium">Industry</p>
                                <p className="text-sm font-semibold text-slate-800">{query.industry}</p>
                            </div>
                        )}
                        <div className="space-y-1">
                            <p className="text-xs text-slate-500 uppercase tracking-wide font-medium">Category</p>
                            <p className="text-sm font-semibold text-slate-800">{query?.category || 'N/A'}</p>
                        </div>
                        {query?.product_type && (
                            <div className="space-y-1">
                                <p className="text-xs text-slate-500 uppercase tracking-wide font-medium">Product Type</p>
                                <p className="text-sm font-semibold text-slate-800">{query.product_type}</p>
                            </div>
                        )}
                        <div className="space-y-1">
                            <p className="text-xs text-slate-500 uppercase tracking-wide font-medium">Positioning</p>
                            <p className="text-sm font-semibold text-slate-800">{query?.positioning || 'N/A'}</p>
                        </div>
                        <div className="space-y-1">
                            <p className="text-xs text-slate-500 uppercase tracking-wide font-medium">Market Scope</p>
                            <p className="text-sm font-semibold text-slate-800">{query?.market_scope || 'N/A'}</p>
                        </div>
                        <div className="space-y-1 col-span-2">
                            <p className="text-xs text-slate-500 uppercase tracking-wide font-medium">Target Countries</p>
                            <p className="text-sm font-semibold text-slate-800">
                                {formatCountriesWithFlags(query?.countries)}
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </PrintCard>
    );
};

// ============ SCORE CARD ============
const ScoreCardRevamped = ({ score, verdict }) => {
    const getStyle = () => {
        switch(verdict) {
            case 'GO': return 'from-emerald-400 to-teal-500 text-emerald-700 bg-emerald-50 border-emerald-200';
            case 'CONDITIONAL GO': return 'from-amber-400 to-orange-500 text-amber-700 bg-amber-50 border-amber-200';
            default: return 'from-red-400 to-rose-500 text-red-700 bg-red-50 border-red-200';
        }
    };
    const style = getStyle();
    
    return (
        <PrintCard>
            <div className={`rounded-2xl p-6 border-2 ${style.split(' ').slice(2).join(' ')} print:p-4`}>
                <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold uppercase tracking-widest opacity-70">RIGHTNAME™ INDEX</span>
                    <Award className="w-5 h-5 opacity-50" />
                </div>
                <div className="text-center py-4 print:py-2">
                    <div className="text-6xl font-black print:text-5xl">{score}</div>
                    <div className="text-xl text-slate-400 font-bold">/100</div>
                </div>
                <div className={`text-center py-2 px-4 rounded-xl bg-gradient-to-r ${style.split(' ').slice(0, 2).join(' ')} text-white font-bold text-lg`}>
                    {verdict}
                </div>
            </div>
        </PrintCard>
    );
};

// ============ PERFORMANCE RADAR CHART ============
const PerformanceRadar = ({ dimensions, brandName }) => {
    if (!dimensions || dimensions.length === 0) return null;
    
    // Transform dimensions data for Recharts radar
    const radarData = dimensions.slice(0, 8).map(dim => ({
        dimension: dim.name?.length > 12 ? dim.name.substring(0, 12) + '...' : dim.name,
        fullName: dim.name,
        score: dim.score || 0,
        fullMark: 10
    }));
    
    return (
        <PrintCard>
            <div className="bg-white rounded-2xl p-6 border border-slate-200 print:p-4">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg bg-fuchsia-100 flex items-center justify-center">
                            <Target className="w-4 h-4 text-fuchsia-600" />
                        </div>
                        <div>
                            <h3 className="text-sm font-bold text-slate-800">Performance Radar</h3>
                            <p className="text-xs text-slate-500">Dimension Analysis</p>
                        </div>
                    </div>
                </div>
                <div className="h-64 print:h-56">
                    <ResponsiveContainer width="100%" height="100%">
                        <RadarChart cx="50%" cy="50%" outerRadius="70%" data={radarData}>
                            <PolarGrid 
                                stroke="#e2e8f0" 
                                strokeDasharray="3 3"
                            />
                            <PolarAngleAxis 
                                dataKey="dimension" 
                                tick={{ 
                                    fill: '#64748b', 
                                    fontSize: 10,
                                    fontWeight: 500
                                }}
                                tickLine={false}
                            />
                            <PolarRadiusAxis 
                                angle={90} 
                                domain={[0, 10]} 
                                tick={{ fill: '#94a3b8', fontSize: 9 }}
                                tickCount={6}
                                axisLine={false}
                            />
                            <Radar
                                name={brandName || "Score"}
                                dataKey="score"
                                stroke="#a855f7"
                                fill="#a855f7"
                                fillOpacity={0.3}
                                strokeWidth={2}
                                dot={{ 
                                    fill: '#a855f7', 
                                    strokeWidth: 0,
                                    r: 4
                                }}
                                activeDot={{
                                    fill: '#7c3aed',
                                    strokeWidth: 0,
                                    r: 6
                                }}
                            />
                            <Tooltip 
                                content={({ active, payload }) => {
                                    if (active && payload && payload.length) {
                                        const data = payload[0].payload;
                                        return (
                                            <div className="bg-slate-900 text-white px-3 py-2 rounded-lg shadow-lg text-xs">
                                                <p className="font-bold">{data.fullName}</p>
                                                <p className="text-fuchsia-300">Score: {data.score}/10</p>
                                            </div>
                                        );
                                    }
                                    return null;
                                }}
                            />
                        </RadarChart>
                    </ResponsiveContainer>
                </div>
                <div className="mt-2 text-center">
                    <p className="text-xs text-slate-400">Hover/tap points for details</p>
                </div>
            </div>
        </PrintCard>
    );
};

// ============ QUICK DIMENSIONS GRID ============
const QuickDimensionsGrid = ({ dimensions }) => (
    <PrintCard>
        <div className="bg-white rounded-2xl p-6 border border-slate-200 print:p-4">
            <SubSectionHeader icon={BarChart3} title="Quick Dimensions" />
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 print:gap-3">
                {dimensions?.slice(0, 6).map((dim, i) => (
                    <div key={i} className="p-3 bg-slate-50 rounded-xl">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-semibold text-slate-600 truncate max-w-[100px]">{dim.name}</span>
                            <span className="text-sm font-black text-slate-800">{dim.score}/10</span>
                        </div>
                        <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                            <div 
                                className={`h-full rounded-full ${dim.score >= 8 ? 'bg-emerald-500' : dim.score >= 6 ? 'bg-violet-500' : 'bg-amber-500'}`}
                                style={{ width: `${dim.score * 10}%` }}
                            />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    </PrintCard>
);

// ============ FINAL ASSESSMENT (FULL) ============
const FinalAssessmentFull = ({ assessment, verdict, score }) => {
    if (!assessment) return null;
    
    return (
        <div className="space-y-4">
            {/* Verdict Banner */}
            <PrintCard>
                <div className={`rounded-2xl p-6 text-white ${
                    verdict === 'GO' ? 'bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500' :
                    verdict === 'CONDITIONAL GO' ? 'bg-gradient-to-r from-amber-500 via-orange-500 to-yellow-500' :
                    'bg-gradient-to-r from-red-500 via-rose-500 to-pink-500'
                }`}>
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <div className="w-14 h-14 bg-white/20 rounded-2xl flex items-center justify-center">
                                <Zap className="w-7 h-7" />
                            </div>
                            <div>
                                <p className="text-sm uppercase tracking-widest opacity-80">Consultant Verdict</p>
                                <h2 className="text-3xl font-black">{verdict}</h2>
                            </div>
                        </div>
                        <div className="text-right">
                            <p className="text-xs opacity-80">Suitability Score</p>
                            <p className="text-3xl font-black">{assessment.suitability_score || (score/10).toFixed(1)}/10</p>
                        </div>
                    </div>
                    {(assessment.bottom_line || assessment.verdict_statement) && (
                        <p className="mt-4 text-white/90 border-t border-white/20 pt-4 text-sm">
                            "{assessment.bottom_line || assessment.verdict_statement}"
                        </p>
                    )}
                </div>
            </PrintCard>

            {/* Strategic Roadmap - Handle both old and new data structures */}
            {(assessment.recommendations?.length > 0 || assessment.ip_strategy || assessment.brand_narrative || assessment.launch_tactics) && (
                <PrintCard>
                    <div className="bg-white rounded-2xl p-6 border border-slate-200">
                        <SubSectionHeader icon={Map} title="Strategic Roadmap" color="violet" />
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            {/* New structure: recommendations array */}
                            {assessment.recommendations?.map((rec, i) => {
                                const colors = [
                                    { bg: 'bg-violet-50', border: 'border-violet-200', text: 'text-violet-800', icon: 'text-violet-600' },
                                    { bg: 'bg-fuchsia-50', border: 'border-fuchsia-200', text: 'text-fuchsia-800', icon: 'text-fuchsia-600' },
                                    { bg: 'bg-orange-50', border: 'border-orange-200', text: 'text-orange-800', icon: 'text-orange-600' },
                                ];
                                const icons = [Shield, MessageSquare, Rocket];
                                const color = colors[i % colors.length];
                                const Icon = icons[i % icons.length];
                                return (
                                    <div key={i} className={`${color.bg} rounded-xl p-4 border ${color.border}`}>
                                        <div className="flex items-center gap-2 mb-2">
                                            <Icon className={`w-4 h-4 ${color.icon}`} />
                                            <h5 className={`font-bold ${color.text} text-sm`}>{rec.title}</h5>
                                        </div>
                                        <p className="text-xs text-slate-600 leading-relaxed">{rec.content}</p>
                                    </div>
                                );
                            })}
                            {/* Old structure fallback */}
                            {!assessment.recommendations && assessment.ip_strategy && (
                                <div className="bg-violet-50 rounded-xl p-4 border border-violet-200">
                                    <div className="flex items-center gap-2 mb-2">
                                        <Shield className="w-4 h-4 text-violet-600" />
                                        <h5 className="font-bold text-violet-800 text-sm">IP Strategy</h5>
                                    </div>
                                    <p className="text-xs text-slate-600">{assessment.ip_strategy}</p>
                                </div>
                            )}
                            {!assessment.recommendations && assessment.brand_narrative && (
                                <div className="bg-fuchsia-50 rounded-xl p-4 border border-fuchsia-200">
                                    <div className="flex items-center gap-2 mb-2">
                                        <MessageSquare className="w-4 h-4 text-fuchsia-600" />
                                        <h5 className="font-bold text-fuchsia-800 text-sm">Brand Narrative</h5>
                                    </div>
                                    <p className="text-xs text-slate-600">{assessment.brand_narrative}</p>
                                </div>
                            )}
                            {!assessment.recommendations && assessment.launch_tactics && (
                                <div className="bg-orange-50 rounded-xl p-4 border border-orange-200">
                                    <div className="flex items-center gap-2 mb-2">
                                        <Rocket className="w-4 h-4 text-orange-600" />
                                        <h5 className="font-bold text-orange-800 text-sm">Launch Tactics</h5>
                                    </div>
                                    <p className="text-xs text-slate-600">{assessment.launch_tactics}</p>
                                </div>
                            )}
                        </div>
                        {(assessment.contingency_note || assessment.alternative_path) && (
                            <div className="mt-4 p-3 bg-slate-50 rounded-lg border border-slate-200">
                                <p className="text-xs text-slate-600 italic">💡 {assessment.contingency_note || assessment.alternative_path}</p>
                            </div>
                        )}
                    </div>
                </PrintCard>
            )}

            {/* Recommended Next Steps */}
            {assessment.recommended_next_steps && assessment.recommended_next_steps.length > 0 && (
                <PrintCard>
                    <div className="bg-white rounded-2xl p-6 border border-slate-200">
                        <SubSectionHeader icon={FileText} title="Recommended Next Steps" color="blue" />
                        <div className="space-y-2">
                            {assessment.recommended_next_steps.map((step, i) => (
                                <div key={i} className="flex items-start gap-3 p-3 bg-blue-50 rounded-lg">
                                    <span className="w-6 h-6 bg-blue-500 text-white rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0">{i + 1}</span>
                                    <p className="text-sm text-slate-700">{step}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                </PrintCard>
            )}
        </div>
    );
};

// ============ STRATEGY SNAPSHOT ============
const StrategySnapshot = ({ classification, pros, cons }) => (
    <div className="space-y-4">
        {classification && (
            <PrintCard>
                <div className="bg-violet-50 border border-violet-200 rounded-xl p-4">
                    <p className="text-lg font-bold text-violet-900 italic text-center">"{classification}"</p>
                </div>
            </PrintCard>
        )}
        <PrintCard>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-gradient-to-br from-emerald-50 to-white border border-emerald-200 rounded-xl p-5">
                    <div className="flex items-center gap-2 mb-4">
                        <div className="w-8 h-8 bg-emerald-100 rounded-lg flex items-center justify-center">
                            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                        </div>
                        <h4 className="font-bold text-emerald-700">KEY STRENGTHS</h4>
                    </div>
                    <ul className="space-y-2">
                        {pros?.map((pro, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                                <span className="text-emerald-500 mt-0.5">✓</span>
                                {pro}
                            </li>
                        ))}
                    </ul>
                </div>
                <div className="bg-gradient-to-br from-amber-50 to-white border border-amber-200 rounded-xl p-5">
                    <div className="flex items-center gap-2 mb-4">
                        <div className="w-8 h-8 bg-amber-100 rounded-lg flex items-center justify-center">
                            <AlertTriangle className="w-4 h-4 text-amber-600" />
                        </div>
                        <h4 className="font-bold text-amber-700">KEY RISKS</h4>
                    </div>
                    <ul className="space-y-2">
                        {cons?.map((con, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                                <span className="text-amber-500 mt-0.5">!</span>
                                {con}
                            </li>
                        ))}
                    </ul>
                </div>
            </div>
        </PrintCard>
    </div>
);

// ============ DETAILED DIMENSION CARD ============
const DetailedDimensionCard = ({ dimension, index }) => {
    const icons = ['✨', '🌍', '💎', '📈', '⚖️', '🎯', '🔮', '🎨'];
    const getScoreColor = (score) => {
        if (score >= 8) return 'from-emerald-400 to-emerald-500 bg-emerald-100 text-emerald-700';
        if (score >= 6) return 'from-violet-400 to-fuchsia-500 bg-violet-100 text-violet-700';
        return 'from-amber-400 to-orange-500 bg-amber-100 text-amber-700';
    };
    const colors = getScoreColor(dimension.score);
    
    // Parse sub-sections from reasoning if available
    const parseReasoning = (text) => {
        if (!text) return { main: '', sections: [] };
        const sections = [];
        const patterns = [
            /\*\*([^*]+)\*\*:?\s*([^*]+?)(?=\*\*|$)/g,
            /([A-Z][a-z]+ [A-Z][a-z]+):\s*([^.]+\.)/g
        ];
        
        let main = text;
        patterns.forEach(pattern => {
            let match;
            while ((match = pattern.exec(text)) !== null) {
                sections.push({ title: match[1].trim(), content: match[2].trim() });
            }
        });
        
        return { main: sections.length > 0 ? '' : text, sections };
    };
    
    const parsed = parseReasoning(dimension.reasoning);
    
    return (
        <PrintCard>
            <div className="bg-white border border-slate-200 rounded-xl overflow-hidden hover:shadow-lg transition-shadow">
                <div className={`px-5 py-4 ${colors.split(' ').slice(2, 4).join(' ')} border-b`}>
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <span className="text-xl">{icons[index % icons.length]}</span>
                            <h4 className="font-bold text-slate-800">{dimension.name}</h4>
                        </div>
                        <div className={`px-3 py-1 rounded-full bg-gradient-to-r ${colors.split(' ').slice(0, 2).join(' ')} text-white text-sm font-bold`}>
                            {dimension.score}/10
                        </div>
                    </div>
                </div>
                <div className="p-5">
                    {/* Progress bar */}
                    <div className="h-2 bg-slate-100 rounded-full overflow-hidden mb-4">
                        <div className={`h-full rounded-full bg-gradient-to-r ${colors.split(' ').slice(0, 2).join(' ')}`} style={{ width: `${dimension.score * 10}%` }} />
                    </div>
                    
                    {/* Sub-sections or main text */}
                    {parsed.sections.length > 0 ? (
                        <div className="space-y-3">
                            {parsed.sections.map((sec, i) => (
                                <div key={i} className="p-3 bg-slate-50 rounded-lg">
                                    <h5 className="text-xs font-bold text-slate-700 uppercase mb-1">{sec.title}</h5>
                                    <p className="text-xs text-slate-600">{sec.content}</p>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="text-sm text-slate-600 leading-relaxed">{dimension.reasoning}</p>
                    )}
                </div>
            </div>
        </PrintCard>
    );
};

// ============ DIGITAL PRESENCE SECTION ============
const DigitalPresenceSection = ({ multiDomain, domainAnalysis, socialAvailability }) => {
    const categoryDomains = multiDomain?.category_domains || [];
    const countryDomains = multiDomain?.country_domains || [];
    // Get ALL social handles from the platforms array
    const socialHandles = socialAvailability?.platforms || socialAvailability?.handles || [];
    
    const availableCount = [...categoryDomains, ...countryDomains].filter(d => d.available || d.status?.toLowerCase().includes('available')).length;
    const totalCount = categoryDomains.length + countryDomains.length;
    
    // Count social handle availability
    const availableSocials = socialHandles.filter(s => s.available || s.status?.toLowerCase().includes('available')).length;
    const takenSocials = socialHandles.filter(s => !s.available && s.status && !s.status?.toLowerCase().includes('available') && !s.status?.toLowerCase().includes('error') && !s.status?.toLowerCase().includes('unsupported')).length;
    
    const getStatusIcon = (s) => {
        if (s.available || s.status?.toLowerCase().includes('available')) {
            return <CheckCircle className="w-4 h-4 text-emerald-500" />;
        }
        if (s.status?.toLowerCase().includes('unsupported') || s.status?.toLowerCase().includes('error')) {
            return <AlertCircle className="w-4 h-4 text-slate-400" />;
        }
        return <XOctagon className="w-4 h-4 text-red-500" />;
    };
    
    const getStatusStyle = (s) => {
        if (s.available || s.status?.toLowerCase().includes('available')) {
            return 'bg-emerald-50 border-emerald-200';
        }
        if (s.status?.toLowerCase().includes('unsupported') || s.status?.toLowerCase().includes('error')) {
            return 'bg-slate-50 border-slate-200';
        }
        return 'bg-red-50 border-red-200';
    };
    
    const getBadgeStyle = (s) => {
        if (s.available || s.status?.toLowerCase().includes('available')) {
            return 'bg-emerald-100 text-emerald-700';
        }
        if (s.status?.toLowerCase().includes('unsupported') || s.status?.toLowerCase().includes('error')) {
            return 'bg-slate-100 text-slate-500';
        }
        return 'bg-red-100 text-red-700';
    };
    
    return (
        <div className="space-y-4">
            {/* Domain Check */}
            <PrintCard>
                <div className="bg-white rounded-2xl p-6 border border-slate-200">
                    <div className="flex items-center justify-between mb-4">
                        <SubSectionHeader icon={Globe} title="Multi-Domain Check" />
                        <Badge className={availableCount > totalCount/2 ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}>
                            {availableCount}/{totalCount} Available
                        </Badge>
                    </div>
                    
                    {categoryDomains.length > 0 && (
                        <div className="mb-4">
                            <p className="text-xs font-bold text-slate-500 uppercase mb-2">Category TLDs</p>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                                {categoryDomains.map((d, i) => (
                                    <div key={i} className={`p-3 rounded-lg border flex items-center justify-between ${
                                        d.available || d.status?.toLowerCase().includes('available') 
                                            ? 'bg-emerald-50 border-emerald-200' 
                                            : 'bg-red-50 border-red-200'
                                    }`}>
                                        <span className="font-mono text-xs font-bold text-slate-700">{d.domain}</span>
                                        {d.available || d.status?.toLowerCase().includes('available') 
                                            ? <CheckCircle className="w-4 h-4 text-emerald-500" />
                                            : <XOctagon className="w-4 h-4 text-red-500" />
                                        }
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                    
                    {countryDomains.length > 0 && (
                        <div className="mb-4">
                            <p className="text-xs font-bold text-slate-500 uppercase mb-2">Country TLDs</p>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                                {countryDomains.map((d, i) => (
                                    <div key={i} className={`p-3 rounded-lg border flex items-center justify-between ${
                                        d.available || d.status?.toLowerCase().includes('available') 
                                            ? 'bg-emerald-50 border-emerald-200' 
                                            : 'bg-red-50 border-red-200'
                                    }`}>
                                        <span className="font-mono text-xs font-bold text-slate-700">{d.domain}</span>
                                        {d.available || d.status?.toLowerCase().includes('available') 
                                            ? <CheckCircle className="w-4 h-4 text-emerald-500" />
                                            : <XOctagon className="w-4 h-4 text-red-500" />
                                        }
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                    
                    {multiDomain?.recommended_domain && (
                        <div className="p-4 bg-violet-50 rounded-xl border border-violet-200">
                            <p className="text-xs font-bold text-violet-700 uppercase mb-1">Recommended Domain</p>
                            <p className="font-mono font-bold text-violet-900">{multiDomain.recommended_domain}</p>
                            {multiDomain.acquisition_strategy && (
                                <p className="text-xs text-slate-600 mt-2">{multiDomain.acquisition_strategy}</p>
                            )}
                        </div>
                    )}
                </div>
            </PrintCard>
            
            {/* Social Handles - Show ALL platforms with their status */}
            {socialHandles.length > 0 && (
                <PrintCard>
                    <div className="bg-white rounded-2xl p-6 border border-slate-200">
                        <div className="flex items-center justify-between mb-4">
                            <SubSectionHeader icon={AtSign} title="Social Media Handles" />
                            <div className="flex gap-2">
                                <Badge className="bg-emerald-100 text-emerald-700 text-xs">
                                    {availableSocials} Available
                                </Badge>
                                <Badge className="bg-red-100 text-red-700 text-xs">
                                    {takenSocials} Taken
                                </Badge>
                            </div>
                        </div>
                        
                        {/* Show handle being checked */}
                        {socialAvailability?.handle && (
                            <p className="text-xs text-slate-500 mb-3">
                                Checking handle: <span className="font-mono font-bold">@{socialAvailability.handle}</span>
                            </p>
                        )}
                        
                        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                            {socialHandles.map((s, i) => (
                                <div key={i} className={`p-3 rounded-lg border flex items-center justify-between ${getStatusStyle(s)}`}>
                                    <div className="flex items-center gap-2">
                                        {getStatusIcon(s)}
                                        <span className="text-xs font-bold text-slate-700 capitalize">{s.platform || s.name}</span>
                                    </div>
                                    <Badge className={`text-xs ${getBadgeStyle(s)}`}>
                                        {s.status || (s.available ? 'Available' : 'Taken')}
                                    </Badge>
                                </div>
                            ))}
                        </div>
                        
                        {/* Recommendation */}
                        {socialAvailability?.recommendation && (
                            <div className="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
                                <p className="text-xs text-blue-700">{socialAvailability.recommendation}</p>
                            </div>
                        )}
                    </div>
                </PrintCard>
            )}
        </div>
    );
};

// ============ MARKET INTELLIGENCE SECTION ============
const MarketIntelligenceSection = ({ domainAnalysis, visibilityAnalysis, culturalAnalysis }) => {
    return (
        <div className="space-y-4">
            {/* Domain Status */}
            {domainAnalysis && (
                <PrintCard>
                    <div className="bg-white rounded-2xl p-6 border border-slate-200">
                        <SubSectionHeader icon={Globe} title="Domain Status" />
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className={`p-4 rounded-xl ${
                                domainAnalysis.exact_match_status === 'AVAILABLE' 
                                    ? 'bg-emerald-50 border border-emerald-200' 
                                    : 'bg-red-50 border border-red-200'
                            }`}>
                                <p className="text-xs font-bold text-slate-500 uppercase mb-1">.COM Status</p>
                                <p className={`text-xl font-black ${
                                    domainAnalysis.exact_match_status === 'AVAILABLE' ? 'text-emerald-700' : 'text-red-700'
                                }`}>{domainAnalysis.exact_match_status}</p>
                                <Badge className="mt-2">{domainAnalysis.risk_level || 'LOW'} RISK</Badge>
                            </div>
                            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200">
                                <p className="text-xs font-bold text-slate-500 uppercase mb-2">Conflict Verification</p>
                                <div className="space-y-2">
                                    <div className="flex items-center justify-between text-sm">
                                        <span className="text-slate-600">Active Trademark</span>
                                        <Badge variant="outline">{domainAnalysis.has_trademark || 'UNKNOWN'}</Badge>
                                    </div>
                                    <div className="flex items-center justify-between text-sm">
                                        <span className="text-slate-600">Operating Business</span>
                                        <Badge variant="outline">{domainAnalysis.has_active_business || 'UNKNOWN'}</Badge>
                                    </div>
                                </div>
                                <p className="text-xs text-emerald-600 mt-2 flex items-center gap-1">
                                    <CheckCircle className="w-3 h-3" /> No trademark or active business found
                                </p>
                            </div>
                        </div>
                        
                        {/* Alternatives */}
                        {domainAnalysis.alternatives?.length > 0 && (
                            <div className="mt-4 p-4 bg-blue-50 rounded-xl border border-blue-200">
                                <p className="text-xs font-bold text-blue-700 uppercase mb-2">Recommended Alternatives</p>
                                <div className="flex flex-wrap gap-2">
                                    {domainAnalysis.alternatives.map((alt, i) => (
                                        <Badge key={i} className="bg-white text-blue-700 border border-blue-200">
                                            {alt.domain || alt}
                                        </Badge>
                                    ))}
                                </div>
                            </div>
                        )}
                        
                        {domainAnalysis.strategy_note && (
                            <div className="mt-4 p-3 bg-amber-50 rounded-lg border border-amber-200">
                                <p className="text-xs text-amber-800">💡 {domainAnalysis.strategy_note}</p>
                            </div>
                        )}
                        
                        {domainAnalysis.score_impact && (
                            <p className="mt-3 text-xs text-slate-500">
                                <strong>Score Impact:</strong> {domainAnalysis.score_impact}
                            </p>
                        )}
                    </div>
                </PrintCard>
            )}
            
            {/* Visibility / Conflict Analysis */}
            {visibilityAnalysis && (
                <PrintCard>
                    <div className="bg-white rounded-2xl p-6 border border-slate-200">
                        <SubSectionHeader icon={Target} title="Conflict Relevance Analysis" />
                        
                        {/* Summary - Show NO DIRECT CONFLICTS if both counts are 0 */}
                        <div className={`p-4 rounded-xl border mb-4 ${
                            (visibilityAnalysis.direct_competitors?.length || 0) === 0 && (visibilityAnalysis.phonetic_conflicts?.length || 0) === 0
                                ? 'bg-emerald-50 border-emerald-200'
                                : 'bg-amber-50 border-amber-200'
                        }`}>
                            <p className={`text-lg font-bold ${
                                (visibilityAnalysis.direct_competitors?.length || 0) === 0 && (visibilityAnalysis.phonetic_conflicts?.length || 0) === 0
                                    ? 'text-emerald-700'
                                    : 'text-amber-700'
                            }`}>
                                {(visibilityAnalysis.direct_competitors?.length || 0) === 0 && (visibilityAnalysis.phonetic_conflicts?.length || 0) === 0
                                    ? 'NO DIRECT CONFLICTS'
                                    : `${visibilityAnalysis.direct_competitors?.length || 0} direct competitors • ${visibilityAnalysis.phonetic_conflicts?.length || 0} phonetic conflicts`
                                }
                            </p>
                            <p className="text-sm text-slate-600 mt-1">
                                {visibilityAnalysis.direct_competitors?.length || 0} direct competitors. {visibilityAnalysis.phonetic_conflicts?.length || 0} phonetic conflicts. {visibilityAnalysis.name_twins?.length || 0} name twins identified with distinct intents.
                            </p>
                        </div>
                        
                        {/* Product Intent & Target Customer */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                            {(visibilityAnalysis.user_product_intent || visibilityAnalysis.product_intent) && (
                                <div className="p-4 bg-violet-50 rounded-xl border border-violet-200">
                                    <div className="flex items-center gap-2 mb-2">
                                        <Briefcase className="w-4 h-4 text-violet-600" />
                                        <p className="text-xs font-bold text-violet-700 uppercase">Your Product Intent</p>
                                    </div>
                                    <p className="text-sm text-slate-700">{visibilityAnalysis.user_product_intent || visibilityAnalysis.product_intent}</p>
                                </div>
                            )}
                            {(visibilityAnalysis.user_customer_avatar || visibilityAnalysis.target_customer) && (
                                <div className="p-4 bg-fuchsia-50 rounded-xl border border-fuchsia-200">
                                    <div className="flex items-center gap-2 mb-2">
                                        <UserCheck className="w-4 h-4 text-fuchsia-600" />
                                        <p className="text-xs font-bold text-fuchsia-700 uppercase">Your Target Customer</p>
                                    </div>
                                    <p className="text-sm text-slate-700">{visibilityAnalysis.user_customer_avatar || visibilityAnalysis.target_customer}</p>
                                </div>
                            )}
                        </div>
                        
                        {/* Name Twins / False Positives - These are NOT conflicts */}
                        {(visibilityAnalysis.name_twins?.length > 0 || visibilityAnalysis.false_positives?.length > 0) && (
                            <div>
                                <p className="text-xs font-bold text-slate-500 uppercase mb-3">False Positives Filtered (Keyword Match Only)</p>
                                <div className="space-y-3">
                                    {(visibilityAnalysis.name_twins || visibilityAnalysis.false_positives || []).map((fp, i) => (
                                        <div key={i} className="p-4 bg-slate-50 rounded-xl border border-slate-200">
                                            <div className="flex items-center justify-between mb-2">
                                                <h5 className="font-bold text-slate-800">{fp.name}</h5>
                                                <Badge className="bg-emerald-100 text-emerald-700">NOT A CONFLICT</Badge>
                                            </div>
                                            <p className="text-xs text-amber-600 mb-2">Different - {fp.category}</p>
                                            
                                            {/* Their Intent & Customers */}
                                            <div className="space-y-2 text-xs bg-white p-3 rounded-lg border border-slate-100">
                                                {(fp.their_product_intent || fp.their_intent) && (
                                                    <div>
                                                        <span className="font-bold text-slate-600">Their Intent:</span>{' '}
                                                        <span className="text-slate-700">{fp.their_product_intent || fp.their_intent}</span>
                                                    </div>
                                                )}
                                                {(fp.their_customer_avatar || fp.their_customers) && (
                                                    <div>
                                                        <span className="font-bold text-slate-600">Their Customers:</span>{' '}
                                                        <span className="text-slate-700">{fp.their_customer_avatar || fp.their_customers}</span>
                                                    </div>
                                                )}
                                            </div>
                                            
                                            {/* Intent Match & Customer Overlap */}
                                            <div className="flex gap-4 mt-2 text-xs">
                                                <div className="flex items-center gap-1">
                                                    <span className="font-bold text-slate-500">Intent:</span>
                                                    <Badge className={`text-xs ${fp.intent_match === 'SAME' ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'}`}>
                                                        {fp.intent_match || 'DIFFERENT'}
                                                    </Badge>
                                                </div>
                                                <div className="flex items-center gap-1">
                                                    <span className="font-bold text-slate-500">Customers:</span>
                                                    <Badge className={`text-xs ${fp.customer_overlap === 'HIGH' ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'}`}>
                                                        {fp.customer_overlap || 'NONE'}
                                                    </Badge>
                                                </div>
                                            </div>
                                            
                                            {/* Conclusion/Reason */}
                                            {(fp.reason || fp.conclusion) && (
                                                <p className="text-xs text-slate-500 mt-2 italic">{fp.reason || fp.conclusion}</p>
                                            )}
                                        </div>
                                    ))}
                                </div>
                                <p className="mt-3 text-xs text-emerald-600 flex items-center gap-1">
                                    <CheckCircle className="w-3 h-3" /> These are keyword matches only - different intent/customers. NOT rejection factors.
                                </p>
                            </div>
                        )}
                        
                        {/* Conflict Summary */}
                        {visibilityAnalysis.conflict_summary && (
                            <div className="mt-4 p-4 bg-blue-50 rounded-xl border border-blue-200">
                                <p className="text-sm text-blue-800">{visibilityAnalysis.conflict_summary}</p>
                            </div>
                        )}
                    </div>
                </PrintCard>
            )}
            
            {/* Cultural Fit */}
            {culturalAnalysis?.length > 0 && (
                <PrintCard>
                    <div className="bg-white rounded-2xl p-6 border border-slate-200">
                        <SubSectionHeader icon={Globe} title="Cultural Fit" />
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            {culturalAnalysis.map((c, i) => {
                                const countryName = typeof c.country === 'object' ? c.country?.name : c.country;
                                return (
                                    <div key={i} className="bg-gradient-to-br from-fuchsia-50 to-white border border-fuchsia-200 rounded-xl p-4 text-center">
                                        <h4 className="font-bold text-slate-800 text-sm mb-2">{countryName}</h4>
                                        <div className="text-2xl font-black text-fuchsia-600 my-2">{c.cultural_resonance_score}/10</div>
                                        <p className="text-xs text-slate-500">{c.cultural_notes}</p>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                </PrintCard>
            )}
        </div>
    );
};

// ============ COMPETITIVE LANDSCAPE SECTION ============
const CompetitiveLandscapeSection = ({ competitorAnalysis, countryCompetitorAnalysis }) => {
    if (!competitorAnalysis && (!countryCompetitorAnalysis || countryCompetitorAnalysis.length === 0)) return null;
    
    const competitors = competitorAnalysis?.competitors || competitorAnalysis?.true_market_competitors || [];
    
    // Country colors for different markets
    const countryColors = [
        { bg: 'from-blue-500 to-indigo-500', light: 'bg-blue-50 border-blue-200', text: 'text-blue-700' },
        { bg: 'from-emerald-500 to-teal-500', light: 'bg-emerald-50 border-emerald-200', text: 'text-emerald-700' },
        { bg: 'from-amber-500 to-orange-500', light: 'bg-amber-50 border-amber-200', text: 'text-amber-700' },
        { bg: 'from-rose-500 to-pink-500', light: 'bg-rose-50 border-rose-200', text: 'text-rose-700' },
    ];
    
    // Render a single positioning matrix
    const renderMatrix = (analysis, title, colorScheme, showFlag = false) => {
        const comps = analysis.competitors || [];
        return (
            <PrintCard key={title}>
                <div className="bg-white rounded-2xl p-6 border border-slate-200">
                    <div className="flex items-center justify-between mb-4">
                        <SubSectionHeader icon={BarChart3} title={title} />
                        {showFlag && analysis.country_flag && (
                            <span className="text-3xl">{analysis.country_flag}</span>
                        )}
                    </div>
                    
                    {/* Axis Labels */}
                    <div className="text-center mb-4">
                        <p className="text-xs text-slate-500">
                            X: {analysis.x_axis_label || 'Price: Budget → Luxury'} | Y: {analysis.y_axis_label || 'Style: Classic → Avant-Garde'}
                        </p>
                    </div>
                    
                    {/* Visual Matrix */}
                    <div className="relative bg-gradient-to-br from-slate-50 to-white border border-slate-200 rounded-xl p-4 h-64">
                        {/* Grid lines */}
                        <div className="absolute inset-4 border-l border-b border-slate-300"></div>
                        <div className="absolute left-1/2 top-4 bottom-4 border-l border-dashed border-slate-200"></div>
                        <div className="absolute left-4 right-4 top-1/2 border-t border-dashed border-slate-200"></div>
                        
                        {/* Plot competitors */}
                        {comps.slice(0, 5).map((comp, i) => {
                            const x = (comp.x_coordinate || 50) / 100 * 80 + 10;
                            const y = 100 - ((comp.y_coordinate || 50) / 100 * 80 + 10);
                            return (
                                <div
                                    key={i}
                                    className="absolute transform -translate-x-1/2 -translate-y-1/2 group"
                                    style={{ left: `${x}%`, top: `${y}%` }}
                                >
                                    <div className={`w-7 h-7 bg-gradient-to-r ${colorScheme.bg} rounded-full flex items-center justify-center text-white text-xs font-bold shadow-lg`}>
                                        {i + 1}
                                    </div>
                                    <div className="hidden group-hover:block absolute top-full left-1/2 transform -translate-x-1/2 mt-1 px-2 py-1 bg-slate-800 text-white text-xs rounded whitespace-nowrap z-10">
                                        {comp.name}
                                    </div>
                                </div>
                            );
                        })}
                        
                        {/* User brand position */}
                        {analysis.user_brand_position && (
                            <div
                                className="absolute transform -translate-x-1/2 -translate-y-1/2"
                                style={{
                                    left: `${(analysis.user_brand_position.x_coordinate || analysis.user_brand_position.x || 70) / 100 * 80 + 10}%`,
                                    top: `${100 - ((analysis.user_brand_position.y_coordinate || analysis.user_brand_position.y || 70) / 100 * 80 + 10)}%`
                                }}
                            >
                                <div className="w-9 h-9 bg-gradient-to-r from-violet-500 to-fuchsia-500 rounded-full flex items-center justify-center text-white text-xs font-bold shadow-lg border-2 border-white">
                                    YOU
                                </div>
                            </div>
                        )}
                    </div>
                    
                    {/* Legend */}
                    <div className="mt-3 flex flex-wrap gap-2">
                        {comps.slice(0, 5).map((comp, i) => (
                            <div key={i} className="flex items-center gap-1 text-xs">
                                <div className={`w-4 h-4 bg-gradient-to-r ${colorScheme.bg} rounded-full flex items-center justify-center text-white text-xs`}>{i + 1}</div>
                                <span className="text-slate-600 text-xs">{comp.name}</span>
                            </div>
                        ))}
                    </div>
                    
                    {/* Market Insights */}
                    <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
                        {analysis.white_space_analysis && (
                            <div className={`p-3 rounded-lg border ${colorScheme.light}`}>
                                <p className={`text-xs font-bold ${colorScheme.text} mb-1`}>White Space</p>
                                <p className="text-xs text-slate-600">{analysis.white_space_analysis}</p>
                            </div>
                        )}
                        {analysis.strategic_advantage && (
                            <div className={`p-3 rounded-lg border ${colorScheme.light}`}>
                                <p className={`text-xs font-bold ${colorScheme.text} mb-1`}>Strategic Advantage</p>
                                <p className="text-xs text-slate-600">{analysis.strategic_advantage}</p>
                            </div>
                        )}
                    </div>
                    
                    {/* Market Entry Recommendation (for country-specific) */}
                    {analysis.market_entry_recommendation && (
                        <div className="mt-3 p-3 bg-violet-50 rounded-lg border border-violet-200">
                            <p className="text-xs font-bold text-violet-700 mb-1">Market Entry Recommendation</p>
                            <p className="text-xs text-slate-600">{analysis.market_entry_recommendation}</p>
                        </div>
                    )}
                </div>
            </PrintCard>
        );
    };
    
    return (
        <div className="space-y-4">
            {/* Global/Overall Strategic Positioning Matrix */}
            {competitorAnalysis && competitors.length > 0 && (
                <>
                    <PrintCard>
                        <div className="bg-white rounded-2xl p-6 border border-slate-200">
                            <SubSectionHeader icon={BarChart3} title="Strategic Positioning Matrix (Global Overview)" />
                            
                            {/* Axis Labels */}
                            <div className="text-center mb-4">
                                <p className="text-xs text-slate-500">
                                    X: {competitorAnalysis.x_axis_label || 'Price: Budget → Luxury'} | Y: {competitorAnalysis.y_axis_label || 'Style: Classic → Avant-Garde'}
                                </p>
                            </div>
                            
                            {/* Visual Matrix */}
                            <div className="relative bg-gradient-to-br from-slate-50 to-white border border-slate-200 rounded-xl p-4 h-80">
                                {/* Grid lines */}
                                <div className="absolute inset-4 border-l border-b border-slate-300"></div>
                                <div className="absolute left-1/2 top-4 bottom-4 border-l border-dashed border-slate-200"></div>
                                <div className="absolute left-4 right-4 top-1/2 border-t border-dashed border-slate-200"></div>
                                
                                {/* Quadrant Labels */}
                                <div className="absolute top-6 left-6 text-xs text-slate-400">Budget + Avant-Garde</div>
                                <div className="absolute top-6 right-6 text-xs text-slate-400 text-right">Luxury + Avant-Garde</div>
                                <div className="absolute bottom-6 left-6 text-xs text-slate-400">Budget + Classic</div>
                                <div className="absolute bottom-6 right-6 text-xs text-slate-400 text-right">Luxury + Classic</div>
                                
                                {/* Plot competitors */}
                                {competitors.slice(0, 6).map((comp, i) => {
                                    const x = (comp.x_coordinate || 50) / 100 * 80 + 10;
                                    const y = 100 - ((comp.y_coordinate || 50) / 100 * 80 + 10);
                                    return (
                                        <div
                                            key={i}
                                            className="absolute transform -translate-x-1/2 -translate-y-1/2 group"
                                            style={{ left: `${x}%`, top: `${y}%` }}
                                        >
                                            <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center text-white text-xs font-bold shadow-lg">
                                                {i + 1}
                                            </div>
                                            <div className="hidden group-hover:block absolute top-full left-1/2 transform -translate-x-1/2 mt-1 px-2 py-1 bg-slate-800 text-white text-xs rounded whitespace-nowrap z-10">
                                                {comp.name}
                                            </div>
                                        </div>
                                    );
                                })}
                                
                                {/* User brand position */}
                                {competitorAnalysis.user_brand_position && (
                                    <div
                                        className="absolute transform -translate-x-1/2 -translate-y-1/2"
                                        style={{
                                            left: `${(competitorAnalysis.user_brand_position.x || competitorAnalysis.user_brand_position.x_coordinate || 70) / 100 * 80 + 10}%`,
                                            top: `${100 - ((competitorAnalysis.user_brand_position.y || competitorAnalysis.user_brand_position.y_coordinate || 70) / 100 * 80 + 10)}%`
                                        }}
                                    >
                                        <div className="w-10 h-10 bg-gradient-to-r from-violet-500 to-fuchsia-500 rounded-full flex items-center justify-center text-white text-xs font-bold shadow-lg border-2 border-white">
                                            YOU
                                        </div>
                                    </div>
                                )}
                            </div>
                            
                            {/* Legend */}
                            <div className="mt-4 flex flex-wrap gap-3">
                                {competitors.slice(0, 6).map((comp, i) => (
                                    <div key={i} className="flex items-center gap-2 text-xs">
                                        <div className="w-5 h-5 bg-blue-500 rounded-full flex items-center justify-center text-white text-xs">{i + 1}</div>
                                        <span className="text-slate-600">{comp.name}</span>
                                        <Badge variant="outline" className="text-xs">{comp.quadrant || comp.price_position}</Badge>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </PrintCard>
                    
                    {/* White Space & Strategic Advantage for Global */}
                    <PrintCard>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {competitorAnalysis.white_space_analysis && (
                                <div className="bg-emerald-50 rounded-xl p-5 border border-emerald-200">
                                    <div className="flex items-center gap-2 mb-3">
                                        <Lightbulb className="w-5 h-5 text-emerald-600" />
                                        <h4 className="font-bold text-emerald-700">White Space Analysis</h4>
                                    </div>
                                    <p className="text-sm text-slate-700">{competitorAnalysis.white_space_analysis}</p>
                                </div>
                            )}
                            {competitorAnalysis.strategic_advantage && (
                                <div className="bg-violet-50 rounded-xl p-5 border border-violet-200">
                                    <div className="flex items-center gap-2 mb-3">
                                        <Target className="w-5 h-5 text-violet-600" />
                                        <h4 className="font-bold text-violet-700">Strategic Advantage</h4>
                                    </div>
                                    <p className="text-sm text-slate-700">{competitorAnalysis.strategic_advantage}</p>
                                </div>
                            )}
                        </div>
                    </PrintCard>
                </>
            )}
            
            {/* Country-Specific Positioning Matrices (up to 4) */}
            {countryCompetitorAnalysis && countryCompetitorAnalysis.length > 0 && (
                <>
                    <PrintCard>
                        <div className="bg-gradient-to-r from-violet-50 to-fuchsia-50 rounded-xl p-4 border border-violet-200">
                            <div className="flex items-center gap-2">
                                <Globe className="w-5 h-5 text-violet-600" />
                                <h4 className="font-bold text-violet-700">Country-Specific Competitive Analysis</h4>
                            </div>
                            <p className="text-xs text-slate-600 mt-1">Market positioning analysis for {countryCompetitorAnalysis.length} target {countryCompetitorAnalysis.length === 1 ? 'market' : 'markets'}</p>
                        </div>
                    </PrintCard>
                    
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        {countryCompetitorAnalysis.slice(0, 4).map((countryAnalysis, idx) => {
                            const countryName = typeof countryAnalysis.country === 'object' ? countryAnalysis.country?.name : countryAnalysis.country;
                            return renderMatrix(
                                countryAnalysis, 
                                `${countryName} Market`, 
                                countryColors[idx % countryColors.length],
                                true
                            );
                        })}
                    </div>
                </>
            )}
            
            {/* Recommended Pricing (Global) */}
            {competitorAnalysis?.suggested_pricing && (
                <PrintCard>
                    <div className="bg-amber-50 rounded-xl p-5 border border-amber-200">
                        <div className="flex items-center gap-2 mb-3">
                            <TrendingUp className="w-5 h-5 text-amber-600" />
                            <h4 className="font-bold text-amber-700">Recommended Pricing Strategy</h4>
                        </div>
                        <p className="text-sm text-slate-700">{competitorAnalysis.suggested_pricing}</p>
                    </div>
                </PrintCard>
            )}
        </div>
    );
};

// ============ LEGAL RISK MATRIX ============
const LegalRiskMatrix = ({ trademarkMatrix, trademarkClasses }) => {
    if (!trademarkMatrix) return null;
    
    const getZoneColor = (zone) => {
        const z = (zone || '').toLowerCase();
        if (z.includes('green') || z.includes('low')) return 'bg-emerald-100 text-emerald-700';
        if (z.includes('yellow') || z.includes('medium')) return 'bg-amber-100 text-amber-700';
        return 'bg-red-100 text-red-700';
    };
    
    const risks = [
        { key: 'genericness', label: 'Genericness', data: trademarkMatrix.genericness },
        { key: 'existing_conflicts', label: 'Existing Conflicts', data: trademarkMatrix.existing_conflicts },
        { key: 'phonetic_similarity', label: 'Phonetic Similarity', data: trademarkMatrix.phonetic_similarity },
        { key: 'relevant_classes', label: 'Relevant Classes', data: trademarkMatrix.relevant_classes },
        { key: 'rebranding_probability', label: 'Rebranding Probability', data: trademarkMatrix.rebranding_probability },
    ].filter(r => r.data);
    
    return (
        <div className="space-y-4">
            <PrintCard>
                <div className="bg-white rounded-2xl p-6 border border-slate-200">
                    <SubSectionHeader icon={Scale} title="Legal Risk Assessment Matrix" />
                    
                    {/* Table */}
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="bg-slate-50">
                                    <th className="text-left p-3 font-bold text-slate-700">Risk Factor</th>
                                    <th className="text-center p-3 font-bold text-slate-700">Likelihood</th>
                                    <th className="text-center p-3 font-bold text-slate-700">Severity</th>
                                    <th className="text-center p-3 font-bold text-slate-700">Zone</th>
                                    <th className="text-left p-3 font-bold text-slate-700">Mitigation Strategy</th>
                                </tr>
                            </thead>
                            <tbody>
                                {risks.map((risk, i) => (
                                    <tr key={i} className="border-t border-slate-100">
                                        <td className="p-3 font-semibold text-slate-800">{risk.label}</td>
                                        <td className="p-3 text-center">
                                            <span className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-slate-100 font-bold">
                                                {risk.data.likelihood || risk.data.probability}/10
                                            </span>
                                        </td>
                                        <td className="p-3 text-center">
                                            <span className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-slate-100 font-bold">
                                                {risk.data.severity}/10
                                            </span>
                                        </td>
                                        <td className="p-3 text-center">
                                            <Badge className={getZoneColor(risk.data.zone)}>{risk.data.zone}</Badge>
                                        </td>
                                        <td className="p-3 text-xs text-slate-600">{risk.data.commentary || risk.data.mitigation || 'No specific mitigation required'}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </PrintCard>
            
            {/* Nice Classes */}
            {trademarkClasses && (
                <PrintCard>
                    <div className="bg-blue-50 rounded-xl p-5 border border-blue-200">
                        <div className="flex items-center gap-2 mb-3">
                            <FileText className="w-5 h-5 text-blue-600" />
                            <h4 className="font-bold text-blue-700">Recommended NICE Classes for Filing</h4>
                        </div>
                        <p className="text-sm text-slate-700">{trademarkClasses}</p>
                    </div>
                </PrintCard>
            )}
            
            {/* Overall Assessment */}
            {trademarkMatrix.overall_assessment && (
                <PrintCard>
                    <div className="bg-emerald-50 rounded-xl p-5 border border-emerald-200">
                        <div className="flex items-center gap-2 mb-3">
                            <Shield className="w-5 h-5 text-emerald-600" />
                            <h4 className="font-bold text-emerald-700">Overall Assessment</h4>
                        </div>
                        <p className="text-sm text-slate-700">{trademarkMatrix.overall_assessment}</p>
                    </div>
                </PrintCard>
            )}
        </div>
    );
};

// ============ LOCKED SECTION ============
const LockedSection = ({ title, onUnlock }) => (
    <div className="relative overflow-hidden rounded-2xl border-2 border-dashed border-slate-200 bg-gradient-to-br from-slate-50 to-white print:hidden">
        <div className="p-8 filter blur-sm opacity-50">
            <div className="h-4 w-3/4 bg-slate-200 rounded mb-3"></div>
            <div className="h-4 w-1/2 bg-slate-200 rounded mb-3"></div>
            <div className="h-20 w-full bg-slate-100 rounded"></div>
        </div>
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/80">
            <Lock className="w-12 h-12 text-violet-400 mb-3" />
            <h3 className="text-lg font-bold text-slate-800 mb-2">{title}</h3>
            <Button onClick={onUnlock} className="bg-violet-600 hover:bg-violet-700 text-white">
                <Sparkles className="w-4 h-4 mr-2" /> Register to Unlock
            </Button>
        </div>
    </div>
);

// ============ TRADEMARK RESEARCH SECTION (NEW - Perplexity-Level Analysis) ============
const TrademarkResearchSection = ({ trademarkResearch, registrationTimeline, mitigationStrategies }) => {
    if (!trademarkResearch) return null;
    
    const getRiskColor = (level) => {
        const l = (level || '').toLowerCase();
        if (l === 'critical') return 'bg-red-600 text-white';
        if (l === 'high') return 'bg-red-100 text-red-700';
        if (l === 'medium') return 'bg-amber-100 text-amber-700';
        return 'bg-emerald-100 text-emerald-700';
    };
    
    const getScoreColor = (score) => {
        if (score >= 7) return 'text-red-600';
        if (score >= 5) return 'text-amber-600';
        return 'text-emerald-600';
    };
    
    const getProbabilityColor = (prob) => {
        if (prob >= 70) return 'bg-emerald-500';
        if (prob >= 40) return 'bg-amber-500';
        return 'bg-red-500';
    };
    
    return (
        <div className="space-y-6">
            {/* Risk Summary Card */}
            <PrintCard>
                <div className="bg-white rounded-2xl p-6 border border-slate-200">
                    <SubSectionHeader icon={BarChart3} title="Trademark Research Risk Summary" />
                    
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                        {/* Overall Risk Score */}
                        <div className="text-center p-4 bg-slate-50 rounded-xl">
                            <div className={`text-4xl font-black ${getScoreColor(trademarkResearch.overall_risk_score)}`}>
                                {trademarkResearch.overall_risk_score}/10
                            </div>
                            <div className="text-xs text-slate-500 mt-1">Overall Risk</div>
                        </div>
                        
                        {/* Registration Success */}
                        <div className="text-center p-4 bg-slate-50 rounded-xl">
                            <div className="text-4xl font-black text-blue-600">
                                {trademarkResearch.registration_success_probability}%
                            </div>
                            <div className="text-xs text-slate-500 mt-1">Registration Success</div>
                            <div className={`h-2 rounded-full mt-2 ${getProbabilityColor(trademarkResearch.registration_success_probability)}`} 
                                 style={{width: `${trademarkResearch.registration_success_probability}%`}}></div>
                        </div>
                        
                        {/* Opposition Probability */}
                        <div className="text-center p-4 bg-slate-50 rounded-xl">
                            <div className="text-4xl font-black text-amber-600">
                                {trademarkResearch.opposition_probability}%
                            </div>
                            <div className="text-xs text-slate-500 mt-1">Opposition Risk</div>
                        </div>
                        
                        {/* Total Conflicts */}
                        <div className="text-center p-4 bg-slate-50 rounded-xl">
                            <div className="text-4xl font-black text-slate-700">
                                {trademarkResearch.total_conflicts_found}
                            </div>
                            <div className="text-xs text-slate-500 mt-1">Conflicts Found</div>
                            {trademarkResearch.critical_conflicts_count > 0 && (
                                <Badge className="bg-red-600 text-white mt-1">{trademarkResearch.critical_conflicts_count} Critical</Badge>
                            )}
                        </div>
                    </div>
                    
                    {/* Nice Classification */}
                    {trademarkResearch.nice_classification && (
                        <div className="bg-blue-50 rounded-xl p-4 border border-blue-200">
                            <div className="flex items-center gap-2 mb-2">
                                <FileText className="w-4 h-4 text-blue-600" />
                                <span className="font-bold text-blue-700">Nice Classification</span>
                            </div>
                            <p className="text-sm text-slate-700">
                                <span className="font-bold">Class {trademarkResearch.nice_classification.class_number}</span>: {trademarkResearch.nice_classification.class_description}
                            </p>
                        </div>
                    )}
                </div>
            </PrintCard>
            
            {/* Trademark Conflicts */}
            {trademarkResearch.trademark_conflicts && trademarkResearch.trademark_conflicts.length > 0 && (
                <PrintCard>
                    <div className="bg-white rounded-2xl p-6 border border-red-200">
                        <SubSectionHeader icon={AlertTriangle} title={`Trademark Conflicts Found (${trademarkResearch.trademark_conflicts.length})`} color="red" />
                        
                        <div className="space-y-3">
                            {trademarkResearch.trademark_conflicts.map((conflict, i) => (
                                <div key={i} className="p-4 bg-red-50 rounded-xl border border-red-100">
                                    <div className="flex items-start justify-between mb-2">
                                        <div>
                                            <span className="font-bold text-red-800 text-lg">{conflict.name}</span>
                                            {conflict.application_number && (
                                                <span className="ml-2 text-xs text-slate-500">#{conflict.application_number}</span>
                                            )}
                                        </div>
                                        <Badge className={getRiskColor(conflict.risk_level)}>{conflict.risk_level}</Badge>
                                    </div>
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                                        <div><span className="text-slate-500">Source:</span> <span className="font-medium">{conflict.source}</span></div>
                                        <div><span className="text-slate-500">Status:</span> <span className="font-medium">{conflict.status || 'Unknown'}</span></div>
                                        <div><span className="text-slate-500">Class:</span> <span className="font-medium">{conflict.class_number || 'N/A'}</span></div>
                                        <div><span className="text-slate-500">Type:</span> <span className="font-medium">{conflict.conflict_type}</span></div>
                                    </div>
                                    {conflict.details && (
                                        <p className="text-xs text-slate-600 mt-2">{conflict.details}</p>
                                    )}
                                    {conflict.url && (
                                        <a href={conflict.url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-600 hover:underline mt-1 inline-block">
                                            View Source →
                                        </a>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                </PrintCard>
            )}
            
            {/* Company Conflicts */}
            {trademarkResearch.company_conflicts && trademarkResearch.company_conflicts.length > 0 && (
                <PrintCard>
                    <div className="bg-white rounded-2xl p-6 border border-amber-200">
                        <SubSectionHeader icon={Building2} title={`Company Registry Conflicts (${trademarkResearch.company_conflicts.length})`} color="amber" />
                        
                        <div className="space-y-3">
                            {trademarkResearch.company_conflicts.map((conflict, i) => (
                                <div key={i} className="p-4 bg-amber-50 rounded-xl border border-amber-100">
                                    <div className="flex items-start justify-between mb-2">
                                        <div>
                                            <span className="font-bold text-amber-800">{conflict.name}</span>
                                            {conflict.cin && (
                                                <span className="ml-2 text-xs text-slate-500">CIN: {conflict.cin}</span>
                                            )}
                                        </div>
                                        <Badge className={getRiskColor(conflict.risk_level)}>{conflict.risk_level}</Badge>
                                    </div>
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                                        <div><span className="text-slate-500">Status:</span> <span className="font-medium">{conflict.status}</span></div>
                                        <div><span className="text-slate-500">Industry:</span> <span className="font-medium">{conflict.industry || 'N/A'}</span></div>
                                        <div><span className="text-slate-500">State:</span> <span className="font-medium">{conflict.state || 'N/A'}</span></div>
                                        <div><span className="text-slate-500">Source:</span> <span className="font-medium">{conflict.source}</span></div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </PrintCard>
            )}
            
            {/* Common Law Conflicts */}
            {trademarkResearch.common_law_conflicts && trademarkResearch.common_law_conflicts.length > 0 && (
                <PrintCard>
                    <div className="bg-white rounded-2xl p-6 border border-slate-200">
                        <SubSectionHeader icon={Globe} title={`Common Law / Online Presence (${trademarkResearch.common_law_conflicts.length})`} color="slate" />
                        
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            {trademarkResearch.common_law_conflicts.map((conflict, i) => (
                                <div key={i} className="p-3 bg-slate-50 rounded-lg border border-slate-100 text-sm">
                                    <div className="flex items-center justify-between">
                                        <span className="font-medium text-slate-800">{conflict.name}</span>
                                        <Badge className={getRiskColor(conflict.risk_level)}>{conflict.risk_level}</Badge>
                                    </div>
                                    <div className="text-xs text-slate-500 mt-1">
                                        Platform: {conflict.platform} | Industry Match: {conflict.industry_match ? 'Yes' : 'No'}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </PrintCard>
            )}
            
            {/* Legal Precedents */}
            {trademarkResearch.legal_precedents && trademarkResearch.legal_precedents.length > 0 && (
                <PrintCard>
                    <div className="bg-white rounded-2xl p-6 border border-violet-200">
                        <SubSectionHeader icon={Scale} title="Relevant Legal Precedents" color="violet" />
                        
                        <div className="space-y-3">
                            {trademarkResearch.legal_precedents.map((precedent, i) => (
                                <div key={i} className="p-4 bg-violet-50 rounded-xl border border-violet-100">
                                    <div className="font-bold text-violet-800 mb-1">{precedent.case_name}</div>
                                    <div className="text-xs text-slate-600 mb-2">
                                        {precedent.court && <span>{precedent.court}</span>}
                                        {precedent.year && <span> • {precedent.year}</span>}
                                    </div>
                                    {precedent.relevance && (
                                        <p className="text-sm text-slate-700">{precedent.relevance}</p>
                                    )}
                                    {precedent.key_principle && (
                                        <p className="text-xs text-violet-600 mt-2 italic">Key Principle: {precedent.key_principle}</p>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                </PrintCard>
            )}
            
            {/* Registration Timeline */}
            {registrationTimeline && (
                <PrintCard>
                    <div className="bg-white rounded-2xl p-6 border border-blue-200">
                        <SubSectionHeader icon={Calendar} title="Registration Timeline & Costs" color="blue" />
                        
                        <div className="mb-4">
                            <div className="text-2xl font-bold text-blue-700">{registrationTimeline.estimated_duration}</div>
                            <div className="text-sm text-slate-500">Estimated registration duration</div>
                        </div>
                        
                        {registrationTimeline.stages && registrationTimeline.stages.length > 0 && (
                            <div className="space-y-2 mb-4">
                                {registrationTimeline.stages.map((stage, i) => (
                                    <div key={i} className="flex items-center gap-3 p-3 bg-blue-50 rounded-lg">
                                        <div className="w-8 h-8 bg-blue-200 rounded-full flex items-center justify-center text-blue-700 font-bold text-sm">
                                            {i + 1}
                                        </div>
                                        <div className="flex-1">
                                            <div className="font-medium text-slate-800">{stage.stage}</div>
                                            <div className="text-xs text-slate-500">{stage.duration}</div>
                                        </div>
                                        {stage.risk && (
                                            <Badge variant="outline" className="text-xs">{stage.risk}</Badge>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                        
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                            {registrationTimeline.filing_cost && (
                                <div className="p-3 bg-emerald-50 rounded-lg">
                                    <div className="text-xs text-slate-500">Filing Cost</div>
                                    <div className="font-bold text-emerald-700">{registrationTimeline.filing_cost}</div>
                                </div>
                            )}
                            {registrationTimeline.opposition_defense_cost && (
                                <div className="p-3 bg-amber-50 rounded-lg">
                                    <div className="text-xs text-slate-500">Opposition Defense</div>
                                    <div className="font-bold text-amber-700">{registrationTimeline.opposition_defense_cost}</div>
                                </div>
                            )}
                            {registrationTimeline.total_estimated_cost && (
                                <div className="p-3 bg-red-50 rounded-lg">
                                    <div className="text-xs text-slate-500">Total Estimated</div>
                                    <div className="font-bold text-red-700">{registrationTimeline.total_estimated_cost}</div>
                                </div>
                            )}
                        </div>
                    </div>
                </PrintCard>
            )}
            
            {/* Mitigation Strategies */}
            {mitigationStrategies && mitigationStrategies.length > 0 && (
                <PrintCard>
                    <div className="bg-white rounded-2xl p-6 border border-emerald-200">
                        <SubSectionHeader icon={Lightbulb} title="Risk Mitigation Strategies" color="emerald" />
                        
                        <div className="space-y-3">
                            {mitigationStrategies.map((strategy, i) => (
                                <div key={i} className={`p-4 rounded-xl border ${
                                    strategy.priority === 'HIGH' ? 'bg-red-50 border-red-200' :
                                    strategy.priority === 'MEDIUM' ? 'bg-amber-50 border-amber-200' :
                                    'bg-emerald-50 border-emerald-200'
                                }`}>
                                    <div className="flex items-start justify-between mb-2">
                                        <span className="font-bold text-slate-800">{strategy.action}</span>
                                        <Badge className={
                                            strategy.priority === 'HIGH' ? 'bg-red-600 text-white' :
                                            strategy.priority === 'MEDIUM' ? 'bg-amber-500 text-white' :
                                            'bg-emerald-500 text-white'
                                        }>{strategy.priority}</Badge>
                                    </div>
                                    <p className="text-sm text-slate-600">{strategy.rationale}</p>
                                    {strategy.estimated_cost && (
                                        <div className="text-xs text-slate-500 mt-2">Estimated Cost: {strategy.estimated_cost}</div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                </PrintCard>
            )}
            
            {/* No Conflicts Found Message */}
            {(!trademarkResearch.trademark_conflicts || trademarkResearch.trademark_conflicts.length === 0) &&
             (!trademarkResearch.company_conflicts || trademarkResearch.company_conflicts.length === 0) && (
                <PrintCard>
                    <div className="bg-emerald-50 rounded-2xl p-6 border border-emerald-200 text-center">
                        <CheckCircle className="w-12 h-12 text-emerald-500 mx-auto mb-3" />
                        <h4 className="font-bold text-emerald-700 text-lg">No Critical Conflicts Found</h4>
                        <p className="text-sm text-slate-600 mt-2">
                            Our real-time trademark research did not find any direct trademark or company registry conflicts.
                            However, we recommend conducting a professional trademark search before filing.
                        </p>
                    </div>
                </PrintCard>
            )}
        </div>
    );
};

// ============ MAIN DASHBOARD ============
const Dashboard = () => {
    const location = useLocation();
    const navigate = useNavigate();
    const { user, openAuthModal } = useAuth();
    const [reportData, setReportData] = useState(null);
    const [queryData, setQueryData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [downloading, setDownloading] = useState(false);
    const reportRef = useRef(null);
    
    const isAuthenticated = !!user;
    const currentDate = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

    useEffect(() => {
        if (location.state?.data) {
            setReportData(location.state.data);
            setQueryData(location.state.query);
            localStorage.setItem('current_report', JSON.stringify(location.state.data));
            localStorage.setItem('current_query', JSON.stringify(location.state.query));
        } else {
            const savedReport = localStorage.getItem('current_report');
            const savedQuery = localStorage.getItem('current_query');
            if (savedReport && savedQuery) {
                setReportData(JSON.parse(savedReport));
                setQueryData(JSON.parse(savedQuery));
            }
        }
        setLoading(false);
    }, [location.state]);

    const handleRegister = () => {
        localStorage.setItem('auth_return_url', '/dashboard');
        openAuthModal(reportData?.report_id);
    };

    // PDF Download function
    const handleDownloadPDF = async () => {
        if (!reportRef.current) {
            alert('Report not ready. Please wait and try again.');
            return;
        }
        
        setDownloading(true);
        
        try {
            const brandName = reportData?.brand_scores?.[0]?.brand_name || 'Report';
            const element = reportRef.current;
            
            const opt = {
                margin: 10,
                filename: 'RIGHTNAME_' + brandName + '_Report.pdf',
                image: { type: 'jpeg', quality: 0.95 },
                html2canvas: { 
                    scale: 2,
                    useCORS: true,
                    logging: false
                },
                jsPDF: { 
                    unit: 'mm', 
                    format: 'a4', 
                    orientation: 'portrait' 
                },
                pagebreak: { mode: 'avoid-all' }
            };
            
            await html2pdf().set(opt).from(element).save();
            
        } catch (error) {
            console.error('PDF Error:', error);
            alert('PDF generation failed: ' + error.message + '\n\nPlease try using Ctrl+P to print as PDF.');
        } finally {
            setDownloading(false);
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-slate-50">
                <div className="text-center">
                    <div className="w-12 h-12 border-4 border-violet-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                    <p className="text-slate-600">Loading Report...</p>
                </div>
            </div>
        );
    }

    if (!reportData || !reportData.brand_scores?.[0]) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-slate-50">
                <div className="text-center p-8 bg-white rounded-2xl shadow-lg">
                    <h2 className="text-xl font-bold text-slate-800 mb-4">Session Expired</h2>
                    <Button onClick={() => navigate('/')}>Return Home</Button>
                </div>
            </div>
        );
    }

    const data = reportData;
    const query = queryData || {};
    const brand = data.brand_scores[0];

    return (
        <div className="min-h-screen bg-slate-50 text-slate-900 print:bg-white">
            {/* Print Styles - Enhanced Page Break Control */}
            <style>{`
                @media print {
                    @page { size: A4 portrait; margin: 10mm; }
                    body { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
                    .print-card { break-inside: avoid !important; page-break-inside: avoid !important; margin-bottom: 8px; }
                    .no-print { display: none !important; }
                    /* Force new page for each major section (except pages 1 & 2) */
                    .pdf-page-break, .print-new-page { page-break-before: always !important; break-before: page !important; }
                    .pdf-page-break { page-break-before: always !important; break-before: page !important; }
                    .pdf-no-break { page-break-inside: avoid !important; break-inside: avoid !important; }
                    .print-section { break-inside: avoid !important; }
                    /* Keep section headers with their content */
                    .section-header { break-after: avoid !important; page-break-after: avoid !important; }
                }
            `}</style>

            {/* Cover Page */}
            <CoverPage brandName={brand.brand_name} score={brand.namescore} verdict={brand.verdict} date={currentDate} query={query} reportId={data.report_id} />

            {/* Navbar */}
            <div className="bg-white border-b border-slate-200 px-6 py-4 flex justify-between items-center no-print sticky top-0 z-50">
                <div className="flex items-center gap-4">
                    <Button variant="ghost" size="icon" onClick={() => navigate('/')} className="rounded-full">
                        <ArrowLeft className="h-5 w-5" />
                    </Button>
                    <img src={LOGO_URL} alt="RIGHTNAME" className="h-8" />
                </div>
                <div className="flex items-center gap-3">
                    <Badge variant="outline" className="hidden md:flex">
                        {query.category} • {query.countries?.length === 1 
                            ? getCountryName(query.countries[0])
                            : (query.countries?.length > 1 
                                ? `${query.countries.length} Countries` 
                                : query.market_scope)}
                    </Badge>
                    {isAuthenticated ? (
                        <Button 
                            onClick={handleDownloadPDF} 
                            disabled={downloading}
                            className="gap-2 bg-violet-600 hover:bg-violet-700 text-white rounded-xl"
                        >
                            {downloading ? (
                                <>
                                    <Loader2 className="h-4 w-4 animate-spin" /> Generating PDF...
                                </>
                            ) : (
                                <>
                                    <Download className="h-4 w-4" /> Download PDF
                                </>
                            )}
                        </Button>
                    ) : (
                        <Button onClick={handleRegister} className="gap-2 bg-violet-600 hover:bg-violet-700 text-white rounded-xl">
                            <Lock className="h-4 w-4" /> Unlock Full Report
                        </Button>
                    )}
                </div>
            </div>

            {/* Print Header */}
            <div className="hidden print:flex print:justify-between print:items-center print:px-4 print:py-2 print:border-b print:border-slate-200 print:mb-4">
                <img src={LOGO_URL} alt="RIGHTNAME" className="h-5" />
                <span className="text-xs text-slate-500">{currentDate}</span>
            </div>

            {/* Main Content */}
            <main ref={reportRef} className="max-w-5xl mx-auto px-6 py-8 space-y-8 print:px-2 print:py-2 print:space-y-4">
                
                {/* CTA Banner */}
                {!isAuthenticated && (
                    <div className="bg-gradient-to-r from-violet-600 via-fuchsia-500 to-orange-500 rounded-2xl p-6 text-white no-print">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <Lock className="w-10 h-10 opacity-80" />
                                <div>
                                    <h3 className="text-lg font-bold">Unlock Full Report</h3>
                                    <p className="text-sm opacity-80">Register free to see all sections</p>
                                </div>
                            </div>
                            <Button onClick={handleRegister} className="bg-white text-violet-700 hover:bg-slate-100 font-bold">
                                Register Now
                            </Button>
                        </div>
                    </div>
                )}

                {/* INPUT SUMMARY SECTION - Screen only (already on Cover Page for PDF) */}
                <section className="no-print">
                    <InputSummarySection 
                        query={query} 
                        brandName={brand.brand_name} 
                        reportId={data.report_id}
                        date={currentDate}
                    />
                </section>

                {/* SECTION 1: HERO */}
                <section className="print-section">
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 print:gap-4">
                        <div className="lg:col-span-2">
                            <PrintCard>
                                <div className="bg-white rounded-2xl p-6 border border-slate-200 print:p-4">
                                    <h1 className="text-5xl font-black text-slate-900 mb-3 print:text-4xl">{brand.brand_name}</h1>
                                    <div className="flex flex-wrap gap-2 mb-4">
                                        <Badge className="bg-slate-900 text-white font-bold">{brand.verdict}</Badge>
                                        <Badge variant="outline">{brand.positioning_fit}</Badge>
                                    </div>
                                    <div className="flex items-center gap-2 mb-3">
                                        <Star className="w-4 h-4 text-amber-500" />
                                        <span className="text-xs font-bold uppercase tracking-widest text-amber-600">Executive Summary</span>
                                    </div>
                                    <p className="text-slate-700 leading-relaxed print:text-sm">{data.executive_summary}</p>
                                </div>
                            </PrintCard>
                        </div>
                        <div className="space-y-4">
                            <ScoreCardRevamped score={brand.namescore} verdict={brand.verdict} />
                            {brand.dimensions && (
                                <PerformanceRadar dimensions={brand.dimensions} brandName={brand.brand_name} />
                            )}
                        </div>
                    </div>
                </section>

                {/* SECTION 2: QUICK DIMENSIONS */}
                <section className="print-section">
                    <QuickDimensionsGrid dimensions={brand.dimensions} />
                </section>

                {/* SECTION 3: FINAL ASSESSMENT - Pages 1&2 flow naturally */}
                {brand.final_assessment && (
                    <section className="print-section">
                        <SectionHeader icon={Zap} title="Final Assessment" subtitle="Consultant Verdict & Roadmap" color="emerald" />
                        {isAuthenticated ? (
                            <FinalAssessmentFull assessment={brand.final_assessment} verdict={brand.verdict} score={brand.namescore} />
                        ) : (
                            <LockedSection title="Final Assessment" onUnlock={handleRegister} />
                        )}
                    </section>
                )}

                {/* SECTION 4: STRATEGY SNAPSHOT - Still on Page 2 */}
                <section className="print-section">
                    <SectionHeader icon={Target} title="Strategy Snapshot" subtitle="Strengths and risks analysis" color="emerald" />
                    {isAuthenticated ? (
                        <StrategySnapshot classification={brand.strategic_classification} pros={brand.pros} cons={brand.cons} />
                    ) : (
                        <LockedSection title="Strategy Snapshot" onUnlock={handleRegister} />
                    )}
                </section>

                {/* PAGE 3: "WHAT'S IN THE NAME?" + DETAILED FRAMEWORK ANALYSIS */}
                {brand.dimensions && (
                    <section className="pdf-page-break print-new-page">
                        {/* Banner */}
                        <div className="bg-gradient-to-r from-violet-600 via-fuchsia-500 to-orange-500 rounded-2xl p-8 text-center mb-6">
                            <h2 className="text-3xl md:text-4xl font-black text-white tracking-tight">
                                What's in the Name?
                            </h2>
                            <p className="text-white/80 mt-2 text-lg">Deep dive into your brand's DNA</p>
                        </div>
                        
                        {/* Performance Radar Chart */}
                        <div className="mb-6">
                            <PerformanceRadar dimensions={brand.dimensions} brandName={brand.brand_name} />
                        </div>
                        
                        {/* Detailed Framework Analysis */}
                        <SectionHeader icon={BarChart3} title="Detailed Framework Analysis" subtitle="In-depth scoring breakdown" color="fuchsia" />
                        {isAuthenticated ? (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 print:gap-3">
                                {brand.dimensions.map((dim, i) => (
                                    <DetailedDimensionCard key={i} dimension={dim} index={i} />
                                ))}
                            </div>
                        ) : (
                            <LockedSection title="Detailed Framework Analysis" onUnlock={handleRegister} />
                        )}
                    </section>
                )}

                {/* SECTION 6: DIGITAL PRESENCE - New Page */}
                {(brand.multi_domain_availability || brand.social_availability) && (
                    <section className="print-section pdf-page-break print-new-page">
                        <SectionHeader icon={Globe} title="Digital Presence Check" subtitle="Domain & social availability" color="cyan" badge={`${brand.multi_domain_availability?.category_domains?.filter(d => d.available).length || 0}/${brand.multi_domain_availability?.category_domains?.length || 0} Available`} />
                        {isAuthenticated ? (
                            <DigitalPresenceSection 
                                multiDomain={brand.multi_domain_availability} 
                                domainAnalysis={brand.domain_analysis}
                                socialAvailability={brand.social_availability}
                            />
                        ) : (
                            <LockedSection title="Digital Presence Check" onUnlock={handleRegister} />
                        )}
                    </section>
                )}

                {/* SECTION 7: MARKET INTELLIGENCE - New Page */}
                {(brand.domain_analysis || brand.visibility_analysis || brand.cultural_analysis) && (
                    <section className="print-section pdf-page-break print-new-page">
                        <SectionHeader icon={TrendingUp} title="Market Intelligence" subtitle="Domain status, conflicts & cultural fit" color="amber" />
                        {isAuthenticated ? (
                            <MarketIntelligenceSection 
                                domainAnalysis={brand.domain_analysis}
                                visibilityAnalysis={brand.visibility_analysis}
                                culturalAnalysis={brand.cultural_analysis}
                            />
                        ) : (
                            <LockedSection title="Market Intelligence" onUnlock={handleRegister} />
                        )}
                    </section>
                )}

                {/* SECTION 8: COMPETITIVE LANDSCAPE - New Page */}
                {(brand.competitor_analysis || brand.country_competitor_analysis?.length > 0) && (
                    <section className="print-section pdf-page-break print-new-page">
                        <SectionHeader icon={Users} title="Competitive Landscape" subtitle="Strategic positioning matrix by market" color="blue" />
                        {isAuthenticated ? (
                            <CompetitiveLandscapeSection 
                                competitorAnalysis={brand.competitor_analysis} 
                                countryCompetitorAnalysis={brand.country_competitor_analysis}
                            />
                        ) : (
                            <LockedSection title="Competitive Landscape" onUnlock={handleRegister} />
                        )}
                    </section>
                )}

                {/* SECTION 9: LEGAL RISK MATRIX - New Page */}
                {brand.trademark_matrix && (
                    <section className="print-section pdf-page-break print-new-page">
                        <SectionHeader icon={Scale} title="Legal Risk Matrix" subtitle="IP Analysis & Trademark Assessment" color="red" />
                        {isAuthenticated ? (
                            <LegalRiskMatrix trademarkMatrix={brand.trademark_matrix} trademarkClasses={brand.trademark_classes} />
                        ) : (
                            <LockedSection title="Legal Risk Matrix" onUnlock={handleRegister} />
                        )}
                    </section>
                )}

                {/* SECTION 10: TRADEMARK RESEARCH - New Page */}
                {brand.trademark_research && (
                    <section className="print-section pdf-page-break print-new-page">
                        <SectionHeader icon={Shield} title="Trademark Research Intelligence" subtitle="Real-Time Conflict Discovery & Risk Analysis" color="violet" badge="NEW" />
                        {isAuthenticated ? (
                            <TrademarkResearchSection 
                                trademarkResearch={brand.trademark_research} 
                                registrationTimeline={brand.registration_timeline}
                                mitigationStrategies={brand.mitigation_strategies}
                            />
                        ) : (
                            <LockedSection title="Trademark Research Intelligence" onUnlock={handleRegister} />
                        )}
                    </section>
                )}

                {/* Bottom CTA */}
                {!isAuthenticated && (
                    <section className="no-print text-center py-8">
                        <div className="inline-block p-8 bg-white rounded-2xl border-2 border-dashed border-violet-200">
                            <Lock className="w-12 h-12 mx-auto mb-4 text-violet-400" />
                            <h3 className="text-2xl font-black text-slate-900 mb-2">Want the full picture?</h3>
                            <p className="text-slate-500 mb-6 max-w-md">Register free to unlock all sections</p>
                            <Button onClick={handleRegister} size="lg" className="bg-gradient-to-r from-violet-600 to-fuchsia-500 text-white font-bold rounded-xl px-8">
                                <Sparkles className="w-5 h-5 mr-2" /> Unlock Full Report
                            </Button>
                        </div>
                    </section>
                )}

                {/* Print Footer */}
                <div className="hidden print:block mt-4 pt-2 border-t border-slate-200 text-center text-xs text-slate-400">
                    <p>Generated by RIGHTNAME • {currentDate} • rightname.ai</p>
                </div>
            </main>
        </div>
    );
};

export default Dashboard;
