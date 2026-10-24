import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function ChatMarkdown({
  text,
  working = false,
}: {
  text: string;
  working?: boolean;
}) {
  return (
    <div className={`hc-markdown ${working ? "hc-working" : ""}`}>
      <Markdown
        skipHtml
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ children, href }) => (
            <a href={href} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
          img: ({ alt, src }) => (
            <a href={src} target="_blank" rel="noopener noreferrer">
              {alt || "View image"}
            </a>
          ),
          table: ({ children }) => (
            <div
              className="hc-table-scroll"
              role="region"
              aria-label="Response table"
              tabIndex={0}
            >
              <table>{children}</table>
            </div>
          ),
        }}
      >
        {text || (working ? "HANNI is working…" : "No response was returned.")}
      </Markdown>
    </div>
  );
}
