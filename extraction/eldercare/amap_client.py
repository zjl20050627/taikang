# ============================================================
# extraction/eldercare/amap_client.py
# ============================================================
# 高德地图 POI 检索客户端：批量获取养老机构名称、地址、经纬度、电话
#
# 使用前请在 .env 中配置：
#   AMAP_API_KEY=你的高德Web服务Key
#
# 申请地址：https://lbs.amap.com/api/webservice/guide/api/search
# ============================================================

import os
import time
import json
import requests
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

# 高德城市编码（adcode），用于区域检索
CITY_ADCODE = {
    "北京市": "110000",
    "上海市": "310000",
    "深圳市": "440300",
    "广州市": "440100",
    "苏州市": "320500",
    "杭州市": "330100",
    "成都市": "510100",
    "武汉市": "420100",
}

# POI 检索关键词
POI_KEYWORDS = ["养老院", "护理院", "老年公寓", "养老社区", "社会福利院"]


class AmapPOIClient:
    """高德地图 POI 检索客户端"""

    BASE_URL = "https://restapi.amap.com/v3/place/text"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("AMAP_API_KEY", "")
        if not self.api_key:
            print("[WARN] 未配置 AMAP_API_KEY，高德 POI 检索将跳过")
        else:
            print(f"[OK] 高德 POI 客户端已初始化")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def search_poi(
        self,
        keyword: str,
        city: str,
        page: int = 1,
        offset: int = 20,
    ) -> List[Dict]:
        """
        按关键词和城市检索 POI。

        Args:
            keyword: 检索词，如「养老院」
            city: 城市名或 adcode
            page: 页码（从1开始）
            offset: 每页条数（最大25）

        Returns:
            POI 列表
        """
        if not self.api_key:
            return []

        adcode = CITY_ADCODE.get(city, city)
        params = {
            "key": self.api_key,
            "keywords": keyword,
            "city": adcode,
            "citylimit": "true",
            "offset": min(offset, 25),
            "page": page,
            "extensions": "all",
            "output": "json",
        }

        try:
            resp = requests.get(self.BASE_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") != "1":
                print(f"[WARN] 高德 API 返回错误: {data.get('info', 'unknown')}")
                return []

            pois = []
            for poi in data.get("pois", []):
                location = poi.get("location", "")
                lng, lat = None, None
                if location and "," in location:
                    parts = location.split(",")
                    lng, lat = float(parts[0]), float(parts[1])

                pois.append({
                    "amap_id": poi.get("id", ""),
                    "name": poi.get("name", ""),
                    "type": poi.get("type", ""),
                    "address": poi.get("address", ""),
                    "city": city,
                    "district": poi.get("adname", ""),
                    "location": {"lng": lng, "lat": lat} if lng else None,
                    "phone": poi.get("tel", ""),
                    "business_area": poi.get("business_area", ""),
                    "source": "高德地图POI",
                    "keyword": keyword,
                })
            return pois

        except requests.RequestException as e:
            print(f"[ERROR] 高德 API 请求失败: {e}")
            return []

    def search_city_all_keywords(
        self,
        city: str,
        max_per_keyword: int = 20,
        delay_seconds: float = 0.3,
    ) -> List[Dict]:
        """
        对单个城市，用所有关键词检索并去重。

        Args:
            city: 城市名称
            max_per_keyword: 每个关键词最多获取条数
            delay_seconds: 请求间隔（避免触发限流）

        Returns:
            去重后的 POI 列表
        """
        all_pois: Dict[str, Dict] = {}

        for keyword in POI_KEYWORDS:
            pages_needed = (max_per_keyword + 24) // 25
            collected = 0

            for page in range(1, pages_needed + 1):
                pois = self.search_poi(keyword, city, page=page, offset=25)
                if not pois:
                    break

                for poi in pois:
                    key = poi.get("amap_id") or f"{poi['name']}_{poi.get('address', '')}"
                    if key not in all_pois:
                        all_pois[key] = poi

                collected += len(pois)
                if collected >= max_per_keyword:
                    break

                time.sleep(delay_seconds)

            time.sleep(delay_seconds)

        result = list(all_pois.values())
        print(f"  [{city}] 关键词检索完成，共 {len(result)} 条 POI")
        return result

    def search_multiple_cities(
        self,
        cities: List[str] = None,
        max_per_keyword: int = 15,
    ) -> List[Dict]:
        """批量检索多个城市"""
        if cities is None:
            cities = list(CITY_ADCODE.keys())

        all_results = []
        for city in cities:
            pois = self.search_city_all_keywords(city, max_per_keyword=max_per_keyword)
            all_results.extend(pois)
            time.sleep(0.5)

        print(f"[OK] 高德 POI 检索完成，共 {len(all_results)} 条")
        return all_results


def save_amap_pois(pois: List[Dict], output_path: str):
    """保存高德 POI 原始数据"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"total": len(pois), "pois": pois}, f, ensure_ascii=False, indent=2)
    print(f"[OK] 高德 POI 数据已保存: {output_path}")


if __name__ == "__main__":
    client = AmapPOIClient()
    if client.is_available():
        pois = client.search_multiple_cities(cities=["北京市", "上海市"], max_per_keyword=10)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        out = os.path.join(base_dir, "data", "raw", "elderly", "amap_pois.json")
        save_amap_pois(pois, out)
    else:
        print("请在 .env 中设置 AMAP_API_KEY 后重试")
