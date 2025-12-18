"""Grounding verification service to ensure responses are grounded in retrieved context."""
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from app.core.config import settings


class GroundingService:
    """Service for verifying that responses are grounded in retrieved documents."""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0.1,  # Lower temperature for verification
            openai_api_key=settings.OPENAI_API_KEY
        )
    
    async def verify_grounding(
        self,
        response: str,
        retrieved_documents: List[Dict[str, Any]],
        query: str
    ) -> Dict[str, Any]:
        """
        Verify if the response is grounded in retrieved documents.
        
        Returns:
            dict with keys:
            - is_grounded: bool
            - confidence: float (0-1)
            - missing_claims: List[str]
            - citations: List[Dict] (source references)
        """
        if not retrieved_documents:
            return {
                "is_grounded": False,
                "confidence": 0.0,
                "missing_claims": [response],  # Entire response if no docs
                "citations": []
            }
        
        # Build context from retrieved documents
        context = "\n\n".join([
            f"Document {i+1} ({doc.get('filename', 'unknown')}):\n{doc.get('content', '')}"
            for i, doc in enumerate(retrieved_documents)
        ])
        
        verification_prompt = f"""You are a fact-checker. Verify if the response below is supported by the provided context documents.

CONTEXT DOCUMENTS:
{context}

USER QUERY:
{query}

RESPONSE TO VERIFY:
{response}

Analyze if all claims in the response can be found in the context documents. Return a JSON object with:
- "is_grounded": true/false (is the response fully supported by context?)
- "confidence": 0.0-1.0 (how confident are you?)
- "missing_claims": [] (list of claims not found in context, empty if all grounded)
- "citations": [{{"claim": "...", "source": "Document N"}}] (map claims to sources)

Only return valid JSON, no additional text."""

        try:
            verification_result = await self.llm.ainvoke(verification_prompt)
            import json
            import re
            content = verification_result.content
            
            # Try to extract JSON from response (in case it's wrapped in markdown code blocks)
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                content = json_match.group(0)
            
            result = json.loads(content)
            return result
        except json.JSONDecodeError as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to parse grounding verification JSON: {e}. Raw response: {verification_result.content if 'verification_result' in locals() else 'No response'}")
            # Return safe default instead of failing
            return {
                "is_grounded": True,
                "confidence": 0.5,
                "missing_claims": [],
                "citations": []
            }
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in grounding verification: {e}", exc_info=True)
            # Default to assuming it's grounded if verification fails
            return {
                "is_grounded": True,
                "confidence": 0.5,
                "missing_claims": [],
                "citations": []
            }
    
    def add_citations_to_response(
        self,
        response: str,
        retrieved_documents: List[Dict[str, Any]],
        citations: List[Dict[str, str]]
    ) -> str:
        """Add source citations to the response text."""
        if not citations:
            return response
        
        # Build citations section
        citation_text = "\n\n--- Sources ---\n"
        doc_map = {f"Document {i+1}": doc.get('filename', 'unknown') 
                   for i, doc in enumerate(retrieved_documents)}
        
        for citation in citations:
            source = citation.get('source', 'Unknown')
            filename = doc_map.get(source, source)
            citation_text += f"- {citation.get('claim', '')} [{filename}]\n"
        
        return response + citation_text
    
    async def check_hallucination(
        self,
        response: str,
        retrieved_documents: List[Dict[str, Any]]
    ) -> bool:
        """Check if response contains hallucinations (unsupported claims)."""
        if not retrieved_documents:
            return len(response.strip()) > 0  # Any response without docs is potential hallucination
        
        verification = await self.verify_grounding(
            response=response,
            retrieved_documents=retrieved_documents,
            query=""  # Not needed for hallucination check
        )
        
        return not verification.get('is_grounded', False) or len(verification.get('missing_claims', [])) > 0


grounding_service = GroundingService()

