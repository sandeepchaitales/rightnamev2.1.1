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
const LOGO_URL = "https://customer-assets.emergentagent.com/job_naming-hub/artifacts/vj8cw9xx_R.png";

// ============ MARKDOWN TEXT FORMATTER ============
// Converts markdown-style text (**bold**, *italic*) to proper HTML
const formatMarkdownText = (text) => {
    if (!text || typeof text !== 'string') return text;
    
    // Remove unwanted headers and redundant info patterns
    let cleaned = text
        // Remove "RIGHTNAME BRAND EVALUATION REPORT" and similar headers
        .replace(/\*\*RIGHTNAME[^*]*\*\*/gi, '')
        .replace(/RIGHTNAME BRAND EVALUATION REPORT/gi, '')
        // Remove "Brand: xxx" patterns
        .replace(/\*\*Brand:[^*]*\*\*/gi, '')
        .replace(/Brand:\s*\w+/gi, '')
        // Remove "Category: xxx" patterns
        .replace(/\*\*Category:[^*]*\*\*/gi, '')
        .replace(/Category:\s*[\w\s]+/gi, '')
        // Remove "Verdict: xxx" patterns
        .replace(/\*\*Verdict:[^*]*\*\*/gi, '')
        .replace(/Verdict:\s*(GO|NO-GO|REJECT|CONDITIONAL GO)/gi, '')
        // Remove "Score: xxx" patterns
        .replace(/\*\*Score:[^*]*\*\*/gi, '')
        .replace(/Score:\s*\d+\/\d+/gi, '')
        // Remove standalone brand name + category + verdict + score line (e.g., "deepstorika streetwear fashion GO 80/100")
        .replace(/^\s*[\w]+\s+[\w\s]+\s+(GO|NO-GO|REJECT|CONDITIONAL GO)\s+\d+\/\d+\s*/gi, '')
        // Remove patterns like "**brandname** **category** **GO** **80/100**"
        .replace(/\*\*[\w]+\*\*\s*\*\*[\w\s]+\*\*\s*\*\*(GO|NO-GO|REJECT|CONDITIONAL GO)\*\*\s*\*\*\d+\/\d+\*\*/gi, '')
        .trim();
    
    // Convert **text** to <strong>text</strong>
    cleaned = cleaned.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    
    // Convert *text* to <em>text</em> (but not if already part of **)
    cleaned = cleaned.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');
    
    // Convert \n to <br/>
    cleaned = cleaned.replace(/\\n/g, '<br/>');
    
    // Clean up extra whitespace
    cleaned = cleaned.replace(/\s+/g, ' ').trim();
    
    return cleaned;
};

// Component to render markdown-formatted text
const MarkdownText = ({ text, className = "" }) => {
    const formattedText = formatMarkdownText(text);
    return (
        <span 
            className={className}
            dangerouslySetInnerHTML={{ __html: formattedText }}
        />
    );
};

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
    return (
        <div 
            className="cover-page-container"
            style={{ 
                position: 'absolute', 
                left: '-9999px', 
                visibility: 'hidden',
                width: '210mm'
            }}
        >
            {/* Logo - 1.2 inch = ~115px */}
            <div className="mb-6">
                <img 
                    src={LOGO_URL} 
                    alt="RIGHTNAME" 
                    style={{ width: '115px', height: '115px', objectFit: 'contain' }}
                    className="mx-auto"
                />
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
    // Debug logging
    console.log('[EVAL Dashboard] PerformanceRadar dimensions:', dimensions);
    console.log('[EVAL Dashboard] PerformanceRadar dimensions length:', dimensions?.length);
    
    // Fallback UI for missing data
    if (!dimensions || dimensions.length === 0) {
        console.warn('[EVAL Dashboard] PerformanceRadar: No dimensions data!');
        return (
            <PrintCard>
                <div className="bg-white rounded-2xl p-6 border border-slate-200 print:p-4">
                    <div className="flex items-center gap-2 mb-4">
                        <div className="w-8 h-8 rounded-lg bg-fuchsia-100 flex items-center justify-center">
                            <Target className="w-4 h-4 text-fuchsia-600" />
                        </div>
                        <div>
                            <h3 className="text-sm font-bold text-slate-800">Performance Radar</h3>
                            <p className="text-xs text-slate-500">Dimension Analysis</p>
                        </div>
                    </div>
                    <div className="h-64 flex items-center justify-center bg-slate-50 rounded-xl">
                        <div className="text-center">
                            <AlertTriangle className="w-10 h-10 text-amber-400 mx-auto mb-2" />
                            <p className="text-slate-500 text-sm">Dimension data not available</p>
                            <p className="text-slate-400 text-xs mt-1">Try refreshing or run evaluation again</p>
                        </div>
                    </div>
                </div>
            </PrintCard>
        );
    }
    
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
const QuickDimensionsGrid = ({ dimensions }) => {
    // Debug logging
    console.log('[EVAL Dashboard] QuickDimensionsGrid dimensions:', dimensions);
    
    // Fallback UI for missing data
    if (!dimensions || dimensions.length === 0) {
        console.warn('[EVAL Dashboard] QuickDimensionsGrid: No dimensions data!');
        return (
            <PrintCard>
                <div className="bg-white rounded-2xl p-6 border border-slate-200 print:p-4">
                    <SubSectionHeader icon={BarChart3} title="Quick Dimensions" />
                    <div className="h-32 flex items-center justify-center bg-slate-50 rounded-xl">
                        <div className="text-center">
                            <AlertTriangle className="w-8 h-8 text-amber-400 mx-auto mb-2" />
                            <p className="text-slate-500 text-sm">Score data not available</p>
                        </div>
                    </div>
                </div>
            </PrintCard>
        );
    }
    
    return (
        <PrintCard>
            <div className="bg-white rounded-2xl p-6 border border-slate-200 print:p-4">
                <SubSectionHeader icon={BarChart3} title="Quick Dimensions" />
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 print:gap-3">
                    {dimensions.slice(0, 6).map((dim, i) => (
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
};

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
                            <p className="text-3xl font-black">{score || assessment.suitability_score || 'N/A'}/100</p>
                        </div>
                    </div>
                    {(assessment.bottom_line || assessment.verdict_statement) && (
                        <p className="mt-4 text-white/90 border-t border-white/20 pt-4 text-sm">
                            "<MarkdownText text={assessment.bottom_line || assessment.verdict_statement} />"
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
                                        <p className="text-xs text-slate-600 leading-relaxed"><MarkdownText text={rec.content} /></p>
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
                                    <p className="text-xs text-slate-600"><MarkdownText text={assessment.ip_strategy} /></p>
                                </div>
                            )}
                            {!assessment.recommendations && assessment.brand_narrative && (
                                <div className="bg-fuchsia-50 rounded-xl p-4 border border-fuchsia-200">
                                    <div className="flex items-center gap-2 mb-2">
                                        <MessageSquare className="w-4 h-4 text-fuchsia-600" />
                                        <h5 className="font-bold text-fuchsia-800 text-sm">Brand Narrative</h5>
                                    </div>
                                    <p className="text-xs text-slate-600"><MarkdownText text={assessment.brand_narrative} /></p>
                                </div>
                            )}
                            {!assessment.recommendations && assessment.launch_tactics && (
                                <div className="bg-orange-50 rounded-xl p-4 border border-orange-200">
                                    <div className="flex items-center gap-2 mb-2">
                                        <Rocket className="w-4 h-4 text-orange-600" />
                                        <h5 className="font-bold text-orange-800 text-sm">Launch Tactics</h5>
                                    </div>
                                    <p className="text-xs text-slate-600"><MarkdownText text={assessment.launch_tactics} /></p>
                                </div>
                            )}
                        </div>
                        {(assessment.contingency_note || assessment.alternative_path) && (
                            <div className="mt-4 p-3 bg-slate-50 rounded-lg border border-slate-200">
                                <p className="text-xs text-slate-600 italic">💡 <MarkdownText text={assessment.contingency_note || assessment.alternative_path} /></p>
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
                                    <p className="text-sm text-slate-700"><MarkdownText text={step} /></p>
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
                    <p className="text-lg font-bold text-violet-900 italic text-center">
                        <MarkdownText text={classification} />
                    </p>
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
                        {pros && pros.length > 0 ? (
                            pros.map((pro, i) => (
                                <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                                    <span className="text-emerald-500 mt-0.5">✓</span>
                                    <MarkdownText text={pro} />
                                </li>
                            ))
                        ) : (
                            <li className="text-sm text-slate-500 italic">No specific strengths identified in this analysis.</li>
                        )}
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
                        {cons && cons.length > 0 ? (
                            cons.map((con, i) => (
                                <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                                    <span className="text-amber-500 mt-0.5">!</span>
                                    <MarkdownText text={con} />
                                </li>
                            ))
                        ) : (
                            <li className="text-sm text-slate-500 italic">No significant risks identified. Proceed with standard brand registration precautions.</li>
                        )}
                    </ul>
                </div>
            </div>
        </PrintCard>
    </div>
);

// ============ DETAILED DIMENSION CARD ============
const DetailedDimensionCard = ({ dimension, index }) => {
    // Debug logging
    console.log(`[EVAL Dashboard] DetailedDimensionCard ${index}:`, dimension);
    
    // Fallback for missing dimension
    if (!dimension) {
        return (
            <PrintCard>
                <div className="bg-slate-50 border border-slate-200 rounded-xl p-6 text-center">
                    <AlertTriangle className="w-8 h-8 text-amber-400 mx-auto mb-2" />
                    <p className="text-sm text-slate-500">Dimension data unavailable</p>
                </div>
            </PrintCard>
        );
    }
    
    const icons = ['✨', '🌍', '💎', '📈', '⚖️', '🎯', '🔮', '🎨'];
    const getScoreColor = (score) => {
        if (score >= 8) return 'from-emerald-400 to-emerald-500 bg-emerald-100 text-emerald-700';
        if (score >= 6) return 'from-violet-400 to-fuchsia-500 bg-violet-100 text-violet-700';
        return 'from-amber-400 to-orange-500 bg-amber-100 text-amber-700';
    };
    const colors = getScoreColor(dimension.score || 0);
    
    // Parse sub-sections from reasoning if available
    const parseReasoning = (text) => {
        if (!text) return { main: '', sections: [] };
        const sections = [];
        
        // Pattern 1: **HEADER:** content (most common format)
        // Matches: **PHONETIC ARCHITECTURE:**\nContent here...
        const headerPattern = /\*\*([A-Z][A-Z\s&]+):\*\*\s*\n?([^*]+?)(?=\*\*[A-Z]|$)/gi;
        
        let match;
        while ((match = headerPattern.exec(text)) !== null) {
            const title = match[1].trim();
            const content = match[2].trim();
            if (title && content) {
                sections.push({ title, content });
            }
        }
        
        // Pattern 2: HEADER:\n content (alternate format without **)
        if (sections.length === 0) {
            const altPattern = /([A-Z][A-Z\s&]+):\s*\n?([^A-Z\n]+(?:\n[^A-Z\n]+)*)/g;
            while ((match = altPattern.exec(text)) !== null) {
                const title = match[1].trim();
                const content = match[2].trim();
                if (title && content && title.length > 3) {
                    sections.push({ title, content });
                }
            }
        }
        
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
                                    <p className="text-xs text-slate-600"><MarkdownText text={sec.content} /></p>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="text-sm text-slate-600 leading-relaxed"><MarkdownText text={dimension.reasoning} /></p>
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
                                <p className="text-xs text-blue-700"><MarkdownText text={socialAvailability.recommendation} /></p>
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
            
            {/* Cultural Fit - UPDATED: Vertical stack, dynamic score only, no formula shown */}
            {culturalAnalysis?.length > 0 && (
                <PrintCard>
                    <div className="bg-white rounded-2xl p-6 border border-slate-200">
                        <SubSectionHeader icon={Globe} title="Cultural Fit Analysis" />
                        
                        {/* Vertical stack - one country after another */}
                        <div className="space-y-4">
                            {culturalAnalysis.map((c, i) => {
                                const countryName = typeof c.country === 'object' ? c.country?.name : c.country;
                                
                                // Get the DYNAMIC calculated score (single source of truth)
                                const finalScore = c.score_breakdown?.final_score || c.cultural_resonance_score || 0;
                                const riskVerdict = c.score_breakdown?.risk_verdict || 
                                    (finalScore >= 7 ? 'SAFE' : finalScore >= 5 ? 'CAUTION' : 'CRITICAL');
                                
                                // Status colors based on verdict
                                const statusConfig = {
                                    'SAFE': { 
                                        bg: 'bg-emerald-50', 
                                        border: 'border-emerald-200', 
                                        text: 'text-emerald-700',
                                        badge: 'bg-emerald-100 text-emerald-800',
                                        icon: '✅'
                                    },
                                    'CAUTION': { 
                                        bg: 'bg-amber-50', 
                                        border: 'border-amber-200', 
                                        text: 'text-amber-700',
                                        badge: 'bg-amber-100 text-amber-800',
                                        icon: '⚠️'
                                    },
                                    'CRITICAL': { 
                                        bg: 'bg-red-50', 
                                        border: 'border-red-200', 
                                        text: 'text-red-700',
                                        badge: 'bg-red-100 text-red-800',
                                        icon: '🔴'
                                    }
                                };
                                const status = statusConfig[riskVerdict] || statusConfig['CAUTION'];
                                
                                // Get sub-scores for display (without formula)
                                const safetyScore = c.score_breakdown?.safety_score;
                                const fluencyScore = c.score_breakdown?.fluency_score;
                                const vibeScore = c.score_breakdown?.vibe_score;
                                
                                // Clean cultural notes - remove formula display from notes
                                let cleanNotes = c.cultural_notes || '';
                                // Remove the formula section from notes (keep other content)
                                cleanNotes = cleanNotes.replace(/\*\*📊 CULTURAL FIT SCORE:.*?\*\*\n/g, '');
                                cleanNotes = cleanNotes.replace(/\*\*Formula:\*\*.*?\n/g, '');
                                cleanNotes = cleanNotes.replace(/\*\*Calculation:\*\*.*?\n/g, '');
                                cleanNotes = cleanNotes.replace(/\*\*Verdict:\*\*.*?\n/g, '');
                                cleanNotes = cleanNotes.replace(/---\n\*\*🛡️ SAFETY SCORE:.*?(?=---|\*\*🔤|$)/gs, '');
                                cleanNotes = cleanNotes.replace(/\*\*🗣️ FLUENCY SCORE:.*?\n/g, '');
                                cleanNotes = cleanNotes.replace(/\*\*✨ VIBE SCORE:.*?\n/g, '');
                                cleanNotes = cleanNotes.replace(/\s*Issues:.*?\n/g, '');
                                cleanNotes = cleanNotes.replace(/\s*Difficult sounds:.*?\n/g, '');
                                cleanNotes = cleanNotes.replace(/\s*Local competitors:.*?\n/g, '');
                                cleanNotes = cleanNotes.trim();
                                
                                return (
                                    <div key={i} className={`${status.bg} ${status.border} border rounded-xl p-5`}>
                                        {/* Header: Country + Score + Status */}
                                        <div className="flex items-center justify-between mb-4">
                                            <div className="flex items-center gap-3">
                                                <span className="text-3xl">{c.country_flag || '🌍'}</span>
                                                <div>
                                                    <h4 className="font-bold text-slate-800 text-lg">{countryName}</h4>
                                                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${status.badge}`}>
                                                        {status.icon} {riskVerdict}
                                                    </span>
                                                </div>
                                            </div>
                                            
                                            {/* FINAL SCORE - Single Source of Truth */}
                                            <div className="text-right">
                                                <div className={`text-4xl font-black ${status.text}`}>
                                                    {finalScore.toFixed(1)}
                                                </div>
                                                <div className="text-xs text-slate-500 font-medium">out of 10</div>
                                            </div>
                                        </div>
                                        
                                        {/* Sub-scores (without formula - internal only) */}
                                        {(safetyScore !== undefined || fluencyScore !== undefined || vibeScore !== undefined) && (
                                            <div className="grid grid-cols-3 gap-3 mb-4">
                                                {safetyScore !== undefined && (
                                                    <div className="bg-white/60 rounded-lg p-3 text-center">
                                                        <div className="text-xs text-slate-500 mb-1">Safety</div>
                                                        <div className="text-lg font-bold text-slate-700">{safetyScore}/10</div>
                                                        <div className="text-xs text-slate-400">Phonetic risks</div>
                                                    </div>
                                                )}
                                                {fluencyScore !== undefined && (
                                                    <div className="bg-white/60 rounded-lg p-3 text-center">
                                                        <div className="text-xs text-slate-500 mb-1">Fluency</div>
                                                        <div className="text-lg font-bold text-slate-700">{fluencyScore}/10</div>
                                                        <div className="text-xs text-slate-400">Pronunciation</div>
                                                    </div>
                                                )}
                                                {vibeScore !== undefined && (
                                                    <div className="bg-white/60 rounded-lg p-3 text-center">
                                                        <div className="text-xs text-slate-500 mb-1">Vibe</div>
                                                        <div className="text-lg font-bold text-slate-700">{vibeScore}/10</div>
                                                        <div className="text-xs text-slate-400">Market fit</div>
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                        
                                        {/* Cultural Notes - cleaned (no formula shown) */}
                                        {cleanNotes && (
                                            <div className="text-sm text-slate-600 leading-relaxed">
                                                <MarkdownText text={cleanNotes} />
                                            </div>
                                        )}
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
    
    // Country colors for different markets - extended to support 8+ countries
    const countryColors = [
        { bg: 'from-blue-500 to-indigo-500', light: 'bg-blue-50 border-blue-200', text: 'text-blue-700' },
        { bg: 'from-emerald-500 to-teal-500', light: 'bg-emerald-50 border-emerald-200', text: 'text-emerald-700' },
        { bg: 'from-amber-500 to-orange-500', light: 'bg-amber-50 border-amber-200', text: 'text-amber-700' },
        { bg: 'from-rose-500 to-pink-500', light: 'bg-rose-50 border-rose-200', text: 'text-rose-700' },
        { bg: 'from-violet-500 to-purple-500', light: 'bg-violet-50 border-violet-200', text: 'text-violet-700' },
        { bg: 'from-cyan-500 to-sky-500', light: 'bg-cyan-50 border-cyan-200', text: 'text-cyan-700' },
        { bg: 'from-lime-500 to-green-500', light: 'bg-lime-50 border-lime-200', text: 'text-lime-700' },
        { bg: 'from-fuchsia-500 to-pink-500', light: 'bg-fuchsia-50 border-fuchsia-200', text: 'text-fuchsia-700' },
    ];
    
    // Parse axis labels into left/right and bottom/top
    const parseAxisLabels = (axisLabel) => {
        if (!axisLabel) return { low: 'Low', high: 'High' };
        const parts = axisLabel.split(':');
        if (parts.length < 2) return { low: 'Low', high: 'High' };
        const rangePart = parts[1].trim();
        const rangeMatch = rangePart.match(/(.+?)\s*[→→-]\s*(.+)/);
        if (rangeMatch) {
            return { low: rangeMatch[1].trim(), high: rangeMatch[2].trim() };
        }
        return { low: 'Low', high: 'High' };
    };
    
    // Render a single positioning matrix
    const renderMatrix = (analysis, title, colorScheme, showFlag = false) => {
        const comps = analysis.competitors || [];
        const xAxis = parseAxisLabels(analysis.x_axis_label);
        const yAxis = parseAxisLabels(analysis.y_axis_label);
        
        // Generate quadrant labels based on axes
        const quadrants = {
            topLeft: `${xAxis.low} + ${yAxis.high}`,
            topRight: `${xAxis.high} + ${yAxis.high}`,
            bottomLeft: `${xAxis.low} + ${yAxis.low}`,
            bottomRight: `${xAxis.high} + ${yAxis.low}`
        };
        
        return (
            <PrintCard key={title}>
                <div className="bg-white rounded-2xl p-6 border border-slate-200">
                    <div className="flex items-center justify-between mb-4">
                        <SubSectionHeader icon={BarChart3} title={title} />
                        {showFlag && analysis.country_flag && (
                            <span className="text-3xl">{analysis.country_flag}</span>
                        )}
                    </div>
                    
                    {/* Axis Labels Header */}
                    <div className="text-center mb-4">
                        <p className="text-xs text-slate-500">
                            <span className="font-semibold">X-Axis:</span> {analysis.x_axis_label || 'Price: Budget → Luxury'} | 
                            <span className="font-semibold ml-2">Y-Axis:</span> {analysis.y_axis_label || 'Style: Classic → Modern'}
                        </p>
                    </div>
                    
                    {/* Visual Matrix - Strategic Positioning Map */}
                    <div className="relative bg-gradient-to-br from-slate-50 to-white border border-slate-200 rounded-xl p-4 h-72">
                        {/* Grid lines - Axes */}
                        <div className="absolute inset-4 border-l-2 border-b-2 border-slate-300"></div>
                        {/* Center cross lines */}
                        <div className="absolute left-1/2 top-4 bottom-4 border-l border-dashed border-slate-300"></div>
                        <div className="absolute left-4 right-4 top-1/2 border-t border-dashed border-slate-300"></div>
                        
                        {/* Quadrant Labels */}
                        <div className="absolute top-5 left-5 text-[10px] text-slate-400 max-w-[80px] leading-tight">{quadrants.topLeft}</div>
                        <div className="absolute top-5 right-5 text-[10px] text-slate-400 text-right max-w-[80px] leading-tight font-semibold text-emerald-600">{quadrants.topRight}</div>
                        <div className="absolute bottom-5 left-5 text-[10px] text-slate-400 max-w-[80px] leading-tight">{quadrants.bottomLeft}</div>
                        <div className="absolute bottom-5 right-5 text-[10px] text-slate-400 text-right max-w-[80px] leading-tight">{quadrants.bottomRight}</div>
                        
                        {/* Axis End Labels */}
                        <div className="absolute bottom-0 left-4 text-[9px] text-slate-500">{xAxis.low}</div>
                        <div className="absolute bottom-0 right-4 text-[9px] text-slate-500">{xAxis.high}</div>
                        <div className="absolute top-4 left-0 text-[9px] text-slate-500 -rotate-90 origin-left translate-y-4">{yAxis.high}</div>
                        <div className="absolute bottom-4 left-0 text-[9px] text-slate-500 -rotate-90 origin-left translate-y-4">{yAxis.low}</div>
                        
                        {/* Empty state message */}
                        {comps.length === 0 && !analysis.user_brand_position && (
                            <div className="absolute inset-0 flex items-center justify-center">
                                <p className="text-slate-400 text-sm">Competitor data not available</p>
                            </div>
                        )}
                        
                        {/* Plot competitors as grey/colored dots */}
                        {comps.slice(0, 6).map((comp, i) => {
                            const x = (comp.x_coordinate || 50) / 100 * 80 + 10;
                            const y = 100 - ((comp.y_coordinate || 50) / 100 * 80 + 10);
                            return (
                                <div
                                    key={i}
                                    className="absolute transform -translate-x-1/2 -translate-y-1/2 group z-10"
                                    style={{ left: `${x}%`, top: `${y}%` }}
                                >
                                    <div className="w-8 h-8 bg-slate-500 hover:bg-slate-600 rounded-full flex items-center justify-center text-white text-xs font-bold shadow-md transition-all cursor-pointer">
                                        {i + 1}
                                    </div>
                                    <div className="hidden group-hover:block absolute top-full left-1/2 transform -translate-x-1/2 mt-1 px-2 py-1 bg-slate-800 text-white text-xs rounded whitespace-nowrap z-20 shadow-lg">
                                        <span className="font-semibold">{comp.name}</span>
                                        {comp.quadrant && <span className="text-slate-300 ml-1">• {comp.quadrant}</span>}
                                    </div>
                                </div>
                            );
                        })}
                        
                        {/* User brand position - GOLD/HIGHLIGHTED */}
                        {analysis.user_brand_position && (
                            <div
                                className="absolute transform -translate-x-1/2 -translate-y-1/2 z-20 group"
                                style={{
                                    left: `${(analysis.user_brand_position.x_coordinate || analysis.user_brand_position.x || 70) / 100 * 80 + 10}%`,
                                    top: `${100 - ((analysis.user_brand_position.y_coordinate || analysis.user_brand_position.y || 70) / 100 * 80 + 10)}%`
                                }}
                            >
                                <div className="w-10 h-10 bg-gradient-to-r from-amber-400 to-yellow-500 rounded-full flex items-center justify-center text-amber-900 text-[10px] font-bold shadow-lg border-2 border-white animate-pulse">
                                    YOU
                                </div>
                                {analysis.user_brand_position.quadrant && (
                                    <div className="hidden group-hover:block absolute top-full left-1/2 transform -translate-x-1/2 mt-1 px-2 py-1 bg-amber-600 text-white text-xs rounded whitespace-nowrap z-20 shadow-lg">
                                        <span className="font-semibold">{analysis.user_brand_position.quadrant}</span>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                    
                    {/* Legend with improved styling */}
                    <div className="mt-4 p-3 bg-slate-50 rounded-lg">
                        <div className="flex flex-wrap items-center gap-3">
                            {/* User Brand Legend */}
                            <div className="flex items-center gap-2 text-xs border-r border-slate-300 pr-3">
                                <div className="w-5 h-5 bg-gradient-to-r from-amber-400 to-yellow-500 rounded-full flex items-center justify-center text-amber-900 text-[8px] font-bold">Y</div>
                                <span className="text-slate-700 font-semibold">Your Brand</span>
                            </div>
                            {/* Competitors Legend */}
                            {comps.slice(0, 6).map((comp, i) => (
                                <div key={i} className="flex items-center gap-1 text-xs">
                                    <div className="w-5 h-5 bg-slate-500 rounded-full flex items-center justify-center text-white text-[9px] font-bold">{i + 1}</div>
                                    <span className="text-slate-600">{comp.name}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                    
                    {/* Market Insights */}
                    <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
                        {analysis.white_space_analysis && (
                            <div className={`p-3 rounded-lg border ${colorScheme.light}`}>
                                <p className={`text-xs font-bold ${colorScheme.text} mb-1`}>White Space</p>
                                <p className="text-xs text-slate-600"><MarkdownText text={analysis.white_space_analysis} /></p>
                            </div>
                        )}
                        {analysis.strategic_advantage && (
                            <div className={`p-3 rounded-lg border ${colorScheme.light}`}>
                                <p className={`text-xs font-bold ${colorScheme.text} mb-1`}>Strategic Advantage</p>
                                <p className="text-xs text-slate-600"><MarkdownText text={analysis.strategic_advantage} /></p>
                            </div>
                        )}
                    </div>
                    
                    {/* Market Entry Recommendation (for country-specific) */}
                    {analysis.market_entry_recommendation && (
                        <div className="mt-3 p-3 bg-violet-50 rounded-lg border border-violet-200">
                            <p className="text-xs font-bold text-violet-700 mb-1">Market Entry Recommendation</p>
                            <p className="text-xs text-slate-600"><MarkdownText text={analysis.market_entry_recommendation} /></p>
                        </div>
                    )}
                </div>
            </PrintCard>
        );
    };
    
    return (
        <div className="space-y-4">
            {/* Global/Overall Strategic Positioning Matrix - ALWAYS show if competitorAnalysis exists */}
            {competitorAnalysis && (
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
                                
                                {/* Plot competitors - show message if empty */}
                                {competitors.length === 0 && (
                                    <div className="absolute inset-0 flex items-center justify-center">
                                        <p className="text-slate-400 text-sm">Competitor data not available</p>
                                    </div>
                                )}
                                {/* Competitors - Grey dots */}
                                {competitors.slice(0, 6).map((comp, i) => {
                                    const x = (comp.x_coordinate || 50) / 100 * 80 + 10;
                                    const y = 100 - ((comp.y_coordinate || 50) / 100 * 80 + 10);
                                    return (
                                        <div
                                            key={i}
                                            className="absolute transform -translate-x-1/2 -translate-y-1/2 group z-10"
                                            style={{ left: `${x}%`, top: `${y}%` }}
                                        >
                                            <div className="w-8 h-8 bg-slate-500 hover:bg-slate-600 rounded-full flex items-center justify-center text-white text-xs font-bold shadow-md transition-all cursor-pointer">
                                                {i + 1}
                                            </div>
                                            <div className="hidden group-hover:block absolute top-full left-1/2 transform -translate-x-1/2 mt-1 px-2 py-1 bg-slate-800 text-white text-xs rounded whitespace-nowrap z-20 shadow-lg">
                                                <span className="font-semibold">{comp.name}</span>
                                                {comp.quadrant && <span className="text-slate-300 ml-1">• {comp.quadrant}</span>}
                                            </div>
                                        </div>
                                    );
                                })}
                                
                                {/* User brand position - GOLD/HIGHLIGHTED */}
                                {competitorAnalysis.user_brand_position && (
                                    <div
                                        className="absolute transform -translate-x-1/2 -translate-y-1/2 z-20 group"
                                        style={{
                                            left: `${(competitorAnalysis.user_brand_position.x || competitorAnalysis.user_brand_position.x_coordinate || 70) / 100 * 80 + 10}%`,
                                            top: `${100 - ((competitorAnalysis.user_brand_position.y || competitorAnalysis.user_brand_position.y_coordinate || 70) / 100 * 80 + 10)}%`
                                        }}
                                    >
                                        <div className="w-10 h-10 bg-gradient-to-r from-amber-400 to-yellow-500 rounded-full flex items-center justify-center text-amber-900 text-[10px] font-bold shadow-lg border-2 border-white animate-pulse">
                                            YOU
                                        </div>
                                        {competitorAnalysis.user_brand_position.quadrant && (
                                            <div className="hidden group-hover:block absolute top-full left-1/2 transform -translate-x-1/2 mt-1 px-2 py-1 bg-amber-600 text-white text-xs rounded whitespace-nowrap z-20 shadow-lg">
                                                <span className="font-semibold">{competitorAnalysis.user_brand_position.quadrant}</span>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                            
                            {/* Legend with improved styling */}
                            <div className="mt-4 p-3 bg-slate-50 rounded-lg">
                                <div className="flex flex-wrap items-center gap-3">
                                    {/* User Brand Legend */}
                                    <div className="flex items-center gap-2 text-xs border-r border-slate-300 pr-3">
                                        <div className="w-5 h-5 bg-gradient-to-r from-amber-400 to-yellow-500 rounded-full flex items-center justify-center text-amber-900 text-[8px] font-bold">Y</div>
                                        <span className="text-slate-700 font-semibold">Your Brand</span>
                                    </div>
                                    {/* Competitors Legend */}
                                    {competitors.slice(0, 6).map((comp, i) => (
                                        <div key={i} className="flex items-center gap-2 text-xs">
                                            <div className="w-5 h-5 bg-slate-500 rounded-full flex items-center justify-center text-white text-[9px] font-bold">{i + 1}</div>
                                            <span className="text-slate-600">{comp.name}</span>
                                            {comp.quadrant && <Badge variant="outline" className="text-xs">{comp.quadrant}</Badge>}
                                        </div>
                                    ))}
                                </div>
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
                                    <p className="text-sm text-slate-700"><MarkdownText text={competitorAnalysis.white_space_analysis} /></p>
                                </div>
                            )}
                            {competitorAnalysis.strategic_advantage && (
                                <div className="bg-violet-50 rounded-xl p-5 border border-violet-200">
                                    <div className="flex items-center gap-2 mb-3">
                                        <Target className="w-5 h-5 text-violet-600" />
                                        <h4 className="font-bold text-violet-700">Strategic Advantage</h4>
                                    </div>
                                    <p className="text-sm text-slate-700"><MarkdownText text={competitorAnalysis.strategic_advantage} /></p>
                                </div>
                            )}
                        </div>
                    </PrintCard>
                </>
            )}
            
            {/* Country-Specific Positioning Matrices - Show ALL countries */}
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
                        {countryCompetitorAnalysis.map((countryAnalysis, idx) => {
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
                                        <p className="text-xs text-slate-600 mt-2"><MarkdownText text={conflict.details} /></p>
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
            
            {/* Legal Precedents - Updated for Country-Wise Structure */}
            {trademarkResearch.legal_precedents && trademarkResearch.legal_precedents.length > 0 && (
                <PrintCard>
                    <div className="bg-white rounded-2xl p-6 border border-violet-200">
                        <SubSectionHeader icon={Scale} title="Relevant Legal Precedents" color="violet" />
                        
                        <div className="space-y-4">
                            {trademarkResearch.legal_precedents.map((countryPrecedent, i) => (
                                <div key={i} className="border border-violet-100 rounded-xl overflow-hidden">
                                    {/* Country Header */}
                                    <div className="bg-violet-100 px-4 py-2 flex items-center gap-2">
                                        <span className="text-xl">{countryPrecedent.country_flag || '🌍'}</span>
                                        <span className="font-bold text-violet-800">{countryPrecedent.country || 'Unknown'}</span>
                                    </div>
                                    
                                    {/* Precedents for this country */}
                                    <div className="p-4 space-y-3">
                                        {countryPrecedent.precedents && countryPrecedent.precedents.map((precedent, j) => (
                                            <div key={j} className="p-3 bg-violet-50 rounded-lg border border-violet-100">
                                                <div className="font-bold text-violet-800 mb-1">{precedent.case_name}</div>
                                                <div className="text-xs text-slate-600 mb-2">
                                                    {precedent.court && <span>{precedent.court}</span>}
                                                    {precedent.year && <span> • {precedent.year}</span>}
                                                </div>
                                                {precedent.relevance && (
                                                    <p className="text-sm text-slate-700"><MarkdownText text={precedent.relevance} /></p>
                                                )}
                                                {precedent.key_principle && (
                                                    <p className="text-xs text-violet-600 mt-2 italic">Key Principle: <MarkdownText text={precedent.key_principle} /></p>
                                                )}
                                            </div>
                                        ))}
                                        
                                        {/* Fallback for old format (flat precedent objects) */}
                                        {!countryPrecedent.precedents && countryPrecedent.case_name && (
                                            <div className="p-3 bg-violet-50 rounded-lg border border-violet-100">
                                                <div className="font-bold text-violet-800 mb-1">{countryPrecedent.case_name}</div>
                                                <div className="text-xs text-slate-600 mb-2">
                                                    {countryPrecedent.court && <span>{countryPrecedent.court}</span>}
                                                    {countryPrecedent.year && <span> • {countryPrecedent.year}</span>}
                                                </div>
                                                {countryPrecedent.relevance && (
                                                    <p className="text-sm text-slate-700"><MarkdownText text={countryPrecedent.relevance} /></p>
                                                )}
                                                {countryPrecedent.key_principle && (
                                                    <p className="text-xs text-violet-600 mt-2 italic">Key Principle: <MarkdownText text={countryPrecedent.key_principle} /></p>
                                                )}
                                            </div>
                                        )}
                                    </div>
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
                                        <span className="font-bold text-slate-800"><MarkdownText text={strategy.action} /></span>
                                        <Badge className={
                                            strategy.priority === 'HIGH' ? 'bg-red-600 text-white' :
                                            strategy.priority === 'MEDIUM' ? 'bg-amber-500 text-white' :
                                            'bg-emerald-500 text-white'
                                        }>{strategy.priority}</Badge>
                                    </div>
                                    <p className="text-sm text-slate-600"><MarkdownText text={strategy.rationale} /></p>
                                    {strategy.estimated_cost && (
                                        <div className="text-xs text-slate-500 mt-2">Estimated Cost: {strategy.estimated_cost}</div>
                                    )}
                                    {strategy.timeline && (
                                        <div className="text-xs text-slate-500 mt-1">Timeline: {strategy.timeline}</div>
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

// ============ McKINSEY THREE-QUESTION FRAMEWORK ANALYSIS ============
const McKinseyAnalysisSection = ({ mckinsey }) => {
    if (!mckinsey) return null;
    
    const { benefits_experiences, distinctiveness, brand_architecture, executive_recommendation, recommendation_rationale, critical_assessment, alternative_directions } = mckinsey;
    
    const getRecommendationColor = (rec) => {
        switch (rec?.toUpperCase()) {
            case 'PROCEED': return 'bg-emerald-100 text-emerald-700 border-emerald-300';
            case 'REFINE': return 'bg-amber-100 text-amber-700 border-amber-300';
            case 'PIVOT': return 'bg-red-100 text-red-700 border-red-300';
            default: return 'bg-slate-100 text-slate-700 border-slate-300';
        }
    };
    
    const getScoreColor = (score) => {
        if (score >= 8) return 'text-emerald-600';
        if (score >= 5) return 'text-amber-600';
        return 'text-red-600';
    };
    
    const ScoreCircle = ({ score, label }) => (
        <div className="flex flex-col items-center">
            <div className={`w-16 h-16 rounded-full border-4 flex items-center justify-center ${
                score >= 8 ? 'border-emerald-400 bg-emerald-50' :
                score >= 5 ? 'border-amber-400 bg-amber-50' :
                'border-red-400 bg-red-50'
            }`}>
                <span className={`text-2xl font-black ${getScoreColor(score)}`}>{score}</span>
            </div>
            <span className="text-xs text-slate-500 mt-1 text-center">{label}</span>
        </div>
    );
    
    return (
        <div className="space-y-4">
            {/* Executive Recommendation Banner */}
            <PrintCard>
                <div className={`rounded-2xl p-6 border-2 ${getRecommendationColor(executive_recommendation)}`}>
                    <div className="flex items-center justify-between flex-wrap gap-4">
                        <div>
                            <div className="text-sm font-medium opacity-80">Three-Pillar Assessment Verdict</div>
                            <div className="text-3xl font-black">{executive_recommendation || 'ANALYZING'}</div>
                        </div>
                        <div className="flex-1 max-w-xl">
                            <p className="text-sm">{recommendation_rationale}</p>
                        </div>
                    </div>
                    {critical_assessment && (
                        <div className="mt-4 p-3 bg-white/50 rounded-lg">
                            <div className="text-xs font-bold uppercase tracking-wide mb-1">Critical Assessment</div>
                            <p className="text-sm italic"><MarkdownText text={critical_assessment} /></p>
                        </div>
                    )}
                </div>
            </PrintCard>
            
            {/* Module 1: Benefits & Experiences */}
            {benefits_experiences && (
                <PrintCard>
                    <div className="bg-white rounded-2xl p-6 border border-violet-200">
                        <div className="flex items-center gap-2 mb-4">
                            <div className="w-8 h-8 bg-violet-100 rounded-lg flex items-center justify-center">
                                <Sparkles className="w-4 h-4 text-violet-600" />
                            </div>
                            <div>
                                <h4 className="font-bold text-slate-800">Module 1: Benefits & Experiences</h4>
                                <p className="text-xs text-slate-500">Semantic Audit - What does the name promise?</p>
                            </div>
                        </div>
                        
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                            <div className="p-3 bg-violet-50 rounded-lg">
                                <div className="text-xs font-bold text-violet-600 uppercase mb-1">Linguistic Roots</div>
                                <p className="text-sm text-slate-700">{benefits_experiences.linguistic_roots}</p>
                            </div>
                            <div className="p-3 bg-fuchsia-50 rounded-lg">
                                <div className="text-xs font-bold text-fuchsia-600 uppercase mb-1">Phonetic Analysis</div>
                                <p className="text-sm text-slate-700">{benefits_experiences.phonetic_analysis}</p>
                            </div>
                        </div>
                        
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                            {benefits_experiences.emotional_promises?.length > 0 && (
                                <div>
                                    <div className="text-xs font-bold text-slate-500 uppercase mb-2">Emotional Promises</div>
                                    <div className="flex flex-wrap gap-1">
                                        {benefits_experiences.emotional_promises.map((promise, i) => (
                                            <Badge key={i} className="bg-pink-100 text-pink-700">{promise}</Badge>
                                        ))}
                                    </div>
                                </div>
                            )}
                            {benefits_experiences.functional_benefits?.length > 0 && (
                                <div>
                                    <div className="text-xs font-bold text-slate-500 uppercase mb-2">Functional Benefits</div>
                                    <div className="flex flex-wrap gap-1">
                                        {benefits_experiences.functional_benefits.map((benefit, i) => (
                                            <Badge key={i} className="bg-blue-100 text-blue-700">{benefit}</Badge>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                        
                        {/* Benefit Map Table */}
                        {benefits_experiences.benefit_map?.length > 0 && (
                            <div className="mt-4">
                                <div className="text-xs font-bold text-slate-500 uppercase mb-2">Benefit Map</div>
                                <div className="overflow-x-auto">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="bg-slate-100">
                                                <th className="text-left p-2 rounded-tl-lg">Name Trait</th>
                                                <th className="text-left p-2">User Perception</th>
                                                <th className="text-left p-2 rounded-tr-lg">Type</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {benefits_experiences.benefit_map.map((item, i) => (
                                                <tr key={i} className="border-b border-slate-100">
                                                    <td className="p-2 font-medium">{item.name_trait}</td>
                                                    <td className="p-2">{item.user_perception}</td>
                                                    <td className="p-2">
                                                        <Badge className={item.benefit_type === 'Emotional' ? 'bg-pink-100 text-pink-700' : 'bg-blue-100 text-blue-700'}>
                                                            {item.benefit_type}
                                                        </Badge>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        )}
                        
                        {benefits_experiences.target_persona_fit && (
                            <div className="mt-4 p-3 bg-slate-50 rounded-lg">
                                <div className="text-xs font-bold text-slate-500 uppercase mb-1">Target Persona Fit</div>
                                <p className="text-sm text-slate-700">{benefits_experiences.target_persona_fit}</p>
                            </div>
                        )}
                    </div>
                </PrintCard>
            )}
            
            {/* Module 2: Distinctiveness */}
            {distinctiveness && (
                <PrintCard>
                    <div className="bg-white rounded-2xl p-6 border border-amber-200">
                        <div className="flex items-center gap-2 mb-4">
                            <div className="w-8 h-8 bg-amber-100 rounded-lg flex items-center justify-center">
                                <Target className="w-4 h-4 text-amber-600" />
                            </div>
                            <div>
                                <h4 className="font-bold text-slate-800">Module 2: Distinctiveness</h4>
                                <p className="text-xs text-slate-500">Market Comparison - How unique is this name?</p>
                            </div>
                        </div>
                        
                        <div className="flex items-center gap-6 mb-4">
                            <ScoreCircle score={distinctiveness.distinctiveness_score || 0} label="Distinctiveness" />
                            <div className="flex-1">
                                <div className="flex items-center gap-2 mb-2">
                                    <span className="text-sm font-medium text-slate-600">Category Noise Level:</span>
                                    <Badge className={
                                        distinctiveness.category_noise_level === 'HIGH' ? 'bg-red-100 text-red-700' :
                                        distinctiveness.category_noise_level === 'MEDIUM' ? 'bg-amber-100 text-amber-700' :
                                        'bg-emerald-100 text-emerald-700'
                                    }>{distinctiveness.category_noise_level || 'N/A'}</Badge>
                                </div>
                                <p className="text-sm text-slate-600">{distinctiveness.industry_comparison}</p>
                            </div>
                        </div>
                        
                        {distinctiveness.naming_tropes_analysis && (
                            <div className="p-3 bg-amber-50 rounded-lg mb-4">
                                <div className="text-xs font-bold text-amber-600 uppercase mb-1">Naming Tropes Analysis</div>
                                <p className="text-sm text-slate-700">{distinctiveness.naming_tropes_analysis}</p>
                            </div>
                        )}
                        
                        {/* Similar Competitors */}
                        {distinctiveness.similar_competitors?.length > 0 && (
                            <div className="mb-4">
                                <div className="text-xs font-bold text-slate-500 uppercase mb-2">Similar Competitors</div>
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                                    {distinctiveness.similar_competitors.map((comp, i) => (
                                        <div key={i} className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                                            <div className="flex items-center justify-between mb-1">
                                                <span className="font-medium text-slate-800">{comp.name}</span>
                                                <Badge className={
                                                    comp.risk_level === 'HIGH' ? 'bg-red-100 text-red-700' :
                                                    comp.risk_level === 'MEDIUM' ? 'bg-amber-100 text-amber-700' :
                                                    'bg-emerald-100 text-emerald-700'
                                                }>{comp.risk_level}</Badge>
                                            </div>
                                            <p className="text-xs text-slate-500">{comp.similarity_aspect}</p>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                        
                        {/* Differentiation Opportunities */}
                        {distinctiveness.differentiation_opportunities?.length > 0 && (
                            <div>
                                <div className="text-xs font-bold text-slate-500 uppercase mb-2">Differentiation Opportunities</div>
                                <div className="flex flex-wrap gap-2">
                                    {distinctiveness.differentiation_opportunities.map((opp, i) => (
                                        <div key={i} className="flex items-center gap-1 px-3 py-1 bg-emerald-50 rounded-full text-sm text-emerald-700">
                                            <Lightbulb className="w-3 h-3" />
                                            {opp}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </PrintCard>
            )}
            
            {/* Module 3: Brand Architecture */}
            {brand_architecture && (
                <PrintCard>
                    <div className="bg-white rounded-2xl p-6 border border-blue-200">
                        <div className="flex items-center gap-2 mb-4">
                            <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center">
                                <Building2 className="w-4 h-4 text-blue-600" />
                            </div>
                            <div>
                                <h4 className="font-bold text-slate-800">Module 3: Brand Architecture</h4>
                                <p className="text-xs text-slate-500">Strategic Fit - Can this name scale?</p>
                            </div>
                        </div>
                        
                        <div className="flex items-center justify-around mb-4">
                            <ScoreCircle score={brand_architecture.elasticity_score || 0} label="Elasticity" />
                            <ScoreCircle score={brand_architecture.memorability_index || 0} label="Memorability" />
                        </div>
                        
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                            <div className="p-3 bg-blue-50 rounded-lg">
                                <div className="text-xs font-bold text-blue-600 uppercase mb-1">Recommended Architecture</div>
                                <p className="text-sm font-bold text-slate-800">{brand_architecture.recommended_architecture}</p>
                                <p className="text-xs text-slate-600 mt-1">{brand_architecture.architecture_rationale}</p>
                            </div>
                            <div className="p-3 bg-indigo-50 rounded-lg">
                                <div className="text-xs font-bold text-indigo-600 uppercase mb-1">Global Scalability</div>
                                <p className="text-sm text-slate-700">{brand_architecture.global_scalability}</p>
                            </div>
                        </div>
                        
                        {brand_architecture.elasticity_analysis && (
                            <div className="p-3 bg-slate-50 rounded-lg mb-4">
                                <div className="text-xs font-bold text-slate-500 uppercase mb-1">Elasticity Analysis</div>
                                <p className="text-sm text-slate-700">{brand_architecture.elasticity_analysis}</p>
                            </div>
                        )}
                        
                        {/* Memorability Factors */}
                        {brand_architecture.memorability_factors?.length > 0 && (
                            <div>
                                <div className="text-xs font-bold text-slate-500 uppercase mb-2">Memorability Factors</div>
                                <div className="flex flex-wrap gap-2">
                                    {brand_architecture.memorability_factors.map((factor, i) => (
                                        <Badge key={i} className="bg-indigo-100 text-indigo-700">{factor}</Badge>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </PrintCard>
            )}
            
            {/* Alternative Directions (shown if REFINE or PIVOT) */}
            {alternative_directions?.length > 0 && (executive_recommendation === 'REFINE' || executive_recommendation === 'PIVOT') && (
                <PrintCard>
                    <div className="bg-gradient-to-br from-slate-50 to-violet-50 rounded-2xl p-6 border border-violet-200">
                        <div className="flex items-center gap-2 mb-4">
                            <div className="w-8 h-8 bg-violet-100 rounded-lg flex items-center justify-center">
                                <Rocket className="w-4 h-4 text-violet-600" />
                            </div>
                            <div>
                                <h4 className="font-bold text-slate-800">Alternative Naming Directions</h4>
                                <p className="text-xs text-slate-500">Based on Three-Pillar principles</p>
                            </div>
                        </div>
                        
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            {alternative_directions.map((dir, i) => (
                                <div key={i} className="bg-white p-4 rounded-xl border border-slate-200">
                                    <div className="font-bold text-slate-800 mb-2">{dir.direction_name}</div>
                                    <div className="flex flex-wrap gap-1 mb-2">
                                        {dir.example_names?.map((name, j) => (
                                            <Badge key={j} className="bg-violet-100 text-violet-700">{name}</Badge>
                                        ))}
                                    </div>
                                    <p className="text-xs text-slate-600 mb-2">{dir.rationale}</p>
                                    <div className="text-xs text-violet-600 font-medium">
                                        Principle: {dir.mckinsey_principle}
                                    </div>
                                </div>
                            ))}
                        </div>
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
        console.log('='.repeat(50));
        console.log('[EVAL Dashboard] VERSION: 2.1.0-20250108');
        console.log('[EVAL Dashboard] location.state:', location.state);
        
        if (location.state?.data) {
            console.log('[EVAL Dashboard] Setting data from location.state');
            console.log('[EVAL Dashboard] Full data:', location.state.data);
            console.log('[EVAL Dashboard] brand_scores:', location.state.data?.brand_scores);
            console.log('[EVAL Dashboard] First brand dimensions:', location.state.data?.brand_scores?.[0]?.dimensions);
            
            setReportData(location.state.data);
            setQueryData(location.state.query);
            localStorage.setItem('current_report', JSON.stringify(location.state.data));
            localStorage.setItem('current_query', JSON.stringify(location.state.query));
        } else {
            console.log('[EVAL Dashboard] Loading from localStorage');
            const savedReport = localStorage.getItem('current_report');
            const savedQuery = localStorage.getItem('current_query');
            if (savedReport && savedQuery) {
                const parsedReport = JSON.parse(savedReport);
                console.log('[EVAL Dashboard] Loaded from localStorage:', parsedReport);
                console.log('[EVAL Dashboard] First brand dimensions from storage:', parsedReport?.brand_scores?.[0]?.dimensions);
                setReportData(parsedReport);
                setQueryData(JSON.parse(savedQuery));
            }
        }
        setLoading(false);
        console.log('='.repeat(50));
    }, [location.state]);

    const handleRegister = () => {
        localStorage.setItem('auth_return_url', '/dashboard');
        openAuthModal(reportData?.report_id);
    };

    // PDF Download function - Simple and reliable using window.print()
    const handleDownloadPDF = async () => {
        if (!reportRef.current) {
            alert('Report not ready. Please wait and try again.');
            return;
        }
        
        setDownloading(true);
        
        try {
            // Simply trigger browser print dialog - works reliably
            window.print();
        } catch (error) {
            console.error('PDF Error:', error);
            alert('PDF failed: ' + error.message);
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
            {/* Preload logo for print */}
            <img src={LOGO_URL} alt="" style={{ position: 'absolute', width: 1, height: 1, opacity: 0 }} />
            
            {/* Print Styles */}
            <style>{`
                @media print {
                    @page { 
                        size: A4 portrait; 
                        margin: 10mm; 
                    }
                    
                    html, body {
                        margin: 0 !important;
                        padding: 0 !important;
                        -webkit-print-color-adjust: exact !important;
                        print-color-adjust: exact !important;
                    }
                    
                    .no-print { 
                        display: none !important; 
                    }
                    
                    /* ========== PAGE 1: COVER PAGE ========== */
                    .cover-page-container {
                        position: relative !important;
                        left: auto !important;
                        visibility: visible !important;
                        width: 100% !important;
                        height: 100vh !important;
                        min-height: 100vh !important;
                        display: flex !important;
                        flex-direction: column !important;
                        align-items: center !important;
                        justify-content: center !important;
                        background: white !important;
                        padding: 15mm !important;
                        page-break-after: always !important;
                        break-after: page !important;
                        box-sizing: border-box !important;
                    }
                    
                    /* ========== PAGE 2: Evaluation Summary (NO page break before) ========== */
                    .page-2-content {
                        page-break-before: auto !important;
                    }
                    
                    /* ========== PAGE 3+: New pages ========== */
                    .print-new-page { 
                        page-break-before: always !important; 
                        break-before: page !important;
                        padding-top: 5mm !important;
                    }
                    
                    /* ========== PREVENT BREAKS INSIDE ========== */
                    .print-card, 
                    .print-section > div,
                    .print-no-break {
                        break-inside: avoid !important; 
                        page-break-inside: avoid !important;
                    }
                    
                    /* ========== SPACING ========== */
                    main {
                        max-width: 100% !important;
                        padding: 0 !important;
                    }
                    
                    section {
                        margin-bottom: 8mm !important;
                    }
                    
                    /* ========== GRIDS FOR PRINT ========== */
                    .print\\:grid-cols-1 {
                        grid-template-columns: 1fr !important;
                    }
                    
                    .grid {
                        gap: 6px !important;
                    }
                    
                    /* ========== IMAGES ========== */
                    img {
                        max-width: 100% !important;
                    }
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
                                    <Loader2 className="h-4 w-4 animate-spin" /> Opening Print...
                                </>
                            ) : (
                                <>
                                    <Printer className="h-4 w-4" /> Print / Save PDF
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

            {/* Print Header - Date only, no logo (logo is on cover page) */}
            <div className="hidden print:flex print:justify-end print:items-center print:px-4 print:py-2 print:border-b print:border-slate-200 print:mb-4">
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

                {/* ==================== PAGE 2: EVALUATION SUMMARY ==================== */}
                {/* Evaluation Summary (left), Verdict & Index + Performance Radar (right) */}
                <section className="page-2-content">
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
                                    <p className="text-slate-700 leading-relaxed print:text-sm">
                                        <MarkdownText text={data.executive_summary} />
                                    </p>
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

                {/* Quick Dimensions - Screen only, not in PDF per spec */}
                <section className="no-print">
                    <QuickDimensionsGrid dimensions={brand.dimensions} />
                </section>

                {/* ==================== PAGE 3: FINAL ASSESSMENT + STRATEGY SNAPSHOT ==================== */}
                {/* Final Assessment */}
                {brand.final_assessment && (
                    <section className="print-new-page">
                        <SectionHeader icon={Zap} title="Final Assessment" subtitle="Consultant Verdict & Roadmap" color="emerald" />
                        {isAuthenticated ? (
                            <FinalAssessmentFull assessment={brand.final_assessment} verdict={brand.verdict} score={brand.namescore} />
                        ) : (
                            <LockedSection title="Final Assessment" onUnlock={handleRegister} />
                        )}
                    </section>
                )}

                {/* Strategy Snapshot - Same Page 3 as Final Assessment */}
                <section className={brand.final_assessment ? "" : "print-new-page"}>
                    <SectionHeader icon={Target} title="Strategy Snapshot" subtitle="Strengths and risks analysis" color="emerald" />
                    {isAuthenticated ? (
                        <StrategySnapshot classification={brand.strategic_classification} pros={brand.pros} cons={brand.cons} />
                    ) : (
                        <LockedSection title="Strategy Snapshot" onUnlock={handleRegister} />
                    )}
                </section>

                {/* ==================== PAGE 4+: WHAT'S IN THE NAME + 6 DIMENSIONS (STACKED) ==================== */}
                {brand.dimensions && (
                    <section className="print-new-page">
                        {/* Banner */}
                        <div className="bg-gradient-to-r from-violet-600 via-fuchsia-500 to-orange-500 rounded-2xl p-8 text-center mb-6 print:p-6 print:mb-4">
                            <h2 className="text-3xl md:text-4xl font-black text-white tracking-tight print:text-2xl">
                                What's in the Name?
                            </h2>
                            <p className="text-white/80 mt-2 text-lg print:text-sm">Deep dive into your brand's DNA</p>
                        </div>
                        
                        {/* Detailed Framework Analysis - 6 DIMENSIONS STACKED VERTICALLY FOR PRINT */}
                        <SectionHeader icon={BarChart3} title="Detailed Framework Analysis" subtitle="In-depth scoring breakdown" color="fuchsia" />
                        {isAuthenticated ? (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 print:grid-cols-1 print:gap-3">
                                {brand.dimensions.map((dim, i) => (
                                    <DetailedDimensionCard key={i} dimension={dim} index={i} />
                                ))}
                            </div>
                        ) : (
                            <LockedSection title="Detailed Framework Analysis" onUnlock={handleRegister} />
                        )}
                    </section>
                )}

                {/* ==================== McKINSEY THREE-QUESTION FRAMEWORK ANALYSIS ==================== */}
                {brand.mckinsey_analysis && (
                    <section className="print-new-page">
                        <SectionHeader 
                            icon={Briefcase} 
                            title="Three-Pillar Brand Assessment" 
                            subtitle="Three-Question strategic analysis" 
                            color="violet" 
                            badge={brand.mckinsey_analysis?.executive_recommendation}
                        />
                        {isAuthenticated ? (
                            <McKinseyAnalysisSection mckinsey={brand.mckinsey_analysis} />
                        ) : (
                            <LockedSection title="Three-Pillar Brand Assessment Analysis" onUnlock={handleRegister} />
                        )}
                    </section>
                )}

                {/* ==================== NEW PAGE: MARKET INTELLIGENCE (MOVED BEFORE DIGITAL PRESENCE) ==================== */}
                {(brand.domain_analysis || brand.visibility_analysis || brand.cultural_analysis) && (
                    <section className="print-new-page">
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

                {/* ==================== NEW PAGE: DIGITAL PRESENCE ==================== */}
                {(brand.multi_domain_availability || brand.social_availability) && (
                    <section className="print-new-page">
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

                {/* ==================== NEW PAGE: COMPETITIVE LANDSCAPE ==================== */}
                {(brand.competitor_analysis || brand.country_competitor_analysis?.length > 0) && (
                    <section className="print-new-page">
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

                {/* ==================== NEW PAGE: LEGAL RISK MATRIX ==================== */}
                {brand.trademark_matrix && (
                    <section className="print-new-page">
                        <SectionHeader icon={Scale} title="Legal Risk Matrix" subtitle="IP Analysis & Trademark Assessment" color="red" />
                        {isAuthenticated ? (
                            <LegalRiskMatrix trademarkMatrix={brand.trademark_matrix} trademarkClasses={brand.trademark_classes} />
                        ) : (
                            <LockedSection title="Legal Risk Matrix" onUnlock={handleRegister} />
                        )}
                    </section>
                )}

                {/* ==================== NEW PAGE: TRADEMARK RESEARCH ==================== */}
                {brand.trademark_research && (
                    <section className="print-new-page">
                        <SectionHeader icon={Shield} title="Trademark Research Intelligence" subtitle="Real-Time Conflict Discovery & Risk Analysis" color="violet" badge="NEW" />
                        <TrademarkResearchSection 
                            trademarkResearch={brand.trademark_research} 
                            registrationTimeline={brand.registration_timeline}
                            mitigationStrategies={brand.mitigation_strategies}
                        />
                    </section>
                )}
                
                {/* Debug: Show if trademark_research is missing */}
                {!brand.trademark_research && (
                    <section className="print-new-page">
                        <SectionHeader icon={Shield} title="Trademark Research Intelligence" subtitle="Real-Time Conflict Discovery & Risk Analysis" color="violet" badge="NEW" />
                        <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 text-center">
                            <AlertTriangle className="w-10 h-10 text-amber-500 mx-auto mb-3" />
                            <p className="text-amber-700 font-medium">Trademark research data is being processed</p>
                            <p className="text-amber-600 text-sm mt-1">This section will populate with detailed conflict analysis</p>
                        </div>
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
