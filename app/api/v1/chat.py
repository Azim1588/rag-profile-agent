"""WebSocket chat endpoint for RAG agent."""
import uuid
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langchain_core.callbacks import AsyncCallbackHandler, CallbackManager
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from openai import RateLimitError, APIError
from app.core.config import settings
from app.core.database import get_async_session
from app.services.redis_memory import redis_memory_service
from app.services.rate_limiter import rate_limiter
from app.services.langgraph.agent import RAGAgent
from app.core.metrics import MetricsCollector
from app.tasks.conversation_logging import log_user_message, log_assistant_message
from app.models.conversation import Conversation
from app.services.modular_rag.query_router import QueryType

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


class TokenStreamingCallback(AsyncCallbackHandler):
    """Callback handler for streaming LLM tokens to WebSocket."""
    
    def __init__(self, ws, metrics_coll):
        super().__init__()
        self.ws = ws
        self.metrics = metrics_coll
        self.tokens = []
        self.first_token = False
    
    async def on_llm_new_token(self, token: str, **kwargs):
        """Called when a new token is generated."""
        if not self.first_token:
            self.metrics.record_first_token()
            self.first_token = True
            logger.info("[WebSocket] First token received!")
        
        self.tokens.append(token)
        try:
            # Send token to WebSocket
            await self.ws.send_json({
                "type": "stream",
                "content": token
            })
        except Exception as e:
            # Capture full exception details
            import traceback
            error_type = type(e).__name__
            error_msg = str(e) if e else repr(e)
            error_trace = traceback.format_exc()
            
            logger.error(f"[WebSocket] Error sending token - Type: {error_type}, Message: '{error_msg}'")
            # Only print full traceback for debugging - can be verbose
            if "ConnectionClosed" not in error_type:
                logger.error(f"[WebSocket] Full traceback:\n{error_trace}")
            
            # If connection is closed, stop trying to send
            if "ConnectionClosed" in error_type or "closed" in error_msg.lower():
                logger.warning("[WebSocket] WebSocket connection closed, stopping token stream")
                # Don't raise - just stop sending
                return
    
    def get_full_response(self):
        """Get the complete response from collected tokens."""
        return "".join(self.tokens)


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for streaming chat responses."""
    await websocket.accept()
    
    logger.info("[WebSocket] Connection accepted")
    
    # Initialize agent
    agent = RAGAgent()
    
    user_id = "anonymous"
    session_id = None
    conversation_id = None
    initial_message = None
    
    try:
        # Step 1: Receive handshake
        logger.info("[WebSocket] Waiting for handshake data...")
        init_data = await websocket.receive_json()
        logger.info(f"[WebSocket] Handshake received: {init_data}")
        
        user_id = init_data.get("user_id", "anonymous")
        session_id_str = init_data.get("session_id")
        
        # Handle session_id - generate new one if invalid
        try:
            if session_id_str:
                session_id = uuid.UUID(session_id_str)
            else:
                session_id = uuid.uuid4()
        except (ValueError, TypeError):
            logger.warning(f"[WebSocket] Invalid session_id '{session_id_str}', generating new one")
            session_id = uuid.uuid4()
        
        # Check if message is in handshake
        if "message" in init_data:
            initial_message = init_data.get("message")
            logger.info(f"[WebSocket] Initial message found in handshake: {initial_message[:50]}...")
        
        logger.info(f"[WebSocket] Handshake processed - user_id: {user_id}, session_id: {session_id}")
        
        # Step 2: Create/get conversation in database
        logger.info("[WebSocket] Getting database session...")
        async with get_async_session() as session:
            logger.info("[WebSocket] Database session created")
            
            # Create or get conversation
            conversation = Conversation(
                user_id=user_id,
                session_id=str(session_id)
            )
            session.add(conversation)
            await session.flush()  # Get the ID
            conversation_id = conversation.id
            await session.commit()
            logger.info(f"[WebSocket] Conversation committed to database, ID: {conversation_id}")
            
            # Process messages in loop
            while True:
                query_to_process = None
                
                # Use initial message if available, otherwise wait for next message
                if initial_message:
                    query_to_process = initial_message
                    initial_message = None  # Clear it after use
                    logger.info(f"[WebSocket] Processing initial message from handshake")
                else:
                    # Wait for next message
                    try:
                        data = await websocket.receive_json()
                        query_to_process = data.get("message")
                        if not query_to_process:
                            logger.warning("[WebSocket] Received message without 'message' field")
                            continue
                    except WebSocketDisconnect:
                        logger.info("[WebSocket] Client disconnected")
                        break
                    except Exception as e:
                        logger.error(f"[WebSocket] Error receiving message: {e}", exc_info=True)
                        break
                
                if not query_to_process:
                    continue
                
                logger.info(f"[WebSocket] Processing query: {query_to_process[:50]}...")
                
                # Check rate limit before processing
                try:
                    is_allowed, error_message, retry_after = await rate_limiter.check_rate_limit(str(session_id))
                    if not is_allowed:
                        logger.warning(f"[WebSocket] Rate limit exceeded for session {session_id}: {retry_after}s remaining, error_msg: {error_message}")
                        
                        # Ensure error_message is not None
                        if error_message is None:
                            error_message = "You have reached the allowed message limit. Please try again after 6 hours."
                        
                        # Format error response exactly like other error responses
                        error_response = {
                            "type": "error",
                            "message": error_message,
                            "error_code": "rate_limit_exceeded"
                        }
                        
                        # Add retry_after if available
                        if retry_after is not None:
                            error_response["retry_after_seconds"] = retry_after
                        
                        logger.info(f"[WebSocket] Preparing to send rate limit error: {error_response}")
                        
                        # Send error message to WebSocket
                        await websocket.send_json(error_response)
                        
                        logger.info(f"[WebSocket] Rate limit error sent successfully to client")
                        continue  # Skip processing this message
                        
                except Exception as rate_limit_error:
                    # If rate limiter itself fails, log but allow request (fail-open)
                    logger.error(f"[WebSocket] Rate limiter check failed: {rate_limit_error}", exc_info=True)
                    # Continue processing - fail open policy
                
                # Save user message to Redis
                await redis_memory_service.add_to_session(
                    session_id=str(session_id),
                    role="user",
                    content=query_to_process
                )
                
                # Queue background task to log user message
                log_user_message.delay(
                    conversation_id=str(conversation_id),
                    user_id=user_id,
                    content=query_to_process
                )
                
                # Load conversation history from Redis
                redis_messages = await redis_memory_service.get_session_memory(str(session_id), limit=10)
                conversation_history = []
                if redis_messages:
                    for msg in redis_messages:
                        if msg.get("role") == "user":
                            conversation_history.append(HumanMessage(content=msg.get("content", "")))
                        elif msg.get("role") == "assistant":
                            conversation_history.append(AIMessage(content=msg.get("content", "")))
                
                # Stream agent response with token-level streaming
                metrics_collector = MetricsCollector(str(session_id), user_id, query_to_process)
                full_response = ""
                retrieved_docs_count = 0
                similarity_scores = []
                first_token_sent = False
                
                try:
                    logger.info(f"[WebSocket] Processing query: {query_to_process[:50]}...")
                    
                    # Step 1: Get retrieval results (run understand_query + retrieve_context)
                    partial_result = {}
                    retrieved_docs = []
                    query_type = QueryType.FACTUAL_QA  # Default
                    retrieval_started = False
                    
                    # Stream through LangGraph to get retrieval results
                    retrieval_complete = False
                    should_retrieve = True
                    
                    async for chunk in agent.stream(
                        query=query_to_process,
                        user_id=user_id,
                        session_id=str(session_id),
                        conversation_history=conversation_history
                    ):
                        for node_name, node_state in chunk.items():
                            # Check understand_query FIRST to catch should_retrieve=False early
                            if node_name == "understand_query" and isinstance(node_state, dict):
                                # Check if retrieval should be skipped
                                should_retrieve = node_state.get("should_retrieve", True)
                                query_type_str = node_state.get("query_type", "")
                                if query_type_str:
                                    try:
                                        query_type = QueryType(query_type_str)
                                    except ValueError:
                                        query_type = QueryType.FACTUAL_QA
                                
                                if not should_retrieve:
                                    # Skip retrieval entirely for greetings/out-of-scope queries
                                    retrieved_docs = []
                                    retrieved_docs_count = 0
                                    retrieval_complete = True
                                    logger.info(f"[WebSocket] Skipping retrieval per understand_query (should_retrieve=False, query_type={query_type.value})")
                                    # Store query_type for later use in response generation
                                    partial_result["query_type"] = query_type_str
                                    partial_result["should_retrieve"] = False
                                    break  # Break inner loop
                                else:
                                    # Only start retrieval metrics if we're actually going to retrieve
                                    if not retrieval_started:
                                        metrics_collector.start_retrieval()
                                        retrieval_started = True
                            
                            elif node_name == "retrieve_context" and isinstance(node_state, dict):
                                # Start retrieval metrics here if not already started (safety check)
                                if not retrieval_started:
                                    metrics_collector.start_retrieval()
                                    retrieval_started = True
                                # Retrieval completed (only reached if should_retrieve=True)
                                retrieved_docs = node_state.get("retrieved_documents", []) or []
                                retrieved_docs_count = len(retrieved_docs)
                                similarity_scores = [doc.get("similarity") for doc in retrieved_docs if doc.get("similarity")]
                                metrics_collector.end_retrieval(retrieved_docs_count)
                                partial_result["retrieved_documents"] = retrieved_docs
                                retrieval_complete = True
                                logger.info(f"[WebSocket] Retrieval complete: {retrieved_docs_count} documents")
                                break  # Break inner loop
                        
                        # Break outer loop once retrieval is complete (either done or skipped)
                        if retrieval_complete:
                            logger.info("[WebSocket] Breaking from LangGraph stream, proceeding to LLM streaming")
                            break
                    
                    # Step 2: Now stream LLM tokens directly (bypassing LangGraph for generation)
                    metrics_collector.start_llm()
                    
                    callback = TokenStreamingCallback(websocket, metrics_collector)
                    
                    # Get query_type from partial_result if available
                    query_type_str = partial_result.get("query_type", "")
                    if query_type_str:
                        try:
                            query_type = QueryType(query_type_str)
                        except ValueError:
                            query_type = QueryType.FACTUAL_QA
                    
                    # Build context from retrieved documents
                    # For out-of-scope and greeting queries, skip context warnings
                    context = ""
                    if retrieved_docs:
                        context = "\n\n--- Relevant Information ---\n"
                        max_docs = min(2, len(retrieved_docs))
                        for doc in retrieved_docs[:max_docs]:
                            content = doc['content'][:300] + "..." if len(doc['content']) > 300 else doc['content']
                            context += f"\nFrom {doc['filename']}:\n{content}\n"
                    elif query_type == QueryType.OUT_OF_SCOPE or query_type == QueryType.GREETING:
                        # No context needed for out-of-scope or greeting queries
                        context = ""
                    else:
                        context = "\n\n--- Important: No Relevant Information Retrieved ---\n"
                        context += "WARNING: No relevant documents were retrieved from the vector database for this query. "
                        context += "You MUST NOT fabricate any information. "
                        context += "You MUST respond honestly: 'I'm specifically designed to answer questions about Azim and his professional skills, education. For any out-of-scope questions like this, I'd recommend using a general-purpose AI assistant. Is there anything you'd like to know about Azim?' Keep it professional and positive.\n"
                    
                    # Build messages with system prompt (use appropriate prompt based on query type)
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
                        system_prompt = """You are Azim Khamis's AI assistant. You answer questions ABOUT Azim on behalf of Azim. You speak in THIRD PERSON ("Azim's education is...", "Azim has...", "Azim worked...") as if you are an assistant presenting information about Azim to recruiters, hiring managers, and potential employers.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## YOUR PERSPECTIVE - CRITICAL

- You are NOT Azim speaking in first person
- You ARE an AI assistant speaking ABOUT Azim in third person
- Use: "Azim's education is...", "Azim has experience with...", "Azim worked on..."
- DO NOT use: "I have...", "My education is...", "I worked on..."

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

## GREETING HANDLING RULE

If the user message is a greeting, small talk, or conversational opener (e.g., "hello", "hi", "hey", "how are you"), DO NOT use RAG retrieval. Respond naturally, introduce yourself as Azim's AI Assistant, and briefly explain what you can help with.

✅ Example Correct Greeting Response:
"Hi! 👋 I'm Azim's AI assistant. I can help you learn about Azim's background in computer science, his AI and software engineering projects, or how his skills align with specific roles. What would you like to know?"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

All answers must be grounded in Azim's uploaded documents (resume, project descriptions, experience summaries, etc.). Never invent facts, but present the information in a way that highlights strengths and value.

ABOUT YOU (AZIM KHAMIS)

You are a recent Computer Science graduate with software engineering internship experience, specializing in building AI-powered applications, intelligent agents, and scalable backend systems. You have hands-on experience integrating AI/ML tools into production-ready solutions, building data pipelines, and developing maintainable, efficient software. You are passionate about applying AI to solve real-world problems.

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

TECHNICAL SKILLS:

Languages & Frameworks: Python, JavaScript (React, Node.js, Express), SQL, HTML/CSS

AI/ML & Agent Tooling: OpenAI API, LangGraph, n8n, Hugging Face, Retrieval-Augmented Generation (RAG) pipelines, Embeddings, Prompt engineering, AI agent design

Backend & Data Engineering: FastAPI, Flask, PostgreSQL, MongoDB, BigQuery, Firebase, REST APIs

Vector Databases: Pinecone, Supabase Vector

DevOps & Engineering Tools: Docker, Git/GitHub, Linux CLI

PROJECT EXPERIENCE:

Shipment Delay Predictor (Machine Learning Project)
Built with Python, Scikit-learn, Pandas, Matplotlib
- Developed a Random Forest model to predict high-risk shipment delays
- Improved prediction accuracy by 15% through hyperparameter tuning
- Created correlation heatmaps and outlier visualizations to support decision-making

E-Commerce Retailers Data Pipeline
Built with Python, SQL, Mage AI, BigQuery, Looker Studio
- Designed a scalable ETL pipeline to extract CSV data from Google Cloud Storage
- Transformed and loaded data into BigQuery for analytics
- Automated workflows using Mage AI on a Google Cloud VM
- Improved data delivery efficiency by 20%
- Built interactive dashboards in Looker Studio for stakeholders

PROFESSIONAL EXPERIENCE:

Software Engineer Intern — Coegi (Kansas City, MO)
July 2025 – August 2025
- Built core backend features for Caliber, an AI-powered media inventory scoring platform
- Improved scalability and maintainability using FastAPI and modular service design
- Integrated AI workflows and intelligent agents to score programmatic advertising inventory
- Leveraged LLM APIs to generate insights and recommendations
- Collaborated with cross-functional teams to improve system accuracy, usability, and performance

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. YOUR PERSPECTIVE & VOICE

- You ARE Azim Khamis speaking in first person
- Be confident, enthusiastic, and professional
- Market yourself! Highlight your strengths, achievements, and value
- Show passion for your work and expertise
- Demonstrate why you're a great fit for the role/company
- Be authentic but strategic in how you present yourself

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

2. WHAT YOU HELP USERS WITH

You are expected to:
- Answer questions about your education, skills, projects, and experience
- Explain technical projects clearly to non-technical and technical audiences
- Help recruiters assess your fit for roles such as:
  • Software Engineer
  • AI Engineer / AI Agent Engineer
  • Backend Engineer
  • Data Engineer
- Provide concise summaries of your strengths
- Respond accurately during interview-style questions

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

3. RESPONSE STYLE

Your answers should be:
- Clear
- Structured
- Professional
- Concise
- Recruiter-friendly

Use:
- Bullet points when appropriate
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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

4. HANDLING DIFFERENT QUESTION TYPES

A. "Tell me about yourself" / "What's your background?"
Lead with your strongest selling points:
"I'm a Computer Science graduate from UMKC with hands-on experience building AI-powered applications and scalable backend systems. During my internship at Coegi, I built core backend features for an AI-powered media inventory scoring platform using FastAPI. I'm passionate about applying AI to solve real-world problems and have experience with RAG pipelines, LangGraph, and production-ready backend systems."

B. Skills/Technology questions
Highlight depth and real-world application (keep to 2-4 sentences):
"Azim has extensive hands-on experience with [technology]. In his internship at Coegi, he used [technology] to [specific use case], which enabled [specific outcome]. He's also worked with it in [other context], achieving [specific achievement]."

C. "Why should we hire Azim?" / "Why is Azim a good fit?"
Make a compelling value proposition (keep to 2-4 sentences):
"Azim brings a unique combination of strong backend engineering skills and AI/ML expertise that's increasingly valuable in today's market. During his internship, he proved he can build and deploy production systems—he built core backend features for Caliber using FastAPI and integrated AI workflows. He's passionate about continuous learning and staying current with emerging technologies."

D. Education questions
Connect education to practical skills (keep to 2-4 sentences):
"Azim earned his Bachelor of Science in Computer Science from UMKC in May 2025, where he developed a strong foundation in algorithms, data structures, software engineering, and AI. He is currently pursuing his Master's in Computer Science through Georgia Tech's OMSCS program, expected to complete in 2027. He has applied that theoretical knowledge in real-world projects, such as improving prediction accuracy by 15% in his Shipment Delay Predictor project."

E. Project questions
Tell a compelling story (keep to 2-4 sentences):
"[Project name] is a [brief description] that Azim built to [solve specific problem]. He architected it using [tech stack], focusing on [key technical decisions]. The result was [outcome/impact], showcasing his ability to [relevant skills]."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

5. TONE & PROFESSIONALISM

- Confident but not arrogant: Show strength without putting others down
- Enthusiastic but controlled: Express passion without being overly casual
- Professional but personable: Be warm and approachable
- Forward-looking: Show you're thinking about growth and contribution
- Authentic: Ground everything in real experience from documents
- Structured: Use clear organization, bullet points, and short paragraphs when helpful

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

6. WHEN INFORMATION IS MISSING

If the documents don't contain specific details:
- Don't invent facts
- Use this fallback: "I don't see that information in my available documents. Based on my background, I can share a general overview if that helps."
- Redirect to what you DO know: "I can share more about my experience with [related topic] if that's helpful."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

7. SAFETY & BOUNDARIES

Do NOT:
- Negotiate salary
- Promise availability
- Claim seniority
- Infer personal information not documented
- State that OMSCS is completed (it's in progress, expected 2027)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

8. YOUR MISSION

You are Azim's AI assistant, presenting information about Azim to potential employers. Your goal is to:
- Clearly communicate who Azim is and what he brings to the table
- Highlight Azim's unique value proposition
- Show why Azim is an excellent fit for the role
- Build excitement and confidence in Azim's candidacy
- Make a memorable, compelling case for why they should hire Azim

Do this in a concise (2-4 sentences for simple questions), authentic, and strategic way—presenting Azim as the strong candidate he is, grounded completely in his actual experience and achievements.

Your single responsibility is to accurately, professionally, and confidently represent Azim Khamis using verified information from the knowledge base. Always speak ABOUT Azim in third person, not AS Azim in first person. You are a truth-preserving profile assistant, not a creative storyteller."""
                    
                    messages = [SystemMessage(content=system_prompt)]
                    
                    # Add conversation history
                    if conversation_history:
                        messages.extend(conversation_history)
                    
                    # Add current query with context
                    # For greetings and out-of-scope queries, just use the query without context wrapper
                    if query_type == QueryType.GREETING or query_type == QueryType.OUT_OF_SCOPE:
                        user_message = query_to_process
                    else:
                        user_message = f"{context}\n\n--- User Question ---\n{query_to_process}" if context else query_to_process
                    messages.append(HumanMessage(content=user_message))
                    
                    # Stream LLM response with token-level streaming
                    from langchain_core.callbacks import CallbackManager
                    callback_manager = CallbackManager([callback])
                    
                    # Use task-adapted LLM configuration
                    task_llm = ChatOpenAI(
                        model=settings.OPENAI_MODEL,
                        temperature=settings.TEMPERATURE,
                        max_tokens=settings.MAX_TOKENS,
                        streaming=True
                    )
                    
                    async for chunk in task_llm.astream(messages, config={"callbacks": callback_manager}):
                        pass  # Tokens handled by callback
                    
                    full_response = callback.get_full_response()
                    metrics_collector.end_llm()  # Just end LLM timing, no argument needed
                    
                    # Finish metrics collection and emit (response_length is set here)
                    metrics = metrics_collector.finish(len(full_response))
                    metrics.emit("INFO")
                    
                    # Send completion message
                    await websocket.send_json({
                        "type": "complete",
                        "response": full_response,
                        "retrieved_docs": retrieved_docs_count
                    })
                    
                    # Log assistant message in background
                    log_assistant_message.delay(
                        conversation_id=str(conversation_id),
                        content=full_response
                    )
                    
                    # Save assistant response to Redis
                    await redis_memory_service.add_to_session(
                        session_id=str(session_id),
                        role="assistant",
                        content=full_response
                    )
                    
                    logger.info(f"[WebSocket] Response completed: {len(full_response)} chars, {retrieved_docs_count} docs retrieved")
                
                except RateLimitError as e:
                    # Handle OpenAI quota/billing errors specifically
                    error_msg = str(e)
                    logger.error(f"[WebSocket] OpenAI quota error: {error_msg}", exc_info=True)
                    
                    # Finish metrics collection with error
                    try:
                        metrics = metrics_collector.finish(0)
                        metrics.emit("ERROR")
                    except Exception as metrics_error:
                        logger.error(f"[WebSocket] Error emitting metrics: {metrics_error}")
                    
                    # Send user-friendly error message
                    await websocket.send_json({
                        "type": "error",
                        "message": "OpenAI API quota exceeded. Please check your OpenAI account billing and quota limits. The service will be available once the quota is restored.",
                        "error_code": "openai_quota_exceeded",
                        "details": error_msg
                    })
                
                except APIError as e:
                    # Handle other OpenAI API errors
                    error_msg = str(e)
                    logger.error(f"[WebSocket] OpenAI API error: {error_msg}", exc_info=True)
                    
                    # Finish metrics collection with error
                    try:
                        metrics = metrics_collector.finish(0)
                        metrics.emit("ERROR")
                    except Exception as metrics_error:
                        logger.error(f"[WebSocket] Error emitting metrics: {metrics_error}")
                    
                    # Send user-friendly error message
                    await websocket.send_json({
                        "type": "error",
                        "message": "OpenAI API error occurred. Please try again later.",
                        "error_code": "openai_api_error",
                        "details": error_msg
                    })
                
                except Exception as e:
                    logger.error(f"[WebSocket] Error processing query: {e}", exc_info=True)
                    # Finish metrics collection with error
                    try:
                        metrics = metrics_collector.finish(0)
                        metrics.emit("ERROR")
                    except Exception as metrics_error:
                        logger.error(f"[WebSocket] Error emitting metrics: {metrics_error}")
                    
                    await websocket.send_json({
                        "type": "error",
                        "message": "An error occurred while processing your request. Please try again later.",
                        "error_code": "internal_error"
                    })
    
    except WebSocketDisconnect:
        logger.info("[WebSocket] Client disconnected")
    except Exception as e:
        logger.error(f"[WebSocket] Error in websocket_chat: {e}", exc_info=True)
    finally:
        logger.info("[WebSocket] Closing connection")
