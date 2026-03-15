/**
 * TypeScript type definitions for the Excel Agent frontend
 */

// ============================================================================
// Chat Types
// ============================================================================

export interface Chat {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  message_count?: number;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
}

export interface ChatHistory {
  chat: Chat;
  messages: Message[];
}

export interface ChatMessageResponse {
  chat_id: string;
  user_message: Message;
  assistant_message: Message;
  content_markdown: string;
}

// ============================================================================
// File Types
// ============================================================================

export interface SheetInfo {
  name: string;
  index: number;
  row_count: number;
  column_count: number;
  columns: string[];
}

export interface Attachment {
  id: string;
  filename: string;
  original_filename: string;
  file_type: string;
  file_size: number;
  status: string;
  sheets: SheetInfo[];
}

export interface UploadResponse {
  success: boolean;
  attachments: Attachment[];
  total_sheets: number;
  total_rows: number;
}

// ============================================================================
// Job Types
// ============================================================================

export interface Job {
  id: string;
  chat_id: string;
  job_type: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  output_path?: string;
  error_message?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

// ============================================================================
// UI State Types
// ============================================================================

export interface ChatState {
  chats: Chat[];
  activeChat: ChatHistory | null;
  isLoading: boolean;
  error: string | null;
}

export interface MessageState {
  messages: Message[];
  isLoading: boolean;
  isStreaming: boolean;
}

export interface FileState {
  attachments: Attachment[];
  isUploading: boolean;
  uploadProgress: number;
}
