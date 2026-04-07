import os
import httpx
from typing import AsyncGenerator, Optional
from dotenv import load_dotenv
import json

from models.schemas import ChatRequest, Message

load_dotenv()
class ZhipuService:
    def __init__(self):
        # 从环境变量读取配置
        self.api_key = os.getenv("API_KEY")
        self.api_url = os.getenv("BASE_URL")
        
        if not self.api_key:
            raise ValueError("API_KEY 环境变量未设置")
        if not self.api_url:
            raise ValueError("BASE_URL 环境变量未设置")
    
    async def chat_stream(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """调用智谱 AI API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": request.model,
            "messages": [msg.model_dump() for msg in request.messages],
            "temperature": request.temperature,
            "stream": True  # 开启流式
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                self.api_url,
                headers=headers,
                json=payload
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    yield f"data: {json.dumps({'error': f'API错误: {response.status_code}'})}\n\n"
                    return
                
                async for line in response.aiter_lines(): #使用 httpx.AsyncClient.stream() 保持流式特性
                    if not line:  # 跳过空行
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        
                        if not data_str:
                            continue
                        
                        if data_str == "[DONE]":
                            yield f"data: {json.dumps({'done': True})}\n\n"
                            break
                        
                        try:
                            data = json.loads(data_str)
                            if "error" in data:
                                yield f"data: {json.dumps({'error': data['error'].get('message', '未知错误')})}\n\n"
                                return
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    # 发送内容片段
                                    yield f"data: {json.dumps({'content': content})}\n\n"
                        except json.JSONDecodeError:
                            continue
    # async def simple_chat(self, user_message: str, model: str = "glm-4") -> dict:
    #     """简化版对话方法"""
    #     request = ChatRequest(
    #         messages=[Message(role="user", content=user_message)],
    #         model=model
    #     )
    #     return await self.chat(request)
    async def embed_texts(self, texts: list[str]) -> list:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": "embedding-2",
            "input": texts
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
            "https://open.bigmodel.cn/api/paas/v4/embeddings",
            headers=headers,
            json=payload
        )
        data = response.json()
        return [item["embedding"] for item in data["data"]]
    
# 创建全局服务实例（单例模式）
zhipu_service = ZhipuService()