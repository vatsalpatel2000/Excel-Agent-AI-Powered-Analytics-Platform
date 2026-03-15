/**
 * API Client for Excel Agent Backend
 */

import type {
    Chat,
    ChatHistory,
    ChatMessageResponse,
    Attachment,
    UploadResponse,
    Job,
} from './types';

// Base URL for API calls
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ============================================================================
// Helper Functions
// ============================================================================

async function fetchAPI<T>(
    endpoint: string,
    options: RequestInit = {}
): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;

    const response = await fetch(url, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        },
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || `API error: ${response.status}`);
    }

    return response.json();
}

// ============================================================================
// Chat API
// ============================================================================

export async function createChat(title?: string): Promise<Chat> {
    return fetchAPI<Chat>('/api/chat/new', {
        method: 'POST',
        body: JSON.stringify({ title }),
    });
}

export async function listChats(limit = 50, offset = 0): Promise<Chat[]> {
    return fetchAPI<Chat[]>(`/api/chat/list?limit=${limit}&offset=${offset}`);
}

export async function getChat(chatId: string): Promise<ChatHistory> {
    return fetchAPI<ChatHistory>(`/api/chat/${chatId}`);
}

export async function sendMessage(
    chatId: string,
    content: string
): Promise<ChatMessageResponse> {
    return fetchAPI<ChatMessageResponse>(`/api/chat/${chatId}/message`, {
        method: 'POST',
        body: JSON.stringify({ content }),
    });
}

export async function updateChatTitle(
    chatId: string,
    title: string
): Promise<{ success: boolean }> {
    return fetchAPI(`/api/chat/${chatId}/title?title=${encodeURIComponent(title)}`, {
        method: 'PATCH',
    });
}

export async function deleteChat(chatId: string): Promise<{ success: boolean }> {
    return fetchAPI(`/api/chat/${chatId}`, {
        method: 'DELETE',
    });
}

// ============================================================================
// Files API
// ============================================================================

export async function uploadFiles(
    chatId: string,
    files: File[]
): Promise<UploadResponse> {
    const formData = new FormData();
    files.forEach((file) => {
        formData.append('files', file);
    });

    const response = await fetch(`${API_BASE_URL}/api/files/${chatId}/upload`, {
        method: 'POST',
        body: formData,
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(error.detail || 'Upload failed');
    }

    return response.json();
}

export async function listAttachments(chatId: string): Promise<Attachment[]> {
    return fetchAPI<Attachment[]>(`/api/files/${chatId}/attachments`);
}

export function getDownloadUrl(path: string): string {
    return `${API_BASE_URL}/api/files/download/${path}`;
}

// ============================================================================
// Jobs API
// ============================================================================

export async function getJobStatus(jobId: string): Promise<Job> {
    return fetchAPI<Job>(`/api/jobs/${jobId}`);
}

export async function listChatJobs(
    chatId: string,
    jobType?: string,
    status?: string
): Promise<Job[]> {
    let url = `/api/jobs/chat/${chatId}`;
    const params = new URLSearchParams();
    if (jobType) params.append('job_type', jobType);
    if (status) params.append('status_filter', status);
    if (params.toString()) url += `?${params.toString()}`;

    return fetchAPI<Job[]>(url);
}

// ============================================================================
// Health Check
// ============================================================================

export async function checkHealth(): Promise<{ status: string }> {
    return fetchAPI<{ status: string }>('/health');
}
