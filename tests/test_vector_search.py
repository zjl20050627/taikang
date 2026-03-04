# ============================================================
# tests/test_vector_search.py - 向量检索功能快速测试
# ============================================================
# 功能：快速验证向量检索功能是否正常工作
#
# 使用方法：
#   python tests/test_vector_search.py
# ============================================================

import os
import sys

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from data_models import ParsedQuestion
from graph_retrieval.neo4j_retrieval_with_vector import Neo4jGraphRetrievalWithVector


def test_basic_search():
    """测试基本检索功能"""
    print("\n" + "=" * 60)
    print("  向量检索功能快速测试")
    print("=" * 60)
    
    # 创建检索实例
    print("\n[1/4] 初始化检索模块...")
    retrieval = Neo4jGraphRetrievalWithVector()
    
    # 测试问题
    test_question = "高血压用什么药治疗？"
    print(f"\n[2/4] 测试问题：{test_question}")
    
    # 构建解析后的问题
    parsed = ParsedQuestion(
        original_question=test_question,
        entities=[{"text": "高血压", "type": "Disease"}],
        intent="treatment"
    )
    
    # 测试传统检索
    print("\n[3/4] 测试传统关键词检索...")
    retrieval.vector_search_enabled = False
    result_traditional = retrieval.retrieve(parsed)
    print(f"  ✓ 找到 {len(result_traditional.triples)} 条三元组")
    print(f"  ✓ 匹配实体：{result_traditional.matched_entities}")
    
    # 测试向量检索
    print("\n[4/4] 测试向量检索...")
    retrieval.vector_search_enabled = True
    result_vector = retrieval.retrieve(parsed)
    print(f"  ✓ 找到 {len(result_vector.triples)} 条三元组")
    print(f"  ✓ 匹配实体：{result_vector.matched_entities}")
    
    # 对比结果
    print("\n" + "=" * 60)
    print("  测试结果对比")
    print("=" * 60)
    print(f"\n传统检索:")
    print(f"  - 三元组数量：{len(result_traditional.triples)}")
    print(f"  - 匹配实体数：{len(result_traditional.matched_entities)}")
    
    print(f"\n向量检索:")
    print(f"  - 三元组数量：{len(result_vector.triples)}")
    print(f"  - 匹配实体数：{len(result_vector.matched_entities)}")
    
    if len(result_vector.triples) > len(result_traditional.triples):
        if len(result_traditional.triples) > 0:
            improvement = (len(result_vector.triples) - len(result_traditional.triples)) / len(result_traditional.triples) * 100
            print(f"\n✓ 向量检索提升了 {improvement:.1f}% 的检索覆盖率")
        else:
            print(f"\n✓ 向量检索从 0 提升到 {len(result_vector.triples)} 条三元组")
    elif len(result_vector.triples) == len(result_traditional.triples):
        print(f"\n= 两种检索结果相同")
    else:
        print(f"\n⚠ 向量检索结果较少，可能需要调整参数")
    
    print("\n" + "=" * 60)
    print("  测试完成")
    print("=" * 60)
    
    return result_traditional, result_vector


def test_vector_generation():
    """测试向量生成功能"""
    print("\n" + "=" * 60)
    print("  向量生成测试")
    print("=" * 60)
    
    retrieval = Neo4jGraphRetrievalWithVector()
    
    if not retrieval.vector_search_enabled:
        print("\n⚠ 向量检索未启用，请在 .env 中设置 VECTOR_SEARCH_ENABLED=true")
        return None
    
    test_texts = ["高血压", "糖尿病", "护理险"]
    
    print("\n测试向量生成:")
    for text in test_texts:
        embedding = retrieval._generate_embedding(text)
        if embedding:
            print(f"  ✓ '{text}': 向量维度 = {len(embedding)}")
        else:
            print(f"  ✗ '{text}': 向量生成失败")
    
    return True


def test_vector_index():
    """测试 Neo4j 向量索引"""
    print("\n" + "=" * 60)
    print("  Neo4j 向量索引检查")
    print("=" * 60)
    
    from storage.neo4j_config import db
    
    # 检查向量索引
    query = "SHOW INDEXES WHERE type = 'VECTOR'"
    result = db.query(query)
    
    if result and len(result) > 0:
        print("\n✓ 向量索引已存在:")
        for index in result:
            print(f"  - 名称：{index.get('name', 'N/A')}")
            print(f"  - 类型：{index.get('type', 'N/A')}")
            print(f"  - 实体标签：{index.get('entityType', 'N/A')}")
    else:
        print("\n✗ 向量索引不存在")
        print("请运行：python storage\\embed_entities.py")
    
    # 检查已向量化的实体数量
    query_count = "MATCH (n:Entity) WHERE n.embedding IS NOT NULL RETURN count(n) as count"
    result = db.query(query_count)
    if result:
        count = result[0].get('count', 0)
        print(f"\n已向量化的实体数量：{count}")
    
    return result


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("  GraphRAG 向量检索功能验证")
    print("=" * 60)
    
    # 测试 1: 向量索引检查
    test_vector_index()
    
    # 测试 2: 向量生成
    test_vector_generation()
    
    # 测试 3: 基本检索
    test_basic_search()
    
    print("\n✓ 所有测试完成！")
    print("\n下一步:")
    print("  1. 如果向量索引不存在，运行：python storage\\embed_entities.py")
    print("  2. 在 .env 中设置 VECTOR_SEARCH_ENABLED=true")
    print("  3. 运行完整测试：python tests\\benchmark_vector_search.py")


if __name__ == "__main__":
    main()
