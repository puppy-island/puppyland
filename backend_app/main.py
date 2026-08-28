"""
记忆家园后端 API

一个由记忆共同生成、不断生长的虚拟家园。人们将关于逝去宠物的照片、声音、
故事与片段记忆放入其中，AI将这些记忆转化为空间、物件与生命，让离开的动物
在另一个温暖的世界里继续存在，让离开不只是失去，而成为爱与记忆延续的另一种方式。

产品定位：
- 记忆碎片系统：收集关于宠物的各种故事和瞬间
- 虚拟家园：基于记忆生成不断生长的虚拟空间和物品
- 进化系统：宠物可以通过记忆触发进化（NPC触发、项圈成长、主人形态、投胎转世）
- 品种微调：根据狗狗的品种进行AI微调，生成更个性化的内容
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend_app.routes import router
from backend_app.database import init_db
import os

app = FastAPI(
    title="记忆家园 API",
    description="""
## 产品概述

一个由记忆共同生成、不断生长的虚拟家园。

### 核心功能

1. **故事（记忆碎片）** - 记录与宠物建立情感链接的瞬间
   - 第一眼见到ta的瞬间
   - 小狗吃东西之前滑稽的故事
   - 出门前小狗反应的故事
   - 小狗保护你的故事
   - 你保护小狗的故事
   - 让你有从未有过的奇妙感受的瞬间和故事

2. **宠物档案** - 完整的宠物信息
   - 品种、声音、颜色、走路姿态
   - 喜欢吃什么、怎么离开的
   - 性格（敏感、爱咬人、傻乎乎）
   - 想吃饭时的反应、爱不爱穿衣服
   - 看门能力、粘人程度
   - 喜欢什么、怕什么
   - 照片（自媒体+App使用）

3. **虚拟家园** - 基于记忆生成的虚拟空间和物品

4. **进化系统**
   - 摆渡人、触发人（NPC触发，长出项圈、长出主人）
   - 变成小狗的过程（带成旧的记忆到了新的地方）

5. **品种微调** - 根据狗狗品种进行AI微调

### 为什么会决定养狗？
记录领养宠物的初心和故事。
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
def startup_event():
    init_db()

# Include routers
app.include_router(router, prefix="/api/v1")

# Mount uploads directory for serving uploaded images
uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

@app.get("/", tags=["Root"])
def root():
    """Root endpoint - API information"""
    return {
        "name": "记忆家园 API",
        "version": "1.0.0",
        "description": "一个由记忆共同生成、不断生长的虚拟家园",
        "docs": "/docs",
        "redoc": "/redoc"
    }

@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
