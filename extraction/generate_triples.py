import os
import json
import re
from typing import List, Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _data_path(*parts: str) -> str:
    return os.path.join(BASE_DIR, "data", *parts)


def load_extracted_data() -> Dict[str, Any]:
    """加载医疗域已提取的数据"""
    data_dir = _data_path("processed", "medical")
    extracted_data = {}

    commercial_path = os.path.join(data_dir, "commercial_drug_catalog.json")
    if os.path.exists(commercial_path):
        with open(commercial_path, "r", encoding="utf-8") as f:
            extracted_data["commercial_drugs"] = json.load(f)

    icd11_path = os.path.join(data_dir, "icd11_diseases.json")
    if os.path.exists(icd11_path):
        with open(icd11_path, "r", encoding="utf-8") as f:
            extracted_data["icd11"] = json.load(f)

    return extracted_data


def load_insurance_data() -> List[Dict[str, Any]]:
    """加载保险产品结构化数据"""
    path = _data_path("processed", "insurance", "insurance_products.json")
    if not os.path.exists(path):
        print(f"[WARN] 未找到保险数据: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    products = data.get("products", [])
    print(f"[OK] 加载保险产品: {len(products)} 条")
    return products


def load_eldercare_data() -> List[Dict[str, Any]]:
    """加载养老机构结构化数据"""
    path = _data_path("processed", "eldercare", "institutions.json")
    if not os.path.exists(path):
        print(f"[WARN] 未找到养老数据: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    institutions = data.get("institutions", [])
    print(f"[OK] 加载养老机构: {len(institutions)} 条")
    return institutions


def normalize_disease_name(name: str) -> str:
    """标准化疾病名称"""
    if not name:
        return ""
    name = re.sub(r"\([^)]*\)", "", name)
    name = re.sub(r"[\d\s\-]+$", "", name)
    name = name.strip().lower()
    return name


def get_synonym_map() -> Dict[str, str]:
    """获取同义词映射表"""
    return {
        "高血压": "高血压",
        "原发性高血压": "高血压",
        "继发性高血压": "高血压",
        "高血压病": "高血压",
        "糖尿病": "糖尿病",
        "2型糖尿病": "糖尿病",
        "1型糖尿病": "糖尿病",
        "妊娠期糖尿病": "糖尿病",
        "心肌梗死": "心肌梗死",
        "急性心肌梗死": "心肌梗死",
        "脑梗塞": "脑梗死",
        "脑梗死": "脑梗死",
        "脑栓塞": "脑梗死",
        "肺炎": "肺炎",
        "细菌性肺炎": "肺炎",
        "病毒性肺炎": "肺炎",
        "肾炎": "肾炎",
        "肾小球肾炎": "肾炎",
        "肾盂肾炎": "肾炎",
    }


def build_disease_index(diseases: List[Dict]) -> Dict[str, str]:
    """按 aligned_name 建立疾病 ID 索引（取首个匹配）"""
    index: Dict[str, str] = {}
    for disease in diseases:
        aligned = disease.get("aligned_name") or disease.get("normalized_name") or disease.get("name", "")
        if aligned and aligned not in index:
            index[aligned] = disease["id"]
        name = disease.get("name", "")
        if name and name not in index:
            index[name] = disease["id"]
    return index


def _canonical_disease_id(aligned_icd: str) -> str:
    safe = re.sub(r"[^\w\u4e00-\u9fa5]", "_", aligned_icd.strip())
    return f"disease_canonical_{safe}"


def bootstrap_insurance_disease_nodes(
    products: List[Dict],
    aligned_entities: Dict[str, Any],
) -> Dict[str, str]:
    """
    为保险条款中的 aligned_icd 补建标准疾病节点。
    ICD 库中往往没有「高血压」等汇总名，导致 COVERS/EXCLUDES 无法入库。
    """
    disease_index = build_disease_index(aligned_entities["diseases"])
    existing_ids = {d["id"] for d in aligned_entities["diseases"]}
    needed = set()

    for product in products:
        for key in ("covers_diseases", "excludes_diseases"):
            for entry in product.get(key, []):
                icd = (entry.get("aligned_icd") or "").strip()
                if icd:
                    needed.add(icd)

    for icd in sorted(needed):
        if icd in disease_index:
            continue

        did = _canonical_disease_id(icd)
        if did in existing_ids:
            disease_index[icd] = did
            continue

        aligned_entities["diseases"].append({
            "id": did,
            "code": "INSURANCE",
            "name": icd,
            "normalized_name": icd,
            "aligned_name": icd,
            "category": "insurance_canonical",
            "chapter": "",
        })
        disease_index[icd] = did
        existing_ids.add(did)

    return disease_index


def find_disease_id(disease_ref: str, aligned_icd: str, disease_index: Dict[str, str]) -> Optional[str]:
    """根据 aligned_icd 或疾病名查找图谱中的 Disease 节点 ID"""
    if aligned_icd and aligned_icd in disease_index:
        return disease_index[aligned_icd]

    normalized = normalize_disease_name(disease_ref)
    normalized = re.sub(
        r"[iIⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ0-9一二三四五六七八九十]+级",
        "",
        normalized,
    )

    synonym_map = get_synonym_map()
    aligned = synonym_map.get(normalized, normalized)
    if aligned in disease_index:
        return disease_index[aligned]

    if disease_ref:
        if disease_ref in disease_index:
            return disease_index[disease_ref]

    # aligned_icd 仅精确匹配，避免「高血压」误连到「高血压性脑病」
    search_terms = [t for t in (aligned, normalized) if t]
    for term in search_terms:
        if term in disease_index:
            return disease_index[term]
        for key, did in disease_index.items():
            if term in key or key in term:
                return did
    return None


def align_entities(extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """医疗域实体对齐"""
    aligned_entities = {
        "diseases": [],
        "drugs": [],
        "categories": [],
        "insurance_products": [],
        "institutions": [],
        "age_limits": [],
        "medical_services": [],
        "value_nodes": [],
    }

    synonym_map = get_synonym_map()

    if "icd11" in extracted_data:
        icd11_data = extracted_data["icd11"]
        for disease in icd11_data.get("diseases", []):
            if disease.get("code") in ("章节或编码",) or not disease.get("name"):
                continue
            normalized_name = normalize_disease_name(disease["name"])
            aligned_name = synonym_map.get(normalized_name, normalized_name)
            aligned_entities["diseases"].append({
                "id": f"disease_{disease['code']}",
                "code": disease["code"],
                "name": disease["name"],
                "normalized_name": normalized_name,
                "aligned_name": aligned_name,
                "category": disease.get("category", ""),
                "chapter": disease.get("chapter", ""),
            })

        for category in icd11_data.get("categories", []):
            aligned_entities["categories"].append({
                "id": f"category_{category['code']}",
                "code": category["code"],
                "name": category["name"],
                "level": category.get("level", "category"),
                "chapter": category.get("chapter", ""),
            })

    if "commercial_drugs" in extracted_data:
        commercial_data = extracted_data["commercial_drugs"]
        for drug in commercial_data.get("drugs", []):
            normalized_name = normalize_disease_name(drug["name"])
            aligned_entities["drugs"].append({
                "id": f"drug_{drug['code']}",
                "code": drug["code"],
                "name": drug["name"],
                "normalized_name": normalized_name,
                "brand_name": drug.get("brand_name", ""),
                "indication": drug.get("indication", ""),
                "manufacturer": drug.get("manufacturer", ""),
            })

        for category in commercial_data.get("categories", []):
            aligned_entities["categories"].append({
                "id": f"category_{category['code']}",
                "code": category["code"],
                "name": category["name"],
                "level": "drug_category",
            })

    entity_map: Dict[str, List[str]] = {}
    for disease in aligned_entities["diseases"]:
        aligned_name = disease["aligned_name"]
        entity_map.setdefault(aligned_name, []).append(disease["id"])
    aligned_entities["entity_map"] = entity_map

    return aligned_entities


def add_insurance_entities(aligned_entities: Dict[str, Any], products: List[Dict]) -> None:
    """将保险产品及相关辅助实体加入 aligned_entities"""
    seen_services: Dict[str, str] = {}

    for product in products:
        pid = product["id"]
        aligned_entities["insurance_products"].append({
            "id": pid,
            "code": product.get("code", ""),
            "name": product.get("name", ""),
            "short_name": product.get("short_name", ""),
            "type": product.get("type", ""),
            "company": product.get("company", ""),
            "description": product.get("description", ""),
            "source": product.get("source", ""),
            "annual_premium": product.get("annual_premium", ""),
            "coverage_amount": product.get("coverage_amount", ""),
            "waiting_period": product.get("waiting_period", ""),
        })

        age = product.get("age_limit", {})
        if age:
            age_id = f"age_limit_{pid}"
            aligned_entities["age_limits"].append({
                "id": age_id,
                "min_age": age.get("min_age"),
                "max_age": age.get("max_age"),
                "label": f"{age.get('min_age', '?')}-{age.get('max_age', '?')}岁",
            })

        if product.get("annual_premium"):
            aligned_entities["value_nodes"].append({
                "id": f"price_{pid}",
                "value": product["annual_premium"],
                "type": "Price",
                "label": product["annual_premium"],
            })

        for idx, item in enumerate(product.get("coverage_items", [])):
            svc_id = f"coverage_{pid}_{idx}"
            aligned_entities["value_nodes"].append({
                "id": svc_id,
                "value": item,
                "type": "Coverage",
                "label": item,
            })

        for svc_name in product.get("medical_services_covered", []):
            if svc_name not in seen_services:
                svc_id = f"medical_service_{len(seen_services):04d}"
                seen_services[svc_name] = svc_id
                aligned_entities["medical_services"].append({
                    "id": svc_id,
                    "name": svc_name,
                    "description": svc_name,
                })


def add_eldercare_entities(aligned_entities: Dict[str, Any], institutions: List[Dict]) -> None:
    """将养老机构及相关辅助实体加入 aligned_entities"""
    seen_services: Dict[str, str] = {}

    for inst in institutions:
        aligned_entities["institutions"].append({
            "id": inst["id"],
            "name": inst.get("name", ""),
            "type": inst.get("type", "养老机构"),
            "city": inst.get("city", ""),
            "district": inst.get("district", ""),
            "address": inst.get("address", ""),
            "phone": inst.get("phone", ""),
            "monthly_fee": inst.get("monthly_fee", ""),
            "admission_requirements": inst.get("admission_requirements", ""),
            "bed_count": inst.get("bed_count"),
            "rating": inst.get("rating", ""),
            "source": inst.get("source", ""),
            "location": inst.get("location"),
        })

        if inst.get("monthly_fee"):
            aligned_entities["value_nodes"].append({
                "id": f"monthly_fee_{inst['id']}",
                "value": inst["monthly_fee"],
                "type": "Price",
                "label": inst["monthly_fee"],
            })

        if inst.get("admission_requirements"):
            aligned_entities["value_nodes"].append({
                "id": f"admission_{inst['id']}",
                "value": inst["admission_requirements"],
                "type": "AdmissionRequirement",
                "label": inst["admission_requirements"],
            })

        for svc_name in inst.get("services", []):
            if svc_name not in seen_services:
                svc_id = f"medical_service_{len(seen_services):04d}"
                seen_services[svc_name] = svc_id
                if not any(s["id"] == svc_id for s in aligned_entities["medical_services"]):
                    aligned_entities["medical_services"].append({
                        "id": svc_id,
                        "name": svc_name,
                        "description": svc_name,
                    })


def generate_medical_triples(aligned_entities: Dict[str, Any]) -> List[Dict[str, Any]]:
    """生成医疗域三元组"""
    triples = []

    for disease in aligned_entities["diseases"]:
        for category in aligned_entities["categories"]:
            if category["name"] == disease.get("category"):
                triples.append({
                    "subject": disease["id"],
                    "predicate": "BELONGS_TO",
                    "object": category["id"],
                    "subject_type": "Disease",
                    "object_type": "DiseaseCategory",
                    "properties": {
                        "disease_code": disease["code"],
                        "disease_name": disease["name"],
                        "category_code": category["code"],
                        "category_name": category["name"],
                    },
                })
                break

    drug_category = next(
        (c for c in aligned_entities["categories"] if c.get("level") == "drug_category"),
        None,
    )
    if drug_category:
        for drug in aligned_entities["drugs"]:
            triples.append({
                "subject": drug["id"],
                "predicate": "BELONGS_TO",
                "object": drug_category["id"],
                "subject_type": "Drug",
                "object_type": "DrugCategory",
                "properties": {
                    "drug_code": drug["code"],
                    "drug_name": drug["name"],
                    "category_code": drug_category["code"],
                    "category_name": drug_category["name"],
                },
            })

    for drug in aligned_entities["drugs"]:
        indication = drug.get("indication", "")
        if not indication:
            continue
        normalized_indication = normalize_disease_name(indication)
        for disease in aligned_entities["diseases"]:
            matched = (
                disease["normalized_name"] in normalized_indication
                or (
                    disease["aligned_name"] != disease["normalized_name"]
                    and disease["aligned_name"] in normalized_indication
                )
            )
            if matched:
                triples.append({
                    "subject": drug["id"],
                    "predicate": "INDICATED_FOR",
                    "object": disease["id"],
                    "subject_type": "Drug",
                    "object_type": "Disease",
                    "properties": {
                        "drug_name": drug["name"],
                        "disease_name": disease["name"],
                        "indication": indication,
                    },
                })
                triples.append({
                    "subject": disease["id"],
                    "predicate": "TREATED_BY",
                    "object": drug["id"],
                    "subject_type": "Disease",
                    "object_type": "Drug",
                    "properties": {
                        "disease_name": disease["name"],
                        "drug_name": drug["name"],
                    },
                })

    entity_map = aligned_entities.get("entity_map", {})
    for aligned_name, entity_ids in entity_map.items():
        if len(entity_ids) > 1:
            for i in range(len(entity_ids)):
                for j in range(i + 1, len(entity_ids)):
                    triples.append({
                        "subject": entity_ids[i],
                        "predicate": "ALIGNED_WITH",
                        "object": entity_ids[j],
                        "subject_type": "Disease",
                        "object_type": "Disease",
                        "properties": {"aligned_name": aligned_name},
                    })

    return triples


def generate_insurance_triples(
    products: List[Dict],
    aligned_entities: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """生成保险域三元组（含跨域 COVERS / EXCLUDES）"""
    triples = []
    disease_index = bootstrap_insurance_disease_nodes(products, aligned_entities)
    service_map = {s["name"]: s["id"] for s in aligned_entities["medical_services"]}
    linked_diseases = 0
    skipped_diseases = 0

    for product in products:
        pid = product["id"]
        pname = product.get("name", "")

        age = product.get("age_limit", {})
        if age:
            triples.append({
                "subject": pid,
                "predicate": "HAS_AGE_LIMIT",
                "object": f"age_limit_{pid}",
                "subject_type": "InsuranceProduct",
                "object_type": "AgeLimit",
                "properties": {
                    "product_name": pname,
                    "min_age": age.get("min_age"),
                    "max_age": age.get("max_age"),
                },
            })

        if product.get("annual_premium"):
            triples.append({
                "subject": pid,
                "predicate": "PRICE",
                "object": f"price_{pid}",
                "subject_type": "InsuranceProduct",
                "object_type": "Price",
                "properties": {
                    "product_name": pname,
                    "amount": product["annual_premium"],
                },
            })

        for idx, item in enumerate(product.get("coverage_items", [])):
            triples.append({
                "subject": pid,
                "predicate": "COVERAGE",
                "object": f"coverage_{pid}_{idx}",
                "subject_type": "InsuranceProduct",
                "object_type": "Coverage",
                "properties": {"product_name": pname, "content": item},
            })

        for svc_name in product.get("medical_services_covered", []):
            svc_id = service_map.get(svc_name)
            if svc_id:
                triples.append({
                    "subject": pid,
                    "predicate": "COVERS",
                    "object": svc_id,
                    "subject_type": "InsuranceProduct",
                    "object_type": "MedicalService",
                    "properties": {"product_name": pname, "service": svc_name},
                })

        for entry in product.get("covers_diseases", []):
            did = find_disease_id(
                entry.get("disease", ""),
                entry.get("aligned_icd", ""),
                disease_index,
            )
            if did:
                linked_diseases += 1
                triples.append({
                    "subject": pid,
                    "predicate": "COVERS",
                    "object": did,
                    "subject_type": "InsuranceProduct",
                    "object_type": "Disease",
                    "properties": {
                        "product_name": pname,
                        "disease_label": entry.get("disease", ""),
                        "aligned_icd": entry.get("aligned_icd", ""),
                        "note": entry.get("note", ""),
                        "source": product.get("source", ""),
                    },
                })
            else:
                skipped_diseases += 1

        for entry in product.get("excludes_diseases", []):
            if not entry.get("aligned_icd"):
                continue
            did = find_disease_id(
                entry.get("disease", ""),
                entry.get("aligned_icd", ""),
                disease_index,
            )
            if did:
                linked_diseases += 1
                triples.append({
                    "subject": pid,
                    "predicate": "EXCLUDES",
                    "object": did,
                    "subject_type": "InsuranceProduct",
                    "object_type": "Disease",
                    "properties": {
                        "product_name": pname,
                        "disease_label": entry.get("disease", ""),
                        "aligned_icd": entry.get("aligned_icd", ""),
                        "note": entry.get("note", ""),
                        "source": product.get("source", ""),
                    },
                })
            else:
                skipped_diseases += 1

        # 泰康系产品 ↔ 泰康之家 跨域关联
        if "泰康" in product.get("company", ""):
            for inst in aligned_entities.get("institutions", []):
                if "泰康" in inst.get("name", ""):
                    triples.append({
                        "subject": pid,
                        "predicate": "PARTNER_WITH",
                        "object": inst["id"],
                        "subject_type": "InsuranceProduct",
                        "object_type": "Institution",
                        "properties": {
                            "product_name": pname,
                            "institution_name": inst["name"],
                            "relation": "保险+养老协同",
                        },
                    })

    print(f"[OK] 保险域三元组: 跨域疾病链接 {linked_diseases} 条, 未匹配 {skipped_diseases} 条")
    return triples


def generate_eldercare_triples(
    institutions: List[Dict],
    aligned_entities: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """生成养老域三元组"""
    triples = []
    service_map = {s["name"]: s["id"] for s in aligned_entities["medical_services"]}

    for inst in institutions:
        iid = inst["id"]
        iname = inst.get("name", "")

        for svc_name in inst.get("services", []):
            svc_id = service_map.get(svc_name)
            if svc_id:
                triples.append({
                    "subject": iid,
                    "predicate": "PROVIDES",
                    "object": svc_id,
                    "subject_type": "Institution",
                    "object_type": "MedicalService",
                    "properties": {
                        "institution_name": iname,
                        "service": svc_name,
                        "source": inst.get("source", ""),
                    },
                })

        if inst.get("monthly_fee"):
            triples.append({
                "subject": iid,
                "predicate": "CHARGE",
                "object": f"monthly_fee_{iid}",
                "subject_type": "Institution",
                "object_type": "Price",
                "properties": {
                    "institution_name": iname,
                    "amount": inst["monthly_fee"],
                },
            })

        if inst.get("admission_requirements"):
            triples.append({
                "subject": iid,
                "predicate": "ADMISSION",
                "object": f"admission_{iid}",
                "subject_type": "Institution",
                "object_type": "AdmissionRequirement",
                "properties": {
                    "institution_name": iname,
                    "requirements": inst["admission_requirements"],
                },
            })

    print(f"[OK] 养老域三元组: {len(triples)} 条")
    return triples


def save_results(triples: List[Dict[str, Any]], entities: Dict[str, Any]) -> None:
    """保存三元组与实体到 processed 目录"""
    medical_dir = _data_path("processed", "medical")
    os.makedirs(medical_dir, exist_ok=True)

    triples_path = os.path.join(medical_dir, "triples.json")
    entities_path = os.path.join(medical_dir, "aligned_entities.json")

    with open(triples_path, "w", encoding="utf-8") as f:
        json.dump(triples, f, ensure_ascii=False, indent=2)

    with open(entities_path, "w", encoding="utf-8") as f:
        json.dump(entities, f, ensure_ascii=False, indent=2)

    stats_path = os.path.join(medical_dir, "kg_stats.json")
    pred_counts: Dict[str, int] = {}
    for t in triples:
        pred_counts[t["predicate"]] = pred_counts.get(t["predicate"], 0) + 1

    stats = {
        "total_triples": len(triples),
        "entities": {
            "diseases": len(entities.get("diseases", [])),
            "drugs": len(entities.get("drugs", [])),
            "categories": len(entities.get("categories", [])),
            "insurance_products": len(entities.get("insurance_products", [])),
            "institutions": len(entities.get("institutions", [])),
            "age_limits": len(entities.get("age_limits", [])),
            "medical_services": len(entities.get("medical_services", [])),
            "value_nodes": len(entities.get("value_nodes", [])),
        },
        "relations_by_type": pred_counts,
    }
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"三元组生成完成，共 {len(triples)} 条")
    print(f"  保存至: {triples_path}")
    print(f"  实体保存至: {entities_path}")
    print(f"  统计: {stats_path}")


def main():
    print("=" * 55)
    print("  跨域知识图谱三元组生成（医疗 + 保险 + 养老）")
    print("=" * 55)

    extracted_data = load_extracted_data()
    insurance_products = load_insurance_data()
    eldercare_institutions = load_eldercare_data()

    aligned_entities = align_entities(extracted_data)
    add_insurance_entities(aligned_entities, insurance_products)
    add_eldercare_entities(aligned_entities, eldercare_institutions)

    medical_triples = generate_medical_triples(aligned_entities)
    insurance_triples = generate_insurance_triples(insurance_products, aligned_entities)
    eldercare_triples = generate_eldercare_triples(eldercare_institutions, aligned_entities)

    all_triples = medical_triples + insurance_triples + eldercare_triples
    save_results(all_triples, aligned_entities)

    print("-" * 55)
    print(f"  医疗域: {len(medical_triples)} 条")
    print(f"  保险域: {len(insurance_triples)} 条")
    print(f"  养老域: {len(eldercare_triples)} 条")
    print(f"  合计:   {len(all_triples)} 条")
    print("=" * 55)


if __name__ == "__main__":
    main()
