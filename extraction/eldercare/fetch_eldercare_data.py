# ============================================================
# extraction/eldercare/fetch_eldercare_data.py
# ============================================================
# 养老机构数据获取主脚本
#
# 数据来源：
#   1. 民政部/地方民政局公开种子数据（seed_institutions.json）
#   2. 高德地图 POI API（需配置 AMAP_API_KEY）
#   3. 对齐融合后输出 institutions.json
#
# 使用方法：
#   python extraction/eldercare/fetch_eldercare_data.py
#   python extraction/eldercare/fetch_eldercare_data.py --cities 北京市 上海市
#   python extraction/eldercare/fetch_eldercare_data.py --skip-amap   # 仅用种子数据
# ============================================================

import os
import sys
import json
import argparse
from datetime import date

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from amap_client import AmapPOIClient, save_amap_pois, CITY_ADCODE
from align_institutions import align_and_merge


def load_seed_institutions(seed_path: str) -> list:
    """加载民政种子数据"""
    with open(seed_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    institutions = data.get("institutions", [])
    print(f"[OK] 加载民政种子数据: {len(institutions)} 条")
    return institutions


def load_cached_amap(cache_path: str) -> list:
    """加载已缓存的高德 POI 数据"""
    if not os.path.exists(cache_path):
        return []
    with open(cache_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    pois = data.get("pois", [])
    print(f"[OK] 加载缓存高德 POI: {len(pois)} 条")
    return pois


def save_institutions(institutions: list, report: dict, output_path: str):
    """保存融合后的养老机构数据"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    output = {
        "metadata": {
            "version": "1.0",
            "description": "保险+医养跨域知识图谱 - 养老机构结构化数据",
            "data_nature": "民政部门公开信息 + 高德地图POI融合",
            "total_institutions": len(institutions),
            "last_updated": str(date.today()),
            "alignment_report": {
                "civil_affairs_count": report.get("civil_affairs_count", 0),
                "amap_poi_count": report.get("amap_poi_count", 0),
                "matched_pairs": report.get("matched_pairs", 0),
                "civil_only": report.get("civil_only", 0),
                "amap_only": report.get("amap_only", 0),
            },
        },
        "institutions": institutions,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[OK] 养老机构数据已保存: {output_path}")
    print(f"     共 {len(institutions)} 条机构记录")


def save_alignment_report(report: dict, report_path: str):
    """保存对齐详情报告"""
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"[OK] 对齐报告已保存: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="养老机构数据获取与融合")
    parser.add_argument(
        "--cities",
        nargs="+",
        default=None,
        help="指定检索城市，默认全部配置城市",
    )
    parser.add_argument(
        "--skip-amap",
        action="store_true",
        help="跳过高德 API，仅使用民政种子数据",
    )
    parser.add_argument(
        "--max-per-keyword",
        type=int,
        default=15,
        help="每个关键词每城最多获取 POI 数",
    )
    parser.add_argument(
        "--match-threshold",
        type=float,
        default=0.55,
        help="名称+地址对齐阈值（0-1）",
    )
    args = parser.parse_args()

    seed_path = os.path.join(os.path.dirname(__file__), "seed_institutions.json")
    raw_dir = os.path.join(BASE_DIR, "data", "raw", "elderly")
    processed_dir = os.path.join(BASE_DIR, "data", "processed", "eldercare")
    amap_cache = os.path.join(raw_dir, "amap_pois.json")
    output_path = os.path.join(processed_dir, "institutions.json")
    report_path = os.path.join(processed_dir, "alignment_report.json")

    print("=" * 55)
    print("  养老机构数据获取与融合")
    print("=" * 55)

    # Step 1: 加载民政种子数据
    civil_institutions = load_seed_institutions(seed_path)

    # Step 2: 获取高德 POI（或加载缓存）
    amap_pois = []
    if not args.skip_amap:
        client = AmapPOIClient()
        if client.is_available():
            cities = args.cities or list(CITY_ADCODE.keys())
            print(f"[INFO] 开始高德 POI 检索，城市: {', '.join(cities)}")
            amap_pois = client.search_multiple_cities(
                cities=cities,
                max_per_keyword=args.max_per_keyword,
            )
            save_amap_pois(amap_pois, amap_cache)
        else:
            print("[INFO] 未配置 AMAP_API_KEY，尝试加载缓存...")
            amap_pois = load_cached_amap(amap_cache)
            if not amap_pois:
                print("[INFO] 无缓存数据，将仅使用民政种子数据")
    else:
        print("[INFO] 已指定 --skip-amap，跳过高德检索")

    # Step 3: 对齐融合
    print("[INFO] 开始对齐融合...")
    result = align_and_merge(
        civil_institutions=civil_institutions,
        amap_pois=amap_pois,
        match_threshold=args.match_threshold,
    )

    # Step 4: 保存结果
    save_institutions(result["merged"], result["match_report"], output_path)
    save_alignment_report(result["match_report"], report_path)

    # 打印摘要
    report = result["match_report"]
    print()
    print("-" * 55)
    print("  对齐融合摘要")
    print("-" * 55)
    print(f"  民政种子数据:   {report['civil_affairs_count']} 条")
    print(f"  高德 POI 数据:   {report['amap_poi_count']} 条")
    print(f"  成功匹配融合:   {report['matched_pairs']} 对")
    print(f"  仅民政数据:     {report['civil_only']} 条")
    print(f"  仅高德补充:     {report['amap_only']} 条")
    print(f"  最终机构总数:   {report['total_merged']} 条")
    print("=" * 55)


if __name__ == "__main__":
    main()
