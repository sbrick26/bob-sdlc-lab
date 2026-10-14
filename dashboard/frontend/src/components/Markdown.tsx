import type { ReactNode } from 'react';

/** Small, safe markdown: paragraphs, "-" and "1." lists, `code`, **bold**, fenced code. No HTML is injected. */
export function Markdown({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  const lines = text.split('\n');
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (line.startsWith('```')) {
      const body: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].startsWith('```')) body.push(lines[index++]);
      index += 1;
      blocks.push(<pre key={blocks.length}>{body.join('\n')}</pre>);
    } else if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
      const ordered = /^\s*\d+\./.test(line);
      const items: string[] = [];
      while (index < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[index])) items.push(lines[index++].replace(/^\s*([-*]|\d+\.)\s+/, ''));
      const List = ordered ? 'ol' : 'ul';
      blocks.push(<List key={blocks.length}>{items.map((item, at) => <li key={at}>{inline(item)}</li>)}</List>);
    } else if (line.trim()) {
      const para: string[] = [];
      while (index < lines.length && lines[index].trim() && !lines[index].startsWith('```') && !/^\s*([-*]|\d+\.)\s+/.test(lines[index])) para.push(lines[index++].replace(/^#+\s*/, ''));
      blocks.push(<p key={blocks.length}>{inline(para.join(' '))}</p>);
    } else {
      index += 1;
    }
  }
  return <div className="markdown">{blocks}</div>;
}

function inline(text: string): ReactNode[] {
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).filter(Boolean).map((part, index) => {
    if (part.startsWith('`') && part.endsWith('`')) return <code key={index}>{part.slice(1, -1)}</code>;
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={index}>{part.slice(2, -2)}</strong>;
    return part;
  });
}
