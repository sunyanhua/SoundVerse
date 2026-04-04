// API相关类型定义

// 请求选项
export interface RequestOptions {
  url: string;
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  data?: any;
  params?: Record<string, any>;
  headers?: Record<string, string>;
  withAuth?: boolean;
  showLoading?: boolean;
  loadingText?: string;
}

// API响应格式
export interface ApiResponse<T = any> {
  success: boolean;
  data: T | null;
  code: number;
  message: string;
}

// 分页参数
export interface PaginationParams {
  page?: number;
  page_size?: number;
  limit?: number;
  offset?: number;
}

// 分页响应
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_more: boolean;
}

// 用户相关类型
export interface User {
  id: string;
  wechat_openid?: string;
  nickname?: string;
  avatar_url?: string;
  gender?: number;
  country?: string;
  province?: string;
  city?: string;
  is_active: boolean;
  is_premium: boolean;
  is_admin: boolean;
  daily_chat_count: number;
  daily_generate_count: number;
  total_chat_count: number;
  total_generate_count: number;
  last_active_at?: string;
  preferred_voice: string;
  preferred_language: string;
  notification_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserQuota {
  daily_chat_limit: number;
  daily_generate_limit: number;
  daily_asr_limit: number;
  daily_tts_limit: number;
  daily_nlp_limit: number;
  used_chat_count: number;
  used_generate_count: number;
  used_asr_seconds: number;
  used_tts_chars: number;
  used_nlp_requests: number;
  remaining_chat_count: number;
  remaining_generate_count: number;
  remaining_asr_seconds: number;
  remaining_tts_chars: number;
  remaining_nlp_requests: number;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token?: string;
}

// 音频相关类型
export interface AudioSource {
  id: string;
  title: string;
  description?: string;
  program_type: string;
  episode_number?: string;
  broadcast_date?: string;
  original_filename: string;
  file_size: number;
  duration: number;
  format: string;
  sample_rate: number;
  channels: number;
  oss_key: string;
  oss_url: string;
  processing_status: string;
  processing_progress: number;
  error_message?: string;
  copyright_holder?: string;
  license_type?: string;
  is_public: boolean;
  tags?: string[];
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
  segments_count?: number;
}

export interface AudioSegment {
  id: string;
  source_id: string;
  user_id?: string;
  start_time: number;
  end_time: number;
  duration: number;
  transcription?: string;
  language: string;
  speaker?: string;
  emotion?: string;
  sentiment_score?: number;
  vector?: number[];
  vector_dimension?: number;
  vector_updated_at?: string;
  oss_key: string;
  oss_url: string;
  play_count: number;
  favorite_count: number;
  share_count: number;
  tags?: string[];
  categories?: string[];
  keywords?: string[];
  review_status: string;
  reviewer_id?: string;
  review_comment?: string;
  created_at: string;
  updated_at: string;
  is_favorite?: boolean;
  source_title?: string;
}

export interface AudioSearchRequest {
  query: string;
  program_types?: string[];
  min_duration?: number;
  max_duration?: number;
  language?: string;
  limit?: number;
  offset?: number;
}

export interface AudioSearchResult {
  segment: AudioSegment;
  similarity_score: number;
  relevance_explanation?: string;
}

export interface AudioSearchResponse {
  query: string;
  results: AudioSearchResult[];
  total_count: number;
  processing_time_ms: number;
}

export interface AudioUploadRequest {
  title: string;
  description?: string;
  program_type: string;
  tags?: string[];
  is_public?: boolean;
}

export interface AudioUploadResponse {
  upload_id: string;
  oss_policy: Record<string, any>;
  oss_signature: string;
  oss_key: string;
  oss_host: string;
  callback_url: string;
}

export interface AudioProcessingStatus {
  processing_id: string;
  status: string;
  progress: number;
  estimated_time_remaining?: number;
  error_message?: string;
  result?: Record<string, any>;
}

// 聊天相关类型
export interface ChatSession {
  id: string;
  user_id: string;
  title?: string;
  is_active: boolean;
  context_summary?: string;
  recent_topics?: string[];
  message_count: number;
  last_message_at?: string;
  preferred_voice?: string;
  preferred_topic?: string;
  created_at: string;
  updated_at: string;
  unread_count?: number;
  last_message_preview?: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  audio_segment_id?: string;
  role: string;
  content: string;
  audio_url?: string;
  query_vector?: number[];
  similarity_score?: number;
  emotion?: string;
  sentiment_score?: number;
  user_feedback?: string;
  feedback_reason?: string;
  created_at: string;
  updated_at: string;
  audio_segment_preview?: {
    id?: string;
    title?: string;
    duration?: number;
  };
}

export interface ChatResponse {
  message: ChatMessage;
  session?: ChatSession;
  suggestions?: string[];
}

export interface ChatHistoryRequest {
  session_id?: string;
  limit?: number;
  offset?: number;
}

export interface ChatHistoryResponse {
  session: ChatSession;
  messages: ChatMessage[];
  has_more: boolean;
}

// 音频生成相关类型
export interface AudioTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  example_text: string;
  variable_fields: Array<{
    name: string;
    label: string;
    required: boolean;
  }>;
  background_music_options: string[];
  voice_options: string[];
  estimated_duration: number;
}

export interface TemplateCategory {
  id: string;
  name: string;
  description: string;
  icon: string;
  templates: AudioTemplate[];
}

export interface GeneratedAudio {
  id: string;
  user_id: string;
  template_id: string;
  title: string;
  text_content: string;
  voice_type: string;
  background_music?: string;
  duration: number;
  file_size: number;
  format: string;
  oss_key: string;
  oss_url: string;
  share_code: string;
  play_count: number;
  share_count: number;
  download_count: number;
  review_status: string;
  created_at: string;
  updated_at: string;
  share_url: string;
}

export interface GenerateAudioRequest {
  template_id: string;
  variables: Record<string, string>;
  voice_type?: string;
  background_music?: string;
}

export interface GenerateAudioResponse {
  audio: GeneratedAudio;
  estimated_wait_time?: number;
}

export interface ShareAudioRequest {
  audio_id: string;
  share_to?: string;
  message?: string;
}

export interface ShareAudioResponse {
  share_url: string;
  qr_code_url?: string;
  short_url?: string;
}

// 全局状态类型
export interface GlobalState {
  user: User | null;
  token: string | null;
  isLoggedIn: boolean;
  settings: {
    baseUrl: string;
    theme: string;
    language: string;
  };
}

// 组件Props类型
export interface AudioPlayerProps {
  audioUrl: string;
  title: string;
  duration: number;
  isFavorite?: boolean;
  customClass?: string;
}

export interface ChatBubbleProps {
  message: ChatMessage;
  isOwnMessage: boolean;
  onPlayAudio?: (audioUrl: string) => void;
  onFeedback?: (messageId: string, feedback: 'like' | 'dislike') => void;
}