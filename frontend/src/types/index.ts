export interface AuthResponse {
  token: string;
  username: string;
  role: string;
  tenant_id: string;
}

export interface VerifyResponse {
  valid: boolean;
  user: {
    user_id: string;
    username: string;
    role: string;
    tenant_id: string;
  };
}

export interface DocumentResponse {
  id: string;
  filename: string;
  file_size: number;
  file_type: string;
  chunks_count: number;
  status: string;
  created_at?: string;
  tags?: string[];
  source?: string;
}

export interface Conversation {
  id: string;
  title: string;
  tenant_id: string;
  created_at: string;
  updated_at?: string;
}

export interface ConversationDetail extends Conversation {
  messages: ConversationMessage[];
}

export interface ConversationMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

export interface ConversationArchiveUpdate {
  is_archived: boolean;
}

export interface ConversationTagsUpdate {
  tags: string[];
}

export interface User {
  id: string;
  username: string;
  role: string;
  tenant_id: string;
  is_active: boolean;
  status: string;
  created_at: string;
  last_login?: string;
}

export interface CreateUser {
  username: string;
  password: string;
  role?: string;
  tenant_id?: string;
}

export interface UpdateUser {
  username?: string;
  role?: string;
  is_active?: boolean;
}

export interface AuditLog {
  id: string;
  action: string;
  user_id?: string;
  username?: string;
  ip_address?: string;
  details?: string;
  tenant_id: string;
  created_at: string;
}

export interface AuditLogResponse {
  items: AuditLog[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ModelConfig {
  id: string;
  name: string;
  provider: string;
  model_id: string;
  api_base: string;
  model_type: string;
  max_tokens: number;
  is_active: boolean;
  is_default: boolean;
  description?: string;
  created_at?: string;
}

export interface CreateModelConfig {
  name: string;
  provider: string;
  model_id: string;
  api_base: string;
  api_key: string;
  model_type?: string;
  max_tokens?: number;
  is_default?: boolean;
  description?: string;
}

export interface UpdateModelConfig {
  name?: string;
  provider?: string;
  model_id?: string;
  api_base?: string;
  api_key?: string;
  model_type?: string;
  max_tokens?: number;
  is_active?: boolean;
  is_default?: boolean;
  description?: string;
}

export interface TestResult {
  success: boolean;
  message: string;
  response_time?: number;
}

export interface Category {
  id: string;
  name: string;
  parent_id?: string;
  description?: string;
  tenant_id: string;
  created_at?: string;
}

export interface Role {
  name: string;
  display_name: string;
  level: number;
  description?: string;
}

export interface CreateCategory {
  name: string;
  parent_id?: string;
  description?: string;
  tenant_id?: string;
}

export interface Review {
  id: number;
  document_id: string;
  reviewer?: string;
  status: string;
  comment?: string;
  created_at: string;
}

export interface UpdateReview {
  status: string;
  comment?: string;
}

export interface BatchReview {
  review_ids: number[];
  status: string;
  comment?: string;
}

export interface FeedbackStats {
  total_feedback: number;
  avg_rating: number;
  helpful_count: number;
  not_helpful_count: number;
  rating_distribution?: Record<number, number>;
}

export interface FeedbackTrend {
  date: string;
  avg_rating: number;
  count: number;
}

export interface CreateFeedback {
  query: string;
  rating: number;
  answer?: string;
  comment?: string;
  helpful?: boolean;
  tenant_id?: string;
}
