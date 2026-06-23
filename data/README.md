# 数据收集与存储

此目录用于存放各类数据源文件，包括：
- 医疗库数据（ICD、DrugBank、医保目录）
- 保险条款数据
- 养老服务信息

## 目录结构

```
data/
├── raw/
│   ├── medical/          # 医疗原始数据（ICD-11、药品目录 PDF）
│   ├── insurance/        # 保险条款 PDF（可选）
│   └── elderly/          # 养老原始数据（高德 POI 缓存等）
├── processed/
│   ├── medical/          # 医疗结构化数据 + 三元组
│   ├── insurance/        # 保险产品结构化数据
│   └── eldercare/        # 养老机构结构化数据
```

## 数据获取命令

```bash
# 医疗域
python extraction/extract_icd11.py
python extraction/extract_pdf.py
python extraction/generate_triples.py

# 养老域
python extraction/eldercare/fetch_eldercare_data.py --skip-amap
# 配置 AMAP_API_KEY 后可去掉 --skip-amap 启用高德 POI 检索
```