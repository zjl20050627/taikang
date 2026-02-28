# 图谱存储

此目录包含与Neo4j存储相关的配置和脚本。

## 功能模块

- `neo4j_config.py`: Neo4j 数据库连接配置
- `import_data.py`: 将数据导入 Neo4j 数据库
- `query.py`: 常用图谱查询接口

## 使用说明

### 1. 配置 Neo4j 连接

默认连接本地 Neo4j (bolt://localhost:7687)，用户名为 `neo4j`，密码为 `password`。
可以通过环境变量修改配置：

```bash
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=your_password
```

### 2. 导入数据

确保 Neo4j 服务已启动，然后运行导入脚本：

```bash
python storage/import_data.py
```

该脚本会读取 `data/processed/medical/aligned_entities.json` 和 `data/processed/medical/triples.json` 并导入到数据库中。
注意：导入前会清空数据库（如果在脚本中取消了注释）。

### 3. 数据查询

可以使用 `query.py` 中的函数进行查询，或在可视化应用中调用。