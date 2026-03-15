'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { MessageSquare, Plus, Trash2, FileSpreadsheet } from 'lucide-react';
import { Chat } from '@/lib/types';
import { listChats, createChat, deleteChat } from '@/lib/api';

interface ChatListProps {
    onChatCreated?: (chat: Chat) => void;
}

export default function ChatList({ onChatCreated }: ChatListProps) {
    const [chats, setChats] = useState<Chat[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const pathname = usePathname();

    useEffect(() => {
        loadChats();
    }, []);

    const loadChats = async () => {
        try {
            setIsLoading(true);
            const data = await listChats();
            setChats(data);
            setError(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load chats');
        } finally {
            setIsLoading(false);
        }
    };

    const handleNewChat = async () => {
        try {
            const chat = await createChat();
            setChats([chat, ...chats]);
            onChatCreated?.(chat);
            // Redirect to new chat
            window.location.href = `/chat/${chat.id}`;
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to create chat');
        }
    };

    const handleDeleteChat = async (e: React.MouseEvent, chatId: string) => {
        e.preventDefault();
        e.stopPropagation();

        if (!confirm('Delete this chat?')) return;

        try {
            await deleteChat(chatId);
            setChats(chats.filter(c => c.id !== chatId));
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to delete chat');
        }
    };

    const formatDate = (dateString: string) => {
        const date = new Date(dateString);
        const now = new Date();
        const diff = now.getTime() - date.getTime();

        if (diff < 60000) return 'Just now';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
        return date.toLocaleDateString();
    };

    return (
        <div className="flex flex-col h-full bg-gray-900 text-white">
            {/* Header */}
            <div className="p-4 border-b border-gray-700">
                <div className="flex items-center gap-2 mb-4">
                    <FileSpreadsheet className="w-6 h-6 text-emerald-400" />
                    <h1 className="text-lg font-semibold">Excel Agent</h1>
                </div>

                <button
                    onClick={handleNewChat}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors font-medium"
                >
                    <Plus className="w-4 h-4" />
                    New Chat
                </button>
            </div>

            {/* Chat List */}
            <div className="flex-1 overflow-y-auto p-2">
                {isLoading ? (
                    <div className="flex items-center justify-center py-8">
                        <div className="animate-spin rounded-full h-6 w-6 border-2 border-emerald-400 border-t-transparent" />
                    </div>
                ) : error ? (
                    <div className="text-red-400 text-sm text-center py-4">{error}</div>
                ) : chats.length === 0 ? (
                    <div className="text-gray-500 text-sm text-center py-8">
                        No chats yet. Start a new one!
                    </div>
                ) : (
                    <div className="space-y-1">
                        {chats.map((chat) => {
                            const isActive = pathname === `/chat/${chat.id}`;

                            return (
                                <Link
                                    key={chat.id}
                                    href={`/chat/${chat.id}`}
                                    className={`group flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${isActive
                                            ? 'bg-gray-700 text-white'
                                            : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                                        }`}
                                >
                                    <MessageSquare className="w-4 h-4 shrink-0 text-gray-400" />
                                    <div className="flex-1 min-w-0">
                                        <div className="text-sm truncate">
                                            {chat.title || 'New Chat'}
                                        </div>
                                        <div className="text-xs text-gray-500">
                                            {formatDate(chat.updated_at)}
                                        </div>
                                    </div>
                                    <button
                                        onClick={(e) => handleDeleteChat(e, chat.id)}
                                        className="opacity-0 group-hover:opacity-100 p-1 hover:bg-gray-600 rounded transition-opacity"
                                    >
                                        <Trash2 className="w-3.5 h-3.5 text-gray-400 hover:text-red-400" />
                                    </button>
                                </Link>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-gray-700 text-xs text-gray-500 text-center">
                Powered by LangChain + OpenAI
            </div>
        </div>
    );
}
