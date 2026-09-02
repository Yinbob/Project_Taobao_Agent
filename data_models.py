"""
多平台商品推荐Agent数据模型
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

class Platform(str, Enum):
    """电商平台枚举"""
    JD = "jd"
    TAOBAO = "taobao"
    PDD = "pdd"

class Product(BaseModel):
    """商品数据模型"""
    id: str = Field(..., description="商品ID")
    title: str = Field(..., description="商品标题")
    price: float = Field(..., description="商品价格")
    original_price: Optional[float] = Field(None, description="原价")
    discount: Optional[float] = Field(None, description="折扣")
    sales: Optional[int] = Field(None, description="销量")
    shop_name: Optional[str] = Field(None, description="店铺名称")
    shop_type: Optional[str] = Field(None, description="店铺类型")
    platform: Platform = Field(..., description="所属平台")
    product_url: Optional[str] = Field(None, description="商品链接")
    image_url: Optional[str] = Field(None, description="商品图片链接")
    rating: Optional[float] = Field(None, description="评分")
    review_count: Optional[int] = Field(None, description="评价数量")
    specs: Optional[Dict[str, Any]] = Field(None, description="商品规格")

class PriceComparison(BaseModel):
    """价格对比数据模型"""
    product_title: str = Field(..., description="商品标题")
    platforms: Dict[Platform, Product] = Field(..., description="各平台商品信息")
    min_price: float = Field(..., description="最低价格")
    min_price_platform: Platform = Field(..., description="最低价格平台")
    max_price: float = Field(..., description="最高价格")
    price_difference: float = Field(..., description="价格差异")
    price_difference_percentage: float = Field(..., description="价格差异百分比")

class RecommendationScore(BaseModel):
    """推荐评分数据模型"""
    product: Product = Field(..., description="商品信息")
    price_score: float = Field(..., description="价格得分")
    sales_score: float = Field(..., description="销量得分")
    shop_reputation_score: float = Field(..., description="店铺信誉得分")
    platform_reliability_score: float = Field(..., description="平台可靠性得分")
    total_score: float = Field(..., description="综合得分")
    rank: int = Field(..., description="排名")

class RecommendationResult(BaseModel):
    """推荐结果数据模型"""
    query: str = Field(..., description="搜索查询")
    budget_min: float = Field(..., description="最低预算")
    budget_max: float = Field(..., description="最高预算")
    platforms: List[Platform] = Field(..., description="搜索平台")
    price_comparisons: List[PriceComparison] = Field(..., description="价格对比列表")
    recommendations: List[RecommendationScore] = Field(..., description="推荐商品列表")
    total_products_found: int = Field(..., description="找到的商品总数")
    search_time: float = Field(..., description="搜索耗时（秒）")

class SearchRequest(BaseModel):
    """搜索请求数据模型"""
    query: str = Field(..., description="搜索关键词")
    budget_min: float = Field(..., description="最低预算")
    budget_max: float = Field(..., description="最高预算")
    platforms: List[Platform] = Field(default=[Platform.JD, Platform.TAOBAO, Platform.PDD], description="搜索平台")
    top_n: int = Field(default=10, description="返回结果数量")

class SearchResponse(BaseModel):
    """搜索响应数据模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[RecommendationResult] = Field(None, description="推荐结果")
    error: Optional[str] = Field(None, description="错误信息")