"""Script to seed database with sample data."""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import AsyncSessionLocal
from app.models.document import Document
from app.models.conversation import Conversation, Message


async def seed_data():
    """Seed database with sample data."""
    async with AsyncSessionLocal() as session:
        # Create sample document
        sample_doc = Document(
            filename="sample.txt",
            content_hash="sample_hash_123",
            content="This is a sample document for testing purposes.",
            source="sample",
            metadata={"test": True},
        )
        session.add(sample_doc)
        
        # Create sample conversation
        conversation = Conversation(
            user_id="test_user",
            session_id=uuid4(),
        )
        session.add(conversation)
        await session.flush()
        
        # Create sample message
        message = Message(
            conversation_id=conversation.id,
            role="user",
            content="Hello, this is a test message.",
        )
        session.add(message)
        
        await session.commit()
        print("✓ Sample data seeded successfully")


if __name__ == "__main__":
    asyncio.run(seed_data())

