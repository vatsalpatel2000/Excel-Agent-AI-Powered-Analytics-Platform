'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import ChatList from '@/components/ChatList';
import { FileSpreadsheet, MessageSquare, Zap, Download } from 'lucide-react';

export default function HomePage() {
  const router = useRouter();

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-72 shrink-0 border-r border-gray-800">
        <ChatList />
      </aside>

      {/* Main Content - Welcome Screen */}
      <main className="flex-1 flex items-center justify-center bg-gray-950">
        <div className="max-w-2xl text-center px-6">
          {/* Hero */}
          <div className="mb-8">
            <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 mb-6 shadow-lg shadow-emerald-500/20">
              <FileSpreadsheet className="w-10 h-10 text-white" />
            </div>
            <h1 className="text-4xl font-bold text-white mb-4">
              Excel Agent
            </h1>
            <p className="text-lg text-gray-400">
              AI-powered spreadsheet analysis. Upload your files and ask questions in natural language.
            </p>
          </div>

          {/* Features */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
            <div className="p-6 bg-gray-900/50 rounded-xl border border-gray-800">
              <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center mb-4 mx-auto">
                <MessageSquare className="w-5 h-5 text-purple-400" />
              </div>
              <h3 className="font-semibold text-white mb-2">Natural Language Q&A</h3>
              <p className="text-sm text-gray-400">
                Ask questions about your data in plain English
              </p>
            </div>
            <div className="p-6 bg-gray-900/50 rounded-xl border border-gray-800">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center mb-4 mx-auto">
                <Zap className="w-5 h-5 text-emerald-400" />
              </div>
              <h3 className="font-semibold text-white mb-2">Accurate Analysis</h3>
              <p className="text-sm text-gray-400">
                Real calculations, not AI guesses
              </p>
            </div>
            <div className="p-6 bg-gray-900/50 rounded-xl border border-gray-800">
              <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center mb-4 mx-auto">
                <Download className="w-5 h-5 text-blue-400" />
              </div>
              <h3 className="font-semibold text-white mb-2">Data Enrichment</h3>
              <p className="text-sm text-gray-400">
                Auto-add sector & industry columns
              </p>
            </div>
          </div>

          {/* Supported Formats */}
          <div className="flex items-center justify-center gap-4 text-sm text-gray-500">
            <span>Supports:</span>
            {['.xlsx', '.xls', '.xlsm', '.csv'].map((format) => (
              <span
                key={format}
                className="px-2 py-1 bg-gray-800 rounded text-gray-400"
              >
                {format}
              </span>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
