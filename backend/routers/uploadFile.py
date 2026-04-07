from fastapi import APIRouter,UploadFile
from fastapi import FastAPI, UploadFile, File
import os
import asyncio
from models.schemas import ChatRequest
from routers.chat import chat_stream_endpoint
from services.zhipu_service import zhipu_service
import shutil
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from fastapi.responses import StreamingResponse
import uuid
from pathlib import Path
import concurrent.futures
from typing import List
upload_file_router = APIRouter()

# PDF 需要：pypdf
# Word（.docx） 需要：docx2txt
# Excel 需要：pandas
# Txt 不需要额外依赖

UPLOAD_DIR = "uploads/"
FAISS_DIR = "./faiss_db"

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
    
    def __call__(self, text: str) -> List[float]:
        """让实例像函数一样可调用"""
        return self.embed_query(text)
    
embedding = ZhipuEmbeddings(zhipu_service)

@upload_file_router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # 生成唯一 ID
    file_id = str(uuid.uuid4())
    
    # 保存原始文件
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
            os.remove(file_path)  # 删除原始文件
            return {"code": 400, "msg": "格式不支持"}
        
        docs = loader.load()
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)  # 删除原始文件
        return {"code": 500, "msg": f"解析失败: {str(e)}"}
    
    try:
        # 分块
        splitter = RecursiveCharacterTextSplitter(    
            chunk_size=500,
            chunk_overlap=100,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
        )
        chunks = splitter.split_documents(docs)
        
        if not chunks:
            os.remove(file_path)  # 删除原始文件
            return {"code": 400, "msg": "文件内容为空或无法读取"}
        
        # 添加元数据
        for chunk in chunks:
            chunk.metadata.update({
                "file_id": str(file_id),
                "filename": str(file.filename)
            })
        
        # 使用 FAISS 创建向量存储
        vector_store = FAISS.from_documents(
            documents=chunks,
            embedding=embedding
        )
        
        
  

        # 保存向量数据库（按 file_id 分目录）
        faiss_path = os.path.join(FAISS_DIR, file_id)
        os.makedirs(faiss_path, exist_ok=True)
        vector_store.save_local(faiss_path)

        print(f"✅ 保存成功: {faiss_path}")
        print(f"   - {os.path.join(faiss_path, 'index.faiss')}")
        print(f"   - {os.path.join(faiss_path, 'index.pkl')}")
        
        # ✅ 关键：向量化成功后删除原始文件（节省空间）
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"已删除原始文件: {file_path}")
        
        return {
            "code": 200,
            "file_id": file_id,
            "filename": file.filename,
            "msg": "文件上传并向量化完成"
        }
        
    except Exception as e:
        print(f"【错误详情】: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # 出错时清理所有相关文件
        if os.path.exists(file_path):
            os.remove(file_path)
        faiss_path = os.path.join(FAISS_DIR, file_id)
        if os.path.exists(faiss_path):
            shutil.rmtree(faiss_path)
            
        return {"code": 500, "msg": f"存储失败: {str(e)}"}
    
@upload_file_router.post("/upload-file-chat")
async def upload_file_chat(data: ChatRequest):
    chat_request = ChatRequest(
        model="glm-4",
        messages=[msg.model_dump() for msg in data.messages],
        temperature=0.7,
        stream=True
    )
    
    question = ""
    for msg in reversed(data.messages):
        if msg.role == "user":
            question = msg.content
            break
    
    # 1. 获取所有已向量化的文件
    faiss_dir = Path("faiss_db")  # FAISS 存储目录
    
    if not faiss_dir.exists():
        return await chat_stream_endpoint(chat_request)
    
    # 2. 收集所有文件的内容
    all_results = []  # 改为存储带分数的结果
    
    # 遍历所有文件的 FAISS 索引
    for file_dir in faiss_dir.iterdir():
        if not file_dir.is_dir():
            continue
        
        try:
            # ✅ 关键修复：加载每个文件的向量库（使用子目录路径）
            vector_store = FAISS.load_local(
                folder_path=str(file_dir),
                embeddings=embedding,
                allow_dangerous_deserialization=True
            )
            
            # 检索相关片段（带分数）
            chunks_with_scores = vector_store.similarity_search_with_score(question, k=2)
            
            for doc, score in chunks_with_scores:
                all_results.append((score, doc, file_dir.name))
                
        except Exception as e:
            print(f"加载文件 {file_dir.name} 失败: {e}")
            continue
    
    # 3. 如果没有找到任何内容，直接对话
    if not all_results:
        return await chat_stream_endpoint(chat_request)
    
    # 4. 按相关性排序（分数越小越相关）
    all_results.sort(key=lambda x: x[0])
    
    # 5. 取前5个最相关的片段
    top_chunks = all_results[:5]
    
    # 6. 合并所有检索结果
    context_text = "\n---\n".join([doc.page_content for score, doc, file_id in top_chunks])
    
    # 7. 构建 Prompt
    prompt = f"""你是文档助手，请只根据资料回答，不要编造内容。

            资料：
            {context_text}

            问题：{question}

            重要规则：
            - 直接回答问题，不要说"根据资料"、"根据文档"、"资料显示"等任何开头语
            - 不要添加任何解释性文字
            - 直接输出答案内容

            回答："""
    
    # 8. 异步流式生成
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
    """
    删除指定文件的所有数据（向量数据库）
    """
    try:
        deleted_original = False
        #删除向量数据库目录
        faiss_path = os.path.join(FAISS_DIR, file_id)
        if os.path.exists(faiss_path):
            shutil.rmtree(faiss_path)
            print(f"已删除向量数据库: {faiss_path}")
        
        if not deleted_original and not os.path.exists(faiss_path):
            return {"code": 404, "msg": f"文件 {file_id} 不存在"}
        
        return {"code": 200, "msg": f"文件 {file_id} 删除成功"}
        
    except Exception as e:
        print(f"删除失败: {str(e)}")
        return {"code": 500, "msg": f"删除失败: {str(e)}"}