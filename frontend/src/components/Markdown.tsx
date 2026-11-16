import type { ReactNode } from "react";

/** Minimal markdown renderer: headings, lists, tables, bold and inline code. */
function inline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let index = 0;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) nodes.push(text.slice(lastIndex, match.index));
    const token = match[0];
    if (token.startsWith("**")) {
      nodes.push(
        <strong key={`${keyPrefix}-b-${index}`} className="font-semibold text-ink">
          {token.slice(2, -2)}
        </strong>,
      );
    } else {
      nodes.push(
        <code key={`${keyPrefix}-c-${index}`} className="rounded bg-canvas px-1 py-0.5 font-mono text-[11.5px]">
          {token.slice(1, -1)}
        </code>,
      );
    }
    lastIndex = match.index + token.length;
    index += 1;
  }
  if (lastIndex < text.length) nodes.push(text.slice(lastIndex));
  return nodes;
}

export function Markdown({ text }: { text: string }) {
  const lines = (text || "").split("\n");
  const blocks: ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  let table: string[][] | null = null;

  const flushList = () => {
    if (!list) return;
    const Tag = list.ordered ? "ol" : "ul";
    blocks.push(
      <Tag key={`list-${blocks.length}`}>
        {list.items.map((item, index) => (
          <li key={index}>{inline(item, `li-${blocks.length}-${index}`)}</li>
        ))}
      </Tag>,
    );
    list = null;
  };

  const flushTable = () => {
    if (!table || table.length === 0) {
      table = null;
      return;
    }
    const [header, ...rows] = table;
    const body = rows.filter((row) => !row.every((cell) => /^:?-{2,}:?$/.test(cell.trim())));
    blocks.push(
      <table key={`table-${blocks.length}`}>
        <thead>
          <tr>
            {header.map((cell, index) => (
              <th key={index}>{inline(cell, `th-${blocks.length}-${index}`)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex}>{inline(cell, `td-${blocks.length}-${rowIndex}-${cellIndex}`)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>,
    );
    table = null;
  };

  lines.forEach((raw, index) => {
    const line = raw.trimEnd();
    if (line.trim().startsWith("|")) {
      flushList();
      const cells = line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|");
      table = table ?? [];
      table.push(cells);
      return;
    }
    flushTable();
    if (!line.trim()) {
      flushList();
      return;
    }
    if (/^#{1,3}\s/.test(line)) {
      flushList();
      const level = line.match(/^#+/)?.[0].length ?? 1;
      const content = line.replace(/^#+\s*/, "");
      if (level === 1) blocks.push(<h1 key={`h-${index}`}>{inline(content, `h-${index}`)}</h1>);
      else if (level === 2) blocks.push(<h2 key={`h-${index}`}>{inline(content, `h-${index}`)}</h2>);
      else blocks.push(<h3 key={`h-${index}`}>{inline(content, `h-${index}`)}</h3>);
      return;
    }
    const bullet = line.match(/^\s*[-*]\s+(.*)$/);
    if (bullet) {
      if (!list || list.ordered) {
        flushList();
        list = { ordered: false, items: [] };
      }
      list.items.push(bullet[1]);
      return;
    }
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (numbered) {
      if (!list || !list.ordered) {
        flushList();
        list = { ordered: true, items: [] };
      }
      list.items.push(numbered[1]);
      return;
    }
    flushList();
    blocks.push(<p key={`p-${index}`}>{inline(line, `p-${index}`)}</p>);
  });
  flushList();
  flushTable();

  return <div className="prose-md">{blocks}</div>;
}
