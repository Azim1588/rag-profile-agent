# Current Request-to-Response Workflow

## 🔄 Complete Flow Overview

This document describes the **exact workflow** when a user sends a request through the WebSocket endpoint and receives a response.

---

## 📊 Flow Diagram

```
User sends WebSocket message
    ↓
1. WebSocket Connection & Handshake
    ├── Accept connection
    ├── Receive handshake: {user_id, session_id, message?}
    └── Create/get conversation in PostgreSQL
    ↓
2. Message Reception Loop
    ├── Receive message: {"message": "Tell me about Azim"}
    └── Extract query from message
    ↓
3. Save User Message to Redis (Session Memory)
    └── Fast, non-blocking storage for conversation context
    ↓
4. Queue Background Task (Celery)
    └── log_user_message.delay() → PostgreSQL logging (non-blocking)
    ↓
5. Load Conversation History
    ├── Get last 10 messages from Redis
    └── Convert to LangChain message format
    ↓
6. Initialize Metrics Collector
    └── Track performance metrics (retrieval time, LLM time, TTFB)
    ↓
7. LangGraph Agent Processing
    │
    ├── 7a. understand_query Node
    │   ├── QueryRouter Analysis (if enabled)
    │   │   ├── Classify query type (GREETING, OUT_OF_SCOPE, FACTUAL_QA, etc.)
    │   │   ├── Determine retrieval strategy (hybrid, dense, sparse, multi_hop, hyde, none)
    │   │   ├── Extract metadata filters
    │   │   └── Optional: Query rewriting/expansion
    │   │
    │   └── Fallback: Keyword-based detection
    │       ├── Check for greetings (skip retrieval)
    │       ├── Check for out-of-scope (weather, jokes, etc.)
    │       └── Check for RAG keywords
    │
    │   Returns:
    │   - should_retrieve: True/False
    │   - query_type: GREETING | OUT_OF_SCOPE | FACTUAL_QA | etc.
    │   - retrieval_strategy: "none" | "hybrid" | "dense" | etc.
    │
    ├── 7b. Conditional Routing
    │   ├── If should_retrieve = False → Skip to generate_response
    │   └── If should_retrieve = True → Go to retrieve_context
    │
    └── 7c. retrieve_context Node (if should_retrieve = True)
        ├── Get retrieval strategy from state
        ├── RetrieverPool execution:
        │   ├── Hybrid Strategy:
        │   │   ├── Dense Retrieval (pgvector) ~200-500ms
        │   │   ├── Sparse Retrieval (PostgreSQL FTS) ~100-200ms
        │   │   └── RRF Fusion (combine results) ~10ms
        │   │
        │   ├── Multi-Hop Strategy:
        │   │   ├── Iterative retrieval with query refinement
        │   │   └── Combine results from multiple hops
        │   │
        │   ├── HyDE Strategy:
        │   │   ├── Generate hypothetical document
        │   │   └── Retrieve using hypothetical doc
        │   │
        │   └── Dense/Sparse (single strategy)
        │
        ├── Reranking (if enabled)
        │   └── Cross-Encoder reranking ~100-200ms
        │
        └── Returns: retrieved_documents[]
    ↓
8. Extract Results from LangGraph Stream
    ├── Capture query_type from understand_query node
    ├── Capture retrieved_documents from retrieve_context node
    └── Stop streaming after retrieval (don't execute generate_response in LangGraph)
    ↓
9. Build Context for LLM
    ├── If retrieved_docs exists:
    │   └── Format top 2 documents as context
    │
    ├── If query_type = GREETING or OUT_OF_SCOPE:
    │   └── context = "" (empty, no context warnings)
    │
    └── If no docs retrieved (in-scope query):
        └── Add warning context about no information
    ↓
10. Select System Prompt (Based on query_type)
    ├── GREETING → Greeting-specific prompt
    ├── OUT_OF_SCOPE → Out-of-scope redirect prompt
    └── Default → Main RAG system prompt (third-person, concise)
    ↓
11. Direct LLM Streaming (Bypasses LangGraph generate_response)
    ├── Start LLM metrics
    ├── Create TokenStreamingCallback
    ├── Build messages:
    │   ├── SystemMessage (selected prompt)
    │   ├── Conversation history (from Redis)
    │   └── HumanMessage (context + query)
    │
    ├── Call LLM with streaming:
    │   └── ChatOpenAI.astream() with callback
    │
    └── Stream tokens to WebSocket (real-time)
        ├── TokenStreamingCallback.on_llm_new_token()
        ├── Send each token: {"type": "stream", "content": token}
        └── Track first token time (TTFB)
    ↓
12. Response Completion
    ├── End LLM metrics
    ├── Collect full response text
    ├── Send completion signal: {"type": "complete"}
    └── Send metrics: {"type": "metrics", "data": {...}}
    ↓
13. Background Tasks (Non-blocking)
    ├── log_assistant_message.delay() → PostgreSQL logging
    └── Save assistant response to Redis session memory
    ↓
14. Wait for Next Message (Loop continues)
```

---

## 📝 Detailed Step-by-Step

### **Step 1: WebSocket Connection & Handshake**

**Location:** `app/api/v1/chat.py` → `websocket_chat()`

**What happens:**
1. WebSocket connection accepted: `await websocket.accept()`
2. Wait for handshake: `init_data = await websocket.receive_json()`
3. Extract `user_id` and `session_id` (or generate new session_id)
4. Create or get conversation in PostgreSQL database
5. Extract `message` from handshake if present, otherwise wait for first message

**Code:**
```python
await websocket.accept()
init_data = await websocket.receive_json()
user_id = init_data.get("user_id", "anonymous")
session_id = uuid.UUID(init_data.get("session_id")) if init_data.get("session_id") else uuid.uuid4()
```

---

### **Step 2: Message Reception Loop**

**Location:** `app/api/v1/chat.py` (line ~128-152)

**What happens:**
- Loop continuously waiting for messages
- Receive JSON: `{"message": "Tell me about Azim"}`
- Extract `query_to_process` from message

---

### **Step 3: Save User Message to Redis**

**Location:** `app/api/v1/chat.py` (line ~157-161)

**What happens:**
- Save message to Redis session memory for conversation context
- Fast, non-blocking operation (~5ms)

**Code:**
```python
await redis_memory_service.add_to_session(
    session_id=str(session_id),
    role="user",
    content=query_to_process
)
```

---

### **Step 4: Queue Background Task**

**Location:** `app/api/v1/chat.py` (line ~164-168)

**What happens:**
- Queue Celery task to log user message to PostgreSQL
- Non-blocking (doesn't wait for completion)
- Task runs in background worker

**Code:**
```python
log_user_message.delay(
    conversation_id=str(conversation_id),
    user_id=user_id,
    content=query_to_process
)
```

---

### **Step 5: Load Conversation History**

**Location:** `app/api/v1/chat.py` (line ~171-178)

**What happens:**
- Get last 10 messages from Redis
- Convert to LangChain message format (HumanMessage, AIMessage)
- Used as context for query understanding and LLM generation

**Code:**
```python
redis_messages = await redis_memory_service.get_session_memory(str(session_id), limit=10)
conversation_history = []
for msg in redis_messages:
    if msg.get("role") == "user":
        conversation_history.append(HumanMessage(content=msg.get("content", "")))
    elif msg.get("role") == "assistant":
        conversation_history.append(AIMessage(content=msg.get("content", "")))
```

---

### **Step 6: Initialize Metrics Collector**

**Location:** `app/api/v1/chat.py` (line ~181)

**What happens:**
- Create MetricsCollector instance
- Track: retrieval time, LLM time, time-to-first-token (TTFB)

**Code:**
```python
metrics_collector = MetricsCollector(str(session_id), user_id, query_to_process)
```

---

### **Step 7: LangGraph Agent Processing**

**Location:** `app/services/langgraph/agent.py` → `stream()`

**What happens:**
- Stream through LangGraph nodes
- Capture intermediate results from each node

#### **7a. understand_query Node**

**Location:** `app/services/langgraph/nodes.py` → `understand_query()`

**What happens:**
1. **If QueryRouter enabled:**
   - Analyze query using QueryRouter
   - Classify query type (GREETING, OUT_OF_SCOPE, FACTUAL_QA, etc.)
   - Determine retrieval strategy
   - Extract metadata filters
   - Optionally rewrite/expand query

2. **Fallback (keyword matching):**
   - Check for greetings (patterns: "hello", "hi", "hey", etc.)
   - Check for out-of-scope (weather, jokes, recipes, etc.)
   - Check for RAG keywords (experience, skills, projects, etc.)

**Returns:**
```python
{
    "should_retrieve": False,  # For greetings/out-of-scope
    "query_type": "greeting" | "out_of_scope" | "factual_qa",
    "retrieval_strategy": "none" | "hybrid" | "dense" | etc.,
    "metadata_filters": {},
    "query": "rewritten_query" (if rewritten)
}
```

#### **7b. Conditional Routing**

**Location:** `app/services/langgraph/agent.py` → `_build_graph()`

**Flow:**
- If `should_retrieve = False` → Skip to `generate_response` (or bypass entirely)
- If `should_retrieve = True` → Go to `retrieve_context`

#### **7c. retrieve_context Node (if should_retrieve = True)**

**Location:** `app/services/langgraph/nodes.py` → `retrieve_context()`

**What happens:**
1. Get retrieval strategy from state
2. Execute retrieval using RetrieverPool:
   - **Hybrid:** Dense + Sparse + RRF Fusion
   - **Multi-Hop:** Iterative retrieval with query refinement
   - **HyDE:** Generate hypothetical document, then retrieve
   - **Dense/Sparse:** Single strategy retrieval

3. **Reranking (if enabled):**
   - Cross-Encoder reranking on top results
   - Return top-k documents

**Returns:**
```python
{
    "retrieved_documents": [
        {
            "content": "...",
            "filename": "Azim_Khamis.pdf",
            "similarity": 0.85,
            "metadata": {...}
        },
        ...
    ]
}
```

**Timing:**
- Dense retrieval: ~200-500ms
- Sparse retrieval: ~100-200ms
- Reranking: ~100-200ms
- **Total: ~400-900ms**

---

### **Step 8: Extract Results from LangGraph Stream**

**Location:** `app/api/v1/chat.py` (line ~200-252)

**What happens:**
- Stream through LangGraph nodes
- Capture `query_type` from `understand_query` node
- Capture `retrieved_documents` from `retrieve_context` node
- **Stop streaming after retrieval** (don't execute `generate_response` in LangGraph)
- Break loop and proceed to direct LLM streaming

**Code:**
```python
async for chunk in agent.stream(...):
    for node_name, node_state in chunk.items():
        if node_name == "understand_query":
            query_type = node_state.get("query_type")
            should_retrieve = node_state.get("should_retrieve")
            
            if not should_retrieve:
                # Skip retrieval
                break
                
        elif node_name == "retrieve_context":
            retrieved_docs = node_state.get("retrieved_documents", [])
            retrieval_complete = True
            break
    
    if retrieval_complete:
        break  # Stop LangGraph stream
```

---

### **Step 9: Build Context for LLM**

**Location:** `app/api/v1/chat.py` (line ~267-283)

**What happens:**
- Format retrieved documents as context string
- Handle special cases (greetings, out-of-scope)
- Add warnings if no documents retrieved

**Code:**
```python
if retrieved_docs:
    context = "\n\n--- Relevant Information ---\n"
    for doc in retrieved_docs[:2]:  # Top 2 docs
        context += f"\nFrom {doc['filename']}:\n{doc['content'][:300]}...\n"
elif query_type == QueryType.OUT_OF_SCOPE or query_type == QueryType.GREETING:
    context = ""  # No context needed
else:
    context = "\n\n--- Important: No Relevant Information Retrieved ---\n"
    context += "WARNING: No relevant documents..."
```

---

### **Step 10: Select System Prompt**

**Location:** `app/api/v1/chat.py` (line ~286-301)

**What happens:**
- Select appropriate system prompt based on `query_type`
- **GREETING:** Greeting-specific prompt (friendly, introduces assistant)
- **OUT_OF_SCOPE:** Out-of-scope redirect prompt (polite redirection)
- **Default:** Main RAG prompt (third-person, concise, persona-aligned)

**Key Features of Main Prompt:**
- Third-person perspective ("Azim's education is...")
- Response length limits (2-3 sentences for simple, 3-4 for complex)
- No bullet points (flowing sentences)
- Professional, recruiter-friendly tone

---

### **Step 11: Direct LLM Streaming**

**Location:** `app/api/v1/chat.py` (line ~254-575)

**What happens:**
1. **Start LLM metrics:** `metrics_collector.start_llm()`
2. **Create callback:** `TokenStreamingCallback(websocket, metrics_collector)`
3. **Build messages:**
   ```python
   messages = [
       SystemMessage(content=system_prompt),
       *conversation_history,  # From Redis
       HumanMessage(content=f"{context}\n\n--- User Question ---\n{query}")
   ]
   ```
4. **Call LLM with streaming:**
   ```python
   llm = ChatOpenAI(
       model=settings.OPENAI_MODEL,
       temperature=0.7,
       streaming=True
   )
   
   async for chunk in llm.astream(messages, callbacks=[callback]):
       # Tokens streamed via callback
       pass
   ```
5. **Token Streaming:**
   - Each token sent to WebSocket: `{"type": "stream", "content": token}`
   - First token tracked for TTFB measurement
   - Tokens collected for full response

**Timing:**
- Time to First Token (TTFB): ~500-1000ms
- Total generation time: ~2-5 seconds (depends on response length)

---

### **Step 12: Response Completion**

**Location:** `app/api/v1/chat.py` (line ~575-610)

**What happens:**
1. End LLM metrics: `metrics_collector.end_llm()`
2. Get full response: `full_response = callback.get_full_response()`
3. Finish metrics: `metrics = metrics_collector.finish()`
4. Send completion signal:
   ```python
   await websocket.send_json({
       "type": "complete",
       "response": full_response
   })
   ```
5. Send metrics:
   ```python
   await websocket.send_json({
       "type": "metrics",
       "data": {
           "retrieval_time_ms": metrics.retrieval_time_ms,
           "llm_time_ms": metrics.llm_time_ms,
           "ttfb_ms": metrics.ttfb_ms,
           "retrieved_docs_count": retrieved_docs_count
       }
   })
   ```

---

### **Step 13: Background Tasks**

**Location:** `app/api/v1/chat.py` (line ~590-600)

**What happens:**
1. **Queue assistant message logging:**
   ```python
   log_assistant_message.delay(
       conversation_id=str(conversation_id),
       content=full_response
   )
   ```
   - Runs in Celery worker
   - Logs to PostgreSQL for analytics

2. **Save to Redis:**
   ```python
   await redis_memory_service.add_to_session(
       session_id=str(session_id),
       role="assistant",
       content=full_response
   )
   ```
   - Used for conversation context in future messages

---

### **Step 14: Loop Continues**

The WebSocket handler waits for the next message and repeats the process.

---

## ⚡ Performance Characteristics

### **Timing Breakdown:**

1. **WebSocket message reception:** ~1ms
2. **Redis save (user message):** ~5ms
3. **Conversation history load:** ~5ms
4. **understand_query:** ~5-10ms (with QueryRouter: ~50-100ms)
5. **retrieve_context:** 
   - Dense only: ~200-500ms
   - Hybrid: ~400-900ms
   - With reranking: +100-200ms
6. **LLM first token (TTFB):** ~500-1000ms
7. **LLM complete response:** ~2-5 seconds (depends on length)

### **Total Times:**

- **Time to First Token (TTFB):** ~700-1500ms (with retrieval) or ~500-1000ms (no retrieval)
- **Total Response Time:** ~3-6 seconds (with retrieval) or ~2-4 seconds (no retrieval)

---

## 🔍 Key Design Decisions

1. **LangGraph for Orchestration:**
   - Used for query understanding and retrieval
   - Provides conditional routing based on query type

2. **Bypass LangGraph for Generation:**
   - Direct LLM streaming for token-level control
   - Better real-time user experience

3. **Redis for Session Memory:**
   - Fast, non-blocking conversation history
   - Enables multi-turn conversations

4. **Celery for Background Logging:**
   - Non-blocking PostgreSQL writes
   - Doesn't slow down response time

5. **Modular RAG Components:**
   - QueryRouter: Intelligent query classification
   - RetrieverPool: Multiple retrieval strategies
   - Reranker: Improved relevance
   - TaskAdapter: Task-specific LLM configuration

---

## 📊 Request/Response Format

### **Incoming WebSocket Message:**
```json
{
  "message": "Tell me about Azim's education"
}
```

### **Outgoing WebSocket Messages:**

**Streaming tokens:**
```json
{
  "type": "stream",
  "content": "Azim"
}
```

**Completion:**
```json
{
  "type": "complete",
  "response": "Azim earned his Bachelor of Science in Computer Science..."
}
```

**Metrics:**
```json
{
  "type": "metrics",
  "data": {
    "retrieval_time_ms": 450,
    "llm_time_ms": 2300,
    "ttfb_ms": 850,
    "retrieved_docs_count": 3
  }
}
```

---

## 🔄 Special Cases

### **Greeting Queries:**
- `should_retrieve = False`
- No retrieval performed
- Special greeting system prompt
- Fast response (~1-2 seconds)

### **Out-of-Scope Queries:**
- `should_retrieve = False`
- No retrieval performed
- Redirect message system prompt
- Fast response (~1-2 seconds)

### **No Documents Retrieved:**
- Warning context added
- System prompt instructs LLM to be honest
- Response indicates no information available

---

## 🛠️ Configuration

Key settings in `app/core/config.py`:
- `ENABLE_QUERY_ROUTING`: Enable QueryRouter
- `ENABLE_HYBRID_RETRIEVAL`: Enable hybrid retrieval
- `ENABLE_RERANKING`: Enable cross-encoder reranking
- `ENABLE_MULTI_HOP`: Enable multi-hop retrieval
- `ENABLE_HYDE`: Enable HyDE retrieval
- `OPENAI_MODEL`: LLM model (default: "gpt-4o-mini")
- `TEMPERATURE`: LLM temperature (default: 0.7)

