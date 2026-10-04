"use client";

import { useCallback, useRef, useState } from "react";
import { useChatStore } from "@/lib/store";
import { SourceItem, ChatMessage } from "@/lib/store";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

interface StreamEvent {
  type: "metadata" | "text" | "done" | "error";
  data: unknown;
}

interface UseRagChatReturn {
  sendMessage: (message: string) => Promise<void>;
  isStreaming: boolean;
  error: string | null;
  clearError: () => void;
}

export function useRagChat(): UseRagChatReturn {
  const { 
    addMessage, 
    updateLastMessage, 
    setIsStreaming, 
    isStreaming,
    impersonateRole 
  } = useChatStore();
  
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null);

  const clearError = useCallback(() => setError(null), []);

  const parseSSEEvent = (text: string): StreamEvent | null => {
    const lines = text.trim().split("\n");
    let eventType = "text";
    let eventData = "";
    
    for (const line of lines) {
      if (line.startsWith("event: ")) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        eventData = line.slice(6).trim();
      }
    }
    
    if (!eventData) return null;
    
    try {
      return {
        type: eventType as StreamEvent["type"],
        data: JSON.parse(eventData),
      };
    } catch {
      // If data isn't JSON, treat as text
      return {
        type: "text",
        data: { delta: eventData },
      };
    }
  };

  const sendMessage = useCallback(async (message: string) => {
    if (isStreaming) return;
    
    setError(null);
    setIsStreaming(true);
    
    // Add user message
    const userMessage: ChatMessage = {
      id: Math.random().toString(36).substring(2, 15),
      role: "user",
      content: message,
    };
    addMessage(userMessage);
    
    // Create assistant message placeholder
    const assistantMessage: ChatMessage = {
      id: Math.random().toString(36).substring(2, 15),
      role: "assistant",
      content: "",
    };
    addMessage(assistantMessage);
    
    abortControllerRef.current = new AbortController();
    
    // Variables that need to be accessible in catch block
    let accumulatedContent = "";
    let sources: SourceItem[] = [];
    
    try {
      const headers: HeadersInit = {
        "Content-Type": "application/json",
      };
      
      if (process.env.NODE_ENV === "development" && impersonateRole) {
        headers["X-Impersonate-Role"] = impersonateRole;
      }
      
      const response = await fetch(`${API_BASE}/chat/stream`, {
        method: "POST",
        headers,
        body: JSON.stringify({ message, top_k: 5 }),
        signal: abortControllerRef.current.signal,
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: "Unknown error" }));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }
      
      if (!response.body) {
        throw new Error("No response body");
      }
      
      readerRef.current = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      
      while (true) {
        const { done, value } = await readerRef.current.read();
        
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        
        // Split by double newline to get complete SSE events
        const events = buffer.split("\n\n");
        buffer = events.pop() || ""; // Keep incomplete event in buffer
        
        for (const eventText of events) {
          if (!eventText.trim()) continue;
          
          const event = parseSSEEvent(eventText);
          if (!event) continue;
          
          switch (event.type) {
            case "metadata": {
              const metadata = event.data as {
                query: string;
                user_roles: string[];
                has_sufficient_context: boolean;
                retrieval_metrics: Record<string, unknown>;
                sources: SourceItem[];
              };
              
              sources = metadata.sources || [];
              break;
            }
            
            case "text": {
              const textData = event.data as { delta?: string };
              if (textData.delta) {
                accumulatedContent += textData.delta;
                updateLastMessage(accumulatedContent, sources);
              }
              break;
            }
            
            case "done": {
              const doneData = event.data as {
                generation_metrics: {
                  generation_latency_ms: number;
                  total_tokens: number;
                  prompt_tokens: number;
                  completion_tokens: number;
                };
                finish_reason: string;
              };
              
              updateLastMessage(accumulatedContent, sources);
              // Update the last message with generation metrics
              const { messages: currentMessages } = useChatStore.getState();
              const lastIndex = currentMessages.length - 1;
              if (lastIndex >= 0) {
                const updatedMessages = [...currentMessages];
                updatedMessages[lastIndex] = {
                  ...updatedMessages[lastIndex],
                  generationMetrics: doneData.generation_metrics,
                  finishReason: doneData.finish_reason,
                };
                useChatStore.setState({ messages: updatedMessages });
              }
              break;
            }
            
            case "error": {
              const errorData = event.data as { error?: string; request_id?: string };
              throw new Error(errorData.error || "Stream error");
            }
          }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        // Stream was aborted, not an error
        return;
      }
      
      const errorMessage = err instanceof Error ? err.message : "Failed to send message";
      setError(errorMessage);
      
      // Update last message with error
      const { messages: currentMessages } = useChatStore.getState();
      const lastIndex = currentMessages.length - 1;
      if (lastIndex >= 0 && currentMessages[lastIndex].role === "assistant") {
        const updatedMessages = [...currentMessages];
        updatedMessages[lastIndex] = {
          ...updatedMessages[lastIndex],
          content: accumulatedContent || `Error: ${errorMessage}`,
        };
        useChatStore.setState({ messages: updatedMessages });
      }
    } finally {
      setIsStreaming(false);
      readerRef.current = null;
      abortControllerRef.current = null;
    }
  }, [isStreaming, impersonateRole, addMessage, updateLastMessage, setIsStreaming]);

  // Cleanup on unmount
  // Note: In React 19, useEffect cleanup runs after component unmounts
  
  return {
    sendMessage,
    isStreaming,
    error,
    clearError,
  };
}