import os
import json
import re
from typing import List, Dict, Any

def load_extracted_data() -> Dict[str, Any]:
    """加载已提取的数据"""
    data_dir = 'data/processed/medical'
    extracted_data = {}
    
    # 加载商业健康保险创新药品目录
    commercial_path = os.path.join(data_dir, 'commercial_drug_catalog.json')
    if os.path.exists(commercial_path):
        with open(commercial_path, 'r', encoding='utf-8') as f:
            extracted_data['commercial_drugs'] = json.load(f)
    
    # 加载ICD-11疾病数据
    icd11_path = os.path.join(data_dir, 'icd11_diseases.json')
    if os.path.exists(icd11_path):
        with open(icd11_path, 'r', encoding='utf-8') as f:
            extracted_data['icd11'] = json.load(f)
    
    return extracted_data

def normalize_disease_name(name: str) -> str:
    """标准化疾病名称"""
    # 移除括号内容
    name = re.sub(r'\([^)]*\)', '', name)
    # 移除数字和特殊字符
    name = re.sub(r'[\d\s\-]+$', '', name)
    # 去除首尾空格
    name = name.strip()
    return name

def align_entities(extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """实体对齐"""
    aligned_entities = {
        "diseases": [],
        "drugs": [],
        "categories": [],
        "alignments": []
    }
    
    # 处理ICD-11疾病
    if 'icd11' in extracted_data:
        icd11_data = extracted_data['icd11']
        # 添加疾病
        for disease in icd11_data.get('diseases', []):
            normalized_name = normalize_disease_name(disease['name'])
            aligned_entities['diseases'].append({
                "id": f"disease_{disease['code']}",
                "code": disease['code'],
                "name": disease['name'],
                "normalized_name": normalized_name,
                "category": disease['category'],
                "chapter": disease['chapter']
            })
        
        # 添加疾病分类
        for category in icd11_data.get('categories', []):
            aligned_entities['categories'].append({
                "id": f"category_{category['code']}",
                "code": category['code'],
                "name": category['name'],
                "level": category.get('level', 'category'),
                "chapter": category.get('chapter', '')
            })
    
    # 处理药品
    if 'commercial_drugs' in extracted_data:
        commercial_data = extracted_data['commercial_drugs']
        # 添加药品
        for drug in commercial_data.get('drugs', []):
            aligned_entities['drugs'].append({
                "id": f"drug_{drug['code']}",
                "code": drug['code'],
                "name": drug['name'],
                "brand_name": drug['brand_name'],
                "indication": drug['indication'],
                "manufacturer": drug['manufacturer']
            })
        
        # 添加药品分类
        for category in commercial_data.get('categories', []):
            aligned_entities['categories'].append({
                "id": f"category_{category['code']}",
                "code": category['code'],
                "name": category['name'],
                "level": "drug_category"
            })
    
    return aligned_entities

def generate_triples(aligned_entities: Dict[str, Any]) -> List[Dict[str, Any]]:
    """生成三元组"""
    triples = []
    
    # 疾病属于分类的关系
    for disease in aligned_entities['diseases']:
        # 找到对应的分类
        for category in aligned_entities['categories']:
            if category['name'] == disease['category']:
                triples.append({
                    "subject": disease['id'],
                    "predicate": "BELONGS_TO",
                    "object": category['id'],
                    "subject_type": "Disease",
                    "object_type": "DiseaseCategory",
                    "properties": {
                        "disease_code": disease['code'],
                        "disease_name": disease['name'],
                        "category_code": category['code'],
                        "category_name": category['name']
                    }
                })
                break
    
    # 药品属于分类的关系（简化处理，假设药品属于第一个分类）
    if aligned_entities.get('categories'):
        drug_category = None
        for category in aligned_entities['categories']:
            if category.get('level') == 'drug_category':
                drug_category = category
                break
        
        if drug_category:
            for drug in aligned_entities['drugs']:
                triples.append({
                    "subject": drug['id'],
                    "predicate": "BELONGS_TO",
                    "object": drug_category['id'],
                    "subject_type": "Drug",
                    "object_type": "DrugCategory",
                    "properties": {
                        "drug_code": drug['code'],
                        "drug_name": drug['name'],
                        "category_code": drug_category['code'],
                        "category_name": drug_category['name']
                    }
                })
    
    # 药品适应症关系和疾病治疗关系
    for drug in aligned_entities['drugs']:
        indication = drug['indication']
        # 从适应症中提取可能的疾病名称
        for disease in aligned_entities['diseases']:
            # 简单的字符串匹配
            if disease['normalized_name'] in indication:
                triples.append({
                    "subject": drug['id'],
                    "predicate": "INDICATED_FOR",
                    "object": disease['id'],
                    "subject_type": "Drug",
                    "object_type": "Disease",
                    "properties": {
                        "drug_code": drug['code'],
                        "drug_name": drug['name'],
                        "disease_code": disease['code'],
                        "disease_name": disease['name'],
                        "indication": indication
                    }
                })
                
                triples.append({
                    "subject": disease['id'],
                    "predicate": "TREATED_BY",
                    "object": drug['id'],
                    "subject_type": "Disease",
                    "object_type": "Drug",
                    "properties": {
                        "disease_code": disease['code'],
                        "disease_name": disease['name'],
                        "drug_code": drug['code'],
                        "drug_name": drug['name']
                    }
                })
    
    return triples

def save_triples(triples: List[Dict[str, Any]], entities: Dict[str, Any]):
    """保存三元组和实体数据"""
    output_dir = 'data/processed/medical'
    os.makedirs(output_dir, exist_ok=True)
    
    # 保存三元组
    triples_path = os.path.join(output_dir, 'triples.json')
    with open(triples_path, 'w', encoding='utf-8') as f:
        json.dump(triples, f, ensure_ascii=False, indent=2)
    
    # 保存实体
    entities_path = os.path.join(output_dir, 'aligned_entities.json')
    with open(entities_path, 'w', encoding='utf-8') as f:
        json.dump(entities, f, ensure_ascii=False, indent=2)
    
    print(f"三元组生成完成，共生成 {len(triples)} 个三元组")
    print(f"三元组保存在：{triples_path}")
    print(f"对齐后的实体保存在：{entities_path}")

def main():
    """主函数"""
    # 加载提取的数据
    extracted_data = load_extracted_data()
    
    # 实体对齐
    aligned_entities = align_entities(extracted_data)
    
    # 生成三元组
    triples = generate_triples(aligned_entities)
    
    # 保存结果
    save_triples(triples, aligned_entities)

if __name__ == "__main__":
    main()
