import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Novel Agents · 多Agent 修仙创作仪表盘",
  description: "6 Agent 协作的玄幻修仙创作系统 — 实时进度 / Token 留痕 / 人工干预",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="antialiased">{children}</body>
    </html>
  );
}
