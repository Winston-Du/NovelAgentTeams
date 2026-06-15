"""
向量检索相关 API
"""
from fastapi import APIRouter, HTTPException
from typing import Optional

router = APIRouter(prefix="/api/vector", tags=["vector"])


@router.post("/init")
async def init_vector_db():
    """初始化向量数据库。构建或重新构建向量库索引。"""
    try:
        from ..retrieval_engine import get_retrieval_engine
        
        engine = get_retrieval_engine()
        engine._ensure_initialized()
        
        if engine._initialized and engine.vectorstore:
            doc_count = engine.vectorstore._collection.count()
            return {
                "status": "success",
                "message": "向量库初始化完成",
                "document_count": doc_count
            }
        else:
            raise HTTPException(status_code=500, detail="向量库初始化失败")
    
    except ImportError as e:
        raise HTTPException(status_code=501, detail=f"检索引擎模块不可用: {str(e)}")
    except Exception as e:
        import traceback
        print(f"[ERROR] 向量库初始化失败: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"向量库初始化失败: {str(e)}")


@router.get("/status")
async def get_vector_status():
    """获取向量库状态。"""
    try:
        from ..retrieval_engine import get_retrieval_engine
        
        engine = get_retrieval_engine()
        
        if engine._initialized and engine.vectorstore:
            doc_count = engine.vectorstore._collection.count()
            return {
                "status": "initialized",
                "document_count": doc_count,
                "model": engine.embedding_model_name
            }
        else:
            return {
                "status": "not_initialized",
                "document_count": 0,
                "model": engine.embedding_model_name
            }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
