"""
Custom callback handler for streaming LLM tokens to WebSocket.
"""
from typing import Any, Dict, List, Optional
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult
import logging

logger = logging.getLogger(__name__)


class WebSocketStreamingCallback(AsyncCallbackHandler):
    """Callback handler that streams tokens to WebSocket in real-time."""
    
    def __init__(self, websocket=None):
        super().__init__()
        self.websocket = websocket
        self.tokens_received = []
        self.first_token_time = None
        import time
        self.start_time = time.time()
    
    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Called when a new token is generated."""
        import time
        
        # Record first token time
        if self.first_token_time is None:
            self.first_token_time = time.time()
            logger.info(f"[Streaming] First token received at {(self.first_token_time - self.start_time)*1000:.2f}ms")
        
        # Store token
        self.tokens_received.append(token)
        
        # Send token to WebSocket if available
        if self.websocket:
            try:
                await self.websocket.send_json({
                    "type": "stream",
                    "content": token
                })
            except Exception as e:
                logger.error(f"Error sending token to WebSocket: {e}")
    
    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Called when LLM finishes generating."""
        import time
        total_time = (time.time() - self.start_time) * 1000
        logger.info(f"[Streaming] LLM finished. Total tokens: {len(self.tokens_received)}, Time: {total_time:.2f}ms")
    
    def get_full_response(self) -> str:
        """Get the complete response from collected tokens."""
        return "".join(self.tokens_received)

