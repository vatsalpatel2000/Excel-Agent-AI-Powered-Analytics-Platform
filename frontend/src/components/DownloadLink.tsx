'use client';

import { Download } from 'lucide-react';
import { getDownloadUrl } from '@/lib/api';

interface DownloadLinkProps {
    path: string;
    filename?: string;
    children?: React.ReactNode;
}

export default function DownloadLink({
    path,
    filename,
    children,
}: DownloadLinkProps) {
    const url = getDownloadUrl(path);
    const displayName = filename || path.split('/').pop() || 'Download';

    return (
        <a
            href={url}
            download={displayName}
            className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-medium transition-colors"
        >
            <Download className="w-4 h-4" />
            {children || displayName}
        </a>
    );
}
