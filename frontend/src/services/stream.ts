const ESCAPES: Record<string, string> = {
  n: "\n",
  t: "\t",
  r: "\r",
  '"': '"',
  "\\": "\\",
  "/": "/",
  b: "\b",
  f: "\f",
};

/**
 * The model streams the whole JSON envelope, so the visible sentence has to be
 * pulled out of the partial `"message": "..."` value as it arrives.
 */
export function extractPartialMessage(raw: string): string {
  const start = raw.search(/"message"\s*:\s*"/);
  if (start === -1) return "";
  const match = /"message"\s*:\s*"/.exec(raw);
  if (!match) return "";
  let index = (match.index ?? 0) + match[0].length;
  let out = "";
  while (index < raw.length) {
    const char = raw[index];
    if (char === "\\") {
      const next = raw[index + 1];
      if (next === undefined) break;
      if (next === "u") {
        const hex = raw.slice(index + 2, index + 6);
        if (hex.length < 4) break;
        const code = Number.parseInt(hex, 16);
        if (!Number.isNaN(code)) out += String.fromCharCode(code);
        index += 6;
        continue;
      }
      out += ESCAPES[next] ?? next;
      index += 2;
      continue;
    }
    if (char === '"') break;
    out += char;
    index += 1;
  }
  return out;
}
