'use client';

import { User, Bot } from 'lucide-react';
import { Message } from '@/lib/types';
import MarkdownRenderer from './MarkdownRenderer';

interface MessageBubbleProps {
    message: Message;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
    const isUser = message.role === 'user';

    return (
        <div className={`flex gap-4 ${isUser ? 'flex-row-reverse' : ''}`}>
            {/* Avatar */}
            <div
                className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${isUser
                        ? 'bg-emerald-600'
                        : 'bg-gradient-to-br from-purple-500 to-pink-500'
                    }`}
            >
                {isUser ? (
                    <User className="w-4 h-4 text-white" />
                ) : (
                    <Bot className="w-4 h-4 text-white" />
                )}
            </div>

            {/* Message Content */}
            <div
                className={`flex-1 max-w-[80%] ${isUser ? 'text-right' : ''
                    }`}
            >
                <div
                    className={`inline-block text-left px-4 py-3 rounded-2xl ${isUser
                            ? 'bg-emerald-600 text-white rounded-tr-sm'
                            : 'bg-gray-800 text-gray-100 rounded-tl-sm'
                        }`}
                >
                    {isUser ? (
                        <p className="whitespace-pre-wrap">{message.content}</p>
                    ) : (
                        <MarkdownRenderer content={message.content} />
                    )}
                </div>

                {/* Timestamp */}
                <div
                    className={`text-xs text-gray-500 mt-1 ${isUser ? 'text-right' : 'text-left'
                        }`}
                >
                    {new Date(message.created_at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                    })}
                </div>
            </div>
        </div>
    );
}
