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
    # 提取分类信息（如XA 消化道和代谢方面的药物）
    category_pattern = r'(X[A-Z]\w*)\s+([\u4e00-\u9fa5]+(?:\s+[\u4e00-\u9fa5]+)*)'
    category_matches = re.findall(category_pattern, full_text)
    
    for match in category_matches:
        code = match[0].strip()
        name = match[1].strip()
        if code and name:
            categories.append({
                "code": code,
                "name": name
            })
    
    # 解析药品信息
    drugs = []
    
    # 使用正则表达式直接匹配药品信息
    # 模式：编号 + 药品名称 + 商品名 + 适应症
    drug_pattern = r'(\d+)\s+([^\d]+?)\s+(\w+?)(适用于|用于|单药适用于|联合用于)(.*?)(?=\d+\s+|$)'
    drug_matches = re.findall(drug_pattern, full_text, re.DOTALL)
    
    for match in drug_matches:
        code = match[0].strip()
        name = match[1].strip()
        brand_name = match[2].strip()
        indication_prefix = match[3].strip()
        indication = (indication_prefix + match[4]).strip()
        
        # 清理适应症文本
        indication = re.sub(r'\s+', ' ', indication)
        indication = re.sub(r'\n', ' ', indication)
        
        if code and name and indication:
            drugs.append({
                "code": code,
                "name": name,
                "brand_name": brand_name,
                "indication": indication,
                "manufacturer": "",
                "authorized_company": "",
                "validity_period": ""
            })
    
    # 如果正则表达式匹配失败，使用备用方法
    if not drugs:
        # 分割文本为行
        lines = full_text.split('\n')
        
        # 药品信息行的特征：包含编号、药品名称、商品名、适应症等
        drug_lines = []
        for line in lines:
            line = line.strip()
            if line:
                # 查找包含数字编号的行
                if re.match(r'^\d+\s+', line):
                    drug_lines.append(line)
        
        # 解析药品行
        for line in drug_lines:
            # 分割行，提取药品信息
            parts = line.split()
            if len(parts) >= 4:
                # 编号
                code = parts[0]
                # 药品名称（从第1个元素到倒数第2个元素）
                name = ' '.join(parts[1:-2])
                # 商品名（倒数第2个元素）
                brand_name = parts[-2]
                # 适应症（倒数第1个元素）
                indication = parts[-1]
                
                if code and name and indication:
                    drugs.append({
                        "code": code,
                        "name": name,
                        "brand_name": brand_name,
                        "indication": indication,
                        "manufacturer": "",
                        "authorized_company": "",
                        "validity_period": ""
                    })
    
    # 去重药品
    unique_drugs = []
    seen_codes = set()
    for drug in drugs:
        if drug['code'] not in seen_codes:
            seen_codes.add(drug['code'])
            unique_drugs.append(drug)
    
    return {
        "categories": categories,
        "drugs": unique_drugs
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
        print(f"提取到 {len(commercial_data.get('categories', []))} 个分类")
        print(f"提取到 {len(commercial_data.get('drugs', []))} 个药品")
    
    # 处理国家基本医疗保险药品目录
    medical_insurance_pdf = os.path.join(data_dir, '国家基本医疗保险、生育保险和工伤保险药品目录.pdf')
    if os.path.exists(medical_insurance_pdf):
        medical_insurance_data = extract_medical_insurance_catalog(medical_insurance_pdf)
        with open(os.path.join(output_dir, 'medical_insurance_catalog.json'), 'w', encoding='utf-8') as f:
            json.dump(medical_insurance_data, f, ensure_ascii=False, indent=2)
        print(f"国家基本医疗保险药品目录提取完成，保存在：{os.path.join(output_dir, 'medical_insurance_catalog.json')}")

if __name__ == "__main__":
    main()
