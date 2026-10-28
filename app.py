"""HF Spaces 入口 (Gradio SDK)

HF Spaces 运行 `python app.py`,
FastAPI(含REST API + MCP SSE)监听7860端口。

端点:
- /docs          API文档(Swagger)
- /api/health    健康检查
- /mcp/sse       MCP SSE端点(Coze连接用)
"""
import uvicorn

from app.main import app


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)