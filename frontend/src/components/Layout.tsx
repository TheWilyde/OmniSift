"use client";

import { useAuthStore } from "@/lib/store";
import { RoleSwitcher } from "@/components/RoleSwitcher";
import { DocumentDrawer } from "@/components/DocumentDrawer";
import { Menu, X, Bot, MessageSquare, Send, Paperclip, ChevronRight } from "lucide-react";
import { useState, useRef, useEffect } from "react";

export function Layout({ children }: { children: React.ReactNode }) {
  const { 
    selectedDocumentId, 
    setSelectedDocumentId, 
    isDrawerOpen, 
    setDrawerOpen,
    impersonateRole 
  } = useAuthStore();
  
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [messages, setMessages] = useState<Array<{ role: "user" | "assistant"; content: string }>>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input;
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setInput("");
    setIsLoading(true);

    try {
      // In a real implementation, this would call the backend chat API
      // For now, simulate a response
      await new Promise((resolve) => setTimeout(resolve, 1000));
      setMessages((prev) => [
        ...prev,
        { 
          role: "assistant", 
          content: `I received your message: "${userMessage}". This is a simulated response. In the full implementation, this would query the vector database and return relevant document chunks with citations.` 
        }
      ]);
    } catch (error) {
      console.error("Failed to send message:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDocumentClick = (docId: string) => {
    setSelectedDocumentId(docId);
    setDrawerOpen(true);
  };

  const closeDrawer = () => {
    setDrawerOpen(false);
    setSelectedDocumentId(null);
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
              <RoleSwitcher />
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

              {/* Role switcher on mobile */}
              <div className="lg:hidden">
                <RoleSwitcher />
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
              <RoleSwitcher />
            </div>
          </aside>
        )}

        {/* Main Chat Panel */}
        <div className={`flex-1 flex flex-col ${sidebarOpen ? "lg:ml-0" : ""} transition-all duration-300`}>
          {/* Chat Header */}
          <div className="border-b border-gray-200 dark:border-gray-800 px-4 py-3">
            <h1 className="text-lg font-semibold text-gray-900 dark:text-white">Chat</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Ask questions about your documents
            </p>
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
                  Upload documents and ask questions. I'll search through your documents 
                  and provide answers with citations.
                </p>
              </div>
            ) : (
              <>
                {messages.map((message, index) => (
                  <div
                    key={index}
                    className={`flex gap-3 ${message.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[70%] rounded-2xl px-4 py-2.5 ${
                        message.role === "user"
                          ? "bg-blue-600 text-white rounded-br-md"
                          : "bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white rounded-bl-md"
                      }`}
                    >
                      <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                    </div>
                  </div>
                ))}
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
              >
                <Paperclip className="w-5 h-5" />
              </button>
              <div className="flex-1 relative">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask a question about your documents..."
                  className="w-full px-4 py-2.5 pr-12 border border-gray-300 dark:border-gray-600 rounded-full bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  disabled={isLoading}
                />
                <button
                  type="submit"
                  disabled={!input.trim() || isLoading}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-gray-500 hover:text-blue-600 dark:hover:text-blue-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  aria-label="Send message"
                >
                  <Send className="w-5 h-5" />
                </button>
              </div>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-2 text-center">
              Press Enter to send • Shift+Enter for new line
            </p>
          </form>
        </div>

        {/* Document Preview Drawer */}
        <DocumentDrawer 
          documentId={selectedDocumentId} 
          onClose={closeDrawer} 
        />
      </main>
    </div>
  );
}