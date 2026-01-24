import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2, Mail, Lock, User, X, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { ReportPreviewCompact } from './ReportPreview';

const AuthModal = () => {
    const { showAuthModal, closeAuthModal, loginWithGoogle, loginWithEmail, registerWithEmail } = useAuth();
    const [activeTab, setActiveTab] = useState('login');
    const [loading, setLoading] = useState(false);
    
    // Login form
    const [loginEmail, setLoginEmail] = useState('');
    const [loginPassword, setLoginPassword] = useState('');
    
    // Register form
    const [registerName, setRegisterName] = useState('');
    const [registerEmail, setRegisterEmail] = useState('');
    const [registerPassword, setRegisterPassword] = useState('');
    const [registerConfirmPassword, setRegisterConfirmPassword] = useState('');

    if (!showAuthModal) return null;

    const handleLogin = async (e) => {
        e.preventDefault();
        if (!loginEmail || !loginPassword) {
            toast.error("Please fill in all fields");
            return;
        }
        
        setLoading(true);
        const result = await loginWithEmail(loginEmail, loginPassword);
        setLoading(false);
        
        if (result.success) {
            toast.success("Welcome back!");
        } else {
            toast.error(result.error);
        }
    };

    const handleRegister = async (e) => {
        e.preventDefault();
        if (!registerName || !registerEmail || !registerPassword) {
            toast.error("Please fill in all fields");
            return;
        }
        
        if (registerPassword !== registerConfirmPassword) {
            toast.error("Passwords don't match");
            return;
        }
        
        if (registerPassword.length < 6) {
            toast.error("Password must be at least 6 characters");
            return;
        }
        
        setLoading(true);
        const result = await registerWithEmail(registerEmail, registerPassword, registerName);
        setLoading(false);
        
        if (result.success) {
            toast.success("Account created successfully!");
        } else {
            toast.error(result.error);
        }
    };

    return (
        <div 
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
            onClick={(e) => {
                // Close modal when clicking the backdrop (outside the card)
                if (e.target === e.currentTarget) {
                    closeAuthModal();
                }
            }}
        >
            <Card className="w-full max-w-md bg-white rounded-2xl shadow-2xl border-0 overflow-hidden animate-in fade-in zoom-in duration-300 relative z-10"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <CardHeader className="relative bg-gradient-to-r from-violet-600 via-fuchsia-500 to-orange-500 text-white pb-8 pt-6">
                    <button 
                        onClick={closeAuthModal}
                        className="absolute top-4 right-4 p-1 rounded-full hover:bg-white/20 transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                    <div className="flex items-center gap-3 mb-2">
                        <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center">
                            <Sparkles className="w-6 h-6" />
                        </div>
                        <CardTitle className="text-2xl font-black">RIGHTNAME</CardTitle>
                    </div>
                    <CardDescription className="text-white/80 font-medium">
                        Sign in to unlock your full brand analysis report
                    </CardDescription>
                </CardHeader>

                <CardContent className="p-6">
                    {/* Report Preview */}
                    <ReportPreviewCompact />
                    
                    <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                        <TabsList className="grid w-full grid-cols-2 mb-6 bg-slate-100 p-1 rounded-xl">
                            <TabsTrigger 
                                value="login" 
                                className="rounded-lg font-bold data-[state=active]:bg-white data-[state=active]:shadow-sm"
                            >
                                Sign In
                            </TabsTrigger>
                            <TabsTrigger 
                                value="register"
                                className="rounded-lg font-bold data-[state=active]:bg-white data-[state=active]:shadow-sm"
                            >
                                Register
                            </TabsTrigger>
                        </TabsList>

                        {/* Login Tab */}
                        <TabsContent value="login" className="space-y-4">
                            <form onSubmit={handleLogin} className="space-y-4">
                                <div className="space-y-2">
                                    <Label className="text-xs font-bold uppercase tracking-wider text-slate-500">Email</Label>
                                    <div className="relative">
                                        <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                                        <Input 
                                            type="email"
                                            value={loginEmail}
                                            onChange={(e) => setLoginEmail(e.target.value)}
                                            placeholder="you@example.com"
                                            className="pl-10 h-12 bg-slate-50 border-2 border-slate-200 rounded-xl font-medium"
                                        />
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    <Label className="text-xs font-bold uppercase tracking-wider text-slate-500">Password</Label>
                                    <div className="relative">
                                        <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                                        <Input 
                                            type="password"
                                            value={loginPassword}
                                            onChange={(e) => setLoginPassword(e.target.value)}
                                            placeholder="••••••••"
                                            className="pl-10 h-12 bg-slate-50 border-2 border-slate-200 rounded-xl font-medium"
                                        />
                                    </div>
                                </div>
                                <Button 
                                    type="submit" 
                                    className="w-full h-12 bg-gradient-to-r from-violet-600 to-fuchsia-500 hover:from-violet-700 hover:to-fuchsia-600 text-white font-bold rounded-xl shadow-lg"
                                    disabled={loading}
                                >
                                    {loading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                                    Sign In
                                </Button>
                            </form>

                            {/* Email Sign In Only */}
                        </TabsContent>

                        {/* Register Tab */}
                        <TabsContent value="register" className="space-y-4">
                            <form onSubmit={handleRegister} className="space-y-4">
                                <div className="space-y-2">
                                    <Label className="text-xs font-bold uppercase tracking-wider text-slate-500">Full Name</Label>
                                    <div className="relative">
                                        <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                                        <Input 
                                            type="text"
                                            value={registerName}
                                            onChange={(e) => setRegisterName(e.target.value)}
                                            placeholder="John Doe"
                                            className="pl-10 h-12 bg-slate-50 border-2 border-slate-200 rounded-xl font-medium"
                                        />
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    <Label className="text-xs font-bold uppercase tracking-wider text-slate-500">Email</Label>
                                    <div className="relative">
                                        <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                                        <Input 
                                            type="email"
                                            value={registerEmail}
                                            onChange={(e) => setRegisterEmail(e.target.value)}
                                            placeholder="you@example.com"
                                            className="pl-10 h-12 bg-slate-50 border-2 border-slate-200 rounded-xl font-medium"
                                        />
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    <Label className="text-xs font-bold uppercase tracking-wider text-slate-500">Password</Label>
                                    <div className="relative">
                                        <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                                        <Input 
                                            type="password"
                                            value={registerPassword}
                                            onChange={(e) => setRegisterPassword(e.target.value)}
                                            placeholder="Min. 6 characters"
                                            className="pl-10 h-12 bg-slate-50 border-2 border-slate-200 rounded-xl font-medium"
                                        />
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    <Label className="text-xs font-bold uppercase tracking-wider text-slate-500">Confirm Password</Label>
                                    <div className="relative">
                                        <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                                        <Input 
                                            type="password"
                                            value={registerConfirmPassword}
                                            onChange={(e) => setRegisterConfirmPassword(e.target.value)}
                                            placeholder="••••••••"
                                            className="pl-10 h-12 bg-slate-50 border-2 border-slate-200 rounded-xl font-medium"
                                        />
                                    </div>
                                </div>
                                <Button 
                                    type="submit" 
                                    className="w-full h-12 bg-gradient-to-r from-violet-600 to-fuchsia-500 hover:from-violet-700 hover:to-fuchsia-600 text-white font-bold rounded-xl shadow-lg"
                                    disabled={loading}
                                >
                                    {loading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                                    Create Account
                                </Button>
                            </form>

                            <div className="relative my-6">
                                <div className="absolute inset-0 flex items-center">
                                    <div className="w-full border-t border-slate-200"></div>
                                </div>
                                <div className="relative flex justify-center text-xs uppercase">
                                    <span className="bg-white px-4 text-slate-400 font-bold">or</span>
                                </div>
                            </div>

                            <Button 
                                type="button"
                                variant="outline" 
                                className="w-full h-12 border-2 border-slate-200 rounded-xl font-bold hover:bg-slate-50"
                                onClick={loginWithGoogle}
                            >
                                <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
                                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                                </svg>
                                Sign up with Google
                            </Button>
                        </TabsContent>
                    </Tabs>

                    <p className="text-xs text-center text-slate-400 mt-6">
                        By continuing, you agree to our Terms of Service and Privacy Policy
                    </p>
                </CardContent>
            </Card>
        </div>
    );
};

export default AuthModal;
