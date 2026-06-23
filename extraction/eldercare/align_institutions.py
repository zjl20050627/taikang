# ============================================================
# extraction/eldercare/align_institutions.py
# ============================================================
# 养老机构数据对齐与融合：
#   民政部/民政局种子数据  +  高德 POI 数据
#   → 名称相似度 + 地址匹配 → 融合字段
# ============================================================

import re
from difflib import SequenceMatcher
from typing import List, Dict, Optional, Tuple


def normalize_name(name: str) -> str:
    """标准化机构名称，便于相似度比较"""
    if not name:
        return ""
    name = name.strip()
    # 去除常见后缀
    for suffix in [
        "有限公司", "有限责任公司", "股份有限公司",
        "（民办非企业单位）", "(民办非企业单位)",
        "养老服务中心", "服务中心",
    ]:
        name = name.replace(suffix, "")
    # 去除标点
    name = re.sub(r"[（）()·\-—\s]", "", name)
    return name.lower()


def normalize_address(address: str) -> str:
    """标准化地址"""
    if not address:
        return ""
    address = address.strip()
    address = re.sub(r"\s+", "", address)
    # 统一省市区表述
    address = address.replace("北京市北京", "北京市")
    address = address.replace("上海市上海", "上海市")
    return address


def name_similarity(name_a: str, name_b: str) -> float:
    """计算两个机构名称的相似度（0-1）"""
    na = normalize_name(name_a)
    nb = normalize_name(name_b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.85
    return SequenceMatcher(None, na, nb).ratio()


def address_overlap(addr_a: str, addr_b: str) -> float:
    """计算地址重叠度（基于公共子串）"""
    aa = normalize_address(addr_a)
    ab = normalize_address(addr_b)
    if not aa or not ab:
        return 0.0
    if aa == ab:
        return 1.0
    if aa in ab or ab in aa:
        return 0.8
    # 提取路/街/号等关键片段比较
    tokens_a = set(re.findall(r"[\u4e00-\u9fa5]{2,}|\d+号?", aa))
    tokens_b = set(re.findall(r"[\u4e00-\u9fa5]{2,}|\d+号?", ab))
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def match_score(civil: Dict, amap: Dict) -> float:
    """
    综合匹配得分。
    名称权重 0.6，地址权重 0.3，城市一致 0.1
    """
    ns = name_similarity(civil.get("name", ""), amap.get("name", ""))
    as_ = address_overlap(civil.get("address", ""), amap.get("address", ""))
    city_match = 1.0 if civil.get("city", "")[:2] == amap.get("city", "")[:2] else 0.0

    return ns * 0.6 + as_ * 0.3 + city_match * 0.1


def find_best_amap_match(
    civil_inst: Dict,
    amap_pois: List[Dict],
    threshold: float = 0.55,
) -> Optional[Tuple[Dict, float]]:
    """为民政种子数据找到最佳高德 POI 匹配"""
    best_poi = None
    best_score = 0.0

    civil_city = civil_inst.get("city", "")
    for poi in amap_pois:
        if civil_city and poi.get("city") and civil_city[:2] != poi["city"][:2]:
            continue

        score = match_score(civil_inst, poi)
        if score > best_score:
            best_score = score
            best_poi = poi

    if best_score >= threshold:
        return best_poi, best_score
    return None


def merge_institution(civil: Dict, amap: Dict = None, match_score_val: float = 0.0) -> Dict:
    """
    融合民政种子数据与高德 POI 数据。
    民政数据为主，高德补充经纬度、电话、POI类型。
    """
    merged = {
        "id": civil.get("id", ""),
        "name": civil.get("name", ""),
        "type": civil.get("type", "养老机构"),
        "city": civil.get("city", ""),
        "district": civil.get("district", ""),
        "address": civil.get("address", ""),
        "phone": civil.get("phone", ""),
        "location": civil.get("location"),
        "services": civil.get("services", []),
        "admission_requirements": civil.get("admission_requirements", ""),
        "monthly_fee": civil.get("monthly_fee", ""),
        "bed_count": civil.get("bed_count"),
        "rating": civil.get("rating", ""),
        "source": civil.get("source", "民政部门公开信息"),
        "data_sources": ["civil_affairs"],
        "amap_match_score": None,
    }

    if amap:
        merged["data_sources"].append("amap")
        merged["amap_match_score"] = round(match_score_val, 3)

        # 高德补充/覆盖字段（仅当民政数据缺失或高德更详细时）
        if amap.get("location") and not merged.get("location"):
            merged["location"] = amap["location"]
        if amap.get("phone") and not merged.get("phone"):
            merged["phone"] = amap["phone"]
        if amap.get("district") and not merged.get("district"):
            merged["district"] = amap["district"]
        if amap.get("address") and len(amap["address"]) > len(merged.get("address", "")):
            merged["address_detail"] = amap["address"]

        merged["amap_id"] = amap.get("amap_id", "")
        merged["amap_type"] = amap.get("type", "")

    return merged


def amap_poi_to_institution(poi: Dict, index: int) -> Dict:
    """将未匹配的高德 POI 转为机构记录"""
    return {
        "id": f"amap_{poi.get('city', 'unknown')[:2]}_{index:04d}",
        "name": poi.get("name", ""),
        "type": _infer_type_from_poi(poi),
        "city": poi.get("city", ""),
        "district": poi.get("district", ""),
        "address": poi.get("address", ""),
        "phone": poi.get("phone", ""),
        "location": poi.get("location"),
        "services": [],
        "admission_requirements": "",
        "monthly_fee": "",
        "bed_count": None,
        "rating": "",
        "source": "高德地图POI",
        "data_sources": ["amap"],
        "amap_id": poi.get("amap_id", ""),
        "amap_type": poi.get("type", ""),
        "amap_match_score": None,
    }


def _infer_type_from_poi(poi: Dict) -> str:
    """根据 POI 类型和关键词推断机构类型"""
    name = poi.get("name", "")
    poi_type = poi.get("type", "")
    keyword = poi.get("keyword", "")

    if "护理院" in name or "护理院" in keyword:
        return "护理院"
    if "老年公寓" in name or "公寓" in keyword:
        return "老年公寓"
    if "社区" in name or "照料中心" in name:
        return "社区养老照料中心"
    if "社会福利" in name:
        return "公办养老机构"
    if "养老" in poi_type or "养老院" in keyword:
        return "养老机构"
    return "养老机构"


def align_and_merge(
    civil_institutions: List[Dict],
    amap_pois: List[Dict],
    match_threshold: float = 0.55,
) -> Dict:
    """
    对齐并融合两套数据源。

    Returns:
        {
            "merged": [...],       # 融合后的机构列表
            "match_report": {...}  # 对齐统计报告
        }
    """
    merged_list = []
    matched_amap_ids = set()
    match_details = []

    # 第一轮：民政种子 ← 匹配 → 高德 POI
    for civil in civil_institutions:
        result = find_best_amap_match(civil, amap_pois, threshold=match_threshold)
        if result:
            amap_poi, score = result
            merged = merge_institution(civil, amap_poi, score)
            matched_amap_ids.add(amap_poi.get("amap_id", ""))
            match_details.append({
                "civil_name": civil["name"],
                "amap_name": amap_poi["name"],
                "score": round(score, 3),
                "status": "matched",
            })
        else:
            merged = merge_institution(civil)
            match_details.append({
                "civil_name": civil["name"],
                "amap_name": None,
                "score": 0,
                "status": "civil_only",
            })
        merged_list.append(merged)

    # 第二轮：未匹配的高德 POI 作为补充入库
    unmatched_count = 0
    for i, poi in enumerate(amap_pois):
        poi_id = poi.get("amap_id", "")
        if poi_id and poi_id in matched_amap_ids:
            continue
        # 也检查名称是否已被覆盖
        already_covered = any(
            name_similarity(poi["name"], m["name"]) > 0.8
            for m in merged_list
        )
        if already_covered:
            continue

        merged_list.append(amap_poi_to_institution(poi, unmatched_count))
        unmatched_count += 1
        match_details.append({
            "civil_name": None,
            "amap_name": poi["name"],
            "score": 0,
            "status": "amap_only",
        })

    report = {
        "total_merged": len(merged_list),
        "civil_affairs_count": len(civil_institutions),
        "amap_poi_count": len(amap_pois),
        "matched_pairs": sum(1 for d in match_details if d["status"] == "matched"),
        "civil_only": sum(1 for d in match_details if d["status"] == "civil_only"),
        "amap_only": sum(1 for d in match_details if d["status"] == "amap_only"),
        "match_details": match_details,
    }

    return {"merged": merged_list, "match_report": report}
