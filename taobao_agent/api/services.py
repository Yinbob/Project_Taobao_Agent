"""
API服务模块
包含业务逻辑，处理API请求
"""

import time
from typing import Dict, Any, Optional
from data_models import SearchRequest, SearchResponse, RecommendationResult
from taobao_agent import agent

class APIService:
    """API服务类"""
    
    def __init__(self):
        self.request_count = 0
        self.total_search_time = 0.0
    
    async def search_products(self, request: SearchRequest) -> SearchResponse:
        """
        搜索商品
        
        Args:
            request: 搜索请求
        
        Returns:
            搜索响应
        """
        start_time = time.time()
        self.request_count += 1
        
        try:
            # 调用Agent进行搜索
            response = await agent.search_and_recommend(request)
            
            # 记录搜索时间
            search_time = time.time() - start_time
            self.total_search_time += search_time
            
            return response
            
        except Exception as e:
            search_time = time.time() - start_time
            self.total_search_time += search_time
            
            return SearchResponse(
                success=False,
                message=f"搜索失败: {str(e)}",
                error=str(e)
            )
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息
        """
        avg_search_time = (
            self.total_search_time / self.request_count 
            if self.request_count > 0 else 0.0
        )
        
        return {
            "total_requests": self.request_count,
            "total_search_time": self.total_search_time,
            "average_search_time": avg_search_time,
            "agent_initialized": agent.initialized
        }
    
    def reset_statistics(self):
        """重置统计信息"""
        self.request_count = 0
        self.total_search_time = 0.0
    
    async def validate_search_request(self, request: SearchRequest) -> Optional[str]:
        """
        验证搜索请求
        
        Args:
            request: 搜索请求
        
        Returns:
            错误信息，如果验证通过则返回None
        """
        # 验证查询关键词
        if not request.query or len(request.query.strip()) == 0:
            return "搜索关键词不能为空"
        
        if len(request.query) > 100:
            return "搜索关键词长度不能超过100个字符"
        
        # 验证预算范围
        if request.budget_min < 0:
            return "最低预算不能为负数"
        
        if request.budget_max < 0:
            return "最高预算不能为负数"
        
        if request.budget_min > request.budget_max:
            return "最低预算不能高于最高预算"
        
        # 验证平台
        if not request.platforms:
            return "至少选择一个平台"
        
        # 验证返回结果数量
        if request.top_n < 1:
            return "返回结果数量不能小于1"
        
        if request.top_n > 50:
            return "返回结果数量不能超过50"
        
        return None
    
    async def get_product_recommendations(self, query: str, budget_min: float, 
                                        budget_max: float, platforms: list = None,
                                        top_n: int = 10) -> SearchResponse:
        """
        获取商品推荐（便捷方法）
        
        Args:
            query: 搜索关键词
            budget_min: 最低预算
            budget_max: 最高预算
            platforms: 平台列表
            top_n: 返回结果数量
        
        Returns:
            搜索响应
        """
        if platforms is None:
            platforms = ["jd", "taobao", "pdd"]
        
        # 转换平台列表
        from data_models import Platform
        platform_enums = []
        for platform in platforms:
            try:
                platform_enums.append(Platform(platform))
            except ValueError:
                continue
        
        # 创建搜索请求
        request = SearchRequest(
            query=query,
            budget_min=budget_min,
            budget_max=budget_max,
            platforms=platform_enums,
            top_n=top_n
        )
        
        # 验证请求
        validation_error = await self.validate_search_request(request)
        if validation_error:
            return SearchResponse(
                success=False,
                message=validation_error,
                error=validation_error
            )
        
        # 执行搜索
        return await self.search_products(request)

# 创建全局API服务实例
api_service = APIService()