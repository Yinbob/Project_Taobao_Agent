"""
推荐算法模块
实现多维度评分算法，包括价格得分、销量得分、店铺信誉得分和平台可靠性得分
"""

import math
from typing import List, Dict, Optional
from data_models import Product, Platform, RecommendationScore, PriceComparison
from config import config

class RecommendationEngine:
    """推荐引擎类"""
    
    def __init__(self):
        self.weights = config.RECOMMENDATION_WEIGHTS
        self.price_params = config.PRICE_SCORE_PARAMS
        self.sales_params = config.SALES_SCORE_PARAMS
        self.platform_reliability = config.PLATFORM_RELIABILITY
    
    def calculate_price_score(self, price: float, budget_min: float, budget_max: float) -> float:
        """
        计算价格得分
        
        Args:
            price: 商品价格
            budget_min: 最低预算
            budget_max: 最高预算
        
        Returns:
            价格得分（0-1）
        """
        if price <= 0:
            return 0.0
        
        # 计算预算中位数
        budget_mid = (budget_min + budget_max) / 2
        
        # 计算最优价格
        optimal_price = budget_mid * self.price_params["optimal_ratio"]
        
        # 计算价格差异
        price_diff = abs(price - optimal_price)
        max_diff = max(optimal_price - budget_min, budget_max - optimal_price)
        
        if max_diff == 0:
            return 1.0
        
        # 计算价格得分（越接近最优价格得分越高）
        price_score = 1.0 - (price_diff / max_diff)
        
        # 应用权重因子
        weight_factor = self.price_params["weight_factor"]
        price_score = price_score ** weight_factor
        
        return max(0.0, min(1.0, price_score))
    
    def calculate_sales_score(self, sales: Optional[int]) -> float:
        """
        计算销量得分
        
        Args:
            sales: 销量
        
        Returns:
            销量得分（0-1）
        """
        if sales is None or sales <= 0:
            return 0.0
        
        # 应用对数归一化
        log_base = self.sales_params["log_base"]
        max_sales = self.sales_params["max_sales_cap"]
        
        # 限制最大销量
        capped_sales = min(sales, max_sales)
        
        # 计算对数得分
        if capped_sales <= 0:
            return 0.0
        
        sales_score = math.log(capped_sales + 1, log_base) / math.log(max_sales + 1, log_base)
        
        return max(0.0, min(1.0, sales_score))
    
    def calculate_shop_reputation_score(self, shop_type: Optional[str], rating: Optional[float]) -> float:
        """
        计算店铺信誉得分
        
        Args:
            shop_type: 店铺类型
            rating: 评分
        
        Returns:
            店铺信誉得分（0-1）
        """
        score = 0.5  # 基础分
        
        # 根据店铺类型调整
        if shop_type:
            shop_type_lower = shop_type.lower()
            if "旗舰" in shop_type_lower or "flagship" in shop_type_lower:
                score += 0.3
            elif "自营" in shop_type_lower or "self" in shop_type_lower:
                score += 0.2
            elif "专营" in shop_type_lower or "specialty" in shop_type_lower:
                score += 0.1
        
        # 根据评分调整
        if rating is not None:
            if rating >= 4.8:
                score += 0.2
            elif rating >= 4.5:
                score += 0.15
            elif rating >= 4.0:
                score += 0.1
            elif rating >= 3.5:
                score += 0.05
        
        return max(0.0, min(1.0, score))
    
    def calculate_platform_reliability_score(self, platform: Platform) -> float:
        """
        计算平台可靠性得分
        
        Args:
            platform: 平台
        
        Returns:
            平台可靠性得分（0-1）
        """
        return self.platform_reliability.get(platform.value, 0.5)
    
    def calculate_total_score(self, price_score: float, sales_score: float, 
                            shop_reputation_score: float, platform_reliability_score: float) -> float:
        """
        计算综合得分
        
        Args:
            price_score: 价格得分
            sales_score: 销量得分
            shop_reputation_score: 店铺信誉得分
            platform_reliability_score: 平台可靠性得分
        
        Returns:
            综合得分（0-1）
        """
        total_score = (
            price_score * self.weights["price"] +
            sales_score * self.weights["sales"] +
            shop_reputation_score * self.weights["shop_reputation"] +
            platform_reliability_score * self.weights["platform_reliability"]
        )
        
        return max(0.0, min(1.0, total_score))
    
    def recommend_products(self, products: List[Product], budget_min: float, 
                          budget_max: float, top_n: int = 10) -> List[RecommendationScore]:
        """
        推荐商品
        
        Args:
            products: 商品列表
            budget_min: 最低预算
            budget_max: 最高预算
            top_n: 返回前N个商品
        
        Returns:
            推荐商品列表（按得分排序）
        """
        recommendations = []
        
        for product in products:
            # 计算各项得分
            price_score = self.calculate_price_score(product.price, budget_min, budget_max)
            sales_score = self.calculate_sales_score(product.sales)
            shop_reputation_score = self.calculate_shop_reputation_score(
                product.shop_type, product.rating
            )
            platform_reliability_score = self.calculate_platform_reliability_score(product.platform)
            
            # 计算综合得分
            total_score = self.calculate_total_score(
                price_score, sales_score, shop_reputation_score, platform_reliability_score
            )
            
            # 创建推荐评分对象
            recommendation = RecommendationScore(
                product=product,
                price_score=price_score,
                sales_score=sales_score,
                shop_reputation_score=shop_reputation_score,
                platform_reliability_score=platform_reliability_score,
                total_score=total_score,
                rank=0  # 稍后设置排名
            )
            
            recommendations.append(recommendation)
        
        # 按综合得分排序
        recommendations.sort(key=lambda x: x.total_score, reverse=True)
        
        # 设置排名
        for i, recommendation in enumerate(recommendations):
            recommendation.rank = i + 1
        
        # 返回前N个商品
        return recommendations[:top_n]
    
    def compare_prices(self, products: List[Product]) -> List[PriceComparison]:
        """
        比较同款商品在不同平台的价格
        
        Args:
            products: 商品列表
        
        Returns:
            价格比较结果列表
        """
        # 按商品标题分组
        title_groups: Dict[str, List[Product]] = {}
        for product in products:
            # 简化的标题匹配（实际应用中可能需要更复杂的匹配算法）
            normalized_title = product.title.strip().lower()
            if normalized_title not in title_groups:
                title_groups[normalized_title] = []
            title_groups[normalized_title].append(product)
        
        comparisons = []
        
        for title, group_products in title_groups.items():
            if len(group_products) < 2:
                continue  # 只有一个平台的商品不需要比较
            
            # 按平台组织商品
            platforms: Dict[Platform, Product] = {}
            for product in group_products:
                platforms[product.platform] = product
            
            # 计算价格信息
            prices = [p.price for p in group_products]
            min_price = min(prices)
            max_price = max(prices)
            
            # 找到最低价格平台
            min_price_product = min(group_products, key=lambda p: p.price)
            min_price_platform = min_price_product.platform
            
            # 计算价格差异
            price_difference = max_price - min_price
            price_difference_percentage = (price_difference / min_price * 100) if min_price > 0 else 0
            
            comparison = PriceComparison(
                product_title=title,
                platforms=platforms,
                min_price=min_price,
                min_price_platform=min_price_platform,
                max_price=max_price,
                price_difference=price_difference,
                price_difference_percentage=price_difference_percentage
            )
            
            comparisons.append(comparison)
        
        # 按价格差异百分比排序（差异最大的排在前面）
        comparisons.sort(key=lambda x: x.price_difference_percentage, reverse=True)
        
        return comparisons

# 创建全局推荐引擎实例
recommendation_engine = RecommendationEngine()