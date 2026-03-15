'use client';

import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, X, FileSpreadsheet, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import { uploadFiles } from '@/lib/api';
import { UploadResponse } from '@/lib/types';

interface FileUploadProps {
    chatId: string;
    onUploadComplete?: (response: UploadResponse) => void;
}

interface UploadingFile {
    file: File;
    status: 'pending' | 'uploading' | 'success' | 'error';
    error?: string;
}

export default function FileUpload({ chatId, onUploadComplete }: FileUploadProps) {
    const [files, setFiles] = useState<UploadingFile[]>([]);
    const [isUploading, setIsUploading] = useState(false);

    const onDrop = useCallback((acceptedFiles: File[]) => {
        const newFiles = acceptedFiles.map((file) => ({
            file,
            status: 'pending' as const,
        }));
        setFiles((prev) => [...prev, ...newFiles]);
    }, []);

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: {
            'text/csv': ['.csv'],
            'application/vnd.ms-excel': ['.xls'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
            'application/vnd.ms-excel.sheet.macroEnabled.12': ['.xlsm'],
        },
        maxFiles: 50,
        disabled: isUploading,
    });

    const removeFile = (index: number) => {
        setFiles((prev) => prev.filter((_, i) => i !== index));
    };

    const handleUpload = async () => {
        if (files.length === 0 || isUploading) return;

        setIsUploading(true);

        // Mark all as uploading
        setFiles((prev) =>
            prev.map((f) => ({ ...f, status: 'uploading' as const }))
        );

        try {
            const filesToUpload = files.map((f) => f.file);
            const response = await uploadFiles(chatId, filesToUpload);

            // Mark as success
            setFiles((prev) =>
                prev.map((f) => ({ ...f, status: 'success' as const }))
            );

            onUploadComplete?.(response);

            // Clear files after a delay
            setTimeout(() => {
                setFiles([]);
            }, 2000);
        } catch (err) {
            // Mark as error
            setFiles((prev) =>
                prev.map((f) => ({
                    ...f,
                    status: 'error' as const,
                    error: err instanceof Error ? err.message : 'Upload failed',
                }))
            );
        } finally {
            setIsUploading(false);
        }
    };

    const formatFileSize = (bytes: number) => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    if (files.length === 0) {
        return (
            <div
                {...getRootProps()}
                className={`mb-3 border-2 border-dashed rounded-xl p-4 transition-colors cursor-pointer ${isDragActive
                        ? 'border-emerald-500 bg-emerald-500/10'
                        : 'border-gray-700 hover:border-gray-600 bg-gray-800/50'
                    }`}
            >
                <input {...getInputProps()} />
                <div className="flex items-center justify-center gap-3 text-gray-400">
                    <Upload className="w-5 h-5" />
                    <span className="text-sm">
                        {isDragActive
                            ? 'Drop files here...'
                            : 'Drag & drop Excel or CSV files, or click to browse'}
                    </span>
                </div>
            </div>
        );
    }

    return (
        <div className="mb-3 bg-gray-800/50 rounded-xl p-3 border border-gray-700">
            {/* File List */}
            <div className="space-y-2 mb-3">
                {files.map((item, index) => (
                    <div
                        key={index}
                        className="flex items-center gap-3 bg-gray-800 rounded-lg px-3 py-2"
                    >
                        <FileSpreadsheet className="w-5 h-5 text-emerald-400 shrink-0" />
                        <div className="flex-1 min-w-0">
                            <div className="text-sm text-white truncate">{item.file.name}</div>
                            <div className="text-xs text-gray-500">
                                {formatFileSize(item.file.size)}
                            </div>
                        </div>

                        {/* Status */}
                        {item.status === 'uploading' && (
                            <Loader2 className="w-4 h-4 text-emerald-400 animate-spin" />
                        )}
                        {item.status === 'success' && (
                            <CheckCircle className="w-4 h-4 text-emerald-400" />
                        )}
                        {item.status === 'error' && (
                            <AlertCircle className="w-4 h-4 text-red-400" />
                        )}
                        {item.status === 'pending' && (
                            <button
                                onClick={() => removeFile(index)}
                                className="p-1 hover:bg-gray-700 rounded transition-colors"
                            >
                                <X className="w-4 h-4 text-gray-400 hover:text-white" />
                            </button>
                        )}
                    </div>
                ))}
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
                <div {...getRootProps()} className="flex-1">
                    <input {...getInputProps()} />
                    <button
                        type="button"
                        disabled={isUploading}
                        className="w-full px-3 py-2 text-sm text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition-colors disabled:opacity-50"
                    >
                        + Add more files
                    </button>
                </div>
                <button
                    onClick={handleUpload}
                    disabled={isUploading || files.every((f) => f.status !== 'pending')}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 text-white text-sm font-medium rounded-lg transition-colors disabled:cursor-not-allowed"
                >
                    {isUploading ? (
                        <span className="flex items-center gap-2">
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Uploading...
                        </span>
                    ) : (
                        `Upload ${files.length} file${files.length !== 1 ? 's' : ''}`
                    )}
                </button>
            </div>
        </div>
    );
}
