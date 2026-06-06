"use client";

import { Copy, ZoomIn, ZoomOut } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ViewerToolbar } from "@/components/invoices/viewers/shared/viewer-toolbar";

interface XmlViewerProps {
  fileUrl: string;
  filename: string;
}

const FONT_SIZES = [12, 14, 16, 18, 20] as const;

type XmlTokenType = "comment" | "tag" | "attr" | "value" | "plain";

interface XmlToken {
  text: string;
  type: XmlTokenType;
}

export function prettyPrintXml(xml: string): string {
  const compact = xml.replace(/>\s+</g, "><").trim();
  let formatted = "";
  let indent = 0;
  const tokens = compact.split(/(<[^>]+>)/g).filter(Boolean);

  for (const token of tokens) {
    if (!token.startsWith("<")) {
      if (token.trim()) {
        formatted += `${"  ".repeat(indent)}${token.trim()}\n`;
      }
      continue;
    }

    if (token.startsWith("<?") || token.startsWith("<!--") || token.endsWith("/>")) {
      formatted += `${"  ".repeat(indent)}${token}\n`;
      continue;
    }

    if (token.startsWith("</")) {
      indent = Math.max(0, indent - 1);
      formatted += `${"  ".repeat(indent)}${token}\n`;
      continue;
    }

    formatted += `${"  ".repeat(indent)}${token}\n`;
    indent += 1;
  }

  return formatted;
}

function tokenizeAttributes(content: string): XmlToken[] {
  const tokens: XmlToken[] = [];
  const attrRegex = /([\w:-]+)(\s*=\s*)("[^"]*"|'[^']*')/g;
  let lastIndex = 0;

  for (const match of content.matchAll(attrRegex)) {
    const attrName = match[1];
    const equalPart = match[2];
    const attrValue = match[3];
    const index = match.index ?? 0;

    if (index > lastIndex) {
      tokens.push({ text: content.slice(lastIndex, index), type: "plain" });
    }

    tokens.push({ text: attrName, type: "attr" });
    tokens.push({ text: equalPart, type: "plain" });
    tokens.push({ text: attrValue, type: "value" });
    lastIndex = index + match[0].length;
  }

  if (lastIndex < content.length) {
    tokens.push({ text: content.slice(lastIndex), type: "plain" });
  }

  return tokens;
}

function tokenizeXmlLine(line: string): XmlToken[] {
  if (line.trim().startsWith("<!--")) {
    return [{ text: line, type: "comment" }];
  }

  const tagMatch = line.match(/^(\s*)(<\/?\??)([\w:-]+)(.*?)(\??\/?>)(\s*)$/);
  if (!tagMatch) {
    return [{ text: line, type: "plain" }];
  }

  const [, leading, opening, name, middle, closing, trailing] = tagMatch;
  const tokens: XmlToken[] = [
    { text: leading + opening, type: "plain" },
    { text: name, type: "tag" },
    ...tokenizeAttributes(middle),
    { text: closing + trailing, type: "plain" },
  ];

  return tokens;
}

function tokenClassName(type: XmlTokenType): string {
  switch (type) {
    case "comment":
      return "text-muted-foreground italic";
    case "tag":
      return "text-blue-600 dark:text-blue-400";
    case "attr":
      return "text-purple-600 dark:text-purple-400";
    case "value":
      return "text-green-700 dark:text-green-400";
    default:
      return "";
  }
}

function highlightXmlLine(line: string): React.JSX.Element {
  const tokens = tokenizeXmlLine(line);
  return (
    <>
      {tokens.map((token, index) => (
        <span key={`${index}-${token.text}`} className={tokenClassName(token.type)}>
          {token.text}
        </span>
      ))}
    </>
  );
}

export function XmlViewer({ fileUrl, filename }: XmlViewerProps): React.JSX.Element {
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fontSizeIndex, setFontSizeIndex] = useState(1);

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
          setContent(prettyPrintXml(text));
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

  const lines = useMemo(() => (content ?? "").split("\n").filter((line) => line.length > 0), [content]);
  const fontSize = FONT_SIZES[fontSizeIndex];

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
    <div className="flex h-full flex-col gap-2">
      <ViewerToolbar
        filename={filename}
        controls={(
          <>
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
              onClick={() => setFontSizeIndex((current) => Math.min(FONT_SIZES.length - 1, current + 1))}
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
          </>
        )}
      />
      <div className="flex-1 overflow-auto rounded-lg bg-muted/30 p-3">
        <pre className="font-mono leading-relaxed" style={{ fontSize: `${fontSize}px` }}>
          {lines.map((line, index) => (
            <div key={`${index}-${line}`} className="flex gap-3">
              <span className="select-none text-right text-muted-foreground/60" style={{ minWidth: "3ch" }}>
                {index + 1}
              </span>
              <span className="whitespace-pre">{highlightXmlLine(line)}</span>
            </div>
          ))}
        </pre>
      </div>
    </div>
  );
}
