"""
Script to add a test document to the vector store for RAG testing.
Run this to populate your database with a sample document.

Usage:
    # Option 1: Run in Docker (recommended)
    sudo docker compose exec app python scripts/add_test_document.py
    
    # Option 2: Run locally with venv (ensure database is accessible)
    source venv/bin/activate
    python scripts/add_test_document.py
"""
import asyncio
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_async_session
from app.services.vector_store import VectorStoreService
from app.services.document_processor import DocumentProcessor


async def add_test_document():
    """Add a sample document to test RAG functionality"""
    
    # Check database connection first
    from app.core.config import settings
    print(f"📡 Connecting to database...")
    print(f"   Host: {settings.POSTGRES_HOST}")
    print(f"   Port: {settings.POSTGRES_PORT}")
    print(f"   Database: {settings.POSTGRES_DB}")
    print()
    
    # Sample document content (resume/profile example)
    test_content = """
    PROFESSIONAL PROFILE
    
    Name: John Doe
    Email: john.doe@example.com
    
    PROFESSIONAL SUMMARY
    Experienced software engineer with 5+ years of experience in Python, 
    JavaScript, and cloud technologies. Strong background in building 
    scalable web applications and machine learning systems.
    
    TECHNICAL SKILLS
    - Programming Languages: Python, JavaScript, TypeScript, Java
    - Frameworks: FastAPI, Django, React, Node.js
    - Databases: PostgreSQL, MongoDB, Redis
    - Cloud: AWS, Docker, Kubernetes
    - ML/AI: TensorFlow, PyTorch, LangChain
    
    WORK EXPERIENCE
    
    Senior Software Engineer | Tech Corp | 2021 - Present
    - Led development of RAG-based AI assistant using LangChain
    - Built microservices architecture serving 1M+ requests/day
    - Implemented vector search using pgvector for semantic search
    
    Software Engineer | StartupXYZ | 2019 - 2021
    - Developed RESTful APIs using FastAPI and PostgreSQL
    - Built real-time chat features using WebSockets
    - Optimized database queries reducing latency by 40%
    
    EDUCATION
    Bachelor of Science in Computer Science
    University of Technology | 2015 - 2019
    
    PROJECTS
    - RAG Profile Agent: Built using LangGraph, PostgreSQL, and OpenAI
    - E-commerce Platform: Full-stack application with React and FastAPI
    """
    
    filename = "test_resume.txt"
    
    print(f"Adding test document: {filename}")
    print(f"Content length: {len(test_content)} characters")
    
    vector_store = VectorStoreService()
    
    async with get_async_session() as session:
        try:
            # Add document to vector store
            document = await vector_store.add_document(
                session=session,
                filename=filename,
                content=test_content,
                metadata={
                    "source": "test",
                    "type": "resume",
                    "category": "profile"
                }
            )
            
            print(f"✅ Successfully added document!")
            print(f"   Document ID: {document.id}")
            print(f"   Filename: {document.filename}")
            print(f"   Content Hash: {document.content_hash}")
            print(f"   Has Embedding: {document.embedding is not None}")
            
            # Test retrieval
            print("\n🔍 Testing retrieval...")
            results = await vector_store.similarity_search(
                session=session,
                query="What are my skills?",
                top_k=3,
                threshold=0.5
            )
            
            print(f"   Found {len(results)} relevant documents")
            for i, doc in enumerate(results, 1):
                similarity = getattr(doc, 'similarity', 'N/A')
                print(f"   {i}. {doc.filename} (similarity: {similarity})")
            
        except Exception as e:
            print(f"\n❌ Error occurred: {type(e).__name__}")
            print(f"   Message: {e}")
            print("\nFull traceback:")
            import traceback
            traceback.print_exc()
            print("\n💡 TIP: If connection errors persist, try running in Docker:")
            print("   sudo docker compose exec app python scripts/add_test_document.py")
            return False
    
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("RAG Profile Agent - Test Document Adder")
    print("=" * 60)
    print()
    
    success = asyncio.run(add_test_document())
    
    if success:
        print("\n✅ Test document added successfully!")
        print("   You can now test the chat endpoint:")
        print('   curl -X POST "http://localhost:8000/v1/chat?query=What%20are%20my%20skills&user_id=test"')
    else:
        print("\n❌ Failed to add test document")
        sys.exit(1)

