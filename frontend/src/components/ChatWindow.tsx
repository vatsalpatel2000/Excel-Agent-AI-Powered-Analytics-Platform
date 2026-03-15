'use client';

import { useState, useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { Message, Attachment } from '@/lib/types';
import { sendMessage } from '@/lib/api';
import MessageBubble from './MessageBubble';
import FileUpload from './FileUpload';

interface ChatWindowProps {
    chatId: string;
    initialMessages: Message[];
    attachments: Attachment[];
    onAttachmentsChange?: () => void;
}

export default function ChatWindow({
    chatId,
    initialMessages,
    attachments,
    onAttachmentsChange,
}: ChatWindowProps) {
    const [messages, setMessages] = useState<Message[]>(initialMessages);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    useEffect(() => {
        setMessages(initialMessages);
    }, [initialMessages]);

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || isLoading) return;

        const userMessage = input.trim();
        setInput('');
        setError(null);

        // Optimistically add user message
        const tempUserMessage: Message = {
            id: `temp-${Date.now()}`,
            role: 'user',
            content: userMessage,
            created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, tempUserMessage]);
        setIsLoading(true);

        try {
            const response = await sendMessage(chatId, userMessage);

            // Replace temp message with real one and add assistant response
            setMessages((prev) => [
                ...prev.filter((m) => m.id !== tempUserMessage.id),
                response.user_message,
                response.assistant_message,
            ]);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to send message');
            // Remove the optimistic message on error
            setMessages((prev) => prev.filter((m) => m.id !== tempUserMessage.id));
        } finally {
            setIsLoading(false);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
        }
    };

    const handleUploadComplete = () => {
        onAttachmentsChange?.();
    };

    // Auto-resize textarea
    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
        }
    }, [input]);

    return (
        <div className="flex flex-col h-full bg-gray-950">
            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto px-4 py-6">
                <div className="max-w-3xl mx-auto space-y-6">
                    {/* File Attachments Info */}
                    {attachments.length > 0 && (
                        <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
                            <h3 className="text-sm font-medium text-gray-300 mb-2">
                                📎 Attached Files ({attachments.length})
                            </h3>
                            <div className="space-y-1">
                                {attachments.map((att) => (
                                    <div key={att.id} className="text-sm text-gray-400 flex items-center gap-2">
                                        <span className="text-emerald-400">✓</span>
                                        <span>{att.original_filename}</span>
                                        <span className="text-gray-600">
                                            ({att.sheets.length} sheet{att.sheets.length !== 1 ? 's' : ''},
                                            {att.sheets.reduce((sum, s) => sum + s.row_count, 0).toLocaleString()} rows)
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Welcome Message */}
                    {messages.length === 0 && (
                        <div className="text-center py-12">
                            <div className="text-4xl mb-4">📊</div>
                            <h2 className="text-xl font-semibold text-white mb-2">
                                Excel Agent
                            </h2>
                            <p className="text-gray-400 max-w-md mx-auto">
                                Upload an Excel or CSV file and ask questions about your data.
                                I can analyze, summarize, and even enrich your data with additional information.
                            </p>
                            <div className="mt-6 flex flex-wrap justify-center gap-2">
                                {[
                                    'Summarize the attached file',
                                    'What are the top 10 rows?',
                                    'Calculate the average of column X',
                                    'Add sector and industry columns',
                                ].map((suggestion) => (
                                    <button
                                        key={suggestion}
                                        onClick={() => setInput(suggestion)}
                                        className="px-3 py-1.5 text-sm bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-full transition-colors"
                                    >
                                        {suggestion}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Messages */}
                    {messages.map((message) => (
                        <MessageBubble key={message.id} message={message} />
                    ))}

                    {/* Loading indicator */}
                    {isLoading && (
                        <div className="flex items-center gap-2 text-gray-400">
                            <Loader2 className="w-4 h-4 animate-spin" />
                            <span className="text-sm">Thinking...</span>
                        </div>
                    )}

                    {/* Error message */}
                    {error && (
                        <div className="bg-red-900/30 border border-red-700 text-red-300 px-4 py-2 rounded-lg text-sm">
                            {error}
                        </div>
                    )}

                    <div ref={messagesEndRef} />
                </div>
            </div>

            {/* Input Area */}
            <div className="border-t border-gray-800 p-4">
                <div className="max-w-3xl mx-auto">
                    {/* File Upload */}
                    <FileUpload chatId={chatId} onUploadComplete={handleUploadComplete} />

                    {/* Message Input */}
                    <form onSubmit={handleSubmit} className="flex items-end gap-2">
                        <div className="flex-1 relative">
                            <textarea
                                ref={textareaRef}
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder="Ask a question about your data..."
                                rows={1}
                                className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-xl text-white placeholder-gray-500 resize-none focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                                disabled={isLoading}
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={!input.trim() || isLoading}
                            className="p-3 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 disabled:cursor-not-allowed rounded-xl transition-colors"
                        >
                            {isLoading ? (
                                <Loader2 className="w-5 h-5 text-white animate-spin" />
                            ) : (
                                <Send className="w-5 h-5 text-white" />
                            )}
                        </button>
                    </form>
                </div>
            </div>
        </div>
    );
}
