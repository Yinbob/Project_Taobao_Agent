"""
API路由模块
提供RESTful API接口
"""

import time
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from data_models import (
    SearchRequest, SearchResponse, Platform, 
    RecommendationResult, Product
)
from taobao_agent import agent

router = APIRouter(prefix="/api", tags=["商品推荐"])

@router.on_event("startup")
async def startup_event():
    """应用启动事件"""
    success = await agent.initialize()
    if not success:
        print("警告：Agent初始化失败，部分功能可能不可用")

@router.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    await agent.shutdown()

@router.post("/search", response_model=SearchResponse)
async def search_products(request: SearchRequest):
    """
    搜索并推荐商品
    
    Args:
        request: 搜索请求
    
    Returns:
        搜索响应
    """
    try:
        response = await agent.search_and_recommend(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")

@router.get("/product/{platform}/{product_id}", response_model=Optional[Product])
async def get_product_details(platform: Platform, product_id: str):
    """
    获取商品详情
    
    Args:
        platform: 平台
        product_id: 商品ID
    
    Returns:
        商品详情
    """
    try:
        product = await agent.get_product_details(product_id, platform)
        if product is None:
            raise HTTPException(status_code=404, detail="商品不存在")
        return product
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取商品详情失败: {str(e)}")

@router.get("/categories", response_model=List[str])
async def get_supported_categories():
    """
    获取支持的商品类别
    
    Returns:
        商品类别列表
    """
    return agent.get_supported_categories()

@router.get("/platforms", response_model=List[Dict[str, str]])
async def get_supported_platforms():
    """
    获取支持的平台
    
    Returns:
        平台列表
    """
    return agent.get_supported_platforms()

@router.get("/weights", response_model=Dict[str, float])
async def get_recommendation_weights():
    """
    获取推荐算法权重
    
    Returns:
        权重配置
    """
    return agent.get_recommendation_weights()

@router.put("/weights")
async def update_recommendation_weights(weights: Dict[str, float]):
    """
    更新推荐算法权重
    
    Args:
        weights: 新的权重配置
    
    Returns:
        更新结果
    """
    success = agent.update_recommendation_weights(weights)
    if not success:
        raise HTTPException(status_code=400, detail="权重配置无效")
    return {"message": "权重更新成功", "weights": weights}

@router.get("/history", response_model=List[Dict[str, Any]])
async def get_search_history():
    """
    获取搜索历史
    
    Returns:
        搜索历史列表
    """
    return agent.get_search_history()

@router.delete("/history")
async def clear_search_history():
    """
    清空搜索历史
    
    Returns:
        清空结果
    """
    agent.clear_search_history()
    return {"message": "搜索历史已清空"}

@router.get("/health")
async def health_check():
    """
    健康检查
    
    Returns:
        健康状态
    """
    return {
        "status": "healthy",
        "initialized": agent.initialized,
        "timestamp": time.time()
    }