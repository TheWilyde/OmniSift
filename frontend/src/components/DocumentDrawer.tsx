"use client";

import { useChatStore } from "@/lib/store";
import { X, FileText, Search, Highlighter, Scale, ChevronRight } from "lucide-react";
import { useMemo } from "react";
import { SourceItem } from "@/lib/store";

interface DocumentDrawerProps {
  documentId: string | null;
  onClose: () => void;
}

function HighlightedText({ 
  text, 
  highlightStart, 
  highlightEnd 
}: { 
  text: string; 
  highlightStart?: number; 
  highlightEnd?: number; 
}) {
  if (highlightStart === undefined || highlightEnd === undefined) {
    return <p className="whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300 leading-relaxed">{text}</p>;
  }
  
  const before = text.slice(0, highlightStart);
  const highlighted = text.slice(highlightStart, highlightEnd);
  const after = text.slice(highlightEnd);
  
  return (
    <p className="whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
      <span>{before}</span>
      <mark className="bg-yellow-200 dark:bg-yellow-800 text-gray-900 dark:text-yellow-100 px-1 rounded">
        {highlighted}
      </mark>
      <span>{after}</span>
    </p>
  );
}

function BoundingBoxPreview({ 
  bboxes, 
  pageStart, 
  pageEnd 
}: { 
  bboxes: SourceItem["child_bboxes"]; 
  pageStart: number;
  pageEnd: number;
}) {
  if (!bboxes || bboxes.length === 0) {
    return (
      <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg text-center">
        <Search className="w-12 h-12 mx-auto text-gray-400 mb-2" />
        <p className="text-sm text-gray-500 dark:text-gray-400">
          No bounding box data available for preview
        </p>
      </div>
    );
  }
  
  // Group bboxes by page
  const pagesWithBboxes = bboxes.filter(b => b.page >= pageStart && b.page <= pageEnd);
  
  return (
    <div className="space-y-4">
      <h4 className="text-sm font-medium text-gray-900 dark:text-white flex items-center gap-2">
        <Highlighter className="w-4 h-4" />
        Visual Location Preview
      </h4>
      {pagesWithBboxes.map((bbox, index) => (
        <div key={index} className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
          <div className="px-3 py-2 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
            <span className="text-xs font-medium text-gray-700 dark:text-gray-300">
              Page {bbox.page}
            </span>
            <span className="text-xs text-gray-500 dark:text-gray-400 font-mono">
              x:{bbox.x0.toFixed(3)} y:{bbox.y0.toFixed(3)} &rarr; x:{bbox.x1.toFixed(3)} y:{bbox.y1.toFixed(3)}
            </span>
          </div>
          <div className="p-4 relative">
            {/* Normalized coordinate preview - 100% = page width/height */}
            <div className="relative w-full aspect-[4/3] bg-gray-100 dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-700">
              <div
                className="absolute border-2 border-yellow-400 bg-yellow-400/20"
                style={{
                  left: `${bbox.x0 * 100}%`,
                  top: `${bbox.y0 * 100}%`,
                  width: `${Math.max(0.02, (bbox.x1 - bbox.x0) * 100)}%`,
                  height: `${Math.max(0.02, (bbox.y1 - bbox.y0) * 100)}%`,
                }}
                title={`x: ${bbox.x0.toFixed(3)}-${bbox.x1.toFixed(3)}, y: ${bbox.y0.toFixed(3)}-${bbox.y1.toFixed(3)}`}
              />
              {/* Page dimensions indicator */}
              <div className="absolute inset-0 border border-dashed border-gray-300 dark:border-gray-600" />
            </div>
            <div className="mt-2 flex gap-4 text-xs text-gray-500 dark:text-gray-400">
              <span>Width: {((bbox.x1 - bbox.x0) * 100).toFixed(1)}%</span>
              <span>Height: {((bbox.y1 - bbox.y0) * 100).toFixed(1)}%</span>
              <span>Top: {(bbox.y0 * 100).toFixed(1)}%</span>
              <span>Left: {(bbox.x0 * 100).toFixed(1)}%</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function DocumentDrawer({ documentId, onClose }: DocumentDrawerProps) {
  const { 
    isDrawerOpen, 
    activeSourceMetadata,
    messages 
  } = useChatStore();

  // Compute values that need to be available before early return
  const source = activeSourceMetadata;

  // Find relevance score for this source from the message (unused but kept for future use)
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const relevanceScore = useMemo(() => {
    if (!source || !messages.length) return null;
    for (const msg of messages) {
      if (msg.sources) {
        const src = msg.sources.find(s => s.source_id === source?.source_id);
        if (src && msg.generationMetrics) {
          return null;
        }
      }
    }
    return null;
  }, [messages, source]);

  // Early return if drawer should not be shown
  if (!documentId || !isDrawerOpen || !activeSourceMetadata) return null;
  
  // Now TypeScript knows activeSourceMetadata is non-null
  const nonNullSource = activeSourceMetadata;
  const nonNullPageRange = nonNullSource.page_start === nonNullSource.page_end
    ? `Page ${nonNullSource.page_start}`
    : `Pages ${nonNullSource.page_start}&#8211;${nonNullSource.page_end}`;

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 z-40 bg-black/50 animate-fade-in"
        onClick={onClose}
        aria-hidden="true"
      />
      
      {/* Drawer */}
      <aside
        className="fixed right-0 top-0 z-50 h-full w-full max-w-xl md:max-w-2xl lg:max-w-3xl bg-white dark:bg-gray-900 shadow-xl flex flex-col animate-slide-in"
        role="dialog"
        aria-label="Document preview"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
          <div className="flex-1 min-w-0">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white truncate">
              {nonNullSource.document_title}
            </h2>
            <div className="flex items-center gap-3 mt-1 text-sm text-gray-500 dark:text-gray-400">
              <span className="flex items-center gap-1">
                <FileText className="w-3.5 h-3.5" />
                {nonNullPageRange}
              </span>
              <span className="px-2 py-0.5 bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-200 rounded-full text-xs font-medium">
                Source
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors ml-4 flex-shrink-0"
            aria-label="Close drawer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {/* Document Preview Snippet */}
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-gray-900 dark:text-white flex items-center gap-2">
              <FileText className="w-4 h-4" />
              Content Preview
            </h3>
            <div className="bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 max-h-64 overflow-y-auto">
              <HighlightedText 
                text={nonNullSource.preview} 
              />
            </div>
          </div>

          {/* Bounding Box Visual Preview */}
          {nonNullSource.child_bboxes && nonNullSource.child_bboxes.length > 0 && (
            <BoundingBoxPreview 
              bboxes={nonNullSource.child_bboxes} 
              pageStart={nonNullSource.page_start}
              pageEnd={nonNullSource.page_end}
            />
          )}

          {/* Retrieval Metrics Footer */}
          <div className="border-t border-gray-200 dark:border-gray-700 pt-4 space-y-3">
            <h3 className="text-sm font-medium text-gray-900 dark:text-white flex items-center gap-2">
              <Scale className="w-4 h-4" />
              Retrieval Metrics
            </h3>
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                  {nonNullSource.child_bboxes?.length || 0}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Child Chunks
                </div>
              </div>
              <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                  {nonNullSource.page_end - nonNullSource.page_start + 1}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Pages Spanned
                </div>
              </div>
              <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
                  {nonNullSource.preview.length}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Chars in Preview
                </div>
              </div>
            </div>
            
            {/* Bounding box details */}
            {nonNullSource.child_bboxes && nonNullSource.child_bboxes.length > 0 && (
              <details className="group">
                <summary className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 cursor-pointer hover:text-gray-900 dark:hover:text-white">
                  <ChevronRight className="w-4 h-4 transition-transform group-open:rotate-90 flex-shrink-0" />
                  Bounding Box Details
                </summary>
                <div className="mt-3 space-y-2 text-xs font-mono">
                  {nonNullSource.child_bboxes.map((bbox, idx) => (
                    <div key={idx} className="bg-gray-50 dark:bg-gray-800 rounded p-2 border border-gray-200 dark:border-gray-700">
                      <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
                        <span className="font-medium">Page {bbox.page}:</span>
                        <span>x&#8739;[{bbox.x0.toFixed(4)}, {bbox.x1.toFixed(4)}]</span>
                        <span>y&#8739;[{bbox.y0.toFixed(4)}, {bbox.y1.toFixed(4)}]</span>
                        <span className="text-gray-400 dark:text-gray-500">
                          (w: {(bbox.x1 - bbox.x0).toFixed(4)}, h: {(bbox.y1 - bbox.y0).toFixed(4)})
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </div>

          {/* Source ID for debugging */}
          <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
            <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
              <span>Source ID:</span>
              <code className="font-mono bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded break-all max-w-[70%]">
                {nonNullSource.source_id}
              </code>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}