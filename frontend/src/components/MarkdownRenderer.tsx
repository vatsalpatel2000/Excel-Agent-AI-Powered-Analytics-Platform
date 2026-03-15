'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Download } from 'lucide-react';
import { getDownloadUrl } from '@/lib/api';

interface MarkdownRendererProps {
    content: string;
}

export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
    // Extract download links from content
    const downloadLinkRegex = /\/api\/files\/download\/([^\s)]+)/g;

    return (
        <div className="prose prose-invert prose-sm max-w-none">
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                    // Headings
                    h1: ({ children }) => (
                        <h1 className="text-xl font-bold text-white mt-4 mb-2 first:mt-0">
                            {children}
                        </h1>
                    ),
                    h2: ({ children }) => (
                        <h2 className="text-lg font-semibold text-white mt-3 mb-2">
                            {children}
                        </h2>
                    ),
                    h3: ({ children }) => (
                        <h3 className="text-base font-semibold text-gray-200 mt-2 mb-1">
                            {children}
                        </h3>
                    ),

                    // Paragraphs
                    p: ({ children }) => (
                        <p className="text-gray-200 my-2 leading-relaxed">{children}</p>
                    ),

                    // Lists
                    ul: ({ children }) => (
                        <ul className="list-disc list-inside my-2 space-y-1 text-gray-200">
                            {children}
                        </ul>
                    ),
                    ol: ({ children }) => (
                        <ol className="list-decimal list-inside my-2 space-y-1 text-gray-200">
                            {children}
                        </ol>
                    ),
                    li: ({ children }) => (
                        <li className="text-gray-200">{children}</li>
                    ),

                    // Code
                    code: ({ className, children, ...props }) => {
                        const isInline = !className;

                        if (isInline) {
                            return (
                                <code className="px-1.5 py-0.5 bg-gray-700 rounded text-emerald-300 text-sm font-mono">
                                    {children}
                                </code>
                            );
                        }

                        return (
                            <code
                                className="block p-3 bg-gray-900 rounded-lg overflow-x-auto text-sm font-mono text-gray-300"
                                {...props}
                            >
                                {children}
                            </code>
                        );
                    },
                    pre: ({ children }) => (
                        <pre className="my-2 overflow-x-auto">{children}</pre>
                    ),

                    // Tables
                    table: ({ children }) => (
                        <div className="my-3 overflow-x-auto rounded-lg border border-gray-700">
                            <table className="min-w-full divide-y divide-gray-700">
                                {children}
                            </table>
                        </div>
                    ),
                    thead: ({ children }) => (
                        <thead className="bg-gray-800">{children}</thead>
                    ),
                    tbody: ({ children }) => (
                        <tbody className="divide-y divide-gray-700">{children}</tbody>
                    ),
                    tr: ({ children }) => <tr>{children}</tr>,
                    th: ({ children }) => (
                        <th className="px-3 py-2 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">
                            {children}
                        </th>
                    ),
                    td: ({ children }) => (
                        <td className="px-3 py-2 text-sm text-gray-300 whitespace-nowrap">
                            {children}
                        </td>
                    ),

                    // Links
                    a: ({ href, children }) => {
                        // Check if it's a download link
                        const isDownload = href?.includes('/api/files/download/');

                        if (isDownload && href) {
                            return (
                                <a
                                    href={href}
                                    download
                                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium transition-colors no-underline"
                                >
                                    <Download className="w-4 h-4" />
                                    {children}
                                </a>
                            );
                        }

                        return (
                            <a
                                href={href}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-emerald-400 hover:text-emerald-300 underline"
                            >
                                {children}
                            </a>
                        );
                    },

                    // Blockquotes
                    blockquote: ({ children }) => (
                        <blockquote className="border-l-4 border-emerald-500 pl-4 my-2 text-gray-300 italic">
                            {children}
                        </blockquote>
                    ),

                    // Horizontal rule
                    hr: () => <hr className="my-4 border-gray-700" />,

                    // Strong/Bold
                    strong: ({ children }) => (
                        <strong className="font-semibold text-white">{children}</strong>
                    ),

                    // Emphasis/Italic
                    em: ({ children }) => (
                        <em className="italic text-gray-300">{children}</em>
                    ),
                }}
            >
                {content}
            </ReactMarkdown>
        </div>
    );
}
