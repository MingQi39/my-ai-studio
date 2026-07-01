"""
内置工具实现
注册 6 个内置工具：get_weather, search_attractions, search_hotels, search_transport, search_food_recommendations, calculate

数据来源：
- 高德 Web 服务：天气、景点/酒店 POI、驾车路线
- 聚合数据 Juhe：高铁班次、航班时刻与票价
- Tavily：Juhe 不可用时的交通信息兜底搜索；美食推荐（含小红书关键词）网页摘要
"""
import json
import re

from app.travel.config.manager import get_settings
from app.travel.services.amap_client import AMapClient
from app.travel.services.exceptions import ExternalAPIError
from app.travel.services.juhe_client import JuheClient, default_travel_date
from app.travel.services.tavily_client import TavilyClient
from app.travel.services.tool_registry import ToolsRegistry


def _require_amap(settings) -> AMapClient | None:
    if not settings.amap_api_key:
        return None
    return AMapClient(settings.amap_api_key, timeout=settings.http_timeout_seconds)


def _weather_suitable(desc: str) -> bool:
    return not any(k in desc for k in ["雨", "雪", "雷", "台风"])


def _filter_by_price(
    items: list[dict],
    max_price: int | None,
    price_key: str,
) -> tuple[list[dict], list[str]]:
    if max_price is None:
        return items, []

    warnings: list[str] = []
    matched: list[dict] = []
    unknown: list[dict] = []

    for item in items:
        price = item.get(price_key)
        if isinstance(price, (int, float)):
            if price <= max_price:
                matched.append(item)
        else:
            unknown.append(item)

    if unknown:
        warnings.append(f"{len(unknown)} 条结果高德未返回价格，未参与价格筛选")
        matched.extend(unknown)

    return matched, warnings


async def get_weather_handler(city: str, date: str = None) -> str:
    """查询城市天气"""
    settings = get_settings()
    client = _require_amap(settings)
    if not client:
        return json.dumps({"error": "未配置 AMAP_API_KEY，无法查询实时天气"}, ensure_ascii=False)

    try:
        weather = await client.get_weather(city=city, date=date)
    except ExternalAPIError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    desc = weather.get("weather", "")
    return json.dumps({
        "city": weather.get("city", city),
        "date": weather.get("date", date or "今天"),
        "temperature": weather.get("temperature"),
        "weather": weather.get("weather"),
        "humidity": weather.get("humidity"),
        "wind_direction": weather.get("wind_direction"),
        "wind_power": weather.get("wind_power"),
        "suitable_for_travel": _weather_suitable(desc),
        "source": "amap",
    }, ensure_ascii=False)


async def search_attractions_handler(city: str, budget: int = None) -> str:
    """搜索城市景点"""
    settings = get_settings()
    client = _require_amap(settings)
    if not client:
        return json.dumps({"error": "未配置 AMAP_API_KEY，无法查询景点"}, ensure_ascii=False)

    try:
        attractions = await client.search_attractions(city=city, limit=10, enrich_details=True)
    except ExternalAPIError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    attractions, price_warnings = _filter_by_price(attractions, budget, "price")
    if not attractions:
        return json.dumps({"error": "未找到符合条件的景点", "warnings": price_warnings}, ensure_ascii=False)

    geo = await client.geocode_city(city)
    return json.dumps({
        "city": geo.get("city", city),
        "count": len(attractions),
        "attractions": attractions[:5],
        "source": "amap",
        "warnings": price_warnings,
    }, ensure_ascii=False)


async def search_hotels_handler(city: str, price_max: int = None) -> str:
    """搜索酒店"""
    settings = get_settings()
    client = _require_amap(settings)
    if not client:
        return json.dumps({"error": "未配置 AMAP_API_KEY，无法查询酒店"}, ensure_ascii=False)

    try:
        hotels = await client.search_hotels(city=city, limit=10, enrich_details=True)
    except ExternalAPIError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    hotels, price_warnings = _filter_by_price(hotels, price_max, "price_per_night")
    if not hotels:
        return json.dumps({"error": "未找到符合价格的酒店", "warnings": price_warnings}, ensure_ascii=False)

    geo = await client.geocode_city(city)
    return json.dumps({
        "city": geo.get("city", city),
        "count": len(hotels),
        "hotels": hotels[:5],
        "source": "amap",
        "warnings": price_warnings,
    }, ensure_ascii=False)


def _format_duration(duration_s: int) -> str:
    hours, remainder = divmod(duration_s, 3600)
    minutes = remainder // 60
    return f"{hours}小时{minutes}分" if hours else f"{minutes}分钟"


async def search_transport_handler(from_city: str, to_city: str, date: str = None) -> str:
    """查询交通方式"""
    settings = get_settings()
    options: list[dict] = []
    warnings: list[str] = []
    travel_date = default_travel_date(date)

    if settings.juhe_train_api_key or settings.juhe_flight_api_key:
        juhe = JuheClient(
            train_api_key=settings.juhe_train_api_key,
            flight_api_key=settings.juhe_flight_api_key,
            timeout=settings.http_timeout_seconds,
        )
        if settings.juhe_train_api_key:
            try:
                options.extend(await juhe.query_trains(from_city, to_city, travel_date))
            except ExternalAPIError as e:
                warnings.append(f"火车票查询: {e}")
        else:
            warnings.append("未配置 JUHE_TRAIN_API_KEY，无法查询高铁")

        if settings.juhe_flight_api_key:
            try:
                options.extend(await juhe.query_flights(from_city, to_city, travel_date))
            except ExternalAPIError as e:
                warnings.append(f"航班查询: {e}")
        else:
            warnings.append("未配置 JUHE_FLIGHT_API_KEY，无法查询航班")
    else:
        warnings.append("未配置 JUHE_TRAIN_API_KEY / JUHE_FLIGHT_API_KEY")

    amap = _require_amap(settings)
    if amap:
        try:
            driving = await amap.plan_driving(from_city=from_city, to_city=to_city)
            options.append({
                **driving,
                "duration": _format_duration(driving.get("duration_s", 0)),
                "distance_km": round(driving.get("distance_m", 0) / 1000, 1),
            })
        except ExternalAPIError as e:
            warnings.append(f"高德驾车路线: {e}")
    else:
        warnings.append("未配置 AMAP_API_KEY，无法查询驾车路线")

    has_structured = any(item.get("mode") in ("train", "flight") for item in options)
    if settings.tavily_api_key and not has_structured:
        tavily_client = TavilyClient(
            settings.tavily_api_key,
            timeout=settings.http_timeout_seconds,
            max_results=settings.tavily_max_results,
        )
        try:
            web_results = await tavily_client.search(
                f"{from_city} 到 {to_city} 高铁 动车 飞机 交通 时长 票价 {travel_date}"
            )
            for item in web_results[:5]:
                options.append({
                    "mode": "web_reference",
                    "title": item.get("title"),
                    "content": item.get("content"),
                    "url": item.get("url"),
                    "score": item.get("score"),
                    "source": "tavily",
                })
        except ExternalAPIError as e:
            warnings.append(f"Tavily 搜索失败: {e}")

    if not options:
        return json.dumps({
            "error": f"暂无 {from_city} 到 {to_city} 的可用交通信息",
            "date": travel_date,
            "warnings": warnings,
        }, ensure_ascii=False)

    return json.dumps({
        "from": from_city,
        "to": to_city,
        "date": travel_date,
        "options": options,
        "warnings": warnings,
    }, ensure_ascii=False)


async def search_food_recommendations_handler(
    city: str,
    area: str | None = None,
    cuisine: str | None = None,
) -> str:
    """通过 Tavily 搜索当地美食推荐（含小红书相关网页摘要）"""
    settings = get_settings()
    if not settings.tavily_api_key:
        return json.dumps({"error": "未配置 TAVILY_API_KEY，无法搜索美食推荐"}, ensure_ascii=False)

    query_parts = [city]
    if area:
        query_parts.append(area)
    if cuisine:
        query_parts.append(cuisine)
    query_parts.extend(["美食", "推荐", "小红书"])
    query = " ".join(query_parts)

    tavily_client = TavilyClient(
        settings.tavily_api_key,
        timeout=settings.http_timeout_seconds,
        max_results=settings.tavily_max_results,
    )
    try:
        web_results = await tavily_client.search(query)
    except ExternalAPIError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    if not web_results:
        return json.dumps({
            "error": f"未找到 {city} 相关美食推荐",
            "city": city,
            "query": query,
        }, ensure_ascii=False)

    recommendations = [
        {
            "title": item.get("title"),
            "summary": item.get("content"),
            "url": item.get("url"),
            "score": item.get("score"),
            "source": "tavily",
        }
        for item in web_results[: settings.tavily_max_results]
    ]

    return json.dumps({
        "city": city,
        "area": area,
        "cuisine": cuisine,
        "query": query,
        "count": len(recommendations),
        "recommendations": recommendations,
        "disclaimer": "以上来自网页搜索摘要（含小红书相关内容），仅供参考，建议交叉验证后再纳入行程",
        "source": "tavily",
    }, ensure_ascii=False)


async def calculate_handler(expression: str) -> str:
    """安全的数学计算"""
    allowed_chars = set("0123456789+-*/()., ")
    if not all(c in allowed_chars for c in expression):
        return json.dumps({"error": "表达式包含非法字符"}, ensure_ascii=False)

    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return json.dumps({"expression": expression, "result": result}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"计算失败: {str(e)}"}, ensure_ascii=False)


def register_builtin_tools(registry: ToolsRegistry):
    """注册所有内置工具"""

    registry.register(
        name="get_weather",
        description="查询指定城市的实时天气（高德 API）",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称"},
                "date": {"type": "string", "description": "日期（可选，如 2025-07-01）"},
            },
            "required": ["city"],
        },
        handler=get_weather_handler,
    )

    registry.register(
        name="search_attractions",
        description="搜索城市真实景点 POI（高德 API），budget 按高德返回的门票/人均消费筛选",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称"},
                "budget": {"type": "integer", "description": "预算上限（可选）"},
            },
            "required": ["city"],
        },
        handler=search_attractions_handler,
    )

    registry.register(
        name="search_hotels",
        description="搜索城市真实酒店 POI（高德 API），price_max 按高德返回的人均/参考价筛选",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称"},
                "price_max": {"type": "integer", "description": "每晚最高价格（可选）"},
            },
            "required": ["city"],
        },
        handler=search_hotels_handler,
    )

    registry.register(
        name="search_transport",
        description="查询两城交通：高铁/航班班次（聚合数据 Juhe）+ 驾车路线（高德）；date 默认今天",
        parameters={
            "type": "object",
            "properties": {
                "from_city": {"type": "string", "description": "出发城市"},
                "to_city": {"type": "string", "description": "目的地城市"},
                "date": {"type": "string", "description": "出发日期（可选，YYYY-MM-DD，默认今天）"},
            },
            "required": ["from_city", "to_city"],
        },
        handler=search_transport_handler,
    )

    registry.register(
        name="search_food_recommendations",
        description="搜索当地美食推荐（Tavily 网页摘要，含小红书关键词）；返回种草/避雷类参考信息，非结构化 POI",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称"},
                "area": {"type": "string", "description": "区域或商圈（可选，如 西湖、春熙路）"},
                "cuisine": {"type": "string", "description": "菜系或口味偏好（可选，如 火锅、小吃）"},
            },
            "required": ["city"],
        },
        handler=search_food_recommendations_handler,
    )

    registry.register(
        name="calculate",
        description="执行数学计算（支持加减乘除、括号）",
        parameters={
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "数学表达式，如 '258*3+45'"},
            },
            "required": ["expression"],
        },
        handler=calculate_handler,
    )
