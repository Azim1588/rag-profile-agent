"""OpenAI LLM service."""
from typing import List, Optional
from openai import AsyncOpenAI
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from app.core.config import settings


class LLMService:
    """Service for interacting with OpenAI LLM."""
    
    def __init__(self):
        """Initialize OpenAI client and LangChain models."""
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.llm = ChatOpenAI(
            model_name=settings.OPENAI_MODEL,
            temperature=settings.TEMPERATURE,
            max_tokens=settings.MAX_TOKENS,
            openai_api_key=settings.OPENAI_API_KEY,
        )
        self.embeddings = OpenAIEmbeddings(
            model=settings.OPENAI_EMBEDDING_MODEL,
            openai_api_key=settings.OPENAI_API_KEY,
        )
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text."""
        result = await self.embeddings.aembed_query(text)
        return result
    
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        result = await self.embeddings.aembed_documents(texts)
        return result
    
    async def chat_completion(
        self,
        messages: List[dict],
        temperature: Optional[float] = None,
    ) -> str:
        """Generate chat completion."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            temperature=temperature or settings.TEMPERATURE,
            max_tokens=settings.MAX_TOKENS,
        )
        return response.choices[0].message.content


llm_service = LLMService()

