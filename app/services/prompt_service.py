"""Prompt builder service for citation-grounded LLM generation."""

from typing import List, Optional
from app.schemas.document import ResolvedParentChunk


# System prompt with strict citation rules
SYSTEM_PROMPT = """You are a precise, citation-grounded assistant. You must follow these rules exactly:

1. SOURCE RELIANCE: Rely solely on the provided source excerpts. Never use outside knowledge, training data, or extrapolate beyond what is explicitly stated in the sources.

2. CITATION FORMAT: After every factual claim, you MUST include an inline citation in the format [[<SOURCE_ID>]] where SOURCE_ID is the exact UUID shown in the source delimiter. Place the citation immediately after the claim, before any punctuation.

3. CITATION PLACEMENT: Each sentence or distinct claim requires its own citation. If a sentence draws from multiple sources, include multiple citations: [[<SOURCE_ID_1>]][[<SOURCE_ID_2>]].

4. FORBIDDEN FORMATS: Do NOT use markdown footnotes, numbered references like [1], vague attributions like "according to the document", or any citation format other than [[<SOURCE_ID>]].

5. INSUFFICIENT CONTEXT: If the system indicates insufficient context, you must NOT generate an answer. The system will handle this case before calling you.

6. QUOTING: You may quote short phrases directly from sources, but always cite them. Do not paraphrase in a way that changes meaning.

7. UNCERTAINTY: If the sources do not contain enough information to answer the question, state that clearly and cite the relevant sources that were checked.

8. ROLE AWARENESS: You only have access to sources permitted for the user's role. Never reference or imply knowledge of sources you were not given."""


# Fallback message when no context passes confidence floor
INSUFFICIENT_CONTEXT_MESSAGE = """I couldn't find any relevant documents for your query with your current access level. This could mean:

- No documents match your query within your permitted roles
- The relevant documents exist but didn't meet the relevance threshold
- You may need additional permissions to access the relevant information

Please try rephrasing your query or contact your administrator if you believe you should have access to this information."""


def format_source_block(chunk: ResolvedParentChunk, index: int) -> str:
    """
    Format a single parent chunk as a source block with delimiter.
    
    Format:
    [SOURCE_ID: <parent_uuid> | Document: <title> | Pages: <page_start>-<page_end>]
    <content>
    [END_SOURCE]
    """
    pages = f"{chunk.page_start}-{chunk.page_end}" if chunk.page_start != chunk.page_end else str(chunk.page_start)
    
    delimiter = f"[SOURCE_ID: {chunk.id} | Document: {chunk.document_title} | Pages: {pages}]"
    end_delimiter = "[END_SOURCE]"
    
    return f"{delimiter}\n{chunk.content}\n{end_delimiter}"


def build_context_section(chunks: List[ResolvedParentChunk]) -> str:
    """Build the full context section from retrieved parent chunks."""
    if not chunks:
        return "No source excerpts provided."
    
    blocks = []
    for i, chunk in enumerate(chunks):
        blocks.append(format_source_block(chunk, i))
    
    return "\n\n".join(blocks)


def build_user_prompt(query: str, chunks: List[ResolvedParentChunk]) -> str:
    """Build the user prompt with context and query."""
    context = build_context_section(chunks)
    
    return f"""Here are the source excerpts for your reference:

{context}

---

Question: {query}

Answer the question using only the provided sources. Include inline citations [[SOURCE_ID]] after every claim."""


def build_messages(query: str, chunks: List[ResolvedParentChunk], history: Optional[List[dict]] = None) -> List[dict]:
    """
    Build the full message list for the LLM.
    
    Args:
        query: User's current query
        chunks: Retrieved and re-ranked parent chunks
        history: Optional conversation history as [{"role": "user|assistant", "content": "..."}]
    
    Returns:
        List of messages for the LLM API
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Add conversation history if provided
    if history:
        for turn in history:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
    
    # Add current query with context
    user_prompt = build_user_prompt(query, chunks)
    messages.append({"role": "user", "content": user_prompt})
    
    return messages


def estimate_prompt_tokens(messages: List[dict]) -> int:
    """Rough token estimation for prompt (4 chars ≈ 1 token)."""
    total_chars = sum(len(m.get("content", "")) for m in messages)
    return total_chars // 4


def validate_context_sufficiency(has_sufficient_context: bool) -> tuple[bool, str]:
    """
    Check if context is sufficient for generation.
    
    Returns:
        (should_generate, message_or_empty_string)
    """
    if not has_sufficient_context:
        return False, INSUFFICIENT_CONTEXT_MESSAGE
    return True, ""