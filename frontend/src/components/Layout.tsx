"use client";

import { useChatStore } from "@/lib/store";
import { useRagChat } from "@/hooks/useRagChat";
import { RoleSwitcher } from "@/components/RoleSwitcher";
import { DocumentDrawer } from "@/components/DocumentDrawer";
import { MessageRenderer } from "@/components/CitationBadge";
import { Menu, X, Bot, MessageSquare, Send, Paperclip, Loader2, AlertCircle, RefreshCw, Trash2 } from "lucide-react";
import { useState, useRef, useEffect, useCallback } from "react";

export function Layout() {
  const { 
    messages, 
    clearMessages,
    selectedSourceId, 
    activeSourceMetadata,
    closeDrawer,
    impersonateRole,
    setImpersonateRole,
  } = useChatStore();
  
  const { sendMessage, isStreaming, error, clearError } = useRagChat();
  
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const handleSendMessage = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;

    const userMessage = input;
    setInput("");
    await sendMessage(userMessage);
  }, [input, isStreaming, sendMessage]);

  const handleRoleChange = useCallback((role: string | null) => {
    setImpersonateRole(role as typeof impersonateRole);
    // Messages are cleared in the store's setImpersonateRole
  }, [setImpersonateRole]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage(e);
    }
  }, [handleSendMessage]);

  const retryLastMessage = useCallback(() => {
    if (messages.length === 0) return;
    const lastUserMessage = [...messages].reverse().find(m => m.role === "user");
    if (lastUserMessage) {
      sendMessage(lastUserMessage.content);
    }
  }, [messages, sendMessage]);

  const currentRole = impersonateRole || "general";
  const ROLE_LABELS: Record<string, string> = {
    general: "General",
    finance: "Finance",
    legal: "Legal",
    admin: "Admin",
    hr: "Human Resources",
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex flex-col">
      {/* Top Navigation */}
      <header className="sticky top-0 z-30 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Left side - Logo and mobile menu */}
            <div className="flex items-center gap-4">
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="lg:hidden p-2 rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                aria-label="Toggle sidebar"
              >
                {sidebarOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
              </button>
              <div className="flex items-center gap-2">
                <Bot className="w-8 h-8 text-blue-600" />
                <span className="text-xl font-bold text-gray-900 dark:text-white">OmniSift</span>
              </div>
            </div>

            {/* Center - Role switcher (visible on desktop) */}
            <div className="hidden lg:flex items-center">
              <RoleSwitcher onRoleChange={handleRoleChange} />
            </div>

            {/* Right side - Status indicators */}
            <div className="flex items-center gap-4">
              {/* Connection status */}
              <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                </span>
                <span>API Connected</span>
              </div>

              {/* Error indicator */}
              {error && (
                <div className="flex items-center gap-2 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30 px-3 py-1 rounded-lg">
                  <AlertCircle className="w-4 h-4" />
                  <span>{error}</span>
                  <button onClick={clearError} className="p-1 hover:bg-red-100 dark:hover:bg-red-900/50 rounded">
                    <X className="w-3 h-3" />
                  </button>
                </div>
              )}

              {/* Role switcher on mobile */}
              <div className="lg:hidden">
                <RoleSwitcher onRoleChange={handleRoleChange} />
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 flex overflow-hidden">
        {/* Sidebar - Mobile only */}
        {sidebarOpen && (
          <aside className="fixed inset-y-0 left-0 z-40 w-64 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 lg:hidden transform transition-transform">
            <div className="flex flex-col h-full p-4 space-y-4">
              <nav className="flex-1 space-y-2">
                <button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
                  <MessageSquare className="w-5 h-5" />
                  <span>Chat</span>
                </button>
                <button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
                  <Paperclip className="w-5 h-5" />
                  <span>Documents</span>
                </button>
              </nav>
              <RoleSwitcher onRoleChange={handleRoleChange} />
            </div>
          </aside>
        )}

        {/* Main Chat Panel */}
        <div className={`flex-1 flex flex-col ${sidebarOpen ? "lg:ml-0" : ""} transition-all duration-300`}>
          {/* Chat Header */}
          <div className="border-b border-gray-200 dark:border-gray-800 px-4 py-3 flex items-center justify-between">
            <div>
              <h1 className="text-lg font-semibold text-gray-900 dark:text-white">Chat</h1>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Ask questions about your documents
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500 dark:text-gray-400 px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded-full capitalize">
                {ROLE_LABELS[currentRole]} Mode
              </span>
              {messages.length > 0 && (
                <button
                  onClick={() => clearMessages()}
                  className="p-2 rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-red-600 dark:hover:text-red-400 transition-colors"
                  aria-label="Clear conversation"
                  title="Clear conversation"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>

          {/* Messages Area */}
          <div 
            ref={scrollAreaRef}
            className="flex-1 overflow-y-auto p-4 space-y-4"
          >
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center text-gray-500 dark:text-gray-400">
                <Bot className="w-16 h-16 mb-4 opacity-50" />
                <h2 className="text-xl font-medium text-gray-900 dark:text-white mb-2">
                  Welcome to OmniSift
                </h2>
                <p className="max-w-md text-sm">
                  Upload documents and ask questions. I&apos;ll search through your documents 
                  and provide answers with citations.
                </p>
              </div>
            ) : (
              <>
                {messages.map((message, index) => (
                  <div
                    key={`${message.id}-${index}`}
                    className={`flex gap-3 ${message.role === "user" ? "justify-end" : "justify-start"} message-enter`}
                  >
                    <div
                      className={`max-w-[75%] rounded-2xl px-4 py-2.5 ${
                        message.role === "user"
                          ? "bg-blue-600 text-white rounded-br-md"
                          : "bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white rounded-bl-md"
                      }`}
                    >
                      {message.role === "assistant" && message.sources && message.sources.length > 0 ? (
                        <MessageRenderer
                          content={message.content}
                          sources={message.sources}
                          selectedSourceId={selectedSourceId}
                          onSelectCitation={(sourceId) => {
                            const fullSource = activeSourceMetadata?.source_id === sourceId 
                              ? activeSourceMetadata 
                              : message.sources?.find(s => s.source_id === sourceId);
                            if (fullSource) {
                              useChatStore.getState().selectCitation(sourceId, fullSource);
                            }
                          }}
                        />
                      ) : (
                        <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                      )}
                      
                      {/* Generation metrics for assistant messages */}
                      {message.role === "assistant" && message.generationMetrics && (
                        <div className="mt-2 flex items-center gap-3 text-[10px] text-gray-500 dark:text-gray-400">
                          <span className="flex items-center gap-1">
                            <Loader2 className="w-3 h-3" />
                            {message.generationMetrics.generation_latency_ms.toFixed(0)}ms
                          </span>
                          <span className="flex items-center gap-1">
                            <span className="w-3 h-3" />
                            {message.generationMetrics.total_tokens} tokens
                          </span>
                          {message.finishReason && (
                            <span className="px-1.5 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-[9px]">
                              {message.finishReason}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                
                {/* Streaming indicator */}
                {isStreaming && (
                  <div className="flex gap-3 justify-start">
                    <div className="max-w-[75%] bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white rounded-2xl rounded-bl-md px-4 py-2.5">
                      <div className="flex items-center gap-2 text-sm">
                        <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
                        <span className="text-gray-500 dark:text-gray-400">Generating response...</span>
                      </div>
                    </div>
                  </div>
                )}
                
                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {/* Input Area */}
          <form onSubmit={handleSendMessage} className="border-t border-gray-200 dark:border-gray-800 p-4">
            <div className="flex gap-2">
              <button
                type="button"
                className="p-2 rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                aria-label="Attach file"
                disabled={isStreaming}
              >
                <Paperclip className="w-5 h-5" />
              </button>
              <div className="flex-1 relative">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={isStreaming ? "Waiting for response..." : "Ask a question about your documents..."}
                  className="w-full px-4 py-2.5 pr-12 border border-gray-300 dark:border-gray-600 rounded-full bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 dark:disabled:bg-gray-800"
                  disabled={isStreaming}
                />
                <button
                  type="submit"
                  disabled={!input.trim() || isStreaming}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-gray-500 hover:text-blue-600 dark:hover:text-blue-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  aria-label="Send message"
                >
                  <Send className="w-5 h-5" />
                </button>
              </div>
            </div>
            <div className="flex items-center justify-between mt-2">
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Press Enter to send • Shift+Enter for new line
              </p>
              {error && (
                <button
                  type="button"
                  onClick={retryLastMessage}
                  className="text-xs text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1"
                >
                  <RefreshCw className="w-3 h-3" />
                  Retry
                </button>
              )}
            </div>
          </form>
        </div>

        {/* Document Preview Drawer */}
        <DocumentDrawer 
          documentId={selectedSourceId} 
          onClose={closeDrawer} 
        />
      </main>
    </div>
  );
}