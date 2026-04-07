from pydantic import BaseModel
from typing import List, Optional

class Message(BaseModel):
    role: str  # user, assistant, system
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    model: str = "glm-4"  # 默认使用 glm-4
    temperature: Optional[float] = 0.8
    stream: Optional[bool] = False

class ChatResponse(BaseModel):
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    usage: Optional[dict] = None