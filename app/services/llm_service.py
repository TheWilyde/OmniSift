"""LLM streaming service wrapper using LiteLLM for provider-agnostic async token streaming."""

import os
import asyncio
import json
import logging
from typing import AsyncGenerator, List, Optional, Dict, Any
from dataclasses import dataclass

import litellm
from litellm import acompletion

from app.core.config import settings

logger = logging.getLogger(__name__)

# Configure LiteLLM
litellm.set_verbose = False
litellm.drop_params = True


@dataclass
class LLMStreamChunk:
    """Represents a chunk from the LLM stream."""
    delta: str
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None


@dataclass
class LLMGenerationMetrics:
    """Metrics for LLM generation."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    finish_reason: Optional[str] = None
    model: str = ""


class LLMService:
    """Async LLM service with token streaming support."""
    
    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        top_p: float = 1.0,
    ):
        self.model = model or settings.llm_model
        self.temperature = temperature
        self.max_tokens = max_tokens or settings.llm_max_tokens
        self.top_p = top_p
        
        # Configure API keys from settings
        if settings.openai_api_key:
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key
        if settings.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
        if settings.gemini_api_key:
            os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
        if settings.groq_api_key:
            os.environ["GROQ_API_KEY"] = settings.groq_api_key
    
    async def stream_chat(
        self,
        messages: List[dict],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        """
        Stream chat completion tokens asynchronously.
        
        Yields:
            LLMStreamChunk with delta text and optional finish_reason/usage
        """
        model = model or self.model
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens or self.max_tokens
        
        start_time = asyncio.get_event_loop().time()
        accumulated_tokens = 0
        
        try:
            response = await acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=self.top_p,
                stream=True,
                stream_options={"include_usage": True},
            )
            
            async for chunk in response:
                if chunk.choices and len(chunk.choices) > 0:
                    choice = chunk.choices[0]
                    delta_content = choice.delta.content or ""
                    finish_reason = choice.finish_reason
                    
                    # Handle usage info (comes in last chunk with stream_options)
                    usage = None
                    if hasattr(chunk, 'usage') and chunk.usage:
                        usage = {
                            "prompt_tokens": chunk.usage.prompt_tokens,
                            "completion_tokens": chunk.usage.completion_tokens,
                            "total_tokens": chunk.usage.total_tokens,
                        }
                    
                    if delta_content:
                        accumulated_tokens += len(delta_content) // 4  # rough estimate
                        yield LLMStreamChunk(
                            delta=delta_content,
                            finish_reason=finish_reason,
                            usage=usage,
                        )
                    
                    if finish_reason:
                        # Final chunk with usage
                        latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                        if usage:
                            yield LLMStreamChunk(
                                delta="",
                                finish_reason=finish_reason,
                                usage=usage,
                            )
                        break
                        
        except Exception as e:
            logger.error(f"LLM streaming error: {e}")
            # Yield error as a chunk with finish_reason
            yield LLMStreamChunk(
                delta=f"\n\n[Error: {str(e)}]",
                finish_reason="error",
            )
    
    async def generate_chat(
        self,
        messages: List[dict],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> tuple[str, LLMGenerationMetrics]:
        """
        Non-streaming chat completion for testing/fallback.
        
        Returns:
            (full_response_text, metrics)
        """
        model = model or self.model
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens or self.max_tokens
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            response = await acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=self.top_p,
                stream=False,
            )
            
            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            content = response.choices[0].message.content or ""
            usage = response.usage
            
            metrics = LLMGenerationMetrics(
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
                latency_ms=latency_ms,
                finish_reason=response.choices[0].finish_reason,
                model=model,
            )
            
            return content, metrics
            
        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            metrics = LLMGenerationMetrics(
                latency_ms=(asyncio.get_event_loop().time() - start_time) * 1000,
                finish_reason="error",
                model=model,
            )
            return f"[Error: {str(e)}]", metrics
    
    def estimate_context_window(self, messages: List[dict]) -> tuple[int, bool]:
        """
        Estimate if prompt fits in context window.
        
        Returns:
            (estimated_tokens, fits_in_window)
        """
        estimated = sum(len(m.get("content", "")) for m in messages) // 4
        # Default to 128k context window (Gemini 1.5 Pro, GPT-4o, etc.)
        context_window = 128000
        # Reserve space for completion
        available = context_window - self.max_tokens - 1000  # buffer
        return estimated, estimated < available


# Singleton instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get or create the singleton LLM service with current config."""
    global _llm_service
    # Always create fresh instance to pick up config changes
    from app.core.config import settings
    _llm_service = LLMService(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        top_p=settings.llm_top_p,
    )
    return _llm_service