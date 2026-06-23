# 养老机构数据获取说明

## 数据来源

| 来源 | 文件/脚本 | 说明 |
|------|----------|------|
| 民政部/地方民政局公开信息 | `seed_institutions.json` | 20 条种子数据，覆盖北京/上海/深圳/广州/苏州/杭州/成都/武汉 |
| 高德地图 POI API | `amap_client.py` | 按「养老院」「护理院」等关键词区域检索 |
| 对齐融合 | `align_institutions.py` | 名称相似度 + 地址匹配，融合两套数据 |

## 快速开始

### 1. 仅使用民政种子数据（无需 API Key）

```bash
python extraction/eldercare/fetch_eldercare_data.py --skip-amap
```

输出：`data/processed/eldercare/institutions.json`

### 2. 启用高德 POI 检索（推荐）

1. 前往 [高德开放平台](https://lbs.amap.com/) 注册开发者账号
2. 创建应用，获取 **Web 服务 Key**
3. 在项目根目录 `.env` 中添加：

```env
AMAP_API_KEY=你的高德Web服务Key
```

4. 运行：

```bash
# 检索全部配置城市
python extraction/eldercare/fetch_eldercare_data.py

# 仅检索指定城市
python extraction/eldercare/fetch_eldercare_data.py --cities 北京市 上海市 深圳市
```

### 3. 单独测试高德 API

```bash
python extraction/eldercare/amap_client.py
```

## 对齐融合策略

```
民政种子数据（主）          高德 POI（辅）
     │                         │
     ├─ 名称相似度 (权重 0.6) ──┤
     ├─ 地址重叠度 (权重 0.3) ──┤
     └─ 城市一致性 (权重 0.1) ──┘
                 │
                 ▼
         score ≥ 0.55 → 融合为一条记录
         score < 0.55 → 各自保留
         未匹配 POI   → 作为补充入库
```

融合后字段优先级：
- **民政数据为主**：服务、收费标准、入住条件、床位数、评级
- **高德补充**：经纬度、电话、详细地址、POI 类型

## 输出文件

| 文件 | 说明 |
|------|------|
| `data/processed/eldercare/institutions.json` | 融合后的养老机构结构化数据 |
| `data/processed/eldercare/alignment_report.json` | 对齐匹配详情报告 |
| `data/raw/elderly/amap_pois.json` | 高德 POI 原始缓存 |

## 扩展民政种子数据

1. 访问各地民政局官网「养老服务」专栏
2. 下载《养老机构名录》Excel/CSV
3. 按 `seed_institutions.json` 格式追加条目
4. 重新运行 `fetch_eldercare_data.py`

### 推荐政务公开渠道

- 北京市民政局：https://mzj.beijing.gov.cn/
- 上海市民政局：https://mzj.sh.gov.cn/
- 深圳市民政局：https://mzj.sz.gov.cn/
- 全国养老服务信息平台：https://yanglao.mca.gov.cn/

## 后续步骤

获取 `institutions.json` 后，需：
1. 扩展 `generate_triples.py` 生成养老域三元组
2. 扩展 `import_data.py` 导入 `Institution` 节点
3. 与保险域数据建立跨域关联（如泰康之家 ↔ 泰康保险）
