-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Documents table (for RAG)
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename VARCHAR(255) NOT NULL,
    content_hash VARCHAR(64) UNIQUE NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    embedding vector(1536),  -- OpenAI text-embedding-3-small dimension
    source VARCHAR(50) DEFAULT 's3',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create HNSW index for fast vector search (production-ready)
CREATE INDEX IF NOT EXISTS documents_embedding_idx 
ON documents USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Document sources table (for incremental ingestion tracking)
CREATE TABLE IF NOT EXISTS document_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    s3_key VARCHAR(255) UNIQUE NOT NULL,
    etag VARCHAR(64),
    last_modified TIMESTAMP,
    file_hash VARCHAR(64),
    file_size BIGINT,
    status VARCHAR(20) DEFAULT 'pending',  -- 'synced', 'pending', 'failed', 'processing'
    synced_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on document_sources for efficient lookups
CREATE INDEX IF NOT EXISTS idx_document_sources_s3_key ON document_sources(s3_key);
CREATE INDEX IF NOT EXISTS idx_document_sources_status ON document_sources(status);
CREATE INDEX IF NOT EXISTS idx_document_sources_synced_at ON document_sources(synced_at);

-- Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL,
    session_id UUID NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Messages table (conversation history)
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- LangGraph checkpoints (state persistence)
CREATE TABLE IF NOT EXISTS langgraph_checkpoints (
    thread_id VARCHAR(255) NOT NULL,
    checkpoint_id VARCHAR(255) NOT NULL,
    parent_checkpoint_id VARCHAR(255),
    checkpoint JSONB NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (thread_id, checkpoint_id)
);

-- Analytics table (for Celery background tasks)
CREATE TABLE IF NOT EXISTS analytics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_documents_filename ON documents(filename);
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_langgraph_checkpoints_thread_id ON langgraph_checkpoints(thread_id);
CREATE INDEX IF NOT EXISTS idx_analytics_created_at ON analytics(created_at);

-- Create GIN index for full-text search (for future hybrid search)
CREATE INDEX IF NOT EXISTS idx_documents_content_fts ON documents 
USING GIN (to_tsvector('english', content));

-- Create GIN index for metadata JSONB queries
CREATE INDEX IF NOT EXISTS idx_documents_metadata_gin ON documents USING GIN (metadata);
