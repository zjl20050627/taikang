# 向量检索优化模块

## 📚 概述

本模块为 GraphRAG 系统添加了**向量检索（Vector Search）**功能，通过结合传统关键词匹配和向量相似度搜索，显著提升实体召回率和检索效果。

## 🎯 核心功能

### 1. 混合检索架构
- **传统关键词检索**：基于 Cypher 查询的精确匹配
- **向量相似度检索**：基于语义的模糊匹配
- **智能融合**：自动合并两种检索结果，去重并排序

### 2. Ollama 嵌入模型支持
- 使用本地 Ollama 服务生成文本嵌入向量
- 支持多种嵌入模型（默认：`nomic-embed-text`）
- 无需依赖云端 API，保护数据隐私

### 3. Neo4j 向量索引
- 利用 Neo4j 原生向量索引功能
- 支持余弦相似度搜索
- 高效的近似最近邻（ANN）查询

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install requests python-dotenv matplotlib
```

### 2. 配置 Ollama

```bash
# 启动 Ollama 服务
ollama serve

# 拉取嵌入模型（首次使用）
ollama pull nomic-embed-text
```

### 3. 向量化数据

将知识图谱中的实体向量化并存储到 Neo4j：

```bash
cd d:\taikang\final
python storage\embed_entities.py
```

**执行过程**：
1. 测试 Ollama 连接
2. 在 Neo4j 中创建向量索引
3. 获取所有实体
4. 批量生成嵌入向量
5. 将向量存储到 Neo4j

**输出示例**：
```
============================================================
  实体向量化流程
============================================================

[Step 1/4] 测试 Ollama 连接...
✓ Ollama 连接成功，向量维度：768

[Step 2/4] 创建向量索引...
✓ 向量索引创建成功

[Step 3/4] 获取所有实体...
找到 150 个实体

[Step 4/4] 生成向量并存储...
正在为 150 个文本生成嵌入向量...
  批次 1: 处理 32/150
  ...

向量化完成:
  ✓ 成功：148
  ✗ 失败：2
```

### 4. 启用向量检索

修改 `.env` 文件：

```env
# 启用向量检索
VECTOR_SEARCH_ENABLED=true

# Ollama 配置（可选）
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=nomic-embed-text

# 检索参数（可选）
VECTOR_TOP_K=10
VECTOR_SIMILARITY_THRESHOLD=0.7
```

### 5. 运行测试

```bash
python pipeline.py
```

## 📊 性能对比测试

运行基准测试，对比传统检索和向量检索的效果：

```bash
python tests\benchmark_vector_search.py
```

**测试内容**：
- 响应时间对比
- 检索覆盖率对比（三元组数量）
- 实体召回率对比

**输出**：
- `tests/benchmark_results.json`：详细测试数据
- `tests/benchmark_results.png`：可视化对比图表

## 🔧 技术细节

### 向量检索流程

```
用户问题
  ↓
[问题理解] 提取实体
  ↓
[向量生成] 使用 Ollama 生成查询向量
  ↓
[向量搜索] Neo4j 向量索引相似度搜索
  ↓
[关键词检索] 传统 Cypher 查询
  ↓
[结果融合] 合并两种检索结果
  ↓
[去重] 去除重复三元组
  ↓
返回最终结果
```

### 核心代码

**向量生成**：
```python
def _generate_embedding(self, text: str) -> Optional[List[float]]:
    response = requests.post(
        f"{self.ollama_base_url}/api/embeddings",
        json={"model": self.ollama_embedding_model, "prompt": text},
        timeout=30
    )
    return response.json().get("embedding")
```

**向量搜索**：
```python
CALL db.index.vector.queryNodes('entity_embedding_index', $top_k, $embedding)
YIELD node, score
WHERE score >= $threshold
RETURN node, score
```

### 配置参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `VECTOR_SEARCH_ENABLED` | false | 是否启用向量检索 |
| `OLLAMA_BASE_URL` | http://localhost:11434 | Ollama 服务地址 |
| `OLLAMA_EMBEDDING_MODEL` | nomic-embed-text | 嵌入模型名称 |
| `VECTOR_TOP_K` | 10 | 返回的最相似实体数量 |
| `VECTOR_SIMILARITY_THRESHOLD` | 0.7 | 相似度阈值（低于此值的結果会被过滤） |

## 📈 优化建议

### 1. 选择合适的嵌入模型

不同模型的特点：

| 模型 | 维度 | 速度 | 精度 | 适用场景 |
|------|------|------|------|----------|
| `nomic-embed-text` | 768 | 快 | 高 | 通用场景（推荐） |
| `mxbai-embed-large` | 1024 | 中 | 很高 | 高精度需求 |
| `all-minilm` | 384 | 很快 | 中 | 低延迟需求 |

### 2. 调整相似度阈值

- **提高阈值**（如 0.8）：更精确，但可能漏掉一些相关实体
- **降低阈值**（如 0.5）：召回更多实体，但可能包含噪声

### 3. 批量处理优化

修改 `embed_entities.py` 中的 `batch_size` 参数：

```python
self.embedder.embed_batch(texts, batch_size=32)  # 增大批次大小
```

### 4. 索引优化

对于大规模图谱，考虑：
- 增加 Neo4j 内存配置
- 使用 GPU 加速向量计算
- 定期重建索引

## 🔍 故障排查

### 问题 1：无法连接 Ollama

**错误信息**：
```
错误：无法连接到 Ollama 服务 (http://localhost:11434)
```

**解决方案**：
```bash
# 检查 Ollama 是否运行
ollama serve

# 检查模型是否已拉取
ollama list

# 如果没有 nomic-embed-text，拉取它
ollama pull nomic-embed-text
```

### 问题 2：向量索引创建失败

**错误信息**：
```
警告：创建向量索引失败：Index with name 'entity_embedding_index' already exists
```

**解决方案**：
索引已存在，可以直接使用。如需重建：

```cypher
DROP INDEX entity_embedding_index
```

然后重新运行 `python storage\embed_entities.py`

### 问题 3：向量检索无结果

**可能原因**：
1. 实体未向量化
2. 相似度过低
3. 向量索引未就绪

**解决方案**：
```bash
# 1. 检查实体是否已向量化
MATCH (n:Entity) WHERE n.embedding IS NOT NULL RETURN count(n)

# 2. 降低相似度阈值（修改 .env）
VECTOR_SIMILARITY_THRESHOLD=0.5

# 3. 等待索引就绪（通常 2-3 秒）
```

## 📝 使用示例

### 示例 1：在 pipeline.py 中使用

```python
from graph_retrieval.neo4j_retrieval_with_vector import Neo4jGraphRetrievalWithVector

# 初始化（会自动读取 .env 配置）
retrieval = Neo4jGraphRetrievalWithVector()

# 执行检索
parsed_question = ...  # 来自问题理解模块
result = retrieval.retrieve(parsed_question)

# 查看结果
print(f"找到 {len(result.triples)} 条三元组")
print(f"匹配实体：{result.matched_entities}")
```

### 示例 2：动态切换检索模式

```python
# 临时禁用向量检索
retrieval.vector_search_enabled = False
result = retrieval.retrieve(parsed_question)

# 启用向量检索
retrieval.vector_search_enabled = True
result = retrieval.retrieve(parsed_question)
```

## 📊 性能对比结果示例

典型场景下的性能提升：

| 指标 | 传统检索 | 向量检索 | 提升 |
|------|----------|----------|------|
| 平均响应时间 | 50ms | 120ms | -2.4x |
| 三元组数量 | 15 条 | 25 条 | +66% |
| 匹配实体数 | 3 个 | 5 个 | +67% |
| 同义词识别 | ❌ | ✅ | ∞ |

**说明**：
- 向量检索响应时间稍长（需要生成向量）
- 但显著提升了召回率和语义理解能力
- 特别适合处理同义词、拼写变体等情况

## 🎓 最佳实践

1. **开发阶段**：先用传统检索快速迭代，稳定后再启用向量检索
2. **生产环境**：启用向量检索，提升用户体验
3. **资源受限**：可以只在传统检索无结果时启用向量检索作为补充
4. **持续优化**：定期运行 benchmark 测试，调整参数

## 📚 参考资料

- [Neo4j Vector Index 官方文档](https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/)
- [Ollama Embeddings API](https://github.com/ollama/ollama/blob/main/docs/api.md#generate-embeddings)
- [nomic-embed-text 模型](https://ollama.com/library/nomic-embed-text)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request 来改进向量检索功能！

---

**最后更新**: 2026-03-04
**维护者**: GraphRAG Team
