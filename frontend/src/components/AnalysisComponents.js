import React from 'react';
import {
  Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

export const BrandRadarChart = ({ data }) => {
  return (
    <div className="h-[350px] w-full min-w-[300px]">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart cx="50%" cy="50%" outerRadius="70%" data={data}>
          <PolarGrid stroke="#e2e8f0" strokeDasharray="3 3" />
          <PolarAngleAxis 
            dataKey="name" 
            tick={{ fill: '#64748b', fontSize: 11, fontWeight: 600 }} 
          />
          <PolarRadiusAxis angle={30} domain={[0, 10]} tick={false} axisLine={false} />
          <Radar
            name="Score"
            dataKey="score"
            stroke="#8b5cf6"
            strokeWidth={3}
            fill="#a78bfa"
            fillOpacity={0.4}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
};

export const ScoreCard = ({ title, score, verdict, subtitle, className }) => {
    let colorClass = "text-slate-900";
    let badgeClass = "bg-slate-100 text-slate-700";
    
    if (verdict === "GO") {
        colorClass = "text-emerald-600";
        badgeClass = "bg-emerald-100 text-emerald-700 border-emerald-200";
    }
    if (verdict === "CONDITIONAL GO") {
        colorClass = "text-amber-600";
        badgeClass = "bg-amber-100 text-amber-700 border-amber-200";
    }
    if (verdict === "NO-GO" || verdict === "REJECT") {
        colorClass = "text-rose-600";
        badgeClass = "bg-rose-100 text-rose-700 border-rose-200";
    }

    return (
        <Card className={`playful-card border-l-4 border-l-violet-500 h-full overflow-hidden ${className}`}>
            <CardHeader className="pb-2 bg-gradient-to-r from-violet-50 to-white">
                <CardTitle className="text-xs font-bold uppercase tracking-widest text-violet-400">
                    {title}
                </CardTitle>
            </CardHeader>
            <CardContent className="pt-4 flex flex-col items-center justify-center text-center">
                <div className="flex items-baseline space-x-2">
                    <span className={`text-6xl font-extrabold ${colorClass}`}>{score}</span>
                    <span className="text-sm text-slate-400 font-bold">/100</span>
                </div>
                {verdict && (
                    <div className="mt-4">
                        <Badge variant="outline" className={`px-4 py-1.5 text-base font-bold border-2 ${badgeClass}`}>
                            {verdict}
                        </Badge>
                    </div>
                )}
                {subtitle && <p className="mt-3 text-xs text-slate-400 font-medium">{subtitle}</p>}
            </CardContent>
        </Card>
    );
};

export const CompetitionAnalysis = ({ data }) => {
    return (
        <Card className="playful-card border-0 shadow-none ring-1 ring-slate-100 overflow-hidden w-full">
            <CardHeader className="bg-slate-900 text-white p-6">
                <CardTitle className="text-xl font-bold flex items-center">
                    <span className="mr-2">⚔️</span> Competitive Landscape
                </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
                <div className="p-8 bg-gradient-to-br from-violet-50 to-white border-b border-slate-100">
                     <h4 className="text-xs font-black uppercase tracking-widest text-violet-500 mb-3">✨ Competitive White Space</h4>
                     <p className="text-slate-800 font-medium text-lg leading-relaxed">{data.white_space_analysis}</p>
                </div>

                <div className="p-0 overflow-x-auto">
                    <Table className="min-w-[600px]">
                        <TableHeader>
                            <TableRow className="hover:bg-transparent">
                                <TableHead className="w-[200px] font-bold text-slate-900 pl-8 py-4">Competitor</TableHead>
                                <TableHead className="font-bold text-slate-900">Positioning</TableHead>
                                <TableHead className="text-right font-bold text-slate-900 pr-8">Price Range</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {data.competitors && data.competitors.map((comp, idx) => (
                                <TableRow key={idx} className="hover:bg-slate-50/50 border-slate-100">
                                    <TableCell className="font-bold text-slate-700 pl-8 py-4">{comp.name}</TableCell>
                                    <TableCell className="text-slate-600">{comp.positioning}</TableCell>
                                    <TableCell className="text-right font-mono text-violet-600 font-bold pr-8">{comp.price_range}</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2">
                     <div className="p-8 bg-emerald-50/30 border-t md:border-r border-slate-100">
                        <h4 className="text-xs font-black uppercase tracking-widest text-emerald-600 mb-2">🚀 Strategic Advantage</h4>
                        <p className="text-sm text-slate-700 font-medium">{data.strategic_advantage}</p>
                     </div>
                     <div className="p-8 bg-white flex flex-col items-center justify-center border-t border-slate-100">
                        <h4 className="text-xs font-black uppercase tracking-widest text-slate-400 mb-2">Suggested Pricing</h4>
                        <span className="text-3xl font-extrabold text-slate-900 bg-slate-100 px-4 py-2 rounded-xl text-center">
                            {data.suggested_pricing}
                        </span>
                     </div>
                </div>
            </CardContent>
        </Card>
    );
};

export const TrademarkRiskTable = ({ matrix }) => {
    if (!matrix) return null;

    const rows = [
        { label: "Genericness / Descriptiveness", ...matrix.genericness },
        { label: "Existing Conflicts", ...matrix.existing_conflicts },
        { label: "Phonetic Similarity", ...matrix.phonetic_similarity },
        { label: "Relevant Trademark Classes", ...matrix.relevant_classes },
        { label: "Rebranding Probability (3-5y)", ...matrix.rebranding_probability },
    ];

    const getZoneBadge = (zone) => {
        if (zone === "Green") return <Badge className="bg-emerald-100 text-emerald-800 hover:bg-emerald-200 border-0 px-3 py-1 whitespace-nowrap">Safe</Badge>;
        if (zone === "Yellow") return <Badge className="bg-amber-100 text-amber-800 hover:bg-amber-200 border-0 px-3 py-1 whitespace-nowrap">Caution</Badge>;
        if (zone === "Red") return <Badge className="bg-rose-100 text-rose-800 hover:bg-rose-200 border-0 px-3 py-1 whitespace-nowrap">High Risk</Badge>;
        return zone;
    };

    return (
        <Card className="playful-card overflow-hidden w-full">
            <CardHeader className="bg-slate-900 text-white p-6">
                 <CardTitle className="text-xl font-bold flex items-center">
                    <span className="mr-2">⚖️</span> Trademark Risk Matrix
                 </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
                <div className="overflow-x-auto">
                    <Table className="min-w-[800px]">
                        <TableHeader>
                            <TableRow className="bg-slate-50 hover:bg-slate-50 border-slate-100">
                                <TableHead className="w-[200px] font-bold text-slate-900 pl-6">Risk Factor</TableHead>
                                <TableHead className="text-center font-bold text-slate-900 w-[100px]">Likelihood</TableHead>
                                <TableHead className="text-center font-bold text-slate-900 w-[100px]">Severity</TableHead>
                                <TableHead className="text-center font-bold text-slate-900 w-[100px]">Zone</TableHead>
                                <TableHead className="font-bold text-slate-900 min-w-[300px]">Commentary & Mitigation</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {rows.map((row, idx) => (
                                <TableRow key={idx} className="border-slate-100 hover:bg-slate-50/50">
                                    <TableCell className="font-bold text-slate-700 pl-6 py-4">{row.label}</TableCell>
                                    <TableCell className="text-center font-mono text-slate-500">{row.likelihood}/10</TableCell>
                                    <TableCell className="text-center font-mono text-slate-500">{row.severity}/10</TableCell>
                                    <TableCell className="text-center">{getZoneBadge(row.zone)}</TableCell>
                                    <TableCell className="text-sm text-slate-600 leading-relaxed font-medium">{row.commentary}</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
                <div className="p-8 bg-amber-50/50 border-t border-slate-100">
                    <h4 className="text-xs font-black uppercase tracking-widest text-amber-600 mb-2">⚠️ Overall Legal Assessment</h4>
                    <p className="text-sm text-slate-800 leading-relaxed font-medium">{matrix.overall_assessment}</p>
                </div>
            </CardContent>
        </Card>
    );
};

export const DomainAvailabilityCard = ({ analysis }) => {
    if (!analysis) return null;

    return (
        <Card className="playful-card border-l-4 border-l-blue-400 h-full">
            <CardHeader className="pb-2">
                <CardTitle className="text-xs font-bold uppercase tracking-widest text-blue-400">
                    🌐 Domain Status
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6 pt-4">
                <div>
                    <div className="text-2xl font-extrabold text-slate-900 mb-1 break-words">
                        {analysis.exact_match_status}
                    </div>
                </div>
                
                <div>
                    <h4 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3">Alternatives</h4>
                    <ul className="space-y-3">
                        {analysis.alternatives.map((alt, i) => (
                            <li key={i} className="flex flex-col sm:flex-row justify-between items-start sm:items-center text-sm bg-slate-50 p-3 rounded-lg gap-2">
                                <span className="font-bold text-slate-700">{alt.domain}</span>
                                <span className="text-xs text-slate-400 font-medium">{alt.example}</span>
                            </li>
                        ))}
                    </ul>
                </div>

                <div className="bg-blue-50 p-4 rounded-xl border-2 border-blue-100">
                    <p className="text-sm text-blue-800 leading-relaxed font-medium">
                        <span className="font-bold block text-xs uppercase tracking-wider text-blue-400 mb-1">Strategy</span> 
                        {analysis.strategy_note}
                    </p>
                </div>
            </CardContent>
        </Card>
    );
};
