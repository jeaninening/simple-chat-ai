from fastapi import APIRouter
from routers.chat import chats_router
from routers.uploadFile import upload_file_router

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(chats_router, tags=["对话管理"])
v1_router.include_router(upload_file_router, tags=["文件管理"])