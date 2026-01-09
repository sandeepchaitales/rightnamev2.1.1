import React, { useState, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
    RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, 
    ResponsiveContainer, Tooltip
} from 'recharts';
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
    Zap,
    Activity,
    MessageSquare,
    ThumbsUp,
    ThumbsDown,
    Quote,
    ExternalLink
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

// ============ PERFORMANCE RADAR CHART ============
const PerformanceRadar = ({ dimensions, brandName }) => {
    // Debug logging
    console.log('[PerformanceRadar] Received dimensions:', dimensions);
    console.log('[PerformanceRadar] Dimensions length:', dimensions?.length);
    
    // Fallback UI for missing data
    if (!dimensions || dimensions.length === 0) {
        console.warn('[PerformanceRadar] No dimensions data available');
        return (
            <Card>
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                        <div className="w-10 h-10 rounded-xl bg-fuchsia-100 flex items-center justify-center">
                            <Target className="w-5 h-5 text-fuchsia-600" />
                        </div>
                        <div>
                            <h3 className="text-lg font-bold text-slate-800">Performance Radar</h3>
                            <p className="text-xs text-slate-500">8-Dimension Analysis</p>
                        </div>
                    </div>
                </div>
                <div className="h-72 flex items-center justify-center bg-slate-50 rounded-xl">
                    <div className="text-center">
                        <AlertTriangle className="w-12 h-12 text-amber-400 mx-auto mb-2" />
                        <p className="text-slate-500 text-sm">Dimension data not available</p>
                        <p className="text-slate-400 text-xs mt-1">Try refreshing the page</p>
                    </div>
                </div>
            </Card>
        );
    }
    
    // Transform dimensions data for Recharts radar
    const radarData = dimensions.slice(0, 8).map(dim => ({
        dimension: dim.name?.length > 12 ? dim.name.substring(0, 12) + '...' : dim.name,
        fullName: dim.name,
        score: dim.score || 0,
        fullMark: 10
    }));
    
    console.log('[PerformanceRadar] Transformed radarData:', radarData);
    
    const avgScore = dimensions.length > 0 
        ? (dimensions.reduce((acc, d) => acc + (d.score || 0), 0) / dimensions.length).toFixed(1)
        : 0;
    
    return (
        <Card>
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <div className="w-10 h-10 rounded-xl bg-fuchsia-100 flex items-center justify-center">
                        <Target className="w-5 h-5 text-fuchsia-600" />
                    </div>
                    <div>
                        <h3 className="text-lg font-bold text-slate-800">Performance Radar</h3>
                        <p className="text-xs text-slate-500">8-Dimension Analysis</p>
                    </div>
                </div>
                <div className="text-right">
                    <div className="text-2xl font-black text-fuchsia-600">{avgScore}</div>
                    <div className="text-xs text-slate-500">Avg Score</div>
                </div>
            </div>
            <div className="h-72">
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
        </Card>
    );
};

// ============ DETAILED DIMENSION CARD ============
const DetailedDimensionCard = ({ dimension, index }) => {
    // Debug logging
    console.log(`[DetailedDimensionCard ${index}] Received:`, dimension);
    
    // Fallback for missing dimension
    if (!dimension) {
        return (
            <div className="bg-slate-50 border border-slate-200 rounded-xl p-6 text-center">
                <AlertTriangle className="w-8 h-8 text-amber-400 mx-auto mb-2" />
                <p className="text-sm text-slate-500">Dimension data unavailable</p>
            </div>
        );
    }
    
    const icons = ['🏛️', '⭐', '🎯', '📈', '⚙️', '📢', '💰', '🌐'];
    
    const getScoreColorClasses = (score) => {
        if (score >= 8) return 'from-emerald-400 to-emerald-500 bg-emerald-100 text-emerald-700';
        if (score >= 6) return 'from-violet-400 to-fuchsia-500 bg-violet-100 text-violet-700';
        if (score >= 4) return 'from-amber-400 to-orange-500 bg-amber-100 text-amber-700';
        return 'from-red-400 to-red-500 bg-red-100 text-red-700';
    };
    
    const colors = getScoreColorClasses(dimension.score);
    
    // Parse evidence from dimension
    const evidence = dimension.evidence || dimension.data_sources || [];
    const confidence = dimension.confidence || 'MEDIUM';
    
    const confidenceColors = {
        'HIGH': 'bg-emerald-100 text-emerald-700',
        'MEDIUM': 'bg-amber-100 text-amber-700',
        'LOW': 'bg-red-100 text-red-700'
    };
    
    return (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden hover:shadow-lg transition-all duration-300 hover:border-violet-200">
            {/* Header with Score */}
            <div className={`px-5 py-4 ${colors.split(' ').slice(2, 4).join(' ')} border-b`}>
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <span className="text-2xl">{icons[index % icons.length]}</span>
                        <div>
                            <h4 className="font-bold text-slate-800">{dimension.name}</h4>
                            <Badge className={`text-xs mt-1 ${confidenceColors[confidence]}`}>
                                {confidence} Confidence
                            </Badge>
                        </div>
                    </div>
                    <div className={`px-4 py-2 rounded-full bg-gradient-to-r ${colors.split(' ').slice(0, 2).join(' ')} text-white font-black text-lg shadow-lg`}>
                        {dimension.score}/10
                    </div>
                </div>
            </div>
            
            {/* Body */}
            <div className="p-5">
                {/* Progress bar */}
                <div className="h-3 bg-slate-100 rounded-full overflow-hidden mb-4">
                    <div 
                        className={`h-full rounded-full bg-gradient-to-r ${colors.split(' ').slice(0, 2).join(' ')} transition-all duration-500`} 
                        style={{ width: `${dimension.score * 10}%` }} 
                    />
                </div>
                
                {/* Reasoning */}
                <div className="mb-4">
                    <div className="flex items-center gap-2 mb-2">
                        <Activity className="w-4 h-4 text-violet-500" />
                        <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Analysis</span>
                    </div>
                    <p className="text-sm text-slate-600 leading-relaxed">{dimension.reasoning}</p>
                </div>
                
                {/* Evidence/Data Sources */}
                {evidence.length > 0 && (
                    <div className="mt-4 p-3 bg-slate-50 rounded-lg">
                        <div className="flex items-center gap-2 mb-2">
                            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Evidence</span>
                        </div>
                        <ul className="space-y-1">
                            {evidence.slice(0, 3).map((item, i) => (
                                <li key={i} className="text-xs text-slate-600 flex items-start gap-2">
                                    <span className="text-emerald-500 mt-0.5">•</span>
                                    <span>{typeof item === 'string' ? item : item.point || item.source}</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
        </div>
    );
};

// ============ QUICK DIMENSIONS GRID ============
const QuickDimensionsGrid = ({ dimensions }) => (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {dimensions?.slice(0, 8).map((dim, i) => {
            const icons = ['🏛️', '⭐', '🎯', '📈', '⚙️', '📢', '💰', '🌐'];
            const bgColor = dim.score >= 8 ? 'bg-emerald-50 border-emerald-200' : 
                           dim.score >= 6 ? 'bg-violet-50 border-violet-200' : 
                           dim.score >= 4 ? 'bg-amber-50 border-amber-200' : 'bg-red-50 border-red-200';
            const textColor = dim.score >= 8 ? 'text-emerald-700' : 
                             dim.score >= 6 ? 'text-violet-700' : 
                             dim.score >= 4 ? 'text-amber-700' : 'text-red-700';
            
            return (
                <div key={i} className={`${bgColor} border rounded-xl p-3 text-center`}>
                    <span className="text-xl block mb-1">{icons[i]}</span>
                    <div className={`text-2xl font-black ${textColor}`}>{dim.score}</div>
                    <div className="text-xs text-slate-600 truncate">{dim.name}</div>
                </div>
            );
        })}
    </div>
);

// ============ CUSTOMER PERCEPTION & BRAND HEALTH SECTION ============
const CustomerPerceptionSection = ({ data }) => {
    if (!data) return null;
    
    const { 
        overall_sentiment, 
        sentiment_score, 
        platform_ratings = [], 
        average_rating,
        total_reviews,
        rating_vs_competitors,
        competitor_ratings = {},
        positive_themes = [],
        negative_themes = [],
        key_strengths = [],
        key_concerns = [],
        analysis
    } = data;
    
    const sentimentColors = {
        'POSITIVE': 'bg-emerald-100 text-emerald-700',
        'NEUTRAL': 'bg-amber-100 text-amber-700',
        'NEGATIVE': 'bg-red-100 text-red-700'
    };
    
    const platformIcons = {
        'Google Maps': '🗺️',
        'Google': '🔍',
        'Justdial': '📞',
        'Zomato': '🍽️',
        'Swiggy': '🛵',
        'Yelp': '⭐',
        'TripAdvisor': '✈️',
        'Trustpilot': '🛡️',
        'Facebook': '👍',
        'MouthShut': '🗣️'
    };
    
    const getIcon = (platform) => platformIcons[platform] || '📊';
    
    const getRatingColor = (rating) => {
        if (rating >= 4.5) return 'text-emerald-600 bg-emerald-50';
        if (rating >= 4.0) return 'text-green-600 bg-green-50';
        if (rating >= 3.5) return 'text-amber-600 bg-amber-50';
        return 'text-red-600 bg-red-50';
    };
    
    return (
        <section className="print-break">
            <SectionHeader 
                icon={MessageSquare} 
                title="Customer Perception & Brand Health" 
                subtitle="Platform ratings, sentiment analysis, and customer feedback themes" 
                color="pink" 
            />
            
            {/* Overall Metrics Row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                {average_rating && (
                    <Card className="text-center">
                        <div className="text-3xl mb-1">⭐</div>
                        <div className="text-3xl font-black text-amber-600">{average_rating.toFixed(1)}</div>
                        <div className="text-xs text-slate-500">Average Rating</div>
                    </Card>
                )}
                {total_reviews && (
                    <Card className="text-center">
                        <div className="text-3xl mb-1">💬</div>
                        <div className="text-2xl font-black text-blue-600">{total_reviews}</div>
                        <div className="text-xs text-slate-500">Total Reviews</div>
                    </Card>
                )}
                {sentiment_score !== null && sentiment_score !== undefined && (
                    <Card className="text-center">
                        <div className="text-3xl mb-1">{sentiment_score >= 70 ? '😊' : sentiment_score >= 40 ? '😐' : '😟'}</div>
                        <div className="text-3xl font-black text-violet-600">{sentiment_score}</div>
                        <div className="text-xs text-slate-500">Sentiment Score</div>
                    </Card>
                )}
                {rating_vs_competitors && (
                    <Card className="text-center">
                        <div className="text-3xl mb-1">{rating_vs_competitors.toLowerCase().includes('above') ? '📈' : rating_vs_competitors.toLowerCase().includes('below') ? '📉' : '➡️'}</div>
                        <div className={`text-sm font-bold px-2 py-1 rounded-full inline-block ${
                            rating_vs_competitors.toLowerCase().includes('above') ? 'bg-emerald-100 text-emerald-700' :
                            rating_vs_competitors.toLowerCase().includes('below') ? 'bg-red-100 text-red-700' :
                            'bg-amber-100 text-amber-700'
                        }`}>
                            {rating_vs_competitors}
                        </div>
                        <div className="text-xs text-slate-500 mt-1">vs Market</div>
                    </Card>
                )}
            </div>
            
            {/* Platform Ratings Grid */}
            {platform_ratings.length > 0 && (
                <div className="mb-6">
                    <h3 className="font-bold text-slate-800 mb-3 flex items-center gap-2">
                        <Star className="w-4 h-4 text-amber-500" />
                        Platform Ratings
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                        {platform_ratings.map((pr, i) => (
                            <div key={i} className={`p-4 rounded-xl border ${getRatingColor(pr.rating)} border-slate-200`}>
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-xl">{getIcon(pr.platform)}</span>
                                    {pr.url && (
                                        <a href={pr.url} target="_blank" rel="noopener noreferrer" className="text-slate-400 hover:text-blue-500">
                                            <ExternalLink className="w-3 h-3" />
                                        </a>
                                    )}
                                </div>
                                <div className="font-bold text-sm text-slate-800">{pr.platform}</div>
                                <div className="flex items-center gap-1 mt-1">
                                    <span className="text-2xl font-black">{pr.rating?.toFixed(1) || 'N/A'}</span>
                                    <span className="text-xs text-slate-500">/5</span>
                                </div>
                                {pr.review_count && (
                                    <div className="text-xs text-slate-500 mt-1">{pr.review_count}</div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}
            
            {/* Competitor Rating Comparison */}
            {Object.keys(competitor_ratings).length > 0 && (
                <div className="mb-6 p-4 bg-slate-50 rounded-xl">
                    <h3 className="font-bold text-slate-800 mb-3 flex items-center gap-2">
                        <Target className="w-4 h-4 text-violet-500" />
                        Competitor Rating Comparison
                    </h3>
                    <div className="flex flex-wrap gap-4">
                        {Object.entries(competitor_ratings).map(([name, rating], i) => (
                            <div key={i} className="flex items-center gap-2 px-3 py-2 bg-white rounded-lg border">
                                <span className="font-medium text-slate-700">{name}</span>
                                <Badge className={getRatingColor(rating)}>{rating?.toFixed(1) || 'N/A'}/5</Badge>
                            </div>
                        ))}
                    </div>
                </div>
            )}
            
            {/* Positive & Negative Themes */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                {/* Positive Themes */}
                {positive_themes.length > 0 && (
                    <Card className="border-l-4 border-l-emerald-500">
                        <h3 className="font-bold text-emerald-700 mb-4 flex items-center gap-2">
                            <ThumbsUp className="w-5 h-5" />
                            Positive Feedback Themes
                            <Badge className="bg-emerald-100 text-emerald-700">{positive_themes.length}</Badge>
                        </h3>
                        <div className="space-y-4">
                            {positive_themes.slice(0, 5).map((theme, i) => (
                                <div key={i} className="p-3 bg-emerald-50 rounded-lg">
                                    <div className="flex items-center justify-between mb-2">
                                        <span className="font-bold text-emerald-800">{theme.theme}</span>
                                        <Badge variant="outline" className="text-xs">
                                            {theme.frequency || 'MEDIUM'}
                                        </Badge>
                                    </div>
                                    {theme.quote && (
                                        <div className="flex items-start gap-2 mt-2">
                                            <Quote className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                                            <p className="text-sm text-slate-600 italic">"{theme.quote}"</p>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </Card>
                )}
                
                {/* Negative Themes */}
                {negative_themes.length > 0 && (
                    <Card className="border-l-4 border-l-red-500">
                        <h3 className="font-bold text-red-700 mb-4 flex items-center gap-2">
                            <ThumbsDown className="w-5 h-5" />
                            Areas of Concern
                            <Badge className="bg-red-100 text-red-700">{negative_themes.length}</Badge>
                        </h3>
                        <div className="space-y-4">
                            {negative_themes.slice(0, 5).map((theme, i) => (
                                <div key={i} className="p-3 bg-red-50 rounded-lg">
                                    <div className="flex items-center justify-between mb-2">
                                        <span className="font-bold text-red-800">{theme.theme}</span>
                                        <Badge variant="outline" className="text-xs">
                                            {theme.frequency || 'MEDIUM'}
                                        </Badge>
                                    </div>
                                    {theme.quote && (
                                        <div className="flex items-start gap-2 mt-2">
                                            <Quote className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                                            <p className="text-sm text-slate-600 italic">"{theme.quote}"</p>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </Card>
                )}
            </div>
            
            {/* Key Insights */}
            {(key_strengths.length > 0 || key_concerns.length > 0) && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                    {key_strengths.length > 0 && (
                        <div className="p-4 bg-emerald-50 rounded-xl">
                            <h4 className="font-bold text-emerald-700 mb-2 flex items-center gap-2">
                                <CheckCircle2 className="w-4 h-4" />
                                Customer-Validated Strengths
                            </h4>
                            <ul className="space-y-1">
                                {key_strengths.map((s, i) => (
                                    <li key={i} className="text-sm text-slate-700 flex items-start gap-2">
                                        <span className="text-emerald-500">✓</span> {s}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                    {key_concerns.length > 0 && (
                        <div className="p-4 bg-red-50 rounded-xl">
                            <h4 className="font-bold text-red-700 mb-2 flex items-center gap-2">
                                <AlertTriangle className="w-4 h-4" />
                                Customer Pain Points
                            </h4>
                            <ul className="space-y-1">
                                {key_concerns.map((c, i) => (
                                    <li key={i} className="text-sm text-slate-700 flex items-start gap-2">
                                        <span className="text-red-500">!</span> {c}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>
            )}
            
            {/* Analysis Narrative */}
            {analysis && (
                <Card className="bg-gradient-to-r from-pink-50 to-violet-50">
                    <h3 className="font-bold text-slate-800 mb-3 flex items-center gap-2">
                        <Activity className="w-4 h-4 text-pink-500" />
                        Customer Perception Analysis
                    </h3>
                    <p className="text-sm text-slate-700 leading-relaxed">{analysis}</p>
                </Card>
            )}
        </section>
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
        'immediate': 'border-l-emerald-500 bg-emerald-50/30',
        'medium': 'border-l-amber-500 bg-amber-50/30',
        'long': 'border-l-violet-500 bg-violet-50/30'
    };
    
    const priorityColors = {
        'CRITICAL': 'bg-red-100 text-red-700',
        'HIGH': 'bg-orange-100 text-orange-700',
        'MEDIUM': 'bg-amber-100 text-amber-700',
        'LOW': 'bg-slate-100 text-slate-700'
    };
    
    return (
        <div className={`bg-white border border-slate-200 rounded-xl p-5 border-l-4 ${timelineColors[timeline]}`}>
            {/* Header */}
            <div className="flex items-start justify-between mb-3">
                <h4 className="font-bold text-slate-900 text-lg">{rec.title}</h4>
                <Badge className={`text-xs font-bold ${priorityColors[rec.priority] || priorityColors['MEDIUM']}`}>
                    {rec.priority || 'MEDIUM'}
                </Badge>
            </div>
            
            {/* Current State & Root Cause */}
            {(rec.current_state || rec.root_cause) && (
                <div className="mb-4 p-3 bg-slate-50 rounded-lg">
                    {rec.current_state && (
                        <div className="mb-2">
                            <span className="text-xs font-bold text-slate-500 uppercase">Current State:</span>
                            <p className="text-sm text-slate-700 mt-1">{rec.current_state}</p>
                        </div>
                    )}
                    {rec.root_cause && (
                        <div>
                            <span className="text-xs font-bold text-slate-500 uppercase">Root Cause:</span>
                            <p className="text-sm text-slate-700 mt-1">{rec.root_cause}</p>
                        </div>
                    )}
                </div>
            )}
            
            {/* Recommended Action */}
            <div className="mb-4">
                <span className="text-xs font-bold text-emerald-600 uppercase">Recommended Action:</span>
                <p className="text-sm text-slate-700 mt-1 leading-relaxed">{rec.recommended_action}</p>
            </div>
            
            {/* Implementation Steps */}
            {rec.implementation_steps && rec.implementation_steps.length > 0 && (
                <div className="mb-4 p-3 bg-blue-50 rounded-lg">
                    <span className="text-xs font-bold text-blue-600 uppercase mb-2 block">Implementation Steps:</span>
                    <ol className="space-y-1.5">
                        {rec.implementation_steps.map((step, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                                <span className="flex-shrink-0 w-5 h-5 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs font-bold">{i + 1}</span>
                                {step}
                            </li>
                        ))}
                    </ol>
                </div>
            )}
            
            {/* Metrics Row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
                {rec.timeline && (
                    <div className="p-2 bg-slate-50 rounded-lg">
                        <span className="text-xs text-slate-500 block">Timeline</span>
                        <span className="text-sm font-semibold text-slate-900">{rec.timeline}</span>
                    </div>
                )}
                {rec.estimated_cost && (
                    <div className="p-2 bg-slate-50 rounded-lg">
                        <span className="text-xs text-slate-500 block">Est. Cost</span>
                        <span className="text-sm font-semibold text-slate-900">{rec.estimated_cost}</span>
                    </div>
                )}
                {rec.success_metric && (
                    <div className="p-2 bg-slate-50 rounded-lg col-span-2">
                        <span className="text-xs text-slate-500 block">Success Metric</span>
                        <span className="text-sm font-semibold text-slate-900">{rec.success_metric}</span>
                    </div>
                )}
            </div>
            
            {/* Expected Outcome */}
            {rec.expected_outcome && (
                <div className="p-3 bg-green-50 rounded-lg">
                    <span className="text-xs font-bold text-green-600 uppercase">Expected Outcome:</span>
                    <p className="text-sm text-green-800 mt-1">{rec.expected_outcome}</p>
                </div>
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
                                        {data.rating && (
                                            <Badge className={`font-black text-lg px-3 ${
                                                data.rating.startsWith('A') ? 'bg-emerald-100 text-emerald-700' :
                                                data.rating.startsWith('B') ? 'bg-blue-100 text-blue-700' :
                                                data.rating.startsWith('C') ? 'bg-amber-100 text-amber-700' :
                                                'bg-red-100 text-red-700'
                                            }`}>Rating: {data.rating}</Badge>
                                        )}
                                        <Badge variant="outline">{data.category}</Badge>
                                        <Badge variant="outline">{data.geography}</Badge>
                                    </div>
                                    <div className="flex items-center gap-2 mb-3">
                                        <Star className="w-4 h-4 text-amber-500" />
                                        <span className="text-xs font-bold uppercase tracking-widest text-amber-600">Executive Summary</span>
                                    </div>
                                    <p className="text-slate-700 leading-relaxed">{data.executive_summary}</p>
                                    
                                    {/* Investment Thesis */}
                                    {data.investment_thesis && (
                                        <div className="mt-4 p-4 bg-violet-50 rounded-xl border border-violet-200">
                                            <div className="flex items-center gap-2 mb-2">
                                                <Lightbulb className="w-4 h-4 text-violet-600" />
                                                <span className="text-xs font-bold uppercase tracking-widest text-violet-600">Investment Thesis</span>
                                            </div>
                                            <p className="text-slate-700">{data.investment_thesis}</p>
                                        </div>
                                    )}
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
                                    {data.conclusion?.recommendation && (
                                        <div className={`mt-4 p-3 rounded-xl font-bold ${
                                            data.conclusion.recommendation === 'INVEST' ? 'bg-emerald-100 text-emerald-700' :
                                            data.conclusion.recommendation === 'HOLD' ? 'bg-amber-100 text-amber-700' :
                                            'bg-red-100 text-red-700'
                                        }`}>
                                            {data.conclusion.recommendation}
                                        </div>
                                    )}
                                </Card>
                            </div>
                        </div>
                    </section>
                    
                    {/* Market Landscape & Industry Structure */}
                    {data.market_landscape && (
                        <section>
                            <SectionHeader icon={Globe} title="Market Landscape & Industry Structure" subtitle="Porter's Five Forces Analysis" color="blue" />
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                <Card>
                                    <h3 className="font-bold text-slate-900 mb-4">Market Overview</h3>
                                    <div className="grid grid-cols-2 gap-4 mb-4">
                                        {data.market_landscape.tam && (
                                            <div className="p-3 bg-blue-50 rounded-lg">
                                                <span className="text-xs text-slate-500 block">Total Addressable Market</span>
                                                <span className="text-lg font-bold text-blue-700">{data.market_landscape.tam}</span>
                                            </div>
                                        )}
                                        {data.market_landscape.cagr && (
                                            <div className="p-3 bg-emerald-50 rounded-lg">
                                                <span className="text-xs text-slate-500 block">CAGR</span>
                                                <span className="text-lg font-bold text-emerald-700">{data.market_landscape.cagr}</span>
                                            </div>
                                        )}
                                    </div>
                                    {data.market_landscape.analysis && (
                                        <p className="text-sm text-slate-600 leading-relaxed">{data.market_landscape.analysis}</p>
                                    )}
                                </Card>
                                {data.market_landscape.porters_five_forces && (
                                    <Card>
                                        <h3 className="font-bold text-slate-900 mb-4">Porter's Five Forces</h3>
                                        <div className="space-y-3">
                                            {Object.entries(data.market_landscape.porters_five_forces).map(([key, value]) => (
                                                <div key={key} className="flex justify-between items-center p-2 bg-slate-50 rounded-lg">
                                                    <span className="text-sm text-slate-700 capitalize">{key.replace(/_/g, ' ')}</span>
                                                    <Badge className={
                                                        typeof value === 'string' && value.toLowerCase().includes('high') ? 'bg-red-100 text-red-700' :
                                                        typeof value === 'string' && value.toLowerCase().includes('low') ? 'bg-emerald-100 text-emerald-700' :
                                                        'bg-amber-100 text-amber-700'
                                                    }>{typeof value === 'string' ? value.split(' ')[0] : value}</Badge>
                                                </div>
                                            ))}
                                        </div>
                                    </Card>
                                )}
                            </div>
                        </section>
                    )}
                    
                    {/* Financial Performance */}
                    {data.financial_performance && (
                        <section>
                            <SectionHeader icon={TrendingUp} title="Financial Performance & Growth Trajectory" subtitle="Revenue, margins, and growth metrics" color="emerald" />
                            <Card>
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                                    {data.financial_performance.estimated_revenue && (
                                        <div className="p-3 bg-emerald-50 rounded-lg text-center">
                                            <span className="text-xs text-slate-500 block">Est. Revenue</span>
                                            <span className="text-lg font-bold text-emerald-700">{data.financial_performance.estimated_revenue}</span>
                                        </div>
                                    )}
                                    {data.financial_performance.growth_rate && (
                                        <div className="p-3 bg-blue-50 rounded-lg text-center">
                                            <span className="text-xs text-slate-500 block">Growth Rate</span>
                                            <span className="text-lg font-bold text-blue-700">{data.financial_performance.growth_rate}</span>
                                        </div>
                                    )}
                                    {data.financial_performance.profitability && (
                                        <div className="p-3 bg-violet-50 rounded-lg text-center">
                                            <span className="text-xs text-slate-500 block">Profitability</span>
                                            <span className="text-lg font-bold text-violet-700 capitalize">{data.financial_performance.profitability}</span>
                                        </div>
                                    )}
                                    {data.financial_performance.funding_status && (
                                        <div className="p-3 bg-amber-50 rounded-lg text-center">
                                            <span className="text-xs text-slate-500 block">Funding</span>
                                            <span className="text-lg font-bold text-amber-700">{data.financial_performance.funding_status}</span>
                                        </div>
                                    )}
                                </div>
                                {data.financial_performance.analysis && (
                                    <p className="text-sm text-slate-600 leading-relaxed">{data.financial_performance.analysis}</p>
                                )}
                            </Card>
                        </section>
                    )}
                    
                    {/* Consumer Perception */}
                    {data.consumer_perception && (
                        <section>
                            <SectionHeader icon={Users} title="Consumer Perception & Behavioral Analysis" subtitle="Brand awareness, loyalty, and perception" color="pink" />
                            <Card>
                                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
                                    {data.consumer_perception.brand_awareness && (
                                        <div className="p-3 bg-pink-50 rounded-lg">
                                            <span className="text-xs text-slate-500 block">Brand Awareness</span>
                                            <span className="text-lg font-bold text-pink-700">{data.consumer_perception.brand_awareness}</span>
                                        </div>
                                    )}
                                    {data.consumer_perception.customer_ratings && (
                                        <div className="p-3 bg-amber-50 rounded-lg">
                                            <span className="text-xs text-slate-500 block">Avg Rating</span>
                                            <span className="text-lg font-bold text-amber-700">{data.consumer_perception.customer_ratings} ⭐</span>
                                        </div>
                                    )}
                                    {data.consumer_perception.loyalty_metrics && (
                                        <div className="p-3 bg-emerald-50 rounded-lg">
                                            <span className="text-xs text-slate-500 block">Loyalty</span>
                                            <span className="text-lg font-bold text-emerald-700">{data.consumer_perception.loyalty_metrics}</span>
                                        </div>
                                    )}
                                </div>
                                {data.consumer_perception.purchase_drivers?.length > 0 && (
                                    <div className="mb-4">
                                        <h4 className="text-sm font-bold text-slate-700 mb-2">Key Purchase Drivers</h4>
                                        <div className="flex flex-wrap gap-2">
                                            {data.consumer_perception.purchase_drivers.map((driver, i) => (
                                                <Badge key={i} variant="outline" className="bg-white">{driver}</Badge>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                {data.consumer_perception.analysis && (
                                    <p className="text-sm text-slate-600 leading-relaxed">{data.consumer_perception.analysis}</p>
                                )}
                            </Card>
                        </section>
                    )}
                    
                    {/* Customer Perception & Brand Health - NEW DETAILED SECTION */}
                    {data.customer_perception_analysis && (
                        <CustomerPerceptionSection data={data.customer_perception_analysis} />
                    )}
                    
                    {/* Valuation */}
                    {data.valuation && (
                        <section>
                            <SectionHeader icon={TrendingUp} title="Valuation & Financial Outlook" subtitle="Implied valuation and key drivers" color="indigo" />
                            <Card>
                                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
                                    {data.valuation.implied_range && (
                                        <div className="p-4 bg-indigo-50 rounded-xl text-center">
                                            <span className="text-xs text-slate-500 block">Implied Valuation</span>
                                            <span className="text-xl font-black text-indigo-700">{data.valuation.implied_range}</span>
                                        </div>
                                    )}
                                    {data.valuation.revenue_multiple && (
                                        <div className="p-4 bg-violet-50 rounded-xl text-center">
                                            <span className="text-xs text-slate-500 block">Revenue Multiple</span>
                                            <span className="text-xl font-black text-violet-700">{data.valuation.revenue_multiple}</span>
                                        </div>
                                    )}
                                    {data.valuation.bcg_position && (
                                        <div className="p-4 bg-emerald-50 rounded-xl text-center">
                                            <span className="text-xs text-slate-500 block">BCG Matrix</span>
                                            <span className="text-xl font-black text-emerald-700">{data.competitive_positioning?.bcg_position || 'N/A'}</span>
                                        </div>
                                    )}
                                </div>
                                {data.valuation.key_value_drivers?.length > 0 && (
                                    <div className="mb-4">
                                        <h4 className="text-sm font-bold text-slate-700 mb-2">Key Value Drivers</h4>
                                        <div className="flex flex-wrap gap-2">
                                            {data.valuation.key_value_drivers.map((driver, i) => (
                                                <Badge key={i} className="bg-indigo-100 text-indigo-700">{driver}</Badge>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                {data.valuation.three_year_outlook && (
                                    <p className="text-sm text-slate-600 leading-relaxed">{data.valuation.three_year_outlook}</p>
                                )}
                            </Card>
                        </section>
                    )}
                    
                    {/* 8-Dimension Analysis - Radar + Quick Grid + Detailed Cards */}
                    <section>
                        <SectionHeader icon={BarChart3} title="8-Dimension Brand Analysis" subtitle="Comprehensive scoring breakdown with performance radar" color="violet" />
                        
                        {/* Radar Chart + Quick Grid Side by Side */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
                            {/* Performance Radar Chart */}
                            <PerformanceRadar dimensions={data.dimensions || []} brandName={data.brand_name} />
                            
                            {/* Quick Dimensions Overview */}
                            <Card>
                                <div className="flex items-center gap-2 mb-4">
                                    <div className="w-10 h-10 rounded-xl bg-violet-100 flex items-center justify-center">
                                        <BarChart3 className="w-5 h-5 text-violet-600" />
                                    </div>
                                    <div>
                                        <h3 className="text-lg font-bold text-slate-800">Score Overview</h3>
                                        <p className="text-xs text-slate-500">At-a-glance dimension scores</p>
                                    </div>
                                </div>
                                <QuickDimensionsGrid dimensions={data.dimensions || []} />
                                
                                {/* Legend */}
                                <div className="mt-4 pt-4 border-t border-slate-100 flex flex-wrap justify-center gap-4">
                                    <div className="flex items-center gap-1.5">
                                        <div className="w-3 h-3 rounded-full bg-emerald-500"></div>
                                        <span className="text-xs text-slate-600">Excellent (8-10)</span>
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                        <div className="w-3 h-3 rounded-full bg-violet-500"></div>
                                        <span className="text-xs text-slate-600">Good (6-7)</span>
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                        <div className="w-3 h-3 rounded-full bg-amber-500"></div>
                                        <span className="text-xs text-slate-600">Fair (4-5)</span>
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                        <div className="w-3 h-3 rounded-full bg-red-500"></div>
                                        <span className="text-xs text-slate-600">Poor (0-3)</span>
                                    </div>
                                </div>
                            </Card>
                        </div>
                        
                        {/* Detailed Dimension Cards Grid */}
                        <div className="mb-4">
                            <div className="flex items-center gap-2 mb-4">
                                <Activity className="w-5 h-5 text-violet-600" />
                                <h3 className="text-lg font-bold text-slate-800">Detailed Dimension Analysis</h3>
                                <Badge variant="outline" className="ml-2">{data.dimensions?.length || 0} Dimensions</Badge>
                            </div>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            {data.dimensions?.map((dim, i) => (
                                <DetailedDimensionCard key={i} dimension={dim} index={i} />
                            ))}
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
                        <SectionHeader icon={Zap} title="Strategic Recommendations" subtitle="Detailed actionable roadmap with implementation steps" color="emerald" />
                        
                        {/* Immediate (0-6 months) */}
                        {data.immediate_recommendations?.length > 0 && (
                            <div className="mb-8">
                                <div className="flex items-center gap-2 mb-4 p-3 bg-emerald-50 rounded-lg">
                                    <Clock className="w-5 h-5 text-emerald-600" />
                                    <h3 className="font-bold text-emerald-800 text-lg">Immediate Actions (0-6 months)</h3>
                                    <Badge className="bg-emerald-100 text-emerald-700 ml-auto">{data.immediate_recommendations.length} Actions</Badge>
                                </div>
                                <div className="space-y-4">
                                    {data.immediate_recommendations.map((rec, i) => (
                                        <RecommendationCard key={i} rec={rec} index={i} timeline="immediate" />
                                    ))}
                                </div>
                            </div>
                        )}
                        
                        {/* Medium-term (6-18 months) */}
                        {data.medium_term_recommendations?.length > 0 && (
                            <div className="mb-8">
                                <div className="flex items-center gap-2 mb-4 p-3 bg-amber-50 rounded-lg">
                                    <Calendar className="w-5 h-5 text-amber-600" />
                                    <h3 className="font-bold text-amber-800 text-lg">Medium-Term Initiatives (6-18 months)</h3>
                                    <Badge className="bg-amber-100 text-amber-700 ml-auto">{data.medium_term_recommendations.length} Initiatives</Badge>
                                </div>
                                <div className="space-y-4">
                                    {data.medium_term_recommendations.map((rec, i) => (
                                        <RecommendationCard key={i} rec={rec} index={i} timeline="medium" />
                                    ))}
                                </div>
                            </div>
                        )}
                        
                        {/* Long-term (18-36 months) */}
                        {data.long_term_recommendations?.length > 0 && (
                            <div className="mb-8">
                                <div className="flex items-center gap-2 mb-4 p-3 bg-violet-50 rounded-lg">
                                    <TrendingUp className="w-5 h-5 text-violet-600" />
                                    <h3 className="font-bold text-violet-800 text-lg">Long-Term Transformation (18-36 months)</h3>
                                    <Badge className="bg-violet-100 text-violet-700 ml-auto">{data.long_term_recommendations.length} Strategies</Badge>
                                </div>
                                <div className="space-y-4">
                                    {data.long_term_recommendations.map((rec, i) => (
                                        <RecommendationCard key={i} rec={rec} index={i} timeline="long" />
                                    ))}
                                </div>
                            </div>
                        )}
                        
                        {/* Empty state */}
                        {(!data.immediate_recommendations?.length && !data.medium_term_recommendations?.length && !data.long_term_recommendations?.length) && (
                            <div className="p-6 bg-slate-50 rounded-xl text-center">
                                <p className="text-slate-500">No strategic recommendations generated for this brand.</p>
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
