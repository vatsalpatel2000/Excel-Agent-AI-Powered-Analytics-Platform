import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Excel Agent - AI-Powered Spreadsheet Analysis',
  description: 'Upload Excel or CSV files and ask questions about your data. Powered by LangChain and OpenAI.',
  keywords: ['excel', 'csv', 'analysis', 'ai', 'langchain', 'openai', 'spreadsheet'],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-gray-950 text-white antialiased`}>
        {children}
      </body>
    </html>
  );
}
