'use client';

import { useState, useEffect, use } from 'react';
import { useRouter } from 'next/navigation';
import ChatList from '@/components/ChatList';
import ChatWindow from '@/components/ChatWindow';
import { getChat, listAttachments } from '@/lib/api';
import { ChatHistory, Attachment } from '@/lib/types';
import { Loader2, AlertCircle } from 'lucide-react';

interface ChatPageProps {
    params: Promise<{ chatId: string }>;
}

export default function ChatPage({ params }: ChatPageProps) {
    const resolvedParams = use(params);
    const chatId = resolvedParams.chatId;

    const [chat, setChat] = useState<ChatHistory | null>(null);
    const [attachments, setAttachments] = useState<Attachment[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const router = useRouter();

    useEffect(() => {
        loadChatData();
    }, [chatId]);

    const loadChatData = async () => {
        try {
            setIsLoading(true);
            setError(null);

            const [chatData, attachmentData] = await Promise.all([
                getChat(chatId),
                listAttachments(chatId),
            ]);

            setChat(chatData);
            setAttachments(attachmentData);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load chat');
        } finally {
            setIsLoading(false);
        }
    };

    const handleAttachmentsChange = async () => {
        try {
            const attachmentData = await listAttachments(chatId);
            setAttachments(attachmentData);
        } catch (err) {
            console.error('Failed to reload attachments:', err);
        }
    };

    return (
        <div className="flex h-screen">
            {/* Sidebar */}
            <aside className="w-72 shrink-0 border-r border-gray-800">
                <ChatList />
            </aside>

            {/* Main Chat Area */}
            <main className="flex-1 flex flex-col">
                {isLoading ? (
                    <div className="flex-1 flex items-center justify-center bg-gray-950">
                        <div className="text-center">
                            <Loader2 className="w-8 h-8 text-emerald-400 animate-spin mx-auto mb-4" />
                            <p className="text-gray-400">Loading chat...</p>
                        </div>
                    </div>
                ) : error ? (
                    <div className="flex-1 flex items-center justify-center bg-gray-950">
                        <div className="text-center">
                            <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
                            <p className="text-red-400 mb-4">{error}</p>
                            <button
                                onClick={() => router.push('/')}
                                className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-lg transition-colors"
                            >
                                Back to Home
                            </button>
                        </div>
                    </div>
                ) : chat ? (
                    <ChatWindow
                        chatId={chatId}
                        initialMessages={chat.messages}
                        attachments={attachments}
                        onAttachmentsChange={handleAttachmentsChange}
                    />
                ) : null}
            </main>
        </div>
    );
}
