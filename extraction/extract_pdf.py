import PyPDF2
import os
import re
import json
from typing import List, Dict, Any

def extract_commercial_drug_catalog(pdf_path: str) -> Dict[str, Any]:
    """提取商业健康保险创新药品目录"""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = []
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                text.append(page.extract_text())
            full_text = '\n'.join(text)
    except Exception as e:
        return {"error": str(e)}
    
    # 解析药品分类
    categories = []
    category_pattern = r'XA\w*\s+[\u4e00-\u9fa5]+'
    category_matches = re.findall(category_pattern, full_text)
    for match in category_matches:
        parts = match.split()
        if len(parts) >= 2:
            categories.append({
                "code": parts[0],
                "name": ' '.join(parts[1:])
            })
    
    # 解析药品信息
    drugs = []
    # 匹配药品行：编号 药品名称 商品名 适应症 上市许可持有人 被授权企业 有效期
    drug_pattern = r'(\d+)\s+([\u4e00-\u9fa5\w-]+)\s+([\u4e00-\u9fa5\w-]+)\s+([\u4e00-\u9fa5\w\s]+?)\s+([\u4e00-\u9fa5\w-]+)\s+([\u4e00-\u9fa5\w-]+)\s+([\d\u4e00-\u9fa5\-]+)'
    drug_matches = re.findall(drug_pattern, full_text)
    
    for match in drug_matches:
        drugs.append({
            "code": match[0],
            "name": match[1],
            "brand_name": match[2],
            "indication": match[3],
            "manufacturer": match[4],
            "authorized_company": match[5],
            "validity_period": match[6]
        })
    
    return {
        "categories": categories,
        "drugs": drugs
    }

def extract_medical_insurance_catalog(pdf_path: str) -> Dict[str, Any]:
    """提取国家基本医疗保险药品目录"""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = []
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                text.append(page.extract_text())
            full_text = '\n'.join(text)
    except Exception as e:
        return {"error": str(e)}
    
    # 提取目录信息
    catalog_info = {}
    
    # 提取西药、中成药数量
    western_drugs_match = re.search(r'西药部分(\d+)个', full_text)
    chinese_drugs_match = re.search(r'中成药部分(\d+)个', full_text)
    negotiated_drugs_match = re.search(r'协议期内谈判药品部分(\d+)个', full_text)
    
    if western_drugs_match:
        catalog_info["western_drugs_count"] = western_drugs_match.group(1)
    if chinese_drugs_match:
        catalog_info["chinese_drugs_count"] = chinese_drugs_match.group(1)
    if negotiated_drugs_match:
        catalog_info["negotiated_drugs_count"] = negotiated_drugs_match.group(1)
    
    return {
        "catalog_info": catalog_info
    }

def main():
    """主函数"""
    data_dir = 'data/raw/medical'
    output_dir = 'data/processed/medical'
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 处理商业健康保险创新药品目录
    commercial_pdf = os.path.join(data_dir, '商业健康保险创新药品目录.pdf')
    if os.path.exists(commercial_pdf):
        commercial_data = extract_commercial_drug_catalog(commercial_pdf)
        with open(os.path.join(output_dir, 'commercial_drug_catalog.json'), 'w', encoding='utf-8') as f:
            json.dump(commercial_data, f, ensure_ascii=False, indent=2)
        print(f"商业健康保险创新药品目录提取完成，保存在：{os.path.join(output_dir, 'commercial_drug_catalog.json')}")
    
    # 处理国家基本医疗保险药品目录
    medical_insurance_pdf = os.path.join(data_dir, '国家基本医疗保险、生育保险和工伤保险药品目录.pdf')
    if os.path.exists(medical_insurance_pdf):
        medical_insurance_data = extract_medical_insurance_catalog(medical_insurance_pdf)
        with open(os.path.join(output_dir, 'medical_insurance_catalog.json'), 'w', encoding='utf-8') as f:
            json.dump(medical_insurance_data, f, ensure_ascii=False, indent=2)
        print(f"国家基本医疗保险药品目录提取完成，保存在：{os.path.join(output_dir, 'medical_insurance_catalog.json')}")

if __name__ == "__main__":
    main()
