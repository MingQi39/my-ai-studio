/**
 * API 服务层
 *
 * 提供与后端 API 交互的函数
 */

// API 基础配置 - 根据当前访问地址自动适配后端地址
const getApiBaseUrl = () => {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  // 根据当前访问的 hostname 构建后端地址
  const hostname = window.location.hostname;
  return `http://${hostname}:10011/api/v1`;
};

const API_BASE_URL = getApiBaseUrl();

// Token 管理
const TOKEN_KEY = 'auth_token';
const USER_KEY = 'auth_user';

export const getToken = (): string | null => {
  return localStorage.getItem(TOKEN_KEY);
};

export const setToken = (token: string): void => {
  localStorage.setItem(TOKEN_KEY, token);
};

export const removeToken = (): void => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
};

export const getStoredUser = (): User | null => {
  const userStr = localStorage.getItem(USER_KEY);
  if (userStr) {
    try {
      return JSON.parse(userStr);
    } catch {
      return null;
    }
  }
  return null;
};

export const setStoredUser = (user: User): void => {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
};

// 用户类型
export interface User {
  id: string;
  email: string;
  username: string;
  is_active: boolean;
  created_at: string;
}

// 登录请求
export interface LoginRequest {
  email: string;
  password: string;
}

// 注册请求
export interface RegisterRequest {
  email: string;
  username: string;
  password: string;
}

// 认证响应
export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

// 适配器类型
export type AdapterType = 'official' | 'openrouter' | 'ollama' | 'vllm' | 'omp';

// 官方提供商
export type OfficialProvider = 'deepseek' | 'qwen' | 'gemini' | 'openai' | 'anthropic';

// 模型配置创建请求
export interface ModelConfigCreate {
  adapter_type: AdapterType;
  provider?: OfficialProvider | null;
  name: string;
  api_key: string;
  base_url: string;
  model_id: string;
  is_default?: boolean;
}

// 模型配置响应
export interface ModelConfigResponse {
  id: string;
  adapter_type: string;
  provider: string | null;
  name: string;
  base_url: string;
  model_id: string;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// 验证结果
export interface ValidationResult {
  valid: boolean;
  config_id?: string;
  adapter_type?: string;
  provider?: string;
  model_id?: string;
  error?: string;
  latency_ms?: number;
}

// API 错误
export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public detail?: string
  ) {
    super(detail || statusText);
    this.name = 'ApiError';
  }
}

// 通用请求函数
async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const token = getToken();

  const defaultHeaders: HeadersInit = {
    'Content-Type': 'application/json',
  };

  if (token) {
    (defaultHeaders as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  });

  if (!response.ok) {
    let detail: string | undefined;
    try {
      const errorData = await response.json();
      detail = errorData.detail || errorData.message;
    } catch {
      // 忽略 JSON 解析错误
    }
    throw new ApiError(response.status, response.statusText, detail);
  }

  return response.json();
}

// ============================================================================
// 认证 API
// ============================================================================

/**
 * 用户注册
 */
export async function register(data: RegisterRequest): Promise<AuthResponse> {
  const result = await request<AuthResponse>('/auth/register', {
    method: 'POST',
    body: JSON.stringify(data),
  });
  setToken(result.access_token);
  setStoredUser(result.user);
  return result;
}

/**
 * 用户登录
 */
export async function login(data: LoginRequest): Promise<AuthResponse> {
  const result = await request<AuthResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(data),
  });
  setToken(result.access_token);
  setStoredUser(result.user);
  return result;
}

/**
 * 获取当前用户
 */
export async function getCurrentUser(): Promise<User> {
  return request<User>('/auth/me');
}

/**
 * 退出登录
 */
export function logout(): void {
  removeToken();
}

// ============================================================================
// 模型配置 API
// ============================================================================

/**
 * 创建模型配置
 */
export async function createModelConfig(data: ModelConfigCreate): Promise<ModelConfigResponse> {
  return request<ModelConfigResponse>('/models', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * 获取模型配置列表
 */
export async function listModelConfigs(
  adapterType?: AdapterType,
  provider?: string
): Promise<ModelConfigResponse[]> {
  const params = new URLSearchParams();
  if (adapterType) params.append('adapter_type', adapterType);
  if (provider) params.append('provider', provider);

  const queryStr = params.toString();
  return request<ModelConfigResponse[]>(`/models${queryStr ? `?${queryStr}` : ''}`);
}

/**
 * 获取模型配置详情
 */
export async function getModelConfig(configId: string): Promise<ModelConfigResponse> {
  return request<ModelConfigResponse>(`/models/${configId}`);
}

/**
 * 更新模型配置
 */
export async function updateModelConfig(
  configId: string,
  data: Partial<ModelConfigCreate>
): Promise<ModelConfigResponse> {
  return request<ModelConfigResponse>(`/models/${configId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

/**
 * 删除模型配置
 */
export async function deleteModelConfig(configId: string): Promise<{ success: boolean }> {
  return request<{ success: boolean }>(`/models/${configId}`, {
    method: 'DELETE',
  });
}

/**
 * 验证模型配置（测试连接）
 */
export async function validateModelConfig(configId: string): Promise<ValidationResult> {
  const startTime = Date.now();
  const result = await request<ValidationResult>(`/models/${configId}/validate`, {
    method: 'POST',
  });
  result.latency_ms = Date.now() - startTime;
  return result;
}

/**
 * 快速测试连接（不保存配置）
 *
 * 由于后端没有直接的测试端点，我们先创建配置，验证，然后删除
 */
export async function testConnection(data: ModelConfigCreate): Promise<ValidationResult> {
  const startTime = Date.now();

  // 创建临时配置
  const config = await createModelConfig({
    ...data,
    name: `_test_${Date.now()}`,
    is_default: false,
  });

  try {
    // 验证配置
    const result = await validateModelConfig(config.id);
    result.latency_ms = Date.now() - startTime;
    return result;
  } finally {
    // 删除临时配置
    try {
      await deleteModelConfig(config.id);
    } catch {
      // 忽略删除错误
    }
  }
}

/**
 * 获取适配器类型信息
 */
export async function getAdapterTypes(): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>('/models/adapter-types');
}


// ============================================================================
// 内置模型目录（后端读取本机配置后返回的 OpenAI 兼容模型清单）
// ============================================================================

export interface BuiltinModelEntry {
  id: string;
  name: string;
}

export interface BuiltinProviderEntry {
  id: string;
  base_url: string;
  api_key_env: string | null;
  api_key_available: boolean;
  models: BuiltinModelEntry[];
}

export interface BuiltinModelCatalog {
  available: boolean;
  path: string;
  reason?: string;
  providers: BuiltinProviderEntry[];
}

/** 拉取后端预置的可用模型清单。 */
export async function getBuiltinModelCatalog(): Promise<BuiltinModelCatalog> {
  return request<BuiltinModelCatalog>('/models/omp/catalog');
}

// ============================================================================
// 会话管理 API
// ============================================================================

// 会话创建请求
export interface SessionCreate {
  title?: string;
  description?: string;
}

// 会话更新请求
export interface SessionUpdate {
  title?: string;
  description?: string;
  is_archived?: boolean;
}

// 会话响应
export interface SessionResponse {
  id: string;
  title: string;
  description: string | null;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  message_count: number;
}

// 消息响应
export interface MessageResponse {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  thinking_content: string | null;
  tokens_used: number | null;
  model_used: string | null;
  provider_used: string | null;
  tool_calls: Array<Record<string, unknown>> | null;
  created_at: string;
  attachments: Array<Record<string, unknown>> | null;
}

// 分页响应
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

/**
 * 创建会话
 */
export async function createSession(data: SessionCreate = {}): Promise<SessionResponse> {
  return request<SessionResponse>('/sessions', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * 获取会话列表
 */
export async function listSessions(
  page: number = 1,
  pageSize: number = 20,
  includeArchived: boolean = false
): Promise<PaginatedResponse<SessionResponse>> {
  const params = new URLSearchParams();
  params.append('page', page.toString());
  params.append('page_size', pageSize.toString());
  params.append('include_archived', includeArchived.toString());

  return request<PaginatedResponse<SessionResponse>>(`/sessions?${params.toString()}`);
}

/**
 * 获取会话详情
 */
export async function getSession(sessionId: string): Promise<SessionResponse> {
  return request<SessionResponse>(`/sessions/${sessionId}`);
}

/**
 * 更新会话
 */
export async function updateSession(
  sessionId: string,
  data: SessionUpdate
): Promise<SessionResponse> {
  return request<SessionResponse>(`/sessions/${sessionId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

/**
 * 删除会话
 */
export async function deleteSession(sessionId: string): Promise<{ success: boolean }> {
  return request<{ success: boolean }>(`/sessions/${sessionId}`, {
    method: 'DELETE',
  });
}

/**
 * 获取会话消息历史
 */
export async function getSessionMessages(
  sessionId: string,
  limit: number = 50
): Promise<MessageResponse[]> {
  const params = new URLSearchParams();
  params.append('limit', limit.toString());

  return request<MessageResponse[]>(`/sessions/${sessionId}/messages?${params.toString()}`);
}

// ============================================================================
// 聊天 API
// ============================================================================

// 聊天请求
export interface ChatRequest {
  session_id: string;
  message: string;
  file_ids?: string[];
  stream?: boolean;
  enable_reasoning?: boolean; // 是否启用推理模式
  system_prompt?: string; // 系统指令
  model_config_id?: string; // 指定使用的模型配置 ID
}


// 流式聊天块类型
export interface ChatStreamChunk {
  type: 'content' | 'thinking' | 'tool_call' | 'done' | 'error';
  content?: string;
  tool_call?: Record<string, unknown>;
  error?: string;
  message?: string;
  usage?: Record<string, unknown>;
  thinking?: string;
}

/**
 * 流式聊天 (SSE)
 * 返回一个 ReadableStream，可以逐块读取响应
 */
export async function streamChat(
  request: ChatRequest,
  onChunk: (chunk: ChatStreamChunk) => void,
  onError?: (error: Error) => void,
  onComplete?: () => void
): Promise<void> {
  const url = `${API_BASE_URL}/chat/stream`;
  const token = getToken();

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      let detail: string | undefined;
      try {
        const errorData = await response.json();
        detail = errorData.detail || errorData.message;
      } catch {
        // 忽略 JSON 解析错误
      }
      throw new ApiError(response.status, response.statusText, detail);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('Response body is not readable');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });

      // 处理 SSE 格式的数据
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // 保留最后一个不完整的行

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6).trim();
          if (data) {
            try {
              const chunk = JSON.parse(data) as ChatStreamChunk;
              onChunk(chunk);

              if (chunk.type === 'done') {
                onComplete?.();
                return;
              }

              if (chunk.type === 'error') {
                onError?.(new Error(chunk.message || chunk.error || 'Unknown error'));
                return;
              }
            } catch (e) {
              console.error('Failed to parse SSE chunk:', e, data);
            }
          }
        }
      }
    }

    onComplete?.();
  } catch (error) {
    onError?.(error instanceof Error ? error : new Error(String(error)));
  }
}

/**
 * 非流式聊天
 */
export async function completeChat(chatRequest: ChatRequest): Promise<MessageResponse> {
  return request<MessageResponse>('/chat/complete', {
    method: 'POST',
    body: JSON.stringify({ ...chatRequest, stream: false }),
  });
}

/**
 * 获取聊天历史
 */
export async function getChatHistory(
  sessionId: string,
  limit: number = 50
): Promise<MessageResponse[]> {
  const params = new URLSearchParams();
  params.append('limit', limit.toString());

  return request<MessageResponse[]>(`/chat/history/${sessionId}?${params.toString()}`);
}

// ============================================================================
// 文件管理 API
// ============================================================================

export interface FileUploadResponse {
  id: string;
  name: string;
  type: 'image' | 'video' | 'audio' | 'document';
  mime_type: string;
  size: number;
  url: string;
  created_at: string;
}

/**
 * 上传文件
 */
export async function uploadFile(file: File): Promise<FileUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const token = getToken();
  if (!token) {
    throw new Error('Not authenticated');
  }

  const response = await fetch(`${API_BASE_URL}/files/upload`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
    throw new ApiError(response.status, error.detail || 'Upload failed');
  }

  return response.json();
}

/**
 * 获取文件列表
 */
export async function listFiles(fileType?: string): Promise<FileUploadResponse[]> {
  const params = fileType ? `?file_type=${fileType}` : '';
  return request<FileUploadResponse[]>(`/files${params}`);
}

/**
 * 删除文件
 */
export async function deleteFile(fileId: string): Promise<{ success: boolean }> {
  return request<{ success: boolean }>(`/files/${fileId}`, {
    method: 'DELETE',
  });
}

// ============================================================================
// 系统提示词 API
// ============================================================================

export interface SystemInstructionCreate {
  title: string;
  content: string;
  is_default?: boolean;
}

export interface SystemInstructionUpdate {
  title?: string;
  content?: string;
  is_default?: boolean;
}

export interface SystemInstructionResponse {
  id: string;
  title: string;
  content: string;
  is_default: boolean;
  last_used_at: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * 获取系统提示词列表
 */
export async function listSystemInstructions(): Promise<SystemInstructionResponse[]> {
  return request<SystemInstructionResponse[]>('/system-instructions');
}

/**
 * 获取系统提示词详情
 */
export async function getSystemInstruction(id: string): Promise<SystemInstructionResponse> {
  return request<SystemInstructionResponse>(`/system-instructions/${id}`);
}

/**
 * 创建系统提示词
 */
export async function createSystemInstruction(
  data: SystemInstructionCreate
): Promise<SystemInstructionResponse> {
  return request<SystemInstructionResponse>('/system-instructions', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * 更新系统提示词
 */
export async function updateSystemInstruction(
  id: string,
  data: SystemInstructionUpdate
): Promise<SystemInstructionResponse> {
  return request<SystemInstructionResponse>(`/system-instructions/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

/**
 * 删除系统提示词
 */
export async function deleteSystemInstruction(id: string): Promise<void> {
  await request<void>(`/system-instructions/${id}`, {
    method: 'DELETE',
  });
}

/**
 * 标记系统提示词为已使用
 */
export async function markSystemInstructionAsUsed(id: string): Promise<SystemInstructionResponse> {
  return request<SystemInstructionResponse>(`/system-instructions/${id}/use`, {
    method: 'POST',
  });
}
