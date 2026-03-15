# Excel Agent Frontend

Next.js frontend for the Excel Agent - AI-powered spreadsheet analysis.

## Features

- 📊 Chat interface for interacting with your data
- 📁 Drag & drop file upload (Excel, CSV)
- 🎨 Beautiful markdown rendering with tables and code
- 💾 Download generated CSV files
- 🌙 Dark mode by default

## Quick Start

```bash
# Install dependencies
npm install

# Set environment variable
# Create .env.local with:
# NEXT_PUBLIC_API_URL=http://localhost:8000

# Run development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API URL | `http://localhost:8000` |

## Project Structure

```
src/
├── app/
│   ├── layout.tsx           # Root layout
│   ├── page.tsx             # Home page
│   ├── globals.css          # Global styles
│   └── chat/
│       └── [chatId]/
│           └── page.tsx     # Chat page
├── components/
│   ├── ChatList.tsx         # Sidebar chat list
│   ├── ChatWindow.tsx       # Main chat area
│   ├── MessageBubble.tsx    # Message component
│   ├── MarkdownRenderer.tsx # Markdown display
│   ├── FileUpload.tsx       # File upload
│   └── DownloadLink.tsx     # Download button
└── lib/
    ├── api.ts               # API client
    └── types.ts             # TypeScript types
```

## Tech Stack

- **Framework**: Next.js 16 (App Router)
- **Styling**: Tailwind CSS
- **Markdown**: react-markdown + remark-gfm
- **File Upload**: react-dropzone
- **Icons**: lucide-react
- **Language**: TypeScript

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server |
| `npm run build` | Build for production |
| `npm run start` | Start production server |
| `npm run lint` | Run ESLint |

## License

MIT
