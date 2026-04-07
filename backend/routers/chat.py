
from fastapi import APIRouter
from fastapi import HTTPException, status
from models.schemas import ChatRequest, ChatResponse
from services.zhipu_service import zhipu_service
from fastapi.responses import StreamingResponse
import asyncio
import json

chats_router = APIRouter()

@chats_router.get("/")
async def root():
    return {
        "message": "智谱 AI 对话服务已启动",
        "endpoints": {
            "chat": "POST /chat",
            "simple": "POST /simple-chat",
            "health": "GET /health"
        }
    }

# @chats_router.get("/health")
# async def health_check():
#     """健康检查接口"""
#     return {"status": "healthy", "service": "zhipu-ai"}

@chats_router.post("/chat-stream", response_model=ChatResponse)
async def chat_stream_endpoint(request: ChatRequest):
    """
    流式对话接口 - 打字机效果
    
    前端可以实时接收 AI 逐字输出
    """
    async def generate():
        try:
            async for chunk in zhipu_service.chat_stream(request):
                yield chunk
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        }
    )

@chats_router.post("/simple-chat", response_model=ChatResponse)
async def simple_chat_endpoint(user_message: str, model: str = "glm-4"):
    """
    简化对话接口
    
    - **user_message**: 用户输入的消息
    - **model**: 使用的模型名称，默认 glm-4
    """
    result = await zhipu_service.simple_chat(user_message, model)
    
    if result["success"]:
        return ChatResponse(
            success=True,
            content=result["content"],
            usage=result.get("usage")
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "未知错误")
        )

@chats_router.get("/test-stream")
async def test_stream():
    async def generate():
        for i in range(5):
            yield f"data: {json.dumps({'content': f'消息{i}'})}\n\n".encode('utf-8')
            await asyncio.sleep(0.5)
        yield b"data: [DONE]\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")