"""Context compression to remove redundancy and fit token limits."""
import logging
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.models.document import Document
from app.core.config import settings

logger = logging.getLogger(__name__)


class ContextCompressor:
    """Compress retrieved context to remove redundancy and fit token limits."""
    
    def __init__(self):
        """Initialize compressor with LLM for summarization-based compression."""
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",  # Fast, cost-effective model
            temperature=0.1,  # Low temperature for factual compression
            max_tokens=2000
        )
    
    async def compress(
        self,
        documents: List[Document],
        max_tokens: int = 2000,
        preserve_key_info: bool = True,
        compression_mode: str = "moderate"
    ) -> str:
        """
        Compress context from documents.
        
        Args:
            documents: List of Document objects
            max_tokens: Maximum tokens for compressed context
            preserve_key_info: Whether to preserve key information
            compression_mode: "none", "moderate", "aggressive"
        
        Returns:
            Compressed context string
        """
        if not documents:
            return ""
        
        if compression_mode == "none":
            # No compression, just concatenate (with truncation)
            return self._simple_concatenate(documents, max_tokens)
        
        # Extract content from documents
        doc_contents = []
        for doc in documents:
            content = doc.content if hasattr(doc, 'content') else str(doc)
            filename = doc.filename if hasattr(doc, 'filename') else "unknown"
            doc_contents.append(f"From {filename}:\n{content}")
        
        full_context = "\n\n---\n\n".join(doc_contents)
        
        # Estimate tokens (rough: 1 token ≈ 4 characters)
        estimated_tokens = len(full_context) // 4
        
        if estimated_tokens <= max_tokens:
            # No compression needed
            logger.info(f"ContextCompressor: No compression needed ({estimated_tokens} tokens)")
            return full_context
        
        # Apply compression based on mode
        if compression_mode == "moderate":
            return await self._moderate_compression(documents, max_tokens, preserve_key_info)
        elif compression_mode == "aggressive":
            return await self._aggressive_compression(documents, max_tokens, preserve_key_info)
        else:
            # Default: simple truncation
            return self._simple_concatenate(documents, max_tokens)
    
    def _simple_concatenate(self, documents: List[Document], max_tokens: int) -> str:
        """Simple concatenation with truncation."""
        result_parts = []
        current_tokens = 0
        
        for doc in documents:
            content = doc.content if hasattr(doc, 'content') else str(doc)
            filename = doc.filename if hasattr(doc, 'filename') else "unknown"
            
            # Truncate if needed
            doc_tokens = len(content) // 4
            if current_tokens + doc_tokens > max_tokens:
                remaining_tokens = max_tokens - current_tokens
                remaining_chars = remaining_tokens * 4
                content = content[:remaining_chars] + "..."
            
            result_parts.append(f"From {filename}:\n{content}")
            current_tokens += len(content) // 4
            
            if current_tokens >= max_tokens:
                break
        
        return "\n\n---\n\n".join(result_parts)
    
    async def _moderate_compression(
        self,
        documents: List[Document],
        max_tokens: int,
        preserve_key_info: bool
    ) -> str:
        """
        Moderate compression: Remove redundancy while preserving key info.
        
        Uses simple deduplication and truncation, not LLM-based (faster).
        """
        # Group by filename to remove duplicate content
        seen_content = set()
        unique_docs = []
        
        for doc in documents:
            content = doc.content if hasattr(doc, 'content') else str(doc)
            content_hash = hash(content[:100])  # Hash first 100 chars as signature
            
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                unique_docs.append(doc)
        
        # Truncate each document to fit token limit
        max_per_doc = max_tokens // max(len(unique_docs), 1)
        result_parts = []
        
        for doc in unique_docs:
            content = doc.content if hasattr(doc, 'content') else str(doc)
            filename = doc.filename if hasattr(doc, 'filename') else "unknown"
            
            # Truncate to max_per_doc tokens
            max_chars = max_per_doc * 4
            if len(content) > max_chars:
                content = content[:max_chars] + "..."
            
            result_parts.append(f"From {filename}:\n{content}")
        
        compressed = "\n\n---\n\n".join(result_parts)
        logger.info(f"ContextCompressor: Moderate compression: {len(documents)} → {len(unique_docs)} docs")
        return compressed
    
    async def _aggressive_compression(
        self,
        documents: List[Document],
        max_tokens: int,
        preserve_key_info: bool
    ) -> str:
        """
        Aggressive compression: Use LLM to summarize and extract key points.
        
        This is slower but produces more compact, relevant context.
        """
        # Extract content from all documents
        all_content = []
        for doc in documents:
            content = doc.content if hasattr(doc, 'content') else str(doc)
            filename = doc.filename if hasattr(doc, 'filename') else "unknown"
            all_content.append(f"Source: {filename}\n{content}")
        
        combined_context = "\n\n---\n\n".join(all_content)
        
        # Use LLM to summarize (only if context is too long)
        if len(combined_context) // 4 <= max_tokens:
            return combined_context
        
        try:
            system_prompt = """You are a context compression assistant. Compress the following retrieved documents while preserving all key facts, numbers, names, technologies, and important details.

Remove:
- Redundant sentences
- Repetitive information
- Unnecessary filler words

Preserve:
- Specific facts (dates, names, technologies, numbers)
- Important details
- Key relationships and connections

Return the compressed context in the same format, keeping source attribution."""
            
            prompt = f"""Compress the following context to approximately {max_tokens} tokens while preserving all key information:

{combined_context[:8000]}"""  # Limit input to avoid token limits
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            compressed = response.content
            
            logger.info(f"ContextCompressor: Aggressive compression via LLM: {len(combined_context)} → {len(compressed)} chars")
            return compressed
            
        except Exception as e:
            logger.error(f"ContextCompressor: Error in aggressive compression, falling back to moderate: {e}", exc_info=True)
            return await self._moderate_compression(documents, max_tokens, preserve_key_info)

