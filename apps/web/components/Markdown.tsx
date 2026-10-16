'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// Safe Markdown: react-markdown escapes HTML and does NOT render raw HTML unless `rehype-raw`
// is added — which we deliberately do not use. GFM tables/lists are supported.
export default function Markdown({ children }: { children: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}
