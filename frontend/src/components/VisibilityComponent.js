import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, Search, Smartphone, CheckCircle2, XCircle, Info } from "lucide-react";

export const VisibilityAnalysisCard = ({ analysis }) => {
    if (!analysis) return null;

    const directCompetitors = analysis.direct_competitors || [];
    const nameTwins = analysis.name_twins || [];
    const hasDirectCompetitors = directCompetitors.length > 0;

    return (
        <Card className={`playful-card border-l-4 h-full ${hasDirectCompetitors ? 'border-l-rose-500 ring-2 ring-rose-100' : analysis.warning_triggered ? 'border-l-amber-500' : 'border-l-emerald-500'}`}>
            <CardHeader className={`pb-2 ${hasDirectCompetitors ? 'bg-rose-50' : analysis.warning_triggered ? 'bg-amber-50' : 'bg-emerald-50'}`}>
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        {hasDirectCompetitors ? (
                            <XCircle className="w-5 h-5 text-rose-600" />
                        ) : analysis.warning_triggered ? (
                            <AlertTriangle className="w-5 h-5 text-amber-600" />
                        ) : (
                            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                        )}
                        <CardTitle className={`text-sm font-bold uppercase tracking-widest ${hasDirectCompetitors ? 'text-rose-600' : analysis.warning_triggered ? 'text-amber-600' : 'text-emerald-600'}`}>
                            Conflict Relevance Analysis
                        </CardTitle>
                    </div>
                    <Badge className={`${hasDirectCompetitors ? 'bg-rose-100 text-rose-700' : 'bg-emerald-100 text-emerald-700'}`}>
                        {hasDirectCompetitors ? `${directCompetitors.length} DIRECT CONFLICTS` : 'NO DIRECT CONFLICTS'}
                    </Badge>
                </div>
            </CardHeader>
            <CardContent className="pt-4 space-y-5">
                
                {/* Conflict Summary */}
                {analysis.conflict_summary && (
                    <div className={`p-3 rounded-lg border ${hasDirectCompetitors ? 'bg-rose-50 border-rose-200' : 'bg-blue-50 border-blue-200'}`}>
                        <p className={`text-sm font-medium ${hasDirectCompetitors ? 'text-rose-700' : 'text-blue-700'}`}>
                            {analysis.conflict_summary}
                        </p>
                    </div>
                )}

                {/* User's Product Intent & Customer */}
                {(analysis.user_product_intent || analysis.user_customer_avatar) && (
                    <div className="p-3 bg-violet-50 rounded-lg border border-violet-200 space-y-2">
                        {analysis.user_product_intent && (
                            <div>
                                <h4 className="text-[10px] font-bold uppercase tracking-widest text-violet-600 mb-1">Your Product Intent</h4>
                                <p className="text-sm font-medium text-violet-800">{analysis.user_product_intent}</p>
                            </div>
                        )}
                        {analysis.user_customer_avatar && (
                            <div>
                                <h4 className="text-[10px] font-bold uppercase tracking-widest text-violet-600 mb-1">Your Target Customer</h4>
                                <p className="text-sm font-medium text-violet-800">{analysis.user_customer_avatar}</p>
                            </div>
                        )}
                    </div>
                )}

                {/* Direct Competitors (Fatal Conflicts) */}
                {directCompetitors.length > 0 && (
                    <div>
                        <h4 className="text-xs font-black uppercase tracking-widest text-rose-500 mb-3 flex items-center gap-2">
                            <XCircle className="w-3 h-3" /> Fatal Conflicts (Same Intent + Same Customers)
                        </h4>
                        <div className="space-y-2">
                            {directCompetitors.map((item, i) => (
                                <div key={i} className="p-3 bg-rose-50 rounded-lg border border-rose-200">
                                    <div className="flex items-center justify-between mb-1">
                                        <span className="text-sm font-bold text-rose-800">{item.name}</span>
                                        <Badge className="bg-rose-600 text-white text-[10px]">FATAL</Badge>
                                    </div>
                                    <p className="text-xs text-rose-600 mb-1">{item.category}</p>
                                    {item.their_product_intent && (
                                        <p className="text-[10px] text-rose-500 mb-1">
                                            <span className="font-bold">Their Intent:</span> {item.their_product_intent}
                                        </p>
                                    )}
                                    {item.their_customer_avatar && (
                                        <p className="text-[10px] text-rose-500">
                                            <span className="font-bold">Their Customers:</span> {item.their_customer_avatar}
                                        </p>
                                    )}
                                    <div className="flex gap-2 mt-1">
                                        {item.intent_match && (
                                            <Badge className="bg-rose-100 text-rose-700 text-[10px]">
                                                Intent: {item.intent_match}
                                            </Badge>
                                        )}
                                        {item.customer_overlap && (
                                            <Badge className="bg-rose-100 text-rose-700 text-[10px]">
                                                Customers: {item.customer_overlap}
                                            </Badge>
                                    )}
                                    {item.reason && <p className="text-xs text-rose-500 mt-1 italic">{item.reason}</p>}
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Name Twins (Market Noise - Not rejection factors) */}
                {nameTwins.length > 0 && (
                    <div>
                        <h4 className="text-xs font-black uppercase tracking-widest text-slate-400 mb-3 flex items-center gap-2">
                            <Info className="w-3 h-3" /> Market Noise (Different Customers)
                        </h4>
                        <div className="space-y-2">
                            {nameTwins.map((item, i) => (
                                <div key={i} className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                                    <div className="flex items-center justify-between mb-1">
                                        <span className="text-sm font-medium text-slate-700">{item.name}</span>
                                        <Badge variant="secondary" className="bg-slate-200 text-slate-600 text-[10px]">LOW RISK</Badge>
                                    </div>
                                    <p className="text-xs text-slate-500 mb-1">{item.category}</p>
                                    {item.their_customer_avatar && (
                                        <p className="text-[10px] text-slate-400">
                                            <span className="font-medium">Their Customers:</span> {item.their_customer_avatar}
                                        </p>
                                    )}
                                    {item.customer_overlap && (
                                        <Badge variant="outline" className="mt-1 text-[10px] text-slate-500 border-slate-300">
                                            Customer Overlap: {item.customer_overlap}
                                        </Badge>
                                    )}
                                    {item.reason && <p className="text-xs text-slate-400 mt-1 italic">{item.reason}</p>}
                                </div>
                            ))}
                        </div>
                        <p className="text-xs text-slate-400 mt-2 p-2 bg-slate-50 rounded border border-slate-100">
                            ℹ️ Name twins in different industries are NOT rejection factors.
                        </p>
                    </div>
                )}

                {/* Legacy: Google Presence */}
                {analysis.google_presence && analysis.google_presence.length > 0 && (
                    <div>
                        <h4 className="text-xs font-black uppercase tracking-widest text-slate-400 mb-3 flex items-center gap-2">
                            <Search className="w-3 h-3" /> Google Search Results
                        </h4>
                        <ul className="space-y-2">
                            {analysis.google_presence.slice(0, 3).map((item, i) => (
                                <li key={i} className="text-sm bg-slate-50 p-3 rounded-lg text-slate-700 font-medium truncate">
                                    {typeof item === 'string' ? item : (item?.name || item?.title || JSON.stringify(item))}
                                </li>
                            ))}
                        </ul>
                    </div>
                )}

                {/* Legacy: App Store Presence */}
                {analysis.app_store_presence && analysis.app_store_presence.length > 0 && (
                    <div>
                        <h4 className="text-xs font-black uppercase tracking-widest text-slate-400 mb-3 flex items-center gap-2">
                            <Smartphone className="w-3 h-3" /> App Store Presence
                        </h4>
                        <ul className="space-y-2">
                            {analysis.app_store_presence.slice(0, 3).map((item, i) => (
                                <li key={i} className="text-sm bg-slate-50 p-3 rounded-lg text-slate-700 font-medium truncate">
                                    {typeof item === 'string' ? item : (item?.name || item?.title || JSON.stringify(item))}
                                </li>
                            ))}
                        </ul>
                    </div>
                )}

                {/* No conflicts found */}
                {!hasDirectCompetitors && nameTwins.length === 0 && (!analysis.google_presence || analysis.google_presence.length === 0) && (
                    <div className="p-4 bg-emerald-50 rounded-lg border border-emerald-200 text-center">
                        <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                        <p className="text-sm font-bold text-emerald-700">Clean visibility slate</p>
                        <p className="text-xs text-emerald-600">No direct competitors or significant conflicts found.</p>
                    </div>
                )}

            </CardContent>
        </Card>
    );
};
