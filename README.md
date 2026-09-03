# 多平台商品推荐Agent

一个智能商品推荐系统，支持淘宝、京东、拼多多等多平台价格对比，为您提供最佳购买建议。

## 功能特性

### 核心功能
- **多平台同款商品价格对比**：同时搜索淘宝、京东、拼多多，比较同款商品价格
- **更准确的商品搜索**：支持商品标题、品牌、型号等精确匹配
- **用户友好的前端UI界面**：提供直观的Web界面，支持交互式搜索和筛选

### 智能推荐
- **多维度评分算法**：综合考虑价格、销量、店铺信誉、平台可靠性等因素
- **预算优化**：根据您的预算范围，智能筛选性价比最高的商品
- **实时数据**：实时获取电商平台最新价格和库存信息

## 快速开始

### 1. 环境要求
- Python 3.10+
- pip包管理器

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 启动服务
```bash
python main.py
```

### 4. 访问应用
打开浏览器访问：http://localhost:8000

## 项目结构

```
taobao_agent/
├── main.py                    # 主入口点
├── taobao_agent.py            # Agent核心逻辑
├── mcp_client.py              # MCP客户端封装
├── recommendation_engine.py   # 推荐算法引擎
├── data_models.py             # 数据模型定义
├── config.py                  # 配置管理
├── requirements.txt           # 依赖管理
├── README.md                  # 项目说明文档
├── frontend/                  # 前端UI相关文件
│   ├── templates/             # HTML模板
│   └── static/                # 静态资源（CSS、JS）
└── api/                       # API服务
    ├── routes.py              # API路由
    └── services.py            # 业务逻辑
```

## API接口

### 搜索商品
```
POST /api/search
Content-Type: application/json

{
  "query": "华为手机",
  "budget_min": 3000,
  "budget_max": 8000,
  "platforms": ["jd", "taobao", "pdd"],
  "top_n": 10
}
```

### 获取商品详情
```
GET /api/product/{platform}/{product_id}
```

### 获取支持的商品类别
```
GET /api/categories
```

### 获取支持的平台
```
GET /api/platforms
```

### 健康检查
```
GET /health
```

## 推荐算法

### 评分维度
1. **价格得分 (40%)**：价格越接近预算中位数，得分越高
2. **销量得分 (30%)**：销量越高，得分越高（对数归一化）
3. **店铺信誉得分 (20%)**：基于店铺类型和评分
4. **平台可靠性得分 (10%)**：基于平台信誉和用户评价

### 计算公式
```
综合得分 = 价格得分 × 0.4 + 销量得分 × 0.3 + 店铺信誉得分 × 0.2 + 平台可靠性得分 × 0.1
```

## 配置说明

### 配置文件
配置文件位于 `config.py`，包含以下配置项：

- **服务器配置**：主机地址、端口号
- **MCP服务器配置**：多平台MCP服务器连接信息
- **推荐算法权重**：各评分维度的权重配置
- **平台配置**：支持的电商平台列表
- **商品类别**：支持的商品类别列表

### 环境变量
可以通过环境变量覆盖配置：
- `HOST`：服务器主机地址
- `PORT`：服务器端口号

## 测试

### 运行单元测试
```bash
python test_mcp_client.py
python test_recommendation.py
python test_api.py
```

### 运行集成测试
```bash
python test_integration.py
```

## 部署

### 开发环境
```bash
python main.py
```

### 生产环境
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Docker部署
```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 技术栈

- **后端框架**：FastAPI
- **MCP客户端**：MCP Python SDK
- **多平台数据源**：best-price-mcp
- **前端技术**：HTML/CSS/JavaScript
- **UI设计**：现代玻璃拟态设计，响应式布局
- **图标库**：Font Awesome 6.4.0
- **字体**：Google Fonts Inter字体
- **数据验证**：Pydantic
- **异步支持**：asyncio

## 开发指南

### 添加新平台支持
1. 在 `config.py` 中添加平台配置
2. 在 `mcp_client.py` 中实现平台特定的数据获取逻辑
3. 在 `data_models.py` 中添加平台枚举值
4. 更新前端UI的平台选择选项

### 自定义推荐算法
1. 修改 `recommendation_engine.py` 中的评分函数
2. 调整 `config.py` 中的权重配置
3. 添加新的评分维度

### 扩展商品类别
1. 在 `config.py` 的 `SUPPORTED_CATEGORIES` 中添加新类别
2. 更新搜索关键词处理逻辑
3. 添加类别特定的搜索优化

## 故障排除

### 常见问题

#### 1. MCP服务器连接失败
**问题**：无法连接到MCP服务器
**解决方案**：
- 检查网络连接
- 验证MCP服务器配置
- 查看日志文件获取详细错误信息

#### 2. 搜索结果为空
**问题**：搜索商品时返回空结果
**解决方案**：
- 检查搜索关键词是否正确
- 调整预算范围
- 尝试不同的平台组合

#### 3. 推荐结果不准确
**问题**：推荐商品不符合预期
**解决方案**：
- 调整推荐算法权重
- 提供更精确的搜索关键词
- 设置更合理的预算范围

#### 4. 前端界面问题
**问题**：界面样式不显示或动画异常
**解决方案**：
- 检查浏览器控制台是否有错误
- 确保网络连接正常（需要加载外部字体和图标库）
- 尝试清除浏览器缓存
- 检查静态文件是否正确配置

### 日志查看
```bash
# 查看应用日志
tail -f app.log

# 查看错误日志
grep "ERROR" app.log
```

## 贡献指南

1. Fork项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

## 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 联系方式

- 项目链接：https://github.com/yourusername/taobao-agent
- 问题反馈：https://github.com/yourusername/taobao-agent/issues

## 致谢

- 感谢 [best-price-mcp](https://pypi.org/project/best-price-mcp/) 提供多平台价格对比功能
- 感谢 [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) 提供MCP协议支持
- 感谢 [FastAPI](https://fastapi.tiangolo.com/) 提供高性能Web框架

---

**注意**：本项目仅用于学习和研究目的，请遵守各电商平台的使用条款和政策。