"""
多平台商品推荐Agent主入口点
启动FastAPI应用，提供Web服务
"""

import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import os

# 导入API路由
from api.routes import router as api_router

# 创建FastAPI应用
app = FastAPI(
    title="多平台商品推荐Agent",
    description="智能商品推荐系统，支持淘宝、京东、拼多多等多平台价格对比",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
static_dir = os.path.join(os.path.dirname(__file__), "frontend", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 配置模板
templates_dir = os.path.join(os.path.dirname(__file__), "frontend", "templates")
templates = Jinja2Templates(directory=templates_dir)

# 包含API路由
app.include_router(api_router)

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """
    根路径，返回前端页面
    """
    try:
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception as e:
        # 如果模板不存在，返回简单的欢迎页面
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>多平台商品推荐Agent</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    margin: 0;
                    padding: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                }
                .container {
                    background: white;
                    border-radius: 20px;
                    padding: 40px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    text-align: center;
                    max-width: 600px;
                    width: 90%;
                }
                h1 {
                    color: #333;
                    margin-bottom: 20px;
                    font-size: 2.5em;
                }
                p {
                    color: #666;
                    font-size: 1.2em;
                    line-height: 1.6;
                    margin-bottom: 30px;
                }
                .features {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }
                .feature {
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 10px;
                    border-left: 4px solid #667eea;
                }
                .feature h3 {
                    color: #333;
                    margin-top: 0;
                }
                .feature p {
                    color: #666;
                    font-size: 0.9em;
                    margin-bottom: 0;
                }
                .api-link {
                    display: inline-block;
                    background: #667eea;
                    color: white;
                    padding: 15px 30px;
                    text-decoration: none;
                    border-radius: 30px;
                    font-weight: bold;
                    transition: background 0.3s;
                }
                .api-link:hover {
                    background: #764ba2;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🛒 多平台商品推荐Agent</h1>
                <p>智能商品推荐系统，支持淘宝、京东、拼多多等多平台价格对比，为您提供最佳购买建议。</p>
                
                <div class="features">
                    <div class="feature">
                        <h3>📊 多平台对比</h3>
                        <p>同时搜索淘宝、京东、拼多多，比较同款商品价格</p>
                    </div>
                    <div class="feature">
                        <h3>🎯 精准推荐</h3>
                        <p>基于价格、销量、店铺信誉等多维度智能推荐</p>
                    </div>
                    <div class="feature">
                        <h3>💰 预算优化</h3>
                        <p>根据您的预算范围，找到性价比最高的商品</p>
                    </div>
                </div>
                
                <a href="/docs" class="api-link">📚 查看API文档</a>
            </div>
        </body>
        </html>
        """)

@app.get("/health")
async def health_check():
    """健康检查接口"""
    from api.services import api_service
    return {
        "status": "healthy",
        "service": "多平台商品推荐Agent",
        "version": "1.0.0",
        "statistics": api_service.get_statistics()
    }

if __name__ == "__main__":
    # 启动服务器
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )