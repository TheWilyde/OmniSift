"""Token counting utility using tiktoken."""

import tiktoken
from functools import lru_cache

# Default encoding for OpenAI models (cl100k_base)
DEFAULT_ENCODING = "cl100k_base"


@lru_cache(maxsize=4)
def get_encoding(encoding_name: str = DEFAULT_ENCODING) -> tiktoken.Encoding:
    """Get tiktoken encoding (cached)."""
    return tiktoken.get_encoding(encoding_name)


def count_tokens(text: str, encoding_name: str = DEFAULT_ENCODING) -> int:
    """Count tokens in text using tiktoken."""
    if not text:
        return 0
    encoding = get_encoding(encoding_name)
    return len(encoding.encode(text))


def encode_text(text: str, encoding_name: str = DEFAULT_ENCODING) -> list[int]:
    """Encode text to token IDs."""
    encoding = get_encoding(encoding_name)
    return encoding.encode(text)


def decode_tokens(tokens: list[int], encoding_name: str = DEFAULT_ENCODING) -> str:
    """Decode token IDs back to text."""
    encoding = get_encoding(encoding_name)
    return encoding.decode(tokens)


def truncate_to_tokens(text: str, max_tokens: int, encoding_name: str = DEFAULT_ENCODING) -> str:
    """Truncate text to maximum token count."""
    encoding = get_encoding(encoding_name)
    tokens = encoding.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return encoding.decode(tokens[:max_tokens])