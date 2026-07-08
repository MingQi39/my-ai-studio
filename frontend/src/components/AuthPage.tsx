import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { login, register, User } from '@/services/api';
import { Loader2, Mail, Lock, User as UserIcon, Sun, Moon } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { ParticlesBackground } from './ParticlesBackground';
import { LanguageSwitcher } from './LanguageSwitcher';
import { BrandLogo } from '@/components/BrandLogo';

interface AuthPageProps {
  onAuthSuccess: (user: User) => void;
  isDarkMode?: boolean;
  toggleTheme?: () => void;
}

export function AuthPage({ onAuthSuccess, isDarkMode = false, toggleTheme }: AuthPageProps) {
  const { t } = useTranslation();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 登录表单
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  // 注册表单
  const [registerEmail, setRegisterEmail] = useState('');
  const [registerUsername, setRegisterUsername] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  const [registerConfirmPassword, setRegisterConfirmPassword] = useState('');

  // 验证错误状态
  const [loginEmailError, setLoginEmailError] = useState('');
  const [loginPasswordError, setLoginPasswordError] = useState('');
  const [registerEmailError, setRegisterEmailError] = useState('');
  const [registerUsernameError, setRegisterUsernameError] = useState('');
  const [registerPasswordError, setRegisterPasswordError] = useState('');
  const [registerConfirmPasswordError, setRegisterConfirmPasswordError] = useState('');

  // 验证函数
  const validateEmail = (email: string): string => {
    if (!email) return t('auth.errors.emailRequired');
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) return t('auth.errors.emailInvalid');
    return '';
  };

  const validatePassword = (password: string): string => {
    if (!password) return t('auth.errors.passwordRequired');
    if (password.length < 6) return t('auth.errors.passwordTooShort');
    if (password.length > 20) return t('auth.errors.passwordTooLong');
    return '';
  };

  const validateUsername = (username: string): string => {
    if (!username) return t('auth.errors.usernameRequired');
    if (username.length < 3) return t('auth.errors.usernameTooShort');
    if (username.length > 20) return t('auth.errors.usernameTooLong');
    if (!/^[a-zA-Z0-9_\u4e00-\u9fa5]+$/.test(username)) return t('auth.errors.usernamePattern');
    return '';
  };

  const validateConfirmPassword = (password: string, confirmPassword: string): string => {
    if (!confirmPassword) return t('auth.errors.confirmPasswordRequired');
    if (password !== confirmPassword) return t('auth.errors.passwordMismatch');
    return '';
  };

  const handleLoginEmailChange = (value: string) => {
    setLoginEmail(value);
    if (value) setLoginEmailError(validateEmail(value));
    else setLoginEmailError('');
  };

  const handleLoginPasswordChange = (value: string) => {
    setLoginPassword(value);
    if (value) setLoginPasswordError(validatePassword(value));
    else setLoginPasswordError('');
  };

  const handleRegisterEmailChange = (value: string) => {
    setRegisterEmail(value);
    if (value) setRegisterEmailError(validateEmail(value));
    else setRegisterEmailError('');
  };

  const handleRegisterUsernameChange = (value: string) => {
    setRegisterUsername(value);
    if (value) setRegisterUsernameError(validateUsername(value));
    else setRegisterUsernameError('');
  };

  const handleRegisterPasswordChange = (value: string) => {
    setRegisterPassword(value);
    if (value) setRegisterPasswordError(validatePassword(value));
    else setRegisterPasswordError('');
    if (registerConfirmPassword) {
      setRegisterConfirmPasswordError(validateConfirmPassword(value, registerConfirmPassword));
    }
  };

  const handleRegisterConfirmPasswordChange = (value: string) => {
    setRegisterConfirmPassword(value);
    if (value) setRegisterConfirmPasswordError(validateConfirmPassword(registerPassword, value));
    else setRegisterConfirmPasswordError('');
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const emailErr = validateEmail(loginEmail);
    const passwordErr = validatePassword(loginPassword);

    setLoginEmailError(emailErr);
    setLoginPasswordError(passwordErr);

    if (emailErr || passwordErr) return;

    setIsLoading(true);
    try {
      const response = await login({ email: loginEmail, password: loginPassword });
      onAuthSuccess(response.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('auth.loginFailed'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const emailErr = validateEmail(registerEmail);
    const usernameErr = validateUsername(registerUsername);
    const passwordErr = validatePassword(registerPassword);
    const confirmPasswordErr = validateConfirmPassword(registerPassword, registerConfirmPassword);

    setRegisterEmailError(emailErr);
    setRegisterUsernameError(usernameErr);
    setRegisterPasswordError(passwordErr);
    setRegisterConfirmPasswordError(confirmPasswordErr);

    if (emailErr || usernameErr || passwordErr || confirmPasswordErr) return;

    setIsLoading(true);
    try {
      const response = await register({
        email: registerEmail,
        username: registerUsername,
        password: registerPassword,
      });
      onAuthSuccess(response.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('auth.registerFailed'));
    } finally {
      setIsLoading(false);
    }
  };

  // Modern input styles
  const inputContainerClass = "relative group transition-all duration-300";
  const iconClass = (active: boolean) => `absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 transition-colors duration-300 ${isDarkMode
    ? (active ? 'text-blue-400' : 'text-slate-500')
    : (active ? 'text-blue-500' : 'text-slate-400')
    }`;

  const inputClass = `pl-10 h-12 w-full transition-all duration-200 border-2 ${isDarkMode
    ? 'bg-slate-900/40 border-slate-700/50 focus:border-blue-500/80 focus:bg-slate-900/60 text-white placeholder:text-slate-500 hover:border-slate-600'
    : 'bg-white/60 border-slate-200 focus:border-blue-500 focus:bg-white text-slate-900 placeholder:text-slate-400 hover:border-blue-300'
    } rounded-xl shadow-inner backdrop-blur-sm`;

  const pageContainerStyle: React.CSSProperties = {
    position: 'fixed',
    top: 0,
    left: 0,
    width: '100%',
    height: '100dvh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'auto',
    zIndex: 50,
    backgroundColor: isDarkMode ? '#020617' : '#f1f5f9',
  };

  const gradientStyle: React.CSSProperties = {
    position: 'absolute',
    inset: 0,
    background: isDarkMode
      ? 'radial-gradient(circle at 50% -20%, #1e293b 0%, #0f172a 40%, #020617 100%)'
      : 'radial-gradient(circle at 50% -20%, #f1f5f9 0%, #e2e8f0 40%, #cbd5e1 100%)',
    zIndex: 0,
    pointerEvents: 'none',
  };

  return (
    <div style={pageContainerStyle}>
      {/* Background Layer */}
      <div style={gradientStyle}>
        <ParticlesBackground isDarkMode={isDarkMode} />
      </div>

      {/* Top-right Controls */}
      <div className="absolute top-4 right-4 sm:top-6 sm:right-6 z-[100] flex items-center gap-2 pointer-events-auto">
        <div className={`rounded-full ${isDarkMode ? 'bg-slate-900 border border-slate-700' : 'bg-white border border-slate-200 shadow-sm'}`}>
          <LanguageSwitcher compact menuAlign="end" tone="auth" isDarkMode={isDarkMode} />
        </div>
        <Button
          variant="outline"
          size="icon"
          onClick={toggleTheme}
          className={`rounded-full w-10 h-10 transition-all duration-300 ${isDarkMode
            ? 'bg-slate-900 border-slate-700 text-yellow-400 hover:bg-slate-800 hover:text-yellow-300'
            : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50 hover:text-slate-900'
            }`}
        >
          {isDarkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </Button>
      </div>

      {/* Main Content Card - Centered by Flexbox in parent */}
      <div className="relative z-10 w-full max-w-[440px] px-4 flex flex-col items-center justify-center animate-in fade-in zoom-in duration-500">
        <div className={`relative w-full rounded-2xl overflow-hidden transition-all duration-300 ${isDarkMode
          ? 'shadow-[0_0_40px_-10px_rgba(59,130,246,0.3)] hover:shadow-[0_0_60px_-10px_rgba(59,130,246,0.4)]'
          : 'shadow-[0_20px_40px_-5px_rgba(0,0,0,0.1)] hover:shadow-[0_25px_50px_-5px_rgba(0,0,0,0.15)]'
          }`}>
          <div className="absolute inset-0 p-[2px] rounded-2xl bg-gradient-to-br from-blue-500/50 via-cyan-400/30 to-blue-600/50 opacity-100" />

          <Card className={`relative w-full h-full border-0 rounded-xl backdrop-blur-2xl ${isDarkMode
            ? 'bg-slate-950/80'
            : 'bg-white/80'
            }`}>
            <CardHeader className="text-center pb-2 pt-8">
              <div className="mx-auto mb-4 relative">
                <BrandLogo
                  size="lg"
                  alt={t('common.appName')}
                  className="mx-auto transition-transform hover:scale-110 duration-300"
                />
              </div>
              <CardTitle className={`text-3xl font-bold tracking-tight mb-2 ${isDarkMode ? 'text-white' : 'text-slate-900'
                }`}>
                {t('common.appName')}
              </CardTitle>
              <CardDescription className={isDarkMode ? 'text-slate-400' : 'text-slate-500 font-medium'}>
                {t('auth.tagline')}
              </CardDescription>
            </CardHeader>

            <CardContent className="p-8 pt-4">
              <Tabs defaultValue="login" className="w-full">
                <TabsList className={`grid w-full grid-cols-2 mb-8 p-1.5 h-14 rounded-xl ${isDarkMode ? 'bg-slate-900/50' : 'bg-slate-100'
                  }`}>
                  <TabsTrigger
                    value="login"
                    className={`rounded-lg h-full text-base font-medium transition-all duration-200 data-[state=active]:shadow-md ${isDarkMode
                      ? 'data-[state=active]:bg-slate-800 data-[state=active]:text-white text-slate-400 hover:text-slate-200'
                      : 'data-[state=active]:bg-white data-[state=active]:text-blue-600 text-slate-500 hover:text-slate-700'
                      }`}
                  >
                    {t('auth.tabLogin')}
                  </TabsTrigger>
                  <TabsTrigger
                    value="register"
                    className={`rounded-lg h-full text-base font-medium transition-all duration-200 data-[state=active]:shadow-md ${isDarkMode
                      ? 'data-[state=active]:bg-slate-800 data-[state=active]:text-white text-slate-400 hover:text-slate-200'
                      : 'data-[state=active]:bg-white data-[state=active]:text-blue-600 text-slate-500 hover:text-slate-700'
                      }`}
                  >
                    {t('auth.tabRegister')}
                  </TabsTrigger>
                </TabsList>

                <div className="min-h-[300px]">
                  {error && (
                    <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center gap-3 animate-in slide-in-from-top-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-red-500" />
                      <p className="text-sm text-red-500 font-medium">{error}</p>
                    </div>
                  )}

                  <TabsContent value="login" className="animate-in fade-in slide-in-from-right-8 duration-300">
                    <form onSubmit={handleLogin} className="space-y-6">
                      <div className="space-y-2">
                        <Label htmlFor="login-email" className={isDarkMode ? 'text-slate-300' : 'text-slate-700 font-medium'}>
                          {t('auth.email')}
                        </Label>
                        <div className={inputContainerClass}>
                          <Mail className={iconClass(!!loginEmail)} />
                          <Input
                            id="login-email"
                            type="email"
                            placeholder="name@example.com"
                            value={loginEmail}
                            onChange={(e) => handleLoginEmailChange(e.target.value)}
                            required
                            className={`${inputClass} ${loginEmailError ? 'border-red-500 focus:border-red-500' : ''}`}
                          />
                        </div>
                        {loginEmailError && (
                          <p className="text-xs text-red-500 mt-1 animate-in slide-in-from-top-1">{loginEmailError}</p>
                        )}
                      </div>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <Label htmlFor="login-password" className={isDarkMode ? 'text-slate-300' : 'text-slate-700 font-medium'}>
                            {t('auth.password')}
                          </Label>
                          <a href="#" className="text-xs font-medium text-blue-500 hover:text-blue-400 transition-colors">
                            {t('auth.forgotPassword')}
                          </a>
                        </div>
                        <div className={inputContainerClass}>
                          <Lock className={iconClass(!!loginPassword)} />
                          <Input
                            id="login-password"
                            type="password"
                            placeholder="••••••••"
                            value={loginPassword}
                            onChange={(e) => handleLoginPasswordChange(e.target.value)}
                            required
                            className={`${inputClass} ${loginPasswordError ? 'border-red-500 focus:border-red-500' : ''}`}
                          />
                        </div>
                        {loginPasswordError && (
                          <p className="text-xs text-red-500 mt-1 animate-in slide-in-from-top-1">{loginPasswordError}</p>
                        )}
                      </div>
                      <Button
                        type="submit"
                        className="w-full h-12 text-base font-medium rounded-xl bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white shadow-lg shadow-blue-500/30 transition-all hover:scale-[1.02] active:scale-[0.98] mt-4"
                        disabled={isLoading}
                      >
                        {isLoading ? (
                          <>
                            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                            {t('auth.loggingIn')}
                          </>
                        ) : (
                          t('auth.submitLogin')
                        )}
                      </Button>
                    </form>
                  </TabsContent>

                  <TabsContent value="register" className="mt-0 animate-in fade-in slide-in-from-right-8 duration-300">
                    <form onSubmit={handleRegister} className="space-y-5">
                      <div className="space-y-2">
                        <Label htmlFor="register-email" className={isDarkMode ? 'text-slate-300' : 'text-slate-700 font-medium'}>
                          {t('auth.email')}
                        </Label>
                        <div className={inputContainerClass}>
                          <Mail className={iconClass(!!registerEmail)} />
                          <Input
                            id="register-email"
                            type="email"
                            placeholder="name@example.com"
                            value={registerEmail}
                            onChange={(e) => handleRegisterEmailChange(e.target.value)}
                            required
                            className={`${inputClass} ${registerEmailError ? 'border-red-500 focus:border-red-500' : ''}`}
                          />
                        </div>
                        {registerEmailError && (
                          <p className="text-xs text-red-500 mt-1 animate-in slide-in-from-top-1">{registerEmailError}</p>
                        )}
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="register-username" className={isDarkMode ? 'text-slate-300' : 'text-slate-700 font-medium'}>
                          {t('auth.username')}
                        </Label>
                        <div className={inputContainerClass}>
                          <UserIcon className={iconClass(!!registerUsername)} />
                          <Input
                            id="register-username"
                            type="text"
                            placeholder={t('auth.placeholderUsername')}
                            value={registerUsername}
                            onChange={(e) => handleRegisterUsernameChange(e.target.value)}
                            required
                            minLength={3}
                            className={`${inputClass} ${registerUsernameError ? 'border-red-500 focus:border-red-500' : ''}`}
                          />
                        </div>
                        {registerUsernameError && (
                          <p className="text-xs text-red-500 mt-1 animate-in slide-in-from-top-1">{registerUsernameError}</p>
                        )}
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="register-password" className={isDarkMode ? 'text-slate-300' : 'text-slate-700 font-medium'}>
                          {t('auth.newPassword')}
                        </Label>
                        <div className={inputContainerClass}>
                          <Lock className={iconClass(!!registerPassword)} />
                          <Input
                            id="register-password"
                            type="password"
                            placeholder={t('auth.placeholderPassword')}
                            value={registerPassword}
                            onChange={(e) => handleRegisterPasswordChange(e.target.value)}
                            required
                            minLength={6}
                            className={`${inputClass} ${registerPasswordError ? 'border-red-500 focus:border-red-500' : ''}`}
                          />
                        </div>
                        {registerPasswordError && (
                          <p className="text-xs text-red-500 mt-1 animate-in slide-in-from-top-1">{registerPasswordError}</p>
                        )}
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="register-confirm-password" className={isDarkMode ? 'text-slate-300' : 'text-slate-700 font-medium'}>
                          {t('auth.confirmPassword')}
                        </Label>
                        <div className={inputContainerClass}>
                          <Lock className={iconClass(!!registerConfirmPassword)} />
                          <Input
                            id="register-confirm-password"
                            type="password"
                            placeholder={t('auth.placeholderConfirmPassword')}
                            value={registerConfirmPassword}
                            onChange={(e) => handleRegisterConfirmPasswordChange(e.target.value)}
                            required
                            className={`${inputClass} ${registerConfirmPasswordError ? 'border-red-500 focus:border-red-500' : ''}`}
                          />
                        </div>
                        {registerConfirmPasswordError && (
                          <p className="text-xs text-red-500 mt-1 animate-in slide-in-from-top-1">{registerConfirmPasswordError}</p>
                        )}
                      </div>
                      <Button
                        type="submit"
                        className="w-full h-12 text-base font-medium rounded-xl bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white shadow-lg shadow-blue-500/30 transition-all hover:scale-[1.02] active:scale-[0.98] mt-4"
                        disabled={isLoading}
                      >
                        {isLoading ? (
                          <>
                            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                            {t('auth.registering')}
                          </>
                        ) : (
                          t('auth.submitRegister')
                        )}
                      </Button>
                    </form>
                  </TabsContent>
                </div>
              </Tabs>
            </CardContent>
          </Card>
        </div>

        {/* Footer info */}
        <div className="text-center mt-6 sm:mt-8 animate-in fade-in duration-1000 delay-300 pb-6 sm:pb-0 sm:fixed sm:bottom-6 w-full pointer-events-none px-4">
          <p className={`text-sm ${isDarkMode ? 'text-slate-600' : 'text-slate-400'}`}>
            © 2026 {t('common.appOwner')}
          </p>
        </div>
      </div>
    </div>
  );
}
