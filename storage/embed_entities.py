# ============================================================
# storage/embed_entities.py - 实体向量化脚本
# ============================================================
# 功能：使用 Ollama 嵌入模型为知识图谱中的实体生成向量表示
#       并将向量存储到 Neo4j 数据库中
#
# 使用方法：
#   python storage/embed_entities.py
# ============================================================

import os
import sys
import json
import time
from typing import List, Dict, Optional
import requests
from dotenv import load_dotenv

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from storage.neo4j_config import db

# 加载环境变量
load_dotenv()

class OllamaEmbedder:
    """Ollama 嵌入模型客户端"""
    
    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip('/')
        self.model = model or os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
        self.api_url = f"{self.base_url}/api/embeddings"
        
        print(f"[OK] Ollama Embedder 初始化完成:")
        print(f"  - Base URL: {self.base_url}")
        print(f"  - Model: {self.model}")
    
    def embed(self, text: str) -> Optional[List[float]]:
        """
        为文本生成嵌入向量
        
        Args:
            text: 输入文本
            
        Returns:
            嵌入向量（浮点数列表），失败时返回 None
        """
        try:
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "prompt": text
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("embedding")
            else:
                print(f"警告：Ollama API 返回错误状态码 {response.status_code}")
                return None
                
        except requests.exceptions.ConnectionError:
            print(f"错误：无法连接到 Ollama 服务 ({self.base_url})")
            print("请确保 Ollama 正在运行：ollama serve")
            return None
        except Exception as e:
            print(f"错误：生成嵌入向量失败：{e}")
            return None
    
    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[Optional[List[float]]]:
        """
        批量生成嵌入向量
        
        Args:
            texts: 文本列表
            batch_size: 批次大小
            
        Returns:
            嵌入向量列表
        """
        embeddings = []
        total = len(texts)
        
        print(f"正在为 {total} 个文本生成嵌入向量...")
        
        for i in range(0, total, batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = []
            
            for j, text in enumerate(batch):
                embedding = self.embed(text)
                batch_embeddings.append(embedding)
                
                if (j + 1) % 10 == 0:
                    print(f"  批次 {i // batch_size + 1}: 处理 {i + j + 1}/{total}")
            
            embeddings.extend(batch_embeddings)
            
            # 避免请求过快
            time.sleep(0.1)
        
        return embeddings
    
    def test_connection(self) -> bool:
        """测试 Ollama 连接"""
        try:
            # 尝试生成一个简单的嵌入
            test_embedding = self.embed("测试")
            if test_embedding:
                print(f"✓ Ollama 连接成功，向量维度：{len(test_embedding)}")
                return True
            else:
                print("✗ Ollama 连接失败")
                return False
        except Exception as e:
            print(f"✗ Ollama 连接测试失败：{e}")
            return False


class EntityEmbedder:
    """实体向量化器"""
    
    def __init__(self):
        self.embedder = OllamaEmbedder()
        self.vector_index_created = False
    
    def create_vector_index(self):
        """在 Neo4j 中创建向量索引"""
        print("\n正在创建向量索引...")
        
        # 检查是否已存在索引
        check_query = """
        SHOW INDEXES 
        WHERE name = 'entity_embedding_index'
        """
        
        result = db.query(check_query)
        if result and len(result) > 0:
            print("✓ 向量索引已存在")
            self.vector_index_created = True
            return
        
        # 创建向量索引
        create_index_query = """
        CREATE VECTOR INDEX entity_embedding_index 
        FOR (n:Entity) 
        ON (n.embedding) 
        OPTIONS {indexConfig: {
            `vector.dimensions`: 768,
            `vector.similarity_function`: 'cosine'
        }}
        """
        
        try:
            db.execute_write(create_index_query)
            print("✓ 向量索引创建成功")
            self.vector_index_created = True
            
            # 等待索引就绪
            print("等待向量索引就绪...")
            time.sleep(2)
            
        except Exception as e:
            print(f"警告：创建向量索引失败：{e}")
            print("将继续执行，但向量检索功能可能不可用")
    
    def get_all_entities(self) -> List[Dict]:
        """获取所有需要向量化的实体"""
        query = """
        MATCH (n:Entity)
        RETURN n.id as id, n.name as name, n.normalized_name as normalized_name, 
               n.aligned_name as aligned_name, labels(n) as labels
        """
        
        result = db.query(query)
        if not result:
            return []
        
        entities = []
        for record in result:
            # 确定用于向量化的文本（优先使用标准化名称）
            if record.get("aligned_name"):
                embed_text = record["aligned_name"]
            elif record.get("normalized_name"):
                embed_text = record["normalized_name"]
            else:
                embed_text = record["name"]
            
            entities.append({
                "id": record["id"],
                "name": record["name"],
                "embed_text": embed_text,
                "labels": record["labels"]
            })
        
        return entities
    
    def embed_and_store(self, entities: List[Dict], batch_size: int = 32):
        """
        为实体生成向量并存储到 Neo4j
        
        Args:
            entities: 实体列表
            batch_size: 批次大小
        """
        if not entities:
            print("没有需要向量化的实体")
            return
        
        print(f"\n开始为 {len(entities)} 个实体生成向量...")
        
        # 批量生成嵌入向量
        texts = [e["embed_text"] for e in entities]
        embeddings = self.embedder.embed_batch(texts, batch_size)
        
        # 存储到 Neo4j
        print("\n正在将向量存储到 Neo4j...")
        
        update_query = """
        MATCH (n:Entity {id: $id})
        SET n.embedding = $embedding,
            n.embedded_text = $embed_text
        """
        
        success_count = 0
        failed_count = 0
        
        for i, entity in enumerate(entities):
            embedding = embeddings[i]
            
            if embedding:
                try:
                    db.execute_write(update_query, {
                        "id": entity["id"],
                        "embedding": embedding,
                        "embed_text": entity["embed_text"]
                    })
                    success_count += 1
                except Exception as e:
                    print(f"警告：更新实体 {entity['id']} 失败：{e}")
                    failed_count += 1
            else:
                failed_count += 1
            
            if (i + 1) % 50 == 0:
                print(f"  已处理 {i + 1}/{len(entities)} (成功：{success_count}, 失败：{failed_count})")
        
        print(f"\n向量化完成:")
        print(f"  ✓ 成功：{success_count}")
        print(f"  ✗ 失败：{failed_count}")
    
    def process_all(self):
        """执行完整的向量化流程"""
        print("=" * 60)
        print("  实体向量化流程")
        print("=" * 60)
        
        # 1. 测试 Ollama 连接
        print("\n[Step 1/4] 测试 Ollama 连接...")
        if not self.embedder.test_connection():
            print("\n错误：无法连接到 Ollama 服务")
            print("请确保:")
            print("  1. Ollama 已安装并运行：ollama serve")
            print("  2. 已拉取向量化模型：ollama pull nomic-embed-text")
            return False
        
        # 2. 创建向量索引
        print("\n[Step 2/4] 创建向量索引...")
        self.create_vector_index()
        
        # 3. 获取所有实体
        print("\n[Step 3/4] 获取所有实体...")
        entities = self.get_all_entities()
        print(f"找到 {len(entities)} 个实体")
        
        if not entities:
            print("没有找到实体，请先运行 storage/import_data.py 导入数据")
            return False
        
        # 4. 向量化并存储
        print("\n[Step 4/4] 生成向量并存储...")
        self.embed_and_store(entities)
        
        print("\n" + "=" * 60)
        print("  向量化完成！")
        print("=" * 60)
        return True


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("  知识图谱实体向量化脚本")
    print("=" * 60)
    
    embedder = EntityEmbedder()
    success = embedder.process_all()
    
    if success:
        print("\n✓ 所有实体已向量化完成")
        print("\n下一步:")
        print("  1. 修改 .env 文件，设置 VECTOR_SEARCH_ENABLED=true")
        print("  2. 运行 python pipeline.py 测试向量检索效果")
    else:
        print("\n✗ 向量化失败，请检查上述错误信息")
        print("\n提示:")
        print("  1. 确保 Ollama 正在运行：ollama serve")
        print("  2. 确保已拉取向量化模型：ollama pull nomic-embed-text")
        print("  3. 确保 Neo4j 数据库中有数据：python storage/import_data.py")


if __name__ == "__main__":
    main()
