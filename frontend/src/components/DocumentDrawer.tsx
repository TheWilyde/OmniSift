"use client";

import { useAuthStore } from "@/lib/store";
import { X, FileText, Download, Info, ChevronLeft } from "lucide-react";

interface DocumentDrawerProps {
  documentId: string | null;
  onClose: () => void;
}

export function DocumentDrawer({ documentId, onClose }: DocumentDrawerProps) {
  const { isDrawerOpen, setDrawerOpen, selectedDocumentId } = useAuthStore();

  if (!documentId || !isDrawerOpen) return null;

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-black/50"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        className="fixed right-0 top-0 z-50 h-full w-full max-w-md bg-white dark:bg-gray-900 shadow-xl flex flex-col"
        role="dialog"
        aria-label="Document preview"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Document Preview
          </h2>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            aria-label="Close drawer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          <div className="space-y-4">
            {/* Document info placeholder */}
            <div className="flex items-center gap-3 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <FileText className="w-10 h-10 text-gray-400" />
              <div className="min-w-0">
                <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                  Document ID: {documentId.slice(0, 8)}...
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Click to view full document details
                </p>
              </div>
            </div>

            {/* Action buttons */}
            <div className="flex gap-2">
              <button className="flex-1 flex items-center justify-center gap-2 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
                <Download className="w-4 h-4" />
                Download
              </button>
              <button className="flex-1 flex items-center justify-center gap-2 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
                <Info className="w-4 h-4" />
                Details
              </button>
            </div>

            {/* Chunks placeholder */}
            <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
              <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-3">
                Document Chunks
              </h3>
              <div className="space-y-2 text-sm text-gray-500 dark:text-gray-400">
                <p>No chunks loaded yet.</p>
                <p className="text-xs">Chunks will appear here after processing.</p>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}