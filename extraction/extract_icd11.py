import os
import re
import json
from typing import List, Dict, Any

def extract_icd11(icd11_path: str) -> Dict[str, Any]:
    """提取ICD-11疾病分类数据"""
    try:
        with open(icd11_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
    except Exception as e:
        return {"error": str(e)}
    
    # 存储疾病分类和疾病
    categories = []
    diseases = []
    
    # 当前章节和分类
    current_chapter = ""
    current_category = ""
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 匹配章节
        chapter_match = re.match(r'第(\d+)章\s+([\u4e00-\u9fa5\s]+)', line)
        if chapter_match:
            current_chapter = chapter_match.group(2).strip()
            categories.append({
                "code": f"Chapter_{chapter_match.group(1)}",
                "name": current_chapter,
                "level": "chapter"
            })
            continue
        
        # 匹配分类（如L1-1A0）
        category_match = re.match(r'(L\d+-\w+)\s+([\u4e00-\u9fa5\s]+)', line)
        if category_match:
            current_category = category_match.group(2).strip()
            categories.append({
                "code": category_match.group(1),
                "name": current_category,
                "level": "category",
                "chapter": current_chapter
            })
            continue
        
        # 匹配疾病编码和名称（如1A00               霍乱）
        disease_match = re.match(r'(\w+\.?\w*)\s+([\u4e00-\u9fa5\s]+)', line)
        if disease_match:
            code = disease_match.group(1).strip()
            name = disease_match.group(2).strip()
            
            # 过滤掉无效行
            if len(code) < 3:
                continue
            
            diseases.append({
                "code": code,
                "name": name,
                "category": current_category,
                "chapter": current_chapter
            })
    
    # 去重分类
    unique_categories = []
    seen_codes = set()
    for cat in categories:
        if cat["code"] not in seen_codes:
            seen_codes.add(cat["code"])
            unique_categories.append(cat)
    
    # 去重疾病
    unique_diseases = []
    seen_disease_codes = set()
    for disease in diseases:
        if disease["code"] not in seen_disease_codes:
            seen_disease_codes.add(disease["code"])
            unique_diseases.append(disease)
    
    return {
        "categories": unique_categories,
        "diseases": unique_diseases
    }

def main():
    """主函数"""
    data_dir = 'data/raw/medical'
    output_dir = 'data/processed/medical'
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 处理ICD-11文件
    icd11_path = os.path.join(data_dir, 'ICD-11')
    if os.path.exists(icd11_path):
        icd11_data = extract_icd11(icd11_path)
        with open(os.path.join(output_dir, 'icd11_diseases.json'), 'w', encoding='utf-8') as f:
            json.dump(icd11_data, f, ensure_ascii=False, indent=2)
        print(f"ICD-11疾病分类数据提取完成，保存在：{os.path.join(output_dir, 'icd11_diseases.json')}")
        print(f"提取到 {len(icd11_data.get('categories', []))} 个分类")
        print(f"提取到 {len(icd11_data.get('diseases', []))} 个疾病")

if __name__ == "__main__":
    main()
