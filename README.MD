Web/H5 智能小助手

基于 Vue3 + Element Plus + Vite 前端 + FastAPI + 智谱 AI 大模型 开发的轻量级智能对话助手，支持多轮对话、自定义 Prompt、流式打字机效果输出，适配 Web/H5 端。

前后端代码目录：
## 项目目录结构

```
simple-chat-ai/
├── web/                        # 前端项目
│   ├── src/
│   │   ├── components/         # 前端组件
│   │   ├── views/              # 前端页面
│   │   └── App.vue             # 前端入口文件
│   └── package.json            # 前端依赖配置
├── backend/                    # 后端项目
│   ├── main.py                 # FastAPI入口
│   ├── routers/
│   │   └── chat.py             # 对话接口
│   ├── services/
│   │   └── chat.py             # 调用大模型
│   └── models/
│       └── schemas.py          # 定义数据结构
└── README.md
```

# 快速开始
环境要求
Node.js >= 22.0.0
Python >= 3.12
智谱 AI API Key

# 启动后端服务：
激活虚拟环境 D:\anaconda\Scripts\activate.bat && conda activate simple_env

# 安装依赖
pip install -r requirements.txt

# 启动服务
uvicorn main:app --reload --host 0.0.0.0 --port 8000

流式输出：前端使用 EventSource 接收后端 SSE 流式数据，实现打字机效果
多轮对话：后端维护对话上下文列表，每次请求携带历史消息给大模型
Prompt 自定义：前端传递自定义系统提示词，动态修改 AI 角色

基于 H5 标准，支持 PC 浏览器、移动端访问