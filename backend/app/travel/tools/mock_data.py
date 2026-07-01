"""
模拟数据集 - 支持 3 个城市 + 边界情况
（仅供测试参考，工具 handler 已改为仅调用真实 API）
"""
WEATHER_DATA = {
    "杭州": {
        "temperature": "18-24°C",
        "weather": "晴",
        "suitable": True,
        "description": "天气晴好，适合出行"
    },
    "北京": {
        "temperature": "10-18°C",
        "weather": "多云",
        "suitable": True,
        "description": "天气适宜，注意保暖"
    },
    "成都": {
        "temperature": "15-22°C",
        "weather": "阴",
        "suitable": True,
        "description": "天气舒适，适合游玩"
    },
    "拉萨": {
        "temperature": "5-15°C",
        "weather": "晴",
        "suitable": True,
        "description": "高原气候，注意高反"
    }
}

# ========== 景点数据 ==========
ATTRACTIONS = {
    "杭州": [
        {
            "name": "西湖",
            "price": 0,
            "hours": "全天",
            "rating": 4.9,
            "description": "世界文化遗产，免费开放",
            "tags": ["自然风光", "文化遗产", "必游"]
        },
        {
            "name": "灵隐寺",
            "price": 45,
            "hours": "7:00-18:00",
            "rating": 4.7,
            "description": "千年古刹，香火鼎盛",
            "tags": ["宗教文化", "历史古迹"]
        },
        {
            "name": "宋城",
            "price": 280,
            "hours": "10:00-22:00",
            "rating": 4.5,
            "description": "大型主题公园，《宋城千古情》演出",
            "tags": ["主题公园", "演出"]
        },
        {
            "name": "西溪湿地",
            "price": 80,
            "hours": "8:00-17:30",
            "rating": 4.6,
            "description": "城市湿地公园，生态环境优美",
            "tags": ["自然风光", "生态"]
        },
        {
            "name": "千岛湖",
            "price": 150,
            "hours": "8:00-17:00",
            "rating": 4.8,
            "description": "国家5A级景区，湖光山色",
            "tags": ["自然风光", "湖泊"]
        }
    ],
    "北京": [
        {
            "name": "故宫",
            "price": 60,
            "hours": "8:30-17:00",
            "rating": 4.9,
            "description": "世界文化遗产，明清皇宫",
            "tags": ["历史古迹", "文化遗产", "必游"]
        },
        {
            "name": "长城（八达岭）",
            "price": 40,
            "hours": "6:30-19:00",
            "rating": 4.8,
            "description": "世界七大奇迹之一",
            "tags": ["历史古迹", "必游"]
        },
        {
            "name": "颐和园",
            "price": 30,
            "hours": "6:30-18:00",
            "rating": 4.7,
            "description": "皇家园林，世界文化遗产",
            "tags": ["历史古迹", "园林"]
        },
        {
            "name": "天坛",
            "price": 15,
            "hours": "6:00-22:00",
            "rating": 4.6,
            "description": "明清皇帝祭天之所",
            "tags": ["历史古迹", "文化"]
        },
        {
            "name": "鸟巢（国家体育场）",
            "price": 50,
            "hours": "9:00-21:00",
            "rating": 4.4,
            "description": "2008年奥运会主场馆",
            "tags": ["现代建筑", "地标"]
        }
    ],
    "成都": [
        {
            "name": "宽窄巷子",
            "price": 0,
            "hours": "全天",
            "rating": 4.5,
            "description": "成都历史文化街区，免费开放",
            "tags": ["历史街区", "美食", "必游"]
        },
        {
            "name": "锦里",
            "price": 0,
            "hours": "全天",
            "rating": 4.4,
            "description": "三国文化主题街区",
            "tags": ["历史街区", "美食"]
        },
        {
            "name": "大熊猫繁育研究基地",
            "price": 55,
            "hours": "7:30-18:00",
            "rating": 4.8,
            "description": "近距离观赏大熊猫",
            "tags": ["动物", "亲子", "必游"]
        },
        {
            "name": "都江堰",
            "price": 80,
            "hours": "8:00-18:00",
            "rating": 4.7,
            "description": "世界文化遗产，古代水利工程",
            "tags": ["历史古迹", "文化遗产"]
        },
        {
            "name": "青城山",
            "price": 90,
            "hours": "8:00-17:00",
            "rating": 4.6,
            "description": "道教名山，世界文化遗产",
            "tags": ["自然风光", "宗教文化"]
        }
    ]
}

# ========== 酒店数据 ==========
HOTELS = {
    "杭州": [
        {
            "name": "西湖国宾馆",
            "price_per_night": 1200,
            "rating": 4.8,
            "location": "西湖景区内",
            "tags": ["豪华", "景区内", "历史建筑"]
        },
        {
            "name": "全季酒店（西湖店）",
            "price_per_night": 398,
            "rating": 4.5,
            "location": "距西湖 500m",
            "tags": ["中档", "交通便利"]
        },
        {
            "name": "如家快捷酒店",
            "price_per_night": 258,
            "rating": 4.2,
            "location": "市中心",
            "tags": ["经济型", "连锁"]
        }
    ],
    "北京": [
        {
            "name": "北京饭店",
            "price_per_night": 1500,
            "rating": 4.9,
            "location": "天安门广场旁",
            "tags": ["豪华", "地标", "历史建筑"],
            "special": "春节期间已满房"  # 边界情况
        },
        {
            "name": "7天连锁酒店",
            "price_per_night": 299,
            "rating": 4.3,
            "location": "地铁沿线",
            "tags": ["经济型", "交通便利"]
        },
        {
            "name": "汉庭酒店",
            "price_per_night": 328,
            "rating": 4.4,
            "location": "王府井附近",
            "tags": ["经济型", "商圈"]
        }
    ],
    "成都": [
        {
            "name": "成都香格里拉大酒店",
            "price_per_night": 980,
            "rating": 4.7,
            "location": "市中心",
            "tags": ["豪华", "商务"]
        },
        {
            "name": "锦江之星",
            "price_per_night": 268,
            "rating": 4.3,
            "location": "春熙路商圈",
            "tags": ["经济型", "商圈"]
        },
        {
            "name": "如家酒店（宽窄巷子店）",
            "price_per_night": 288,
            "rating": 4.4,
            "location": "宽窄巷子步行 5 分钟",
            "tags": ["经济型", "景区附近"]
        }
    ]
}

# ========== 交通数据 ==========
TRAIN_TICKETS = {
    "杭州-北京": [
        {
            "type": "高铁",
            "train_no": "G20",
            "duration": "5小时30分",
            "price": 538,
            "departure": "08:00",
            "arrival": "13:30"
        },
        {
            "type": "高铁",
            "train_no": "G36",
            "duration": "5小时45分",
            "price": 538,
            "departure": "14:20",
            "arrival": "20:05"
        }
    ],
    "北京-杭州": [
        {
            "type": "高铁",
            "train_no": "G19",
            "duration": "5小时30分",
            "price": 538,
            "departure": "09:00",
            "arrival": "14:30"
        }
    ],
    "杭州-成都": [
        {
            "type": "高铁",
            "train_no": "G1974",
            "duration": "11小时",
            "price": 778,
            "departure": "08:30",
            "arrival": "19:30"
        }
    ],
    "成都-杭州": [
        {
            "type": "高铁",
            "train_no": "G1973",
            "duration": "11小时",
            "price": 778,
            "departure": "09:00",
            "arrival": "20:00"
        }
    ],
    "北京-成都": [
        {
            "type": "高铁",
            "train_no": "G89",
            "duration": "8小时",
            "price": 778,
            "departure": "10:00",
            "arrival": "18:00"
        }
    ],
    "成都-北京": [
        {
            "type": "高铁",
            "train_no": "G90",
            "duration": "8小时",
            "price": 778,
            "departure": "11:00",
            "arrival": "19:00"
        }
    ]
    # 注意：杭州-拉萨 故意不提供数据，用于测试边界情况
}

