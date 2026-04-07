
from routers import v1_router
from fastapi import FastAPI

app = FastAPI()

app.include_router(v1_router)

# 可选：添加 CORS 中间件（如果前端需要调用）
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="localhost", port=8000, reload=True)