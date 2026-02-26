# 图谱检索

## 模块功能
此目录包含图谱检索相关的模块，负责将问题中的实体匹配到图谱节点，执行Cypher查询获取相关子图。

## 已实现的功能

### 1. Neo4jGraphRetrieval 类
- **功能**：连接Neo4j数据库并执行Cypher查询
- **核心方法**：
  - `retrieve(parsed_question) → RetrievalResult`：根据解析后的问题检索相关三元组
  - `_build_cypher_query()`：根据实体类型和意图构建Cypher查询
  - `_execute_query()`：执行Cypher查询并返回结果
  - `_parse_query_result()`：将查询结果解析为Triple对象

### 2. 实体对齐与标准化
- **同义词映射**：处理不同表述的同一概念（如"高血压" vs "原发性高血压"）
- **实体标准化**：移除括号内容、数字和特殊字符，转换为小写

### 3. 意图驱动的查询构建
根据用户意图构建不同的Cypher查询：
- **insurability（能否投保）**：查询保险产品与疾病的关系
- **treatment（治疗）**：查询疾病的治疗药物
- **cost（费用）**：查询保险产品的价格信息
- **coverage（保障范围）**：查询保险产品的保障内容
- **eligibility（资格条件）**：查询保险产品的年龄限制

### 4. 多跳查询支持
- 支持1-2跳关系扩展，返回相关子图
- 根据实体类型和意图优化查询策略

### 5. 容错机制
- 当Neo4j连接失败时，使用Mock数据作为fallback
- 处理查询失败和实体未匹配的情况

## 技术实现
- **数据库**：Neo4j
- **查询语言**：Cypher
- **连接方式**：Neo4j Python Driver
- **配置管理**：通过config.yaml配置数据库连接参数

## 使用说明
1. **配置Neo4j连接**：在config.yaml中设置Neo4j的uri、用户名和密码
2. **导入模块**：`from graph_retrieval.neo4j_retrieval import Neo4jGraphRetrieval`
3. **初始化**：`retrieval = Neo4jGraphRetrieval()`
4. **执行检索**：`result = retrieval.retrieve(parsed_question)`
5. **获取结果**：`result.triples` 包含检索到的三元组

## 测试
运行 `python graph_retrieval/neo4j_retrieval.py` 进行模块测试

## 后续优化方向
- 增加更多实体类型的支持
- 优化Cypher查询性能
- 实现更复杂的实体链接算法
- 支持更灵活的多跳查询策略