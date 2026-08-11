import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import 'katex/dist/katex.min.css';
import 'highlight.js/styles/github.css';
import { Copy, Check } from 'lucide-react';

/**
 * SEC-5: sanitize schema. react-markdown already escapes raw HTML, but we run
 * rehype-sanitize as defense-in-depth on ALL untrusted text (chat, material
 * Ask answers, notebook). The schema extends the GitHub default to keep the
 * className/style/MathML output that KaTeX and highlight.js emit, while still
 * stripping <script>, event handlers, iframes, etc.
 */
const _mathTags = [
  'math', 'semantics', 'annotation', 'mrow', 'mi', 'mo', 'mn', 'ms', 'mtext',
  'msup', 'msub', 'msubsup', 'mfrac', 'msqrt', 'mroot', 'mstyle', 'mspace',
  'mtable', 'mtr', 'mtd', 'munder', 'mover', 'munderover', 'mpadded', 'mphantom',
];
const sanitizeSchema = {
  ...defaultSchema,
  tagNames: [...(defaultSchema.tagNames || []), ..._mathTags],
  attributes: {
    ...defaultSchema.attributes,
    '*': [...(defaultSchema.attributes?.['*'] || []), 'className', 'style', 'ariaHidden'],
    span: [...(defaultSchema.attributes?.span || []), 'className', 'style', 'ariaHidden'],
    div: [...(defaultSchema.attributes?.div || []), 'className', 'style'],
    code: [...(defaultSchema.attributes?.code || []), 'className'],
    annotation: ['encoding'],
    math: ['xmlns', 'display'],
  },
};

/**
 * A1: Rich tutor-message renderer.
 * - $...$ / $$...$$ LaTeX via KaTeX
 * - fenced code with syntax highlighting + copy button
 * - ```mermaid blocks rendered as diagrams (mermaid lazy-loaded from CDN)
 * While `streaming` is true we render plain markdown (KaTeX/mermaid on
 * partial input produces garbage; they apply when the message completes).
 */

function MermaidBlock({ chart }) {
  const [svg, setSvg] = useState('');
  useEffect(() => {
    let cancelled = false;
    const loadMermaid = () => new Promise((resolve, reject) => {
      if (window.mermaid) return resolve(window.mermaid);
      const s = document.createElement('script');
      s.src = 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js';
      s.onload = () => resolve(window.mermaid);
      s.onerror = () => reject(new Error('mermaid load failed'));
      document.head.appendChild(s);
    });
    loadMermaid()
      .then(async (m) => {
        m.initialize({ startOnLoad: false, theme: 'neutral', securityLevel: 'strict' });
        try {
          const id = `mmd-${Math.random().toString(36).slice(2)}`;
          const { svg: rendered } = await m.render(id, chart);
          if (!cancelled) setSvg(rendered);
        } catch { /* invalid diagram — keep raw text */ }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [chart]);

  if (!svg) return <pre className="text-xs text-gray-500 bg-gray-50 rounded p-2 overflow-x-auto">{chart}</pre>;
  return <div className="my-2 overflow-x-auto" dangerouslySetInnerHTML={{ __html: svg }} />;
}

function CodeBlock({ children, ...props }) {
  const [copied, setCopied] = useState(false);
  const getText = (n) => {
    if (typeof n === 'string') return n;
    if (Array.isArray(n)) return n.map(getText).join('');
    if (n?.props?.children) return getText(n.props.children);
    return '';
  };
  const handleCopy = () => {
    navigator.clipboard?.writeText(getText(children)).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }).catch(() => {});
  };
  return (
    <div className="relative group">
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 p-1.5 rounded bg-white/80 border border-gray-200 text-gray-400 hover:text-gray-700 opacity-0 group-hover:opacity-100 transition-opacity"
        title="Copy code"
      >
        {copied ? <Check size={13} className="text-green-600" /> : <Copy size={13} />}
      </button>
      {/* overflow-x-auto keeps long code lines scrolling inside the block instead
          of forcing the whole page (and chat bubble) wider on small screens. */}
      <pre {...props} className={`overflow-x-auto max-w-full ${props.className ?? ''}`}>{children}</pre>
    </div>
  );
}

const components = {
  pre: CodeBlock,
  code({ className, children, ...props }) {
    if (/language-mermaid/.test(className || '')) {
      return <MermaidBlock chart={String(children).trim()} />;
    }
    return <code className={className} {...props}>{children}</code>;
  },
};

export default function Markdown({ children, streaming = false }) {
  if (streaming) {
    // Plain render while tokens stream in; rich render on completion.
    // Sanitize even the streaming pass (SEC-5).
    return (
      <ReactMarkdown rehypePlugins={[[rehypeSanitize, sanitizeSchema]]}>
        {children}
      </ReactMarkdown>
    );
  }
  return (
    <ReactMarkdown
      remarkPlugins={[remarkMath]}
      rehypePlugins={[
        [rehypeKatex, { strict: false, throwOnError: false }],
        rehypeHighlight,
        [rehypeSanitize, sanitizeSchema],
      ]}
      components={components}
    >
      {children}
    </ReactMarkdown>
  );
}
