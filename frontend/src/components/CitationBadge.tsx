"use client";

import { FileText, ExternalLink } from "lucide-react";

interface CitationBadgeProps {
  sourceData: {
    source_id: string;
    document_title: string;
    page_start: number;
    page_end: number;
  };
  isActive: boolean;
  onClick: () => void;
}

export function CitationBadge({ 
  sourceData, 
  isActive, 
  onClick 
}: CitationBadgeProps) {
  const pageText = sourceData.page_start === sourceData.page_end
    ? `p. ${sourceData.page_start}`
    : `pp. ${sourceData.page_start}-${sourceData.page_end}`;

  return (
    <button
      type="button"
      onClick={onClick}
      className={`
        inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-all duration-150
        border ${isActive 
          ? "bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-200 border-blue-300 dark:border-blue-700 shadow-sm" 
          : "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-700 hover:bg-gray-200 dark:hover:bg-gray-700"
        }
        cursor-pointer
      `}
      aria-pressed={isActive}
      title={`${sourceData.document_title}, ${pageText}`}
    >
      <FileText className="w-3 h-3 flex-shrink-0" aria-hidden="true" />
      <span className="truncate max-w-[180px]">{sourceData.document_title}</span>
      <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-white/50 dark:bg-black/30 border border-current/20">
        {pageText}
      </span>
      <ExternalLink className="w-2.5 h-2.5 opacity-60 hover:opacity-100" aria-hidden="true" />
    </button>
  );
}

interface DisabledCitationBadgeProps {
  sourceId: string;
}

export function DisabledCitationBadge({ sourceId }: DisabledCitationBadgeProps) {
  const shortId = sourceId.slice(0, 8);
  
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-600 border border-gray-200 dark:border-gray-700 cursor-not-allowed">
      <span className="relative flex items-center">
        <span className="w-3 h-3" aria-hidden="true" />
        <span className="absolute inset-0 flex items-center justify-center">
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </span>
      </span>
      <span className="truncate max-w-[180px]">Unknown source ({shortId})</span>
      <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-white/50 dark:bg-black/30 border border-current/20 opacity-50">
        N/A
      </span>
    </span>
  );
}

// Source type for citations
interface CitationSource {
  source_id: string;
  document_title: string;
  page_start: number;
  page_end: number;
}

// Main component that parses text and renders citations
interface MessageRendererProps {
  content: string;
  sources: CitationSource[];
  selectedSourceId: string | null;
  onSelectCitation: (sourceId: string, sourceData: CitationSource) => void;
}

export function MessageRenderer({ 
  content, 
  sources, 
  selectedSourceId, 
  onSelectCitation 
}: MessageRendererProps) {
  // Create a map for quick lookup
  const sourceMap = new Map(sources.map(s => [s.source_id, s]));
  
  // Split content by citation pattern [[uuid]]
  // UUID regex: [a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}
  const citationRegex = /\[\[([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})\]\]/gi;
  
  const parts: Array<{ type: "text" | "citation"; value: string }> = [];
  let lastIndex = 0;
  let match;
  
  while ((match = citationRegex.exec(content)) !== null) {
    // Add text before citation
    if (match.index > lastIndex) {
      parts.push({ 
        type: "text", 
        value: content.slice(lastIndex, match.index) 
      });
    }
    
    // Add citation
    parts.push({ 
      type: "citation", 
      value: match[1] 
    });
    
    lastIndex = match.index + match[0].length;
  }
  
  // Add remaining text
  if (lastIndex < content.length) {
    parts.push({ 
      type: "text", 
      value: content.slice(lastIndex) 
    });
  }
  
  // If no citations found, render as plain text
  if (parts.length === 1 && parts[0].type === "text") {
    return <p className="whitespace-pre-wrap">{parts[0].value}</p>;
  }
  
  return (
    <p className="whitespace-pre-wrap leading-relaxed">
      {parts.map((part, index) => {
        if (part.type === "text") {
          return <span key={index}>{part.value}</span>;
        }
        
        const sourceData = sourceMap.get(part.value);
        const isActive = selectedSourceId === part.value;
        
        if (sourceData) {
          return (
            <CitationBadge
              key={index}
              sourceData={sourceData}
              isActive={isActive}
              onClick={() => onSelectCitation(part.value, sourceData)}
            />
          );
        }
        
        return (
          <DisabledCitationBadge key={index} sourceId={part.value} />
        );
      })}
    </p>
  );
}