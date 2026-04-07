from fastapi import APIRouter,UploadFile
from fastapi import FastAPI, UploadFile, File
import os
import asyncio
from models.schemas import ChatRequest
from routers.chat import chat_stream_endpoint
from services.zhipu_service import zhipu_service
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from fastapi.responses import StreamingResponse
import uuid
from pathlib import Path
import concurrent.futures

from typing import List
upload_file_router = APIRouter()

UPLOAD_DIR = "uploads/"
CHROMA_DIR = "./chroma_db"

class ZhipuEmbeddings:
    def __init__(self, zhipu_service):
        self.zhipu_service = zhipu_service
        print("ZhipuEmbeddings init")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        ✅ 终极解决：在线程池中运行异步，彻底避免 event loop 冲突
        适配所有场景：FastAPI、LangChain、Chroma、PGVector 等
        """
        # 在独立线程中执行异步任务
        with concurrent.futures.ThreadPoolExecutor() as executor:
            return executor.submit(
                lambda: asyncio.run(self.zhipu_service.embed_texts(texts))
            ).result()

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]
    
embedding = ZhipuEmbeddings(zhipu_service)

@upload_file_router.post("/upload")
async def upload_file(file: UploadFile = File(...)):

    # 生成唯一 ID ✅ 核心
   file_id = str(uuid.uuid4())
       # 保存文件（用 id 命名，避免重名）
   file_ext = file.filename.split(".")[-1]
   store_filename = f"{file_id}.{file_ext}"
   file_path = os.path.join(UPLOAD_DIR, store_filename)
   with open(file_path, "wb") as f:
      f.write(await file.read())

   # 加载文件
   try:
      if file.filename.endswith(".pdf"):
         loader = PyPDFLoader(file_path)
      elif file.filename.endswith(".docx"):
         loader = Docx2txtLoader(file_path)
      elif file.filename.endswith(".txt"):
         loader = TextLoader(file_path, encoding='utf-8')
      else:
         return {"code": 400, "msg": "格式不支持"}
      
      docs = loader.load()
   except Exception as e:
      return {"code": 500, "msg": f"解析失败: {str(e)}"}
   
   try:
      # 分块
      splitter = RecursiveCharacterTextSplitter(    
      chunk_size=500,      # 更小的块，提高精度
      chunk_overlap=100,   # 重叠避免上下文断裂
      separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""])
      chunks = splitter.split_documents(docs)


      for chunk in chunks:
      
         chunk.metadata.update({"file_id": file_id})

      # 存入 Chroma
      Chroma.from_documents(
         documents=chunks,
         embedding=embedding,
         persist_directory=CHROMA_DIR,
      )
      return {
            "code": 200,
            "file_id": file_id, 
            "filename": file.filename,
            "msg": "上传并向量化完成"
            }
   except Exception as e:
      return {"code": 500, "msg": f"存储失败: {str(e)}"}

@upload_file_router.post("/upload-file-chat")
async def upload_file_chat(data: ChatRequest):
    chat_request = ChatRequest(
        model="glm-4",
        messages=[msg.model_dump() for msg in data.messages],
        temperature=0.7,
        stream=True
    )
     # 1. 检查是否上传了文件
    uploads_path = Path("uploads")
    
    # 检查目录是否存在
    if not uploads_path.exists():
         return await chat_stream_endpoint(chat_request)
    
    # 检查目录中是否有文件
    files = list(uploads_path.glob("*"))
    # 过滤掉目录，只保留文件
    files = [f for f in files if f.is_file()]
    
    if not files:
        return await chat_stream_endpoint(chat_request)
  
   # 提取用户问题（只取最后一条 user 消息）
    question = ""
    for msg in reversed(data.messages):
        if msg.role == "user":
            question = msg.content
            break

    # 1. 向量检索
    vector_db = Chroma(embedding_function=embedding, persist_directory=CHROMA_DIR)
    retriever = vector_db.as_retriever(search_kwargs={"k": 1})
    context = retriever.invoke(question)
    context_text = "\n".join([doc.page_content for doc in context])

    # 2. 构建 Prompt
    prompt = f"""
      你是文档助手，请只根据资料回答，不要编造内容。
      资料：{context_text}
      问题：{question}

      重要规则：
      - 直接回答问题，不要说"根据资料"、"根据文档"、"资料显示"等任何开头语
      - 不要添加任何解释性文字
      - 直接输出答案内容
      回答：
      """

    # 3. 异步流式生成（完全适配你的 zhipu_service）
    async def async_gen():
      request = ChatRequest(
        model="glm-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        stream=True
      )
    
      async for chunk in zhipu_service.chat_stream(request):
         yield chunk

    return StreamingResponse(async_gen(), media_type="text/event-stream")

@upload_file_router.post("/delete-file")
async def delete_file(data: dict):
    file_id = data.get("file_id")
    if not file_id:
        return {"code": 400, "msg": "file_id 不能为空"}

    try:
        vector_db = Chroma(embedding_function=embedding, persist_directory=CHROMA_DIR)
        vector_db._collection.delete(where={"file_id": file_id})
    except:
        return {"code": 500, "msg": "向量删除失败"}

    # 删除本地文件
    for ext in ["pdf", "docx", "txt"]:
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}.{ext}")
        if os.path.exists(file_path):
            os.remove(file_path)

    return {"code": 200, "msg": "删除成功", "file_id": file_id}