"use client";

import { Copy, Search, ZoomIn, ZoomOut } from "lucide-react";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { ViewerToolbar } from "@/components/invoices/viewers/shared/viewer-toolbar";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

interface XmlViewerProps {
  fileUrl: string;
  filename: string;
}

const FONT_SIZES = [12, 14, 16, 18, 20] as const;
const INLINE_TEXT_LIMIT = 100;

interface Attribute {
  name: string;
  value: string;
}

type Token =
  | { kind: "declaration"; raw: string }
  | { kind: "comment"; raw: string }
  | { kind: "open"; tag: string; attrs: Attribute[]; selfClosing: boolean }
  | { kind: "close"; tag: string }
  | { kind: "text"; raw: string };

type Segment =
  | { type: "punct"; text: string }
  | { type: "tag"; text: string }
  | { type: "attrName"; text: string }
  | { type: "attrValue"; text: string }
  | { type: "text"; text: string }
  | { type: "comment"; text: string }
  | { type: "declaration"; text: string };

interface Line {
  indent: number;
  number: number;
  segments: Segment[];
}

function parseAttributes(raw: string): Attribute[] {
  const attrs: Attribute[] = [];
  const attrRegex = /([\w:-]+)\s*=\s*("([^"]*)"|'([^']*)')/g;

  for (const match of raw.matchAll(attrRegex)) {
    attrs.push({
      name: match[1],
      value: match[3] ?? match[4] ?? "",
    });
  }

  return attrs;
}

function tokenize(xml: string): Token[] {
  const scanner = /<\?xml[\s\S]*?\?>|<!--[\s\S]*?-->|<\/[\w:-]+\s*>|<[\w:-]+(?:\s+[^<>]*?)?\s*\/?>|[^<]+/g;
  const tokens: Token[] = [];

  for (const match of xml.matchAll(scanner)) {
    const raw = match[0];
    if (!raw) {
      continue;
    }

    if (raw.startsWith("<?xml")) {
      tokens.push({ kind: "declaration", raw: raw.trim() });
      continue;
    }

    if (raw.startsWith("<!--")) {
      tokens.push({ kind: "comment", raw: raw.trim() });
      continue;
    }

    if (raw.startsWith("</")) {
      tokens.push({ kind: "close", tag: raw.replace(/^<\//, "").replace(/>$/, "").trim() });
      continue;
    }

    if (raw.startsWith("<")) {
      const selfClosing = raw.endsWith("/>");
      const body = raw.slice(1, selfClosing ? -2 : -1).trim();
      const [tag, ...attrParts] = body.split(/\s+/);
      tokens.push({
        kind: "open",
        tag,
        attrs: parseAttributes(attrParts.join(" ")),
        selfClosing,
      });
      continue;
    }

    const text = raw.replace(/\s+/g, " ").trim();
    if (text) {
      tokens.push({ kind: "text", raw: text });
    }
  }

  return tokens;
}

function openSegments(tag: string, attrs: Attribute[], selfClosing: boolean): Segment[] {
  const segments: Segment[] = [
    { type: "punct", text: "<" },
    { type: "tag", text: tag },
  ];

  for (const attr of attrs) {
    segments.push({ type: "text", text: " " });
    segments.push({ type: "attrName", text: attr.name });
    segments.push({ type: "punct", text: "=" });
    segments.push({ type: "punct", text: '"' });
    segments.push({ type: "attrValue", text: attr.value });
    segments.push({ type: "punct", text: '"' });
  }

  segments.push({ type: "punct", text: selfClosing ? "/>" : ">" });
  return segments;
}

function closeSegments(tag: string): Segment[] {
  return [
    { type: "punct", text: "</" },
    { type: "tag", text: tag },
    { type: "punct", text: ">" },
  ];
}

function segmentsToText(segments: Segment[]): string {
  return segments.map((segment) => segment.text).join("");
}

function formatTokens(tokens: Token[]): Line[] {
  const lines: Line[] = [];
  let indent = 0;

  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];

    if (token.kind === "declaration") {
      lines.push({
        indent: 0,
        number: lines.length + 1,
        segments: [{ type: "declaration", text: token.raw }],
      });
      continue;
    }

    if (token.kind === "comment") {
      lines.push({
        indent,
        number: lines.length + 1,
        segments: [{ type: "comment", text: token.raw }],
      });
      continue;
    }

    if (token.kind === "text") {
      lines.push({
        indent,
        number: lines.length + 1,
        segments: [{ type: "text", text: token.raw }],
      });
      continue;
    }

    if (token.kind === "close") {
      indent = Math.max(0, indent - 1);
      lines.push({
        indent,
        number: lines.length + 1,
        segments: closeSegments(token.tag),
      });
      continue;
    }

    const nextToken = tokens[index + 1];
    const afterNextToken = tokens[index + 2];
    if (
      !token.selfClosing &&
      nextToken?.kind === "text" &&
      afterNextToken?.kind === "close" &&
      afterNextToken.tag === token.tag
    ) {
      const inlineSegments = [
        ...openSegments(token.tag, token.attrs, false),
        { type: "text", text: nextToken.raw } as const,
        ...closeSegments(afterNextToken.tag),
      ];
      if (segmentsToText(inlineSegments).length <= INLINE_TEXT_LIMIT) {
        lines.push({
          indent,
          number: lines.length + 1,
          segments: inlineSegments,
        });
        index += 2;
        continue;
      }
    }

    lines.push({
      indent,
      number: lines.length + 1,
      segments: openSegments(token.tag, token.attrs, token.selfClosing),
    });

    if (!token.selfClosing) {
      indent += 1;
    }
  }

  return lines;
}

function segmentClass(type: Segment["type"]): string {
  switch (type) {
    case "declaration":
      return "text-pink-700 dark:text-pink-400";
    case "comment":
      return "text-slate-500 italic";
    case "punct":
      return "text-slate-500 dark:text-slate-400";
    case "tag":
      return "text-sky-700 dark:text-sky-400";
    case "attrName":
      return "text-violet-700 dark:text-violet-400";
    case "attrValue":
      return "text-amber-700 dark:text-amber-300";
    default:
      return "text-foreground";
  }
}

function highlightSearchMatches(text: string, query: string): ReactNode {
  if (!query) {
    return text;
  }

  const normalizedQuery = query.toLowerCase();
  const parts: ReactNode[] = [];
  let start = 0;
  let index = text.toLowerCase().indexOf(normalizedQuery, start);

  while (index !== -1) {
    if (index > start) {
      parts.push(text.slice(start, index));
    }
    const match = text.slice(index, index + query.length);
    parts.push(
      <mark
        key={`${index}-${match}`}
        className="rounded bg-yellow-200 px-0.5 text-foreground dark:bg-yellow-500/40"
      >
        {match}
      </mark>,
    );
    start = index + query.length;
    index = text.toLowerCase().indexOf(normalizedQuery, start);
  }

  if (start < text.length) {
    parts.push(text.slice(start));
  }

  return parts;
}

export function XmlViewer({ fileUrl, filename }: XmlViewerProps): React.JSX.Element {
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fontSizeIndex, setFontSizeIndex] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    let cancelled = false;

    fetch(fileUrl)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        return response.text();
      })
      .then((text) => {
        if (!cancelled) {
          setContent(text);
          setLoading(false);
        }
      })
      .catch((fetchError: unknown) => {
        if (!cancelled) {
          setError(fetchError instanceof Error ? fetchError.message : "Unbekannter Fehler");
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [fileUrl]);

  const fontSize = FONT_SIZES[fontSizeIndex];
  const lines = useMemo(() => formatTokens(tokenize(content ?? "")), [content]);
  const filteredLines = useMemo(() => {
    if (!searchQuery) {
      return lines;
    }

    const normalizedQuery = searchQuery.toLowerCase();
    return lines.filter((line) =>
      line.segments.some((segment) => segment.text.toLowerCase().includes(normalizedQuery)),
    );
  }, [lines, searchQuery]);

  const handleCopy = async (): Promise<void> => {
    if (!content) {
      return;
    }
    await navigator.clipboard.writeText(content);
    toast.success("XML in Zwischenablage kopiert.");
  };

  if (loading) {
    return <Skeleton className="h-[60vh] w-full" />;
  }

  if (error || !content) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-muted-foreground">
          XML konnte nicht geladen werden{error ? `: ${error}` : "."}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="h-full">
      <CardContent className="flex h-full flex-col gap-3 p-4">
        <ViewerToolbar
          filename={filename}
          className="sticky top-0 z-10 bg-background/80 pt-0 backdrop-blur"
          controls={(
            <>
              <div className="relative mr-2 hidden sm:block">
                <Search className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="Suchen"
                  aria-label="XML durchsuchen"
                  className="h-8 w-40 pl-8"
                />
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={() => setFontSizeIndex((current) => Math.max(0, current - 1))}
                disabled={fontSizeIndex === 0}
                aria-label="Verkleinern"
              >
                <ZoomOut className="h-4 w-4" />
              </Button>
              <span className="font-tnum text-xs">{fontSize}px</span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={() =>
                  setFontSizeIndex((current) => Math.min(FONT_SIZES.length - 1, current + 1))
                }
                disabled={fontSizeIndex === FONT_SIZES.length - 1}
                aria-label="Vergrößern"
              >
                <ZoomIn className="h-4 w-4" />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={handleCopy}
                aria-label="Kopieren"
              >
                <Copy className="h-4 w-4" />
              </Button>
              <a
                href={fileUrl}
                download={filename}
                className="inline-flex h-8 items-center justify-center rounded-md border border-input px-3 text-xs font-medium transition-colors hover:bg-accent hover:text-accent-foreground"
              >
                Herunterladen
              </a>
            </>
          )}
        />
        <div className="block sm:hidden">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Suchen"
              aria-label="XML durchsuchen"
              className="h-8 pl-8"
            />
          </div>
        </div>
        <div className="flex-1 overflow-auto rounded-lg bg-muted/30 p-3">
          <div className="font-mono" style={{ fontSize: `${fontSize}px` }}>
            {filteredLines.length === 0 ? (
              <div className="text-sm text-muted-foreground">Keine Treffer gefunden.</div>
            ) : (
              filteredLines.map((line) => (
                <div key={line.number} className="group flex leading-6">
                  <span
                    className="select-none pr-3 text-right tabular-nums text-muted-foreground/50"
                    style={{ minWidth: "3.5ch" }}
                  >
                    {line.number}
                  </span>
                  <div className="flex min-w-0 flex-1">
                    {Array.from({ length: line.indent }).map((_, index) => (
                      <span
                        key={`${line.number}-indent-${index}`}
                        data-testid="xml-indent-guide"
                        className="shrink-0 border-l border-border/30"
                        style={{ width: "1.5ch" }}
                      />
                    ))}
                    <span className="min-w-0 whitespace-pre">
                      {line.segments.map((segment, index) => (
                        <span
                          key={`${line.number}-${index}-${segment.text}`}
                          className={segmentClass(segment.type)}
                        >
                          {highlightSearchMatches(segment.text, searchQuery)}
                        </span>
                      ))}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
