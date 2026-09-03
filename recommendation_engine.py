"""
推荐算法模块
实现多维度评分算法，包括价格得分、销量得分、店铺信誉得分和平台可靠性得分
"""

import math
import re
from difflib import SequenceMatcher
from typing import List, Dict, Optional, Set
from data_models import Product, Platform, RecommendationScore, PriceComparison
from config import config

class RecommendationEngine:
    """推荐引擎类"""

    def __init__(self):
        self.weights = config.RECOMMENDATION_WEIGHTS
        self.price_params = config.PRICE_SCORE_PARAMS
        self.sales_params = config.SALES_SCORE_PARAMS
        self.platform_reliability = config.PLATFORM_RELIABILITY
        self.match_params = config.FUZZY_MATCH_PARAMS
    
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
    
    def _normalize_title(self, title: str) -> str:
        """
        清洗商品标题，为相似度计算做准备

        转小写、单位归一、品牌别名统一、去标点、去营销噪声词

        Args:
            title: 原始商品标题

        Returns:
            清洗后的标题
        """
        if not title:
            return ""
        text = title.lower()
        # 单位归一：512GB -> 512g，避免 256GB 与 256G 这类字面差异
        text = re.sub(r'(\d+)\s*gb', r'\1g', text)
        # 品牌别名统一为中文（apple -> 苹果），便于跨语言匹配
        for en, zh in self.match_params["brand_aliases"].items():
            text = text.replace(en, zh)
        # 去除标点：替换为空格而非删除，防止 "12+512G" 粘成 "12512G" 破坏数字结构
        text = re.sub(r'[^\w一-鿿]+', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        # 去除营销噪声词（店铺/服务信息在其它字段体现，对同款判断是干扰）
        for word in self.match_params["noise_words"]:
            text = text.replace(word, "")
        return text

    def _extract_tokens(self, normalized_title: str) -> Set[str]:
        """
        提取标题特征词集合

        英文/数字连续段（型号如 mate70、512g）+ 中文 2-gram，
        无需分词库即可刻画中文商品标题特征

        Args:
            normalized_title: 清洗后的标题

        Returns:
            特征词集合
        """
        tokens = set(re.findall(r'[a-z0-9]+', normalized_title))
        for seg in re.findall(r'[一-鿿]+', normalized_title):
            if len(seg) == 1:
                tokens.add(seg)
            else:
                for i in range(len(seg) - 1):
                    tokens.add(seg[i:i + 2])
        return tokens

    def _capacity_numbers(self, normalized_title: str) -> Set[str]:
        """
        提取容量/配置数字（如 256g -> 256），用于检测配置冲突

        只取2位及以上数字，避免把 '5G手机' 中的 5G 误判为容量

        Args:
            normalized_title: 清洗后的标题

        Returns:
            容量数字集合
        """
        return set(re.findall(r'(\d{2,})g', normalized_title))

    def calculate_title_similarity(self, title_a: str, title_b: str) -> float:
        """
        计算两个商品标题的相似度（0-1）

        组合「字符序列相似度」与「关键词重合度」，并对容量配置冲突做惩罚

        Args:
            title_a: 标题A
            title_b: 标题B

        Returns:
            相似度得分（0-1）
        """
        norm_a = self._normalize_title(title_a)
        norm_b = self._normalize_title(title_b)
        if not norm_a or not norm_b:
            return 0.0
        if norm_a == norm_b:
            return 1.0

        # 字符序列相似度（difflib，标准库零依赖）
        seq_sim = SequenceMatcher(None, norm_a, norm_b).ratio()
        # 关键词重合度（Jaccard 系数）
        tokens_a = self._extract_tokens(norm_a)
        tokens_b = self._extract_tokens(norm_b)
        token_sim = (len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
                     if tokens_a and tokens_b else 0.0)

        similarity = (seq_sim * self.match_params["sequence_weight"] +
                      token_sim * self.match_params["token_weight"])

        # 容量/配置冲突惩罚：仅当两边都标了容量且「完全无共同容量」时才罚
        # （只要有一个共同容量就可能是同款；完全无重叠才是强冲突信号）
        cap_a = self._capacity_numbers(norm_a)
        cap_b = self._capacity_numbers(norm_b)
        if cap_a and cap_b and cap_a.isdisjoint(cap_b):
            similarity *= self.match_params["capacity_conflict_penalty"]

        return similarity

    def compare_prices(self, products: List[Product]) -> List[PriceComparison]:
        """
        比较同款商品在不同平台的价格（模糊匹配版）

        使用标题相似度对商品聚类，相似度超过阈值即视为同款商品，
        从而识别出不同标题写法但实为同一款的商品

        Args:
            products: 商品列表

        Returns:
            价格比较结果列表
        """
        threshold = self.match_params["similarity_threshold"]

        # 贪心聚类：每个商品归入第一个相似度达标的组，否则新建一组
        # 以「组内第一个商品标题」作为该组代表进行比较，复杂度约 O(N×组数)
        groups: List[List[Product]] = []
        group_representatives: List[str] = []

        for product in products:
            matched = False
            for idx, rep_title in enumerate(group_representatives):
                if self.calculate_title_similarity(product.title, rep_title) >= threshold:
                    groups[idx].append(product)
                    matched = True
                    break
            if not matched:
                groups.append([product])
                group_representatives.append(product.title)

        comparisons = []

        for group_products in groups:
            if len(group_products) < 2:
                continue  # 只有一个平台的商品不需要比较

            # 按平台组织商品（同一平台若有多个匹配商品，保留价格更低者）
            platforms: Dict[Platform, Product] = {}
            for product in group_products:
                if (product.platform not in platforms
                        or product.price < platforms[product.platform].price):
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
                product_title=group_products[0].title,  # 用组内代表商品的原始标题展示
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