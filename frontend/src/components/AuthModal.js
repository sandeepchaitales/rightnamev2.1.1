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

                            {/* Email Sign Up Only */}
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
