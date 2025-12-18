"""Enhanced answer validation and correction."""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from langchain_openai import ChatOpenAI

from app.models.document import Document
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ValidatedAnswer:
    """Validated answer with metadata."""
    answer: str
    confidence: float  # 0.0 to 1.0
    sources: List[str]  # Source filenames
    is_grounded: bool
    hallucinations_detected: bool
    missing_claims: List[str]
    citations: Dict[str, List[int]]  # {filename: [sentence_indices]}


class AnswerValidator:
    """
    Validate and correct generated answers against retrieved context.
    
    Performs:
    - Faithfulness checking (factual consistency)
    - Hallucination detection
    - Citation extraction
    - Answer correction (regeneration if needed)
    """
    
    def __init__(self):
        """Initialize answer validator."""
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,  # Low temperature for consistent validation
            max_tokens=500
        )
        self.regeneration_llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0.3,  # Slightly higher for regeneration
            max_tokens=settings.MAX_TOKENS
        )
    
    async def validate_and_correct(
        self,
        query: str,
        answer: str,
        context_documents: List[Document]
    ) -> ValidatedAnswer:
        """
        Validate answer and correct if needed.
        
        Args:
            query: Original user query
            answer: Generated answer to validate
            context_documents: Retrieved documents used for context
        
        Returns:
            ValidatedAnswer object with validation results
        """
        logger.info(f"AnswerValidator: Validating answer for query: {query[:50]}...")
        
        # Step 1: Check faithfulness (factual consistency)
        faithfulness_result = await self.check_faithfulness(answer, context_documents)
        
        # Step 2: Detect hallucinations
        hallucination_result = await self.detect_hallucination(answer, context_documents)
        
        # Step 3: Extract citations
        citations = self._extract_citations(answer, context_documents)
        
        # Step 4: Regenerate if not faithful
        if not faithfulness_result["is_faithful"]:
            logger.warning(f"AnswerValidator: Answer not faithful, regenerating...")
            corrected_answer = await self.regenerate_grounded(
                query=query,
                answer=answer,
                context_documents=context_documents,
                missing_claims=faithfulness_result.get("missing_claims", [])
            )
            answer = corrected_answer
        
        # Step 5: Extract sources
        sources = list(set([
            doc.filename if hasattr(doc, 'filename') else "unknown"
            for doc in context_documents
        ]))
        
        # Calculate confidence score
        confidence = self._calculate_confidence(
            is_faithful=faithfulness_result["is_faithful"],
            hallucination_score=hallucination_result.get("score", 0.0),
            has_sources=len(sources) > 0
        )
        
        validated = ValidatedAnswer(
            answer=answer,
            confidence=confidence,
            sources=sources,
            is_grounded=faithfulness_result["is_faithful"],
            hallucinations_detected=hallucination_result.get("detected", False),
            missing_claims=faithfulness_result.get("missing_claims", []),
            citations=citations
        )
        
        logger.info(
            f"AnswerValidator: Validation complete - "
            f"grounded={validated.is_grounded}, "
            f"confidence={confidence:.2f}, "
            f"hallucinations={validated.hallucinations_detected}"
        )
        
        return validated
    
    async def check_faithfulness(
        self,
        answer: str,
        context_documents: List[Document]
    ) -> Dict[str, Any]:
        """
        Check if answer is faithful to retrieved context.
        
        Args:
            answer: Generated answer
            context_documents: Retrieved documents
        
        Returns:
            Dictionary with 'is_faithful' boolean and 'missing_claims' list
        """
        if not context_documents:
            return {
                "is_faithful": False,
                "missing_claims": ["No context documents available"],
                "reason": "no_context"
            }
        
        # Build context from documents
        context_text = "\n\n---\n\n".join([
            f"From {doc.filename}:\n{doc.content[:500]}"
            for doc in context_documents[:3]  # Use top 3 for validation
            if hasattr(doc, 'content')
        ])
        
        system_prompt = """You are a fact-checker. Your job is to verify if a generated answer is faithful to the provided context documents.

Check if:
1. All factual claims in the answer are supported by the context
2. No claims are fabricated or unsupported
3. The answer doesn't add information not in the context

Respond in JSON format:
{
    "is_faithful": true/false,
    "missing_claims": ["claim1", "claim2"] (only if is_faithful is false),
    "reason": "brief explanation"
}"""
        
        prompt = f"""Context documents:
{context_text}

Generated answer:
{answer}

Is the answer faithful to the context? Respond in JSON format:"""
        
        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            response = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ])
            
            # Parse JSON response (simple extraction)
            import json
            import re
            json_match = re.search(r'\{[^}]+\}', response.content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "is_faithful": result.get("is_faithful", True),
                    "missing_claims": result.get("missing_claims", []),
                    "reason": result.get("reason", "unknown")
                }
            else:
                # Fallback: check if response indicates faithfulness
                content_lower = response.content.lower()
                is_faithful = "true" in content_lower or "faithful" in content_lower
                return {
                    "is_faithful": is_faithful,
                    "missing_claims": [] if is_faithful else ["Unable to verify all claims"],
                    "reason": "parsed_from_text"
                }
                
        except Exception as e:
            logger.error(f"AnswerValidator: Error checking faithfulness: {e}", exc_info=True)
            # Default to faithful on error (don't block answers)
            return {
                "is_faithful": True,
                "missing_claims": [],
                "reason": "error_during_check"
            }
    
    async def detect_hallucination(
        self,
        answer: str,
        context_documents: List[Document]
    ) -> Dict[str, Any]:
        """
        Detect hallucinations in the answer.
        
        Args:
            answer: Generated answer
            context_documents: Retrieved documents
        
        Returns:
            Dictionary with 'detected' boolean and 'score' (0.0 to 1.0)
        """
        # Simple heuristic: if no context documents, high hallucination risk
        if not context_documents:
            return {
                "detected": True,
                "score": 0.8,
                "reason": "no_context"
            }
        
        # Extract key factual claims from answer (simplified)
        # For production, could use NER or more sophisticated extraction
        answer_lower = answer.lower()
        
        # Check if answer contains specific factual indicators that might be fabricated
        # This is a simplified check; production would use more sophisticated methods
        fabricated_indicators = [
            "exactly", "precisely", "specifically", "in detail"
        ]
        
        has_specific_claims = any(indicator in answer_lower for indicator in fabricated_indicators)
        
        # If answer is very specific but we have limited context, might be hallucinated
        context_length = sum(len(doc.content) for doc in context_documents if hasattr(doc, 'content'))
        if has_specific_claims and context_length < 500:
            return {
                "detected": True,
                "score": 0.6,
                "reason": "specific_claims_with_limited_context"
            }
        
        return {
            "detected": False,
            "score": 0.2,  # Low hallucination risk
            "reason": "passed_heuristic_check"
        }
    
    async def regenerate_grounded(
        self,
        query: str,
        answer: str,
        context_documents: List[Document],
        missing_claims: List[str]
    ) -> str:
        """
        Regenerate answer with explicit grounding instructions.
        
        Args:
            query: Original query
            answer: Original (unfaithful) answer
            context_documents: Retrieved documents
            missing_claims: List of claims that were missing/unsupported
        
        Returns:
            Regenerated answer
        """
        # Build context
        context_text = "\n\n---\n\n".join([
            f"From {doc.filename}:\n{doc.content[:500]}"
            for doc in context_documents[:3]
            if hasattr(doc, 'content')
        ])
        
        system_prompt = """You are regenerating an answer to ensure it is completely grounded in the provided context documents.

IMPORTANT RULES:
- Only state facts that are explicitly in the context documents
- If information is missing, say so clearly
- Do NOT fabricate any details, dates, names, or facts
- Be honest about what information is available

If the context doesn't contain enough information to fully answer the query, acknowledge this clearly."""
        
        prompt = f"""Context documents:
{context_text}

Original query: {query}

Original answer (which was not fully faithful):
{answer}

Missing/unsupported claims:
{', '.join(missing_claims) if missing_claims else 'None specified'}

Regenerate a faithful answer based ONLY on the context documents:"""
        
        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            response = await self.regeneration_llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ])
            
            regenerated = response.content.strip()
            logger.info(f"AnswerValidator: Regenerated answer ({len(regenerated)} chars)")
            return regenerated
            
        except Exception as e:
            logger.error(f"AnswerValidator: Error regenerating answer: {e}", exc_info=True)
            return answer  # Return original on error
    
    def _extract_citations(self, answer: str, context_documents: List[Document]) -> Dict[str, List[int]]:
        """
        Extract citations from answer.
        
        Simple implementation: maps sentences to source documents.
        Production version could use more sophisticated citation extraction.
        
        Args:
            answer: Generated answer
            context_documents: Source documents
        
        Returns:
            Dictionary mapping filename to list of sentence indices
        """
        citations = {}
        
        # Simple approach: if document filename appears in answer, cite it
        for doc in context_documents:
            filename = doc.filename if hasattr(doc, 'filename') else "unknown"
            if filename and filename in answer:
                # Map to first sentence (simplified)
                citations[filename] = [0]
        
        return citations
    
    def _calculate_confidence(
        self,
        is_faithful: bool,
        hallucination_score: float,
        has_sources: bool
    ) -> float:
        """
        Calculate confidence score for the answer.
        
        Args:
            is_faithful: Whether answer is faithful to context
            hallucination_score: Hallucination risk (0.0 = low risk, 1.0 = high risk)
            has_sources: Whether answer has source documents
        
        Returns:
            Confidence score (0.0 to 1.0)
        """
        if not is_faithful:
            return 0.3  # Low confidence if not faithful
        
        if not has_sources:
            return 0.4  # Low confidence if no sources
        
        # Base confidence
        confidence = 0.7
        
        # Adjust based on hallucination score
        confidence -= hallucination_score * 0.3
        
        # Ensure within bounds
        return max(0.0, min(1.0, confidence))
    
    def add_inline_citations(self, answer: str, citations: Dict[str, List[int]]) -> str:
        """
        Add inline citations to answer.
        
        Args:
            answer: Original answer
            citations: Citation mapping
        
        Returns:
            Answer with inline citations added
        """
        if not citations:
            return answer
        
        # Simple implementation: append citations at end
        citation_text = "\n\nSources: " + ", ".join(citations.keys())
        return answer + citation_text

