"""
默认配置
"""
import os
from pydantic import BaseModel
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 数据目录（旅行 Agent 用户偏好配置）
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data",
    "travel",
)


class Settings(BaseModel):
    """配置模型"""
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model_name: str = os.getenv("MODEL_NAME", "gpt-4o-mini")
    amap_api_key: str = os.getenv("AMAP_API_KEY", "")
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
    juhe_train_api_key: str = os.getenv("JUHE_TRAIN_API_KEY", "")
    juhe_flight_api_key: str = os.getenv("JUHE_FLIGHT_API_KEY", "")
    http_timeout_seconds: int = int(os.getenv("HTTP_TIMEOUT_SECONDS", "10"))
    tavily_max_results: int = int(os.getenv("TAVILY_MAX_RESULTS", "5"))
    max_rounds: int = 3


# 默认配置（向后兼容）
DEFAULT_SETTINGS = {
    "llm_api_key": "",
    "llm_base_url": "https://api.openai.com/v1",
    "llm_model": "gpt-4o-mini",
    "system_prompt": """你是一个智能旅行规划助手，使用 ReAct（Reasoning + Acting）框架进行决策。

你拥有以下工具：
- get_weather: 查询城市天气
- search_attractions: 搜索城市景点
- search_hotels: 搜索酒店
- search_transport: 查询交通方式
- search_food_recommendations: 搜索当地美食推荐（网页摘要，含小红书参考）
- calculate: 执行数学计算

默认规划要求：
- 每份完整行程必须包含每日用餐/美食安排（午餐、晚餐或特色小吃）
- 第 1 轮 Observe 已自动获取目的地天气与美食参考，请优先采用并写入最终方案

每一轮你需要：
1. 观察环境（已通过工具获取数据）
2. 分析数据并制定策略
3. 如果需要，执行操作（调用工具）
4. 验证操作结果

请用中文回复。思考要简洁但要有逻辑，体现 ReAct 的推理链条。""",
    "max_rounds": 3
}
