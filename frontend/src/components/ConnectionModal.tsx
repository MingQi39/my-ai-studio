import React, { useState, useEffect } from 'react';
import { X, Wifi, RefreshCw, Terminal, Globe, Bot, Sparkles, Server, Cloud, Layers, AlertCircle, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { cn } from '@/components/ui/utils';
import {
  createModelConfig,
  updateModelConfig,
  validateModelConfig,
  listModelConfigs,
  type AdapterType,
  type OfficialProvider,
  type ModelConfigCreate,
  type ModelConfigResponse,
  ApiError,
} from '@/services/api';

interface ConnectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  isDarkMode: boolean;
  onConfigSave?: (modelName: string, configId: string) => void;
  selectedProviderId?: string;
}

type ProviderCategory = 'official' | 'thirdparty' | 'local';

interface Provider {
  id: string;
  name: string;
  category: ProviderCategory;
  adapterType: AdapterType;
  officialProvider?: OfficialProvider;
  icon: React.ReactNode;
  defaultBaseUrl: string;
  defaultModelId?: string;
  isLocal?: boolean;
  description?: string;
}

const PROVIDERS: Provider[] = [
  // 1. Official Direct
  {
    id: 'deepseek',
    name: 'DeepSeek',
    category: 'official',
    adapterType: 'official',
    officialProvider: 'deepseek',
    icon: <Bot size={24} className="text-blue-500 dark:text-blue-400" />,
    defaultBaseUrl: 'https://api.deepseek.com/v1',
    defaultModelId: 'deepseek-chat',
    description: 'connection.providerDescriptions.deepseek'
  },
  {
    id: 'gemini',
    name: 'Google Gemini',
    category: 'official',
    adapterType: 'official',
    officialProvider: 'gemini',
    icon: <Sparkles size={24} className="text-indigo-500 dark:text-indigo-400" />,
    defaultBaseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai',
    defaultModelId: 'gemini-2.0-flash-exp',
    description: 'connection.providerDescriptions.gemini'
  },
  {
    id: 'qwen',
    name: 'Qwen',
    category: 'official',
    adapterType: 'official',
    officialProvider: 'qwen',
    icon: <Cloud size={24} className="text-purple-500 dark:text-purple-400" />,
    defaultBaseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    defaultModelId: 'qwen-plus',
    description: 'connection.providerDescriptions.qwen'
  },
  {
    id: 'openai',
    name: 'OpenAI (GPT)',
    category: 'official',
    adapterType: 'official',
    officialProvider: 'openai',
    icon: <Zap size={24} className="text-emerald-500 dark:text-emerald-400" />,
    defaultBaseUrl: 'https://api.openai.com/v1',
    defaultModelId: 'gpt-4o',
    description: 'connection.providerDescriptions.openai'
  },

  // 2. Third Party
  {
    id: 'openrouter',
    name: 'OpenRouter',
    category: 'thirdparty',
    adapterType: 'openrouter',
    icon: <Globe size={24} className="text-green-500 dark:text-green-400" />,
    defaultBaseUrl: 'https://openrouter.ai/api/v1',
    defaultModelId: 'openai/gpt-4o',
    description: 'connection.providerDescriptions.openrouter'
  },

  // 4. Local
  {
    id: 'ollama',
    name: 'Ollama',
    category: 'local',
    adapterType: 'ollama',
    icon: <Terminal size={24} className="text-orange-500 dark:text-orange-400" />,
    defaultBaseUrl: 'http://localhost:11434/v1',
    defaultModelId: 'llama3',
    isLocal: true,
    description: 'connection.providerDescriptions.ollama'
  },
  {
    id: 'vllm',
    name: 'vLLM / Local',
    category: 'local',
    adapterType: 'vllm',
    icon: <Server size={24} className="text-slate-500 dark:text-slate-400" />,
    defaultBaseUrl: 'http://localhost:8000/v1',
    defaultModelId: 'local-model',
    isLocal: true,
    description: 'connection.providerDescriptions.vllm'
  },
];

const CATEGORY_LABELS: Record<ProviderCategory, { label: string; icon: React.ReactNode }> = {
  official: { label: 'connection.official', icon: <Bot size={16} /> },
  thirdparty: { label: 'connection.thirdparty', icon: <Layers size={16} /> },
  local: { label: 'connection.local', icon: <Server size={16} /> },
};

// API Key 掩码常量
const API_KEY_MASK = '••••••••••••••••';

export function ConnectionModal({ isOpen, onClose, isDarkMode, onConfigSave, selectedProviderId: externalProviderId }: ConnectionModalProps) {
  const { t } = useTranslation();
  const [selectedCategory, setSelectedCategory] = useState<ProviderCategory>('official');
  const [selectedProviderId, setSelectedProviderId] = useState<string>('deepseek');

  const [baseUrl, setBaseUrl] = useState(PROVIDERS[0].defaultBaseUrl);
  const [apiKey, setApiKey] = useState('');
  const [modelId, setModelId] = useState(PROVIDERS[0].defaultModelId || '');
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [latency, setLatency] = useState(0);
  const [errorMessage, setErrorMessage] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [savedConfigs, setSavedConfigs] = useState<Record<string, ModelConfigResponse>>({});
  const [isLoadingConfigs, setIsLoadingConfigs] = useState(false);


  // Load saved configs when modal opens
  useEffect(() => {
    if (isOpen && !isLoadingConfigs) {
      loadSavedConfigs();
    }

  }, [isOpen]);

  // When externalProviderId is provided, auto-select it
  useEffect(() => {
    if (externalProviderId && isOpen) {
      const provider = PROVIDERS.find(p => p.id === externalProviderId);
      if (provider) {
        setSelectedCategory(provider.category);
        setSelectedProviderId(externalProviderId);
      }
    }
  }, [externalProviderId, isOpen]);

  const loadSavedConfigs = async () => {
    setIsLoadingConfigs(true);
    try {
      const configs = await listModelConfigs();
      // Build a map: provider_id -> config
      const configMap: Record<string, ModelConfigResponse> = {};
      configs.forEach(config => {
        // Map adapter_type + provider to our provider IDs
        let providerId = '';
        if (config.adapter_type === 'official' && config.provider) {
          providerId = config.provider; // deepseek, qwen, gemini
        } else if (config.adapter_type === 'openrouter') {
          providerId = 'openrouter';
        } else if (config.adapter_type === 'ollama') {
          providerId = 'ollama';
        } else if (config.adapter_type === 'vllm') {
          providerId = 'vllm';
        }
        if (providerId) {
          configMap[providerId] = config;
        }
      });
      setSavedConfigs(configMap);
    } catch (err) {
      console.error('Failed to load saved configs:', err);
    } finally {
      setIsLoadingConfigs(false);
    }
  };


  // When category changes, select the first provider in that category
  useEffect(() => {
    const categoryProviders = PROVIDERS.filter(p => p.category === selectedCategory);
    if (categoryProviders.length > 0) {
      const firstProvider = categoryProviders[0];
      // Only update if current provider is not in this category
      const currentProvider = PROVIDERS.find(p => p.id === selectedProviderId);
      if (!currentProvider || currentProvider.category !== selectedCategory) {
        setSelectedProviderId(firstProvider.id);
      }
    }
  }, [selectedCategory]);

  // Update form when provider changes
  useEffect(() => {
    const provider = PROVIDERS.find(p => p.id === selectedProviderId);
    if (provider) {
      // Check if we have saved config for this provider
      const savedConfig = savedConfigs[provider.id];

      if (savedConfig) {
        // Load saved config
        setBaseUrl(savedConfig.base_url);
        setModelId(savedConfig.model_id);
        // 已配置的 API Key 显示为掩码（表示已有配置）
        setApiKey(API_KEY_MASK);
      } else {
        // Use default values
        setBaseUrl(provider.defaultBaseUrl);
        setModelId(provider.defaultModelId || '');
        setApiKey('');
      }
    }
    setTestStatus('idle');
    setErrorMessage('');
  }, [selectedProviderId, savedConfigs]);

  if (!isOpen) return null;

  const currentProvider = PROVIDERS.find(p => p.id === selectedProviderId);
  const isLocal = currentProvider?.isLocal;

  // Filter providers by category
  const categoryProviders = PROVIDERS.filter(p => p.category === selectedCategory);

  // Build config data for API
  const buildConfigData = (name: string): ModelConfigCreate => {
    const provider = currentProvider!;
    // 如果 API Key 是掩码，不发送（后端将保持原密钥）
    const actualApiKey = apiKey === API_KEY_MASK ? '' : apiKey;
    return {
      adapter_type: provider.adapterType,
      provider: provider.officialProvider || null,
      name,
      api_key: actualApiKey,
      base_url: baseUrl,
      model_id: modelId,
      is_default: true,
    };
  };

  const handleTestConnection = async () => {
    if (!modelId.trim()) {
      toast.error(t('connection.modelIdRequired'));
      return;
    }
    // 如果是本地模式不需要 API Key，如果有已保存的配置且 API Key 是掩码也允许
    const hasSavedConfig = !!savedConfigs[currentProvider?.id || ''];
    const isApiKeyValid = isLocal || apiKey.trim() || (hasSavedConfig && apiKey === API_KEY_MASK);

    if (!isApiKeyValid) {
      toast.error(t('connection.apiKeyRequired'));
      return;
    }

    setTestStatus('testing');
    setErrorMessage('');
    const startTime = Date.now();

    try {
      let configId: string;

      // 如果已有保存的配置且 API Key 是掩码（未修改），直接使用已保存的配置验证
      if (hasSavedConfig && apiKey === API_KEY_MASK) {
        configId = savedConfigs[currentProvider!.id].id;
      } else {
        // 需要创建或更新配置后再验证
        const configData = buildConfigData(`_test_${Date.now()}`);
        const config = await createModelConfig(configData);
        configId = config.id;
      }

      try {
        // 验证配置
        const result = await validateModelConfig(configId);
        const elapsed = Date.now() - startTime;

        if (result.valid) {
          setLatency(elapsed);
          setTestStatus('success');
          toast.success(t('connection.testSuccess'));
        } else {
          setTestStatus('error');
          setErrorMessage(result.error || t('connection.validateFailed'));
          toast.error(result.error || t('connection.validateFailed'));
        }
      } catch (err) {
        setTestStatus('error');
        const msg = err instanceof ApiError ? err.detail || err.message : t('connection.validateRequestFailed');
        setErrorMessage(msg);
        toast.error(msg);
      }
    } catch (err) {
      setTestStatus('error');
      const msg = err instanceof ApiError ? err.detail || err.message : t('connection.createConfigFailed');
      setErrorMessage(msg);
      toast.error(msg);
    }
  };

  const handleSave = async () => {
    if (!modelId.trim()) {
      toast.error(t('connection.modelIdRequired'));
      return;
    }
    // 如果是本地模式不需要 API Key，如果有已保存的配置且 API Key 是掩码也允许
    const hasSavedConfig = !!savedConfigs[currentProvider?.id || ''];
    const isApiKeyValid = isLocal || apiKey.trim() || (hasSavedConfig && apiKey === API_KEY_MASK);
    if (!isApiKeyValid) {
      toast.error(t('connection.apiKeyRequired'));
      return;
    }

    setIsSaving(true);
    setErrorMessage('');

    try {
      const existingConfig = savedConfigs[currentProvider?.id || ''];
      let config: ModelConfigResponse;

      if (existingConfig) {
        // 更新现有配置
        const actualApiKey = apiKey === API_KEY_MASK ? undefined : apiKey;
        config = await updateModelConfig(existingConfig.id, {
          name: `${currentProvider?.name} - ${modelId}`,
          model_id: modelId,
          base_url: baseUrl,
          api_key: actualApiKey || undefined,
          is_default: true,
        });
      } else {
        // 创建新配置
        const configData = buildConfigData(`${currentProvider?.name} - ${modelId}`);
        config = await createModelConfig(configData);
      }

      // Reload configs after saving
      await loadSavedConfigs();

      if (onConfigSave) {
        onConfigSave(modelId, config.id);
      }

      toast.success(t(existingConfig ? 'connection.updated' : 'connection.saved', { name: currentProvider?.name }));
      onClose();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail || err.message : t('connection.saveFailed');
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className={cn(
      "fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200",
      isDarkMode && "dark"
    )}>
      <div
        className="w-[640px] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh] animate-in zoom-in-95 duration-200 transition-colors"
        style={{
          backgroundColor: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          boxShadow: isDarkMode ? '0 25px 50px -12px rgba(0, 0, 0, 0.7)' : '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
        }}
      >

        {/* 1. Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-color)]">
          <div className="flex flex-col gap-0.5">
            <h2 className="text-lg font-semibold text-[var(--text-primary)] tracking-tight">{t('connection.title')}</h2>
            <p className="text-xs text-[var(--text-secondary)]">{t('connection.subtitle')}</p>
          </div>
          <button
            onClick={onClose}
            className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors rounded-full p-1 hover:bg-[var(--bg-hover)]"
          >
            <X size={20} />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-6 custom-scrollbar bg-[var(--bg-main)]">

          {/* 2. Platform Category Tabs */}
          <div className="mb-6">
            <label className="block text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider mb-3">
              {t('connection.method')}
            </label>
            <div className="flex p-1 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)]">
              {(Object.keys(CATEGORY_LABELS) as ProviderCategory[]).map((cat) => {
                const isActive = selectedCategory === cat;
                return (
                  <button
                    key={cat}
                    onClick={() => setSelectedCategory(cat)}
                    className={cn(
                      "flex-1 flex items-center justify-center gap-2 py-2 text-sm font-medium rounded-lg transition-all duration-200",
                      isActive
                        ? "bg-[var(--bg-card)] text-[var(--text-primary)] shadow-sm ring-1 ring-black/5 dark:ring-white/10"
                        : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
                    )}
                  >
                    {CATEGORY_LABELS[cat].icon}
                    {t(CATEGORY_LABELS[cat].label)}
                  </button>
                );
              })}
            </div>
          </div>

          {/* 3. Provider Grid */}
          <div className="mb-8">
            <label className="block text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider mb-3">
              {t('connection.vendor')}
            </label>
            <div className="grid grid-cols-2 gap-3">
              {categoryProviders.map((provider) => {
                const isSelected = selectedProviderId === provider.id;
                const hasSavedConfig = !!savedConfigs[provider.id];
                return (
                  <button
                    key={provider.id}
                    onClick={() => setSelectedProviderId(provider.id)}
                    className={cn(
                      "flex items-center gap-3 px-4 h-[72px] rounded-xl border transition-all duration-200 text-left relative overflow-hidden group",
                      isSelected
                        ? (isDarkMode ? "bg-[#303136] border-[#A8C7FA] shadow-sm" : "bg-blue-50 border-blue-200 shadow-sm")
                        : (isDarkMode ? "bg-[#1E1F20] border-[var(--border-color)] hover:bg-[#252628] shadow-sm" : "bg-white border-[var(--border-color)] hover:border-blue-200 hover:bg-slate-50 shadow-sm")
                    )}
                  >
                    <div className={cn(
                      "w-10 h-10 rounded-lg flex items-center justify-center shrink-0 transition-colors border",
                      isSelected
                        ? (isDarkMode ? "bg-[#1E1F20] border-transparent" : "bg-white border-blue-100")
                        : (isDarkMode ? "bg-[#252628] border-transparent group-hover:bg-[#303136]" : "bg-gray-50 border-gray-100 group-hover:bg-white")
                    )}>
                      {provider.icon}
                    </div>
                    <div className="flex flex-col min-w-0 flex-1">
                      <span className={cn(
                        "text-sm font-medium truncate",
                        isSelected ? "text-blue-900 dark:text-white" : "text-[var(--text-primary)]"
                      )}>
                        {provider.name}
                      </span>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        {provider.description && (
                          <span className={cn(
                            "text-[10px] truncate",
                            isSelected ? "text-blue-700/80 dark:text-gray-400" : "text-[var(--text-secondary)]"
                          )}>
                            {t(provider.description)}
                          </span>
                        )}
                        {hasSavedConfig && (
                          <span className="text-[10px] text-green-600 dark:text-green-400 font-medium">
                            {t('connection.configured')}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Selection Indicator */}
                    {isSelected && (
                      <div className="absolute top-2 right-2 w-2 h-2 rounded-full bg-blue-500 dark:bg-[#A8C7FA] shadow-[0_0_8px_rgba(59,130,246,0.5)]" />
                    )}
                  </button>
                )
              })}
            </div>
          </div>

          {/* 4. Connection Details Form */}
          <div className="space-y-5 border-t border-[var(--border-color)] pt-6">

            {/* Base URL */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">{t('connection.endpoint')}</label>
              <div className="relative group">
                <input
                  type="text"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  className="w-full bg-[var(--bg-input)] border border-[var(--border-color)] rounded-lg h-10 px-3 text-sm font-mono text-[var(--text-primary)] focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-[var(--text-placeholder)]"
                />
              </div>
            </div>

            {/* API Key */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">{t('connection.apiKey')}</label>
                {isLocal ? (
                  <span className="text-[10px] text-green-600 dark:text-[#5FA45E] bg-green-100 dark:bg-[#5FA45E]/10 px-2 py-0.5 rounded-full font-medium">
                    {t('connection.localOptional')}
                  </span>
                ) : savedConfigs[currentProvider?.id || ''] && (
                  <span className="text-[10px] text-amber-600 dark:text-amber-400 bg-amber-100 dark:bg-amber-500/10 px-2 py-0.5 rounded-full font-medium">
                    {t('connection.keepKey')}
                  </span>
                )}
              </div>
              <div className="relative">
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  disabled={!!isLocal}
                  placeholder={isLocal ? t('connection.keyPlaceholderLocal') : (savedConfigs[currentProvider?.id || ''] ? t('connection.keyPlaceholderKeep') : t('connection.keyPlaceholderNew'))}
                  className={cn(
                    "w-full bg-[var(--bg-input)] border border-[var(--border-color)] rounded-lg h-10 px-3 text-sm font-mono text-[var(--text-primary)] focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-[var(--text-placeholder)]",
                    isLocal && "opacity-50 cursor-not-allowed bg-[var(--bg-hover)]"
                  )}
                />
              </div>
            </div>

            {/* Model ID */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">{t('connection.modelId')}</label>
              <input
                type="text"
                value={modelId}
                onChange={(e) => setModelId(e.target.value)}
                placeholder="e.g., deepseek-chat"
                className="w-full bg-[var(--bg-input)] border border-[var(--border-color)] rounded-lg h-10 px-3 text-sm text-[var(--text-primary)] focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-[var(--text-placeholder)]"
              />
              <p className="text-[11px] text-[var(--text-secondary)]">{t('connection.modelIdHint', { name: currentProvider?.name })}</p>
            </div>

          </div>

          {/* 5. Connection Test */}
          <div className="mt-8 flex items-center gap-4">
            <Button
              variant="outline"
              onClick={handleTestConnection}
              disabled={testStatus === 'testing'}
              className="border-[var(--border-color)] text-[var(--text-primary)] hover:bg-[var(--bg-hover)] h-9 px-4 gap-2 bg-transparent"
            >
              {testStatus === 'testing' ? (
                <RefreshCw size={14} className="animate-spin" />
              ) : (
                <Wifi size={14} />
              )}
              <span>{testStatus === 'testing' ? t('connection.testing') : t('connection.test')}</span>
            </Button>

            {/* Feedback State */}
            {testStatus === 'success' && (
              <div className="flex items-center gap-2 animate-in fade-in slide-in-from-left-2 duration-300">
                <div className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]"></div>
                <span className="text-sm font-medium text-green-600 dark:text-[#5FA45E]">{t('connection.connectSuccess', { ms: latency })}</span>
              </div>
            )}
            {testStatus === 'error' && (
              <div className="flex items-center gap-2 animate-in fade-in slide-in-from-left-2 duration-300">
                <AlertCircle size={14} className="text-red-500" />
                <span className="text-sm font-medium text-red-600 dark:text-red-400 truncate max-w-[300px]">{errorMessage || t('connection.connectFailed')}</span>
              </div>
            )}
          </div>

        </div>

        {/* 6. Footer */}
        <div className="p-5 border-t border-[var(--border-color)] flex justify-end gap-3 bg-[var(--bg-card)]">
          <Button
            variant="ghost"
            onClick={onClose}
            disabled={isSaving}
            className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
          >
            {t('common.cancel')}
          </Button>
          <Button
            onClick={handleSave}
            disabled={isSaving}
            className="bg-blue-600 hover:bg-blue-700 text-white dark:bg-[#A8C7FA] dark:hover:bg-[#8AB4F8] dark:text-[#000] font-medium min-w-[100px]"
          >
            {isSaving ? (
              <>
                <RefreshCw size={14} className="animate-spin mr-2" />
                {t('connection.saving')}
              </>
            ) : (
              t('connection.save')
            )}
          </Button>
        </div>

      </div>
    </div>
  );
}