import { memo } from "react";

import { MarkdownViewer } from "./MarkdownViewer";

interface DualMarkdownPaneProps {
  collectionName: string | null;
}

export const DualMarkdownPane = memo(function DualMarkdownPane({
  collectionName,
}: DualMarkdownPaneProps) {
  return (
    <div className="dual-markdown-pane">
      <MarkdownViewer collectionName={collectionName} version="original" title="原文" />
      <MarkdownViewer collectionName={collectionName} version="translated" title="翻譯" />
    </div>
  );
});
