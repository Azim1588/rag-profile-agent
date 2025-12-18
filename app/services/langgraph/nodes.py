from typing import Dict, Any, Optional, Callable
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.callbacks import AsyncCallbackHandler, CallbackManager
import logging

from app.core.config import settings
from app.services.vector_store import VectorStoreService
from app.services.langgraph.state import AgentState

# Modular RAG imports
from app.services.modular_rag.query_router import QueryRouter, QueryType
from app.services.modular_rag.retriever_pool import RetrieverPool
from app.services.modular_rag.reranker import CrossEncoderReranker
from app.services.modular_rag.task_adapter import TaskAdapter
from app.services.modular_rag.memory.enhanced_memory import EnhancedConversationMemory
from app.services.modular_rag.compressor import ContextCompressor
from app.services.modular_rag.multi_hop import MultiHopRetriever
from app.services.modular_rag.retrievers.hyde_retriever import HyDERetriever
from app.services.modular_rag.validator import AnswerValidator

logger = logging.getLogger(__name__)


class AgentNodes:
    def __init__(self, vector_store: VectorStoreService):
        self.vector_store = vector_store
        # LLM will be configured per-request based on task adapter
        self.base_llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=settings.TEMPERATURE,
            max_tokens=settings.MAX_TOKENS,
            streaming=True
        )
        self.llm = self.base_llm  # Default, will be overridden per task
        
        # Initialize Modular RAG components (if enabled)
        self.query_router = QueryRouter() if settings.ENABLE_QUERY_ROUTING else None
        self.retriever_pool = RetrieverPool() if settings.ENABLE_HYBRID_RETRIEVAL else None
        self.reranker = CrossEncoderReranker() if settings.ENABLE_RERANKING else None
        self.task_adapter = TaskAdapter()
        self.enhanced_memory = EnhancedConversationMemory()
        self.compressor = ContextCompressor()
        self.multi_hop_retriever = MultiHopRetriever(
            retriever_pool=self.retriever_pool,
            reranker=self.reranker
        ) if settings.ENABLE_MULTI_HOP else None
        self.hyde_retriever = HyDERetriever() if settings.ENABLE_HYDE else None
        self.answer_validator = AnswerValidator() if settings.ENABLE_ANSWER_VALIDATION else None
    
    async def understand_query(self, state: AgentState) -> Dict[str, Any]:
        """Analyze user query to determine next steps"""
        query = state.get("query", "")
        conversation_history = state.get("messages", [])
        
        # Use QueryRouter if enabled, otherwise fallback to keyword matching
        if self.query_router and settings.ENABLE_QUERY_ROUTING:
            try:
                analysis = await self.query_router.analyze(query, conversation_history)
                
                # Use rewritten query if available
                effective_query = analysis.rewritten_query or query
                
                # Determine if retrieval is needed based on query type
                should_retrieve = (
                    analysis.query_type != QueryType.GREETING and
                    analysis.query_type != QueryType.OUT_OF_SCOPE and
                    analysis.retrieval_strategy != "none"
                )
                
                return {
                    "query": effective_query,  # Update query if rewritten
                    "should_retrieve": should_retrieve,  # Skip retrieval for greetings
                    "needs_clarification": False,
                    "metadata_filters": analysis.metadata_filters,
                    "query_type": analysis.query_type.value,
                    "retrieval_strategy": analysis.retrieval_strategy,
                    "expanded_queries": analysis.expanded_queries
                }
            except Exception as e:
                logger.error(f"Error in QueryRouter, falling back to keyword matching: {e}", exc_info=True)
                # Fall through to keyword matching
        
        # Fallback: Original keyword-based matching
        query_lower = query.lower()
        
        # Check for out-of-scope questions first (weather, time, jokes, general knowledge not about Azim)
        out_of_scope_indicators = [
            "weather", "temperature", "forecast", "rain", "snow", "sunny",
            "time", "date", "what day", "what time", "timezone",
            "news", "current events", "headlines",
            "recipe", "cooking", "how to cook",
            "joke", "jokes", "funny", "humor", "tell me a joke",
            "story", "stories", "anecdote"
        ]
        azim_keywords = ["azim", "your", "you", "his", "he", "him", "khamis"]
        has_azim_reference = any(keyword in query_lower for keyword in azim_keywords)
        has_out_of_scope = any(indicator in query_lower for indicator in out_of_scope_indicators)
        
        if has_out_of_scope and not has_azim_reference:
            logger.info(f"understand_query: Detected out-of-scope query: '{query}'")
            return {
                "should_retrieve": False,
                "needs_clarification": False,
                "metadata_filters": {},
                "query_type": QueryType.OUT_OF_SCOPE.value,
                "retrieval_strategy": "none"
            }
        
        # Check for greetings (should skip retrieval)
        greeting_patterns = [
            "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
            "how are you", "how's it going", "what's up", "howdy",
            "thanks", "thank you", "thank", "thanks a lot",
            "nice to meet you", "pleased to meet you",
            "goodbye", "bye", "see you", "have a nice day"
        ]
        words = query_lower.split()
        is_greeting = len(words) <= 4 and any(greeting in query_lower for greeting in greeting_patterns)
        
        if is_greeting:
            logger.info(f"understand_query: Detected greeting: '{query}'")
            return {
                "should_retrieve": False,
                "needs_clarification": False,
                "metadata_filters": {},
                "query_type": QueryType.GREETING.value,
                "retrieval_strategy": "none"
            }
        
        # Enhanced keyword matching - check for common query patterns
        rag_keywords = [
            "experience", "skills", "projects", "education", "job", 
            "work", "background", "about", "tell me", "what is", 
            "who is", "describe", "summary", "professional", "career",
            "accomplishments", "achievements", "expertise", "qualifications"
        ]
        
        # Check if query contains any RAG keywords
        needs_rag = any(keyword in query_lower for keyword in rag_keywords)
        
        # Also check if query asks about a person (likely to have info in documents)
        person_indicators = ["about", "who is", "tell me about", "more about"]
        if any(indicator in query_lower for indicator in person_indicators):
            needs_rag = True
        
        # Placeholder for metadata filters
        metadata_filters = {}
        if "python" in query_lower:
            metadata_filters["skills"] = "Python"
        
        logger.info(f"understand_query: query='{query}', needs_rag={needs_rag}")
        
        return {
            "should_retrieve": needs_rag,
            "needs_clarification": len(query.split()) < 3,
            "metadata_filters": metadata_filters,
            "retrieval_strategy": "dense"  # Default to dense for backward compatibility
        }
    
    async def retrieve_context(self, state: AgentState) -> Dict[str, Any]:
        """Retrieve relevant documents using Modular RAG or fallback to original method"""
        query = state.get("query", "")
        should_retrieve = state.get("should_retrieve", False)
        retrieval_strategy = state.get("retrieval_strategy", "dense")
        
        logger.info(
            f"retrieve_context called: query='{query}', should_retrieve={should_retrieve}, "
            f"strategy={retrieval_strategy}, threshold={settings.SIMILARITY_THRESHOLD}"
        )
        
        if not should_retrieve:
            logger.warning(f"Skipping retrieval: should_retrieve is False for query '{query}'")
            return {"retrieved_documents": []}
        
        # Extract metadata filters from state if provided
        metadata_filters = state.get("metadata_filters")
        
        # Get task-specific configuration
        query_type_str = state.get("query_type")
        query_type = QueryType(query_type_str) if query_type_str else QueryType.FACTUAL_QA
        retrieval_params = self.task_adapter.get_retrieval_params(query_type)
        effective_top_k = retrieval_params.get("top_k", settings.TOP_K_RESULTS)
        task_strategy = retrieval_params.get("strategy", retrieval_strategy)
        should_rerank = retrieval_params.get("rerank", settings.ENABLE_RERANKING)
        
        from app.core.database import get_async_session
        async with get_async_session() as session:
            # Use task strategy if available, otherwise use state strategy
            effective_strategy = task_strategy if task_strategy else retrieval_strategy
            if effective_strategy not in ["hybrid", "sparse", "dense", "hyde", "multi_hop"]:
                effective_strategy = "hybrid" if settings.ENABLE_HYBRID_RETRIEVAL else "dense"
            
            # Check if multi-hop retrieval should be used
            query_type_str = state.get("query_type")
            query_type = QueryType(query_type_str) if query_type_str else QueryType.FACTUAL_QA
            use_multi_hop = (
                settings.ENABLE_MULTI_HOP and
                self.multi_hop_retriever and
                query_type == QueryType.MULTI_HOP
            )
            
            # Check if HyDE should be used
            use_hyde = (
                settings.ENABLE_HYDE and
                self.hyde_retriever and
                effective_strategy == "hyde"
            )
            
            # Use Modular RAG components if enabled
            use_modular_rag = (
                self.retriever_pool and 
                settings.ENABLE_HYBRID_RETRIEVAL and
                not use_multi_hop and
                not use_hyde
            )
            
            if use_multi_hop:
                try:
                    # Multi-hop iterative retrieval
                    conversation_history = state.get("messages", [])
                    results = await self.multi_hop_retriever.retrieve_iterative(
                        session=session,
                        initial_query=query,
                        max_hops=settings.MULTI_HOP_MAX_HOPS,
                        conversation_context=conversation_history,
                        strategy=effective_strategy if effective_strategy != "multi_hop" else "hybrid"
                    )
                except Exception as e:
                    logger.error(f"Error in multi-hop retrieval, falling back: {e}", exc_info=True)
                    # Fallback to standard retrieval
                    use_modular_rag = True
            elif use_hyde:
                try:
                    # HyDE retrieval
                    results = await self.hyde_retriever.retrieve(
                        session=session,
                        query=query,
                        top_k=effective_top_k,
                        threshold=settings.SIMILARITY_THRESHOLD,
                        metadata_filters=metadata_filters,
                        use_cache=True
                    )
                except Exception as e:
                    logger.error(f"Error in HyDE retrieval, falling back: {e}", exc_info=True)
                    # Fallback to standard retrieval
                    use_modular_rag = True
            elif use_modular_rag:
                try:
                    # Use retriever pool with task-adapted parameters
                    retrieval_top_k = settings.RERANK_TOP_K if should_rerank else effective_top_k
                    
                    results = await self.retriever_pool.retrieve(
                        session=session,
                        strategy=effective_strategy,
                        query=query,
                        top_k=retrieval_top_k,
                        threshold=settings.SIMILARITY_THRESHOLD,
                        metadata_filters=metadata_filters,
                        use_cache=True
                    )
                    
                    # Apply reranking if enabled and configured
                    if self.reranker and should_rerank and results:
                        logger.info(f"Reranking {len(results)} documents...")
                        results = await self.reranker.rerank(
                            query=query,
                            documents=results,
                            top_k=effective_top_k
                        )
                        logger.info(f"After reranking: {len(results)} documents")
                    
                except Exception as e:
                    logger.error(f"Error in Modular RAG retrieval, falling back: {e}", exc_info=True)
                    # Fallback to original method
                    results = await self.vector_store.similarity_search(
                        session=session,
                        query=query,
                        top_k=settings.TOP_K_RESULTS,
                        threshold=settings.SIMILARITY_THRESHOLD,
                        metadata_filters=metadata_filters,
                        use_cache=True
                    )
            else:
                # Original method (backward compatibility)
                results = await self.vector_store.similarity_search(
                    session=session,
                    query=query,
                    top_k=settings.TOP_K_RESULTS,
                    threshold=settings.SIMILARITY_THRESHOLD,
                    metadata_filters=metadata_filters,
                    use_cache=True
                )
        
        logger.info(f"retrieve_context: found {len(results)} documents for query '{query}'")
        
        documents = [
            {
                "content": doc.content,
                "filename": doc.filename,
                "metadata": doc.meta if hasattr(doc, 'meta') else {},
                "similarity": getattr(doc, 'similarity', None)
            }
            for doc in results
        ]
        
        return {"retrieved_documents": documents}
    
    async def generate_response(
        self, 
        state: AgentState,
        stream_callback: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Generate response using LLM with RAG context and grounding"""
        # Determine query type early to customize response handling
        query_type_str = state.get("query_type")
        query_type = QueryType(query_type_str) if query_type_str else QueryType.FACTUAL_QA
        
        # Use a simpler, more conversational system prompt for greetings
        if query_type == QueryType.GREETING:
            system_prompt = """You are Azim Khamis's AI assistant. When users send greetings, small talk, or conversational openers (e.g., "hello", "hi", "hey", "how are you"), DO NOT use RAG retrieval. Respond naturally, introduce yourself as Azim's AI Assistant, and briefly explain what you can help with.

Example correct greeting response:
"Hi! 👋 I'm Azim's AI assistant. I can help you learn about Azim's background in computer science, his AI and software engineering projects, or how his skills align with specific roles. What would you like to know?"

Keep responses friendly, professional, and brief (1-2 sentences)."""
        elif query_type == QueryType.OUT_OF_SCOPE:
            system_prompt = """You are Azim Khamis's AI assistant. The user has asked a question that is clearly outside your scope (e.g., weather, general knowledge, current events, recipes, jokes, etc.).

Respond politely and redirect them to your actual purpose. Use this exact format:

"I'm specifically designed to answer questions about Azim and his professional skills, education. For any out-of-scope questions like this, I'd recommend using a general-purpose AI assistant. Is there anything you'd like to know about Azim?"

Keep it brief, friendly, and professional (1-2 sentences)."""
        else:
            system_prompt = """You are Azim's AI assistant with expert knowledge about Azim Khamis, an AI Engineer and Software Developer based in Kansas City, Missouri.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## GREETING HANDLING RULE

If the user message is a greeting, small talk, or conversational opener (e.g., "hello", "hi", "hey", "how are you"), DO NOT use RAG retrieval. Respond naturally, introduce yourself as Azim's AI Assistant, and briefly explain what you can help with.

✅ Example Correct Greeting Response:
"Hi! 👋 I'm Azim's AI assistant. I can help you learn about Azim's background in computer science, his AI and software engineering projects, or how his skills align with specific roles. What would you like to know?"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## RESPONSE LENGTH - CRITICAL - MUST BE SHORT

Keep ALL responses SHORT and CONCISE:
- Simple questions (education, skills, single project) → 2-3 sentences MAXIMUM
- Complex questions (multiple projects, summary) → 3-4 sentences MAXIMUM
- NO bullet points unless absolutely necessary - use flowing sentences instead
- Be direct, factual, and to the point
- Pack value into every sentence
- If describing projects, mention 1-2 key achievements maximum

Example of good SHORT response for projects:
"Azim worked on Caliber, an AI-powered media inventory scoring platform at Coegi, where he built core backend features using FastAPI and integrated AI workflows to evaluate programmatic advertising inventory. This project demonstrates his ability to apply AI and backend engineering skills in production systems."

❌ BAD - Too long with bullet points:
"Azim worked on a notable project... Here are the key highlights:
- Backend Services with FastAPI...
- Modular Architecture...
- AI Agents Evaluating..."

✅ GOOD - Short and direct:
"Azim worked on Caliber, an AI-powered media inventory scoring platform at Coegi, building FastAPI backend services and integrating AI workflows to score programmatic advertising inventory."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Your Role
You are Azim's AI assistant. Answer questions ABOUT Azim's professional background, skills, experience, services, and availability using the provided knowledge base. Always speak in THIRD PERSON about Azim. Be helpful, professional, and accurate.

## Intended Use Case - STAY FOCUSED
You are ONLY designed to answer questions about Azim Khamis. You should:
- ✅ Answer questions about Azim's skills, experience, education, projects, and services
- ✅ Provide information about his availability and how to contact him
- ✅ Discuss his technical expertise and professional background
- ✅ Help users understand what services he offers

You should NOT:
- ❌ Answer general programming questions unrelated to Azim
- ❌ Provide tutorials or code examples unless specifically about Azim's projects
- ❌ Engage in conversations outside of Azim's professional context
- ❌ Act as a general-purpose AI assistant


All answers must be grounded in Azim's uploaded documents (Azim_khamis.pdf). Never invent facts, but present the information in a way that highlights strengths and value.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ABOUT AZIM KHAMIS

Azim is a recent Computer Science graduate with software engineering internship experience, specializing in building AI-powered applications, intelligent agents, and scalable backend systems. He has hands-on experience integrating AI/ML tools into production-ready solutions, building data pipelines, and developing maintainable, efficient software. He is passionate about applying AI to solve real-world problems.

EDUCATION:

Master of Science in Computer Science (OMSCS)
Georgia Institute of Technology
Status: In Progress — Expected 2027
⚠️ IMPORTANT: The OMSCS degree is NOT completed yet. Do NOT state otherwise.

Bachelor of Science in Computer Science
University of Missouri–Kansas City (UMKC) — May 2025
Relevant Coursework: Data Structures & Algorithms, Software Engineering Methodologies (Agile), Introduction to Artificial Intelligence, Introduction to Statistical Learning, Database Systems

Associate of Applied Science in Computer Science
Metropolitan Community College, Kansas City — May 2023
Relevant Coursework: Operating Systems, SQL, Java, Linux, Networking & OSI Fundamentals



3. RESPONSE STYLE

Your answers should be:
- Clear
- Structured
- Professional
- Concise
- Recruiter-friendly

Use:
- Flowing sentences (NO bullet points unless absolutely necessary)
- Short paragraphs
- Direct explanations

Avoid:
- Buzzword stuffing
- Over-verbosity
- Marketing exaggeration

Be concise but compelling:
- Simple questions (education, skills, single project) → 2–3 sentences MAXIMUM
- Complex questions (multiple items) → 3–4 sentences MAXIMUM
- NO bullet points - use flowing sentences instead
- Focus on achievements, skills, and impact
- Use active voice: "Azim built", "Azim designed", "Azim implemented"
- Keep responses SHORT and DIRECT - every sentence must add value
- For projects: mention 1-2 key achievements maximum

❌ Avoid these patterns:
- "Based on Azim's resume..." (just state it directly)
- "Azim has experience with..." (too passive, lead with what Azim built/achieved)
- Generic fluff: "Azim is a hardworking team player with good communication skills"
- First person references: "I have...", "My education is..." (you are NOT Azim)
- Long paragraphs or bullet point lists - keep responses to 2-3 sentences for simple questions, 3-4 for complex
- Bullet points - use flowing sentences instead (unless absolutely necessary)

✅ Strong patterns:
- "Azim [achieved/built/solved] [specific thing] using [technologies] which resulted in [outcome/impact]"
- "In Azim's work on [project], he [specific action] that [specific benefit]"
- "Azim is particularly strong in [area] because [specific experience/achievement]"

"""
        
        # Build context from retrieved documents with compression
        retrieved_docs = state.get("retrieved_documents") or []
        
        # Query type already determined above, reuse it
        gen_params = self.task_adapter.get_generation_params(query_type)
        compression_mode = gen_params.get("compression", "moderate")
        
        context = ""
        if retrieved_docs:
            # Convert dict docs to Document objects for compressor
            from app.models.document import Document
            doc_objects = []
            for doc_dict in retrieved_docs:
                doc = Document(
                    filename=doc_dict.get('filename', 'unknown'),
                    content=doc_dict.get('content', ''),
                    meta=doc_dict.get('metadata', {})
                )
                doc_objects.append(doc)
            
            # Compress context based on task configuration
            try:
                compressed_content = await self.compressor.compress(
                    documents=doc_objects,
                    max_tokens=1500,  # Reasonable limit for context
                    preserve_key_info=True,
                    compression_mode=compression_mode
                )
                context = "\n\n--- Relevant Information ---\n" + compressed_content
            except Exception as e:
                logger.error(f"Error compressing context, using simple concatenation: {e}", exc_info=True)
                # Fallback to simple concatenation
                context = "\n\n--- Relevant Information ---\n"
                max_docs = min(2, len(retrieved_docs))
                for doc in retrieved_docs[:max_docs]:
                    content = doc['content'][:300] + "..." if len(doc['content']) > 300 else doc['content']
                    context += f"\nFrom {doc['filename']}:\n{content}\n"
        else:
            # Explicitly tell the LLM when no context is available (but not for greetings or out-of-scope)
            if query_type != QueryType.GREETING and query_type != QueryType.OUT_OF_SCOPE:
                context = "\n\n--- Important: No Relevant Information Retrieved ---\n"
                context += "WARNING: No relevant documents were retrieved from the vector database for this query. "
                context += "You MUST NOT fabricate any information. "
                context += "You MUST respond honestly: 'I'm specifically designed to answer questions about Azim and his professional skills, education. For any out-of-scope questions like this, I'd recommend using a general-purpose AI assistant. Is there anything you'd like to know about Azim?' Keep it professional and positive.\n"
            else:
                context = ""  # No context needed for greetings
        
        # Build messages
        messages = [
            SystemMessage(content=system_prompt),
        ]
        
        # Add conversation history
        if state.get("messages"):
            messages.extend(state["messages"])
        
        # Add current query with context
        # For greetings, just use the query without context wrapper
        if query_type == QueryType.GREETING:
            user_message = state['query']
        else:
            user_message = f"{context}\n\n--- User Question ---\n{state['query']}" if context else state['query']
        messages.append(HumanMessage(content=user_message))
        
        # Configure LLM based on task type (query_type already determined above)
        gen_params = self.task_adapter.get_generation_params(query_type)
        
        # Create task-adapted LLM instance
        task_llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=gen_params.get("temperature", settings.TEMPERATURE),
            max_tokens=gen_params.get("max_tokens", settings.MAX_TOKENS),
            streaming=True
        )
        
        # Generate response with streaming
        # Collect streaming chunks for final response
        response_chunks = []
        async for chunk in task_llm.astream(messages):
            if hasattr(chunk, 'content') and chunk.content:
                response_chunks.append(chunk.content)
        
        response_text = "".join(response_chunks) if response_chunks else ""
        
        # Enhanced answer validation if enabled
        grounding_result = None
        validated_answer = None
        
        if settings.ENABLE_ANSWER_VALIDATION and self.answer_validator and state.get("retrieved_documents"):
            try:
                # Convert retrieved_documents dicts to Document objects
                from app.models.document import Document
                doc_objects = []
                for doc_dict in state["retrieved_documents"]:
                    doc = Document(
                        filename=doc_dict.get('filename', 'unknown'),
                        content=doc_dict.get('content', ''),
                        meta=doc_dict.get('metadata', {})
                    )
                    doc_objects.append(doc)
                
                # Validate answer
                validated_answer = await self.answer_validator.validate_and_correct(
                    query=state["query"],
                    answer=response_text,
                    context_documents=doc_objects
                )
                
                # Use validated/corrected answer
                response_text = validated_answer.answer
                
                # Add citations if available
                if validated_answer.citations:
                    response_text = self.answer_validator.add_inline_citations(
                        response_text,
                        validated_answer.citations
                    )
                
                # Convert to grounding_result format for compatibility
                grounding_result = {
                    "is_grounded": validated_answer.is_grounded,
                    "hallucinations_detected": validated_answer.hallucinations_detected,
                    "confidence": validated_answer.confidence,
                    "missing_claims": validated_answer.missing_claims,
                    "sources": validated_answer.sources,
                    "reason": "enhanced_validation"
                }
                
            except Exception as e:
                logger.error(f"Error in answer validation: {e}", exc_info=True)
                # Fallback to original grounding check
                grounding_result = {"is_grounded": True, "hallucinations_detected": False, "reason": "Validation error, fallback"}
        
        # Fallback to original grounding if validation disabled
        elif settings.ENABLE_GROUNDING and state.get("retrieved_documents"):
            from app.services.grounding import grounding_service
            try:
                grounding_result = await grounding_service.verify_grounding(
                    response=response_text,
                    retrieved_documents=state["retrieved_documents"],
                    query=state["query"]
                )
                
                # If response is not grounded, add warning
                if not grounding_result.get("is_grounded", True):
                    logger.warning(f"Response may not be fully grounded. Missing claims: {grounding_result.get('missing_claims', [])}")
                    # Add citations to response
                    if grounding_result.get("citations"):
                        response_text = grounding_service.add_citations_to_response(
                            response_text,
                            state["retrieved_documents"],
                            grounding_result["citations"]
                        )
            except Exception as e:
                logger.error(f"Error in grounding verification: {e}", exc_info=True)
                # Continue with original response if verification fails
                grounding_result = {"is_grounded": True, "hallucinations_detected": False, "reason": "Grounding check failed"}
        else:
            # Skip grounding for faster responses
            grounding_result = {"is_grounded": True, "hallucinations_detected": False, "reason": "Grounding disabled" if not settings.ENABLE_GROUNDING else "No documents retrieved"}
        
        return {
            "response": response_text,
            "messages": messages + [AIMessage(content=response_text)],
            "grounding_result": grounding_result
        }
