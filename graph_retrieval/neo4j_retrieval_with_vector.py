# ============================================================
# graph_retrieval/neo4j_retrieval_with_vector.py
# ============================================================
# 图谱检索模块（支持向量检索）：连接 Neo4j 并执行 Cypher 查询
# ============================================================

import os
import sys
import yaml
import requests
from typing import List, Dict, Optional
from dotenv import load_dotenv

# 尝试导入 neo4j 模块，如果失败则使用 Mock 数据
try:
    from neo4j import GraphDatabase, basic_auth
    NEO4J_AVAILABLE = True
except ImportError:
    print("警告：neo4j 模块未安装，将使用 Mock 数据")
    NEO4J_AVAILABLE = False

# 加载环境变量
load_dotenv()

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from data_models import Triple, ParsedQuestion, RetrievalResult


class Neo4jGraphRetrievalWithVector:
    """
    基于 Neo4j 的图谱检索模块（支持向量检索）。
    负责将问题中的实体匹配到图谱节点，执行 Cypher 查询获取相关子图。
    支持传统关键词匹配和向量相似度搜索的混合检索。
    """
    
    def __init__(self, config_path: str = None):
        """
        初始化 Neo4j 连接。
        
        Args:
            config_path: config.yaml 的路径，默认为项目根目录下的 config.yaml
        """
        # 加载配置
        if config_path is None:
            config_path = os.path.join(BASE_DIR, "config.yaml")
        self.config = self._load_config(config_path)
        
        # 加载系统配置
        self.max_hops = self.config.get("system", {}).get("max_hops", 2)
        self.max_triples = self.config.get("system", {}).get("max_triples", 20)
        
        # 连接 Neo4j
        self.driver = self._connect_neo4j()
        
        # 初始化实体对齐映射
        self.entity_alignments = self._load_entity_alignments()
        
        # 初始化向量检索配置
        self.vector_search_enabled = os.getenv("VECTOR_SEARCH_ENABLED", "false").lower() == "true"
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip('/')
        self.ollama_embedding_model = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
        self.vector_top_k = int(os.getenv("VECTOR_TOP_K", "10"))
        self.vector_similarity_threshold = float(os.getenv("VECTOR_SIMILARITY_THRESHOLD", "0.7"))
        
        if self.vector_search_enabled:
            print(f"[OK] 向量检索已启用 (Ollama: {self.ollama_embedding_model})")
        else:
            print("[INFO] 向量检索未启用，使用传统关键词匹配")
        
        print("[OK] Neo4jGraphRetrievalWithVector initialized")
    
    def _load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"警告：加载配置文件失败：{e}")
            return {
                "neo4j": {
                    "uri": "bolt://localhost:7687",
                    "user": "neo4j",
                    "password": "password"
                }
            }
    
    def _connect_neo4j(self):
        """连接 Neo4j 数据库"""
        if not NEO4J_AVAILABLE:
            print("警告：neo4j 模块未安装，将使用 Mock 数据")
            return None
        
        try:
            neo4j_config = self.config.get("neo4j", {})
            uri = neo4j_config.get("uri", "bolt://localhost:7687")
            user = neo4j_config.get("user", "neo4j")
            password = neo4j_config.get("password", "password")
            
            driver = GraphDatabase.driver(uri, auth=basic_auth(user, password))
            
            with driver.session() as session:
                session.run("MATCH (n) RETURN count(n) LIMIT 1")
            
            print(f"[OK] 成功连接到 Neo4j: {uri}")
            return driver
        except Exception as e:
            print(f"警告：连接 Neo4j 失败：{e}")
            print("将使用 Mock 数据进行测试")
            return None
    
    def _load_entity_alignments(self) -> Dict[str, str]:
        """加载实体对齐映射"""
        return {
            "高血压": "高血压",
            "原发性高血压": "高血压",
            "继发性高血压": "高血压",
            "高血压病": "高血压",
            "糖尿病": "糖尿病",
            "2 型糖尿病": "糖尿病",
            "1 型糖尿病": "糖尿病",
            "妊娠期糖尿病": "糖尿病",
            "心肌梗死": "心肌梗死",
            "急性心肌梗死": "心肌梗死",
            "脑梗塞": "脑梗死",
            "脑梗死": "脑梗死",
            "脑栓塞": "脑梗死",
            "肺炎": "肺炎",
            "细菌性肺炎": "肺炎",
            "病毒性肺炎": "肺炎",
            "肾炎": "肾炎",
            "肾小球肾炎": "肾炎",
            "肾盂肾炎": "肾炎",
        }
    
    def _normalize_entity(self, entity_name: str) -> str:
        """标准化实体名称"""
        entity_name = entity_name.replace("（", "(").replace("）", ")")
        import re
        entity_name = re.sub(r'\([^)]*\)', '', entity_name)
        entity_name = re.sub(r'[0-9]+', '', entity_name)
        entity_name = re.sub(r'[^\u4e00-\u9fa5a-zA-Z]', '', entity_name)
        entity_name = entity_name.strip().lower()
        
        for key, value in self.entity_alignments.items():
            if key in entity_name:
                return value
        
        return entity_name
    
    def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """使用 Ollama 生成文本的嵌入向量"""
        try:
            response = requests.post(
                f"{self.ollama_base_url}/api/embeddings",
                json={
                    "model": self.ollama_embedding_model,
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
        except Exception as e:
            print(f"警告：生成嵌入向量失败：{e}")
            return None
    
    def _vector_search(self, query_text: str, top_k: int = None) -> List[Dict]:
        """使用向量相似度搜索实体"""
        if not self.driver:
            return []
        
        top_k = top_k or self.vector_top_k
        
        query_embedding = self._generate_embedding(query_text)
        if not query_embedding:
            print("警告：无法生成查询向量，回退到关键词匹配")
            return []
        
        vector_query = """
        CALL db.index.vector.queryNodes('entity_embedding_index', $top_k, $embedding)
        YIELD node, score
        WHERE score >= $threshold
        RETURN node, score
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(
                    vector_query,
                    top_k=top_k,
                    embedding=query_embedding,
                    threshold=self.vector_similarity_threshold
                )
                
                matches = []
                for record in result:
                    node = record["node"]
                    score = record["score"]
                    matches.append({
                        "id": node.get("id"),
                        "name": node.get("name"),
                        "normalized_name": node.get("normalized_name"),
                        "aligned_name": node.get("aligned_name"),
                        "labels": list(node.labels) if hasattr(node, 'labels') else [],
                        "similarity_score": score
                    })
                
                return matches
        except Exception as e:
            print(f"警告：向量搜索失败：{e}")
            print("回退到关键词匹配")
            return []
    
    def _build_cypher_query(self, parsed_question: ParsedQuestion, max_hops: int = 2) -> str:
        """构建 Cypher 查询语句"""
        entities = parsed_question.entities
        intent = parsed_question.intent
        
        disease_entities = [e for e in entities if e["type"] == "Disease"]
        if disease_entities:
            disease_name = self._normalize_entity(disease_entities[0]["text"])
        
        insurance_entities = [e for e in entities if e["type"] == "InsuranceProduct"]
        if insurance_entities:
            insurance_name = self._normalize_entity(insurance_entities[0]["text"])
        
        if intent == "insurability":
            if disease_entities and insurance_entities:
                return f"MATCH (p:InsuranceProduct)-[r]-(d:Disease) WHERE d.name CONTAINS '{disease_name}' AND p.name CONTAINS '{insurance_name}' RETURN p, r, d LIMIT 20"
            elif disease_entities:
                return f"MATCH (p:InsuranceProduct)-[r]-(d:Disease) WHERE d.name CONTAINS '{disease_name}' RETURN p, r, d LIMIT 20"
            elif insurance_entities:
                return f"MATCH (p:InsuranceProduct)-[r]-(d:Disease) WHERE p.name CONTAINS '{insurance_name}' RETURN p, r, d LIMIT 20"
        elif intent == "treatment":
            if disease_entities:
                return f"MATCH (d:Disease)-[r:TREATED_BY]->(dr:Drug) WHERE d.name CONTAINS '{disease_name}' OR d.aligned_name = '{disease_name}' RETURN d, r, dr LIMIT 20"
        elif intent == "cost":
            if insurance_entities:
                return f"MATCH (p:InsuranceProduct)-[r:PRICE]->(pr:Price) WHERE p.name CONTAINS '{insurance_name}' RETURN p, r, pr LIMIT 20"
        elif intent == "coverage":
            if insurance_entities:
                return f"MATCH (p:InsuranceProduct)-[r:COVERAGE]->(c:Coverage) WHERE p.name CONTAINS '{insurance_name}' RETURN p, r, c LIMIT 20"
        elif intent == "eligibility":
            if insurance_entities:
                return f"MATCH (p:InsuranceProduct)-[r:AGE_LIMIT]->(al:AgeLimit) WHERE p.name CONTAINS '{insurance_name}' RETURN p, r, al LIMIT 20"
        
        if entities:
            entity = entities[0]
            entity_name = self._normalize_entity(entity["text"])
            entity_type = entity["type"]
            if max_hops == 1:
                return f"MATCH (n:{entity_type})-[r]-(m) WHERE n.name CONTAINS '{entity_name}' RETURN n, r, m LIMIT 20"
            else:
                return f"MATCH (n:{entity_type})-[r1]-(m)-[r2]-(o) WHERE n.name CONTAINS '{entity_name}' RETURN n, r1, m, r2, o LIMIT 30"
        
        return "MATCH (n)-[r]-(m) RETURN n, r, m LIMIT 10"
    
    def _execute_query(self, query: str, parameters: Dict = None) -> List[Dict]:
        """执行 Cypher 查询"""
        if not self.driver:
            return self._get_mock_data()
        
        try:
            with self.driver.session() as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            print(f"查询失败：{e}")
            return self._get_mock_data()
    
    def _get_mock_data(self) -> List[Dict]:
        """获取 Mock 数据"""
        mock_data = [
            {'d': {'name': '高血压', 'type': 'Disease'}, 'r': {'type': 'TREATED_BY'}, 'dr': {'name': '硝苯地平', 'type': 'Drug'}},
            {'d': {'name': '高血压', 'type': 'Disease'}, 'r': {'type': 'TREATED_BY'}, 'dr': {'name': '氨氯地平', 'type': 'Drug'}},
            {'p': {'name': '太平养老护理险', 'type': 'InsuranceProduct'}, 'r': {'type': 'AGE_LIMIT'}, 'al': {'min_age': 18, 'max_age': 75, 'type': 'AgeLimit'}},
            {'p': {'name': '平安护理险', 'type': 'InsuranceProduct'}, 'r': {'type': 'AGE_LIMIT'}, 'al': {'min_age': 18, 'max_age': 65, 'type': 'AgeLimit'}},
            {'p': {'name': '太平养老护理险', 'type': 'InsuranceProduct'}, 'r': {'type': 'COVERAGE'}, 'c': {'content': '长期护理费用', 'type': 'Coverage'}},
        ]
        return mock_data
    
    def _parse_query_result(self, result: List[Dict]) -> List[Triple]:
        """解析查询结果为 Triple 对象"""
        triples = []
        
        for record in result:
            if 'd' in record and 'r' in record and 'dr' in record:
                triples.append(Triple(
                    head=record['d'].get('name', 'Unknown'),
                    head_type=record['d'].get('type', 'Entity'),
                    relation=record['r'].get('type', 'RELATED_TO'),
                    tail=record['dr'].get('name', 'Unknown'),
                    tail_type=record['dr'].get('type', 'Entity')
                ))
            elif 'p' in record and 'r' in record and 'd' in record:
                triples.append(Triple(
                    head=record['p'].get('name', 'Unknown'),
                    head_type=record['p'].get('type', 'Entity'),
                    relation=record['r'].get('type', 'RELATED_TO'),
                    tail=record['d'].get('name', 'Unknown'),
                    tail_type=record['d'].get('type', 'Entity')
                ))
            elif 'p' in record and 'r' in record and 'al' in record:
                triples.append(Triple(
                    head=record['p'].get('name', 'Unknown'),
                    head_type=record['p'].get('type', 'Entity'),
                    relation=record['r'].get('type', 'RELATED_TO'),
                    tail=f"{record['al'].get('min_age', 0)}-{record['al'].get('max_age', 100)}岁",
                    tail_type=record['al'].get('type', 'Entity')
                ))
            elif 'p' in record and 'r' in record and 'c' in record:
                triples.append(Triple(
                    head=record['p'].get('name', 'Unknown'),
                    head_type=record['p'].get('type', 'Entity'),
                    relation=record['r'].get('type', 'RELATED_TO'),
                    tail=record['c'].get('content', 'Unknown'),
                    tail_type=record['c'].get('type', 'Entity')
                ))
            elif 'n' in record and 'r' in record and 'm' in record:
                triples.append(Triple(
                    head=record['n'].get('name', 'Unknown'),
                    head_type=record['n'].get('type', 'Entity'),
                    relation=record['r'].get('type', 'RELATED_TO'),
                    tail=record['m'].get('name', 'Unknown'),
                    tail_type=record['m'].get('type', 'Entity')
                ))
        
        return triples
    
    def retrieve(self, parsed_question: ParsedQuestion, max_hops: int = None) -> RetrievalResult:
        """根据解析后的问题，从知识图谱中检索相关三元组"""
        try:
            hop_count = max_hops if max_hops is not None else self.max_hops
            
            # ========== 向量检索（如果启用）==========
            vector_matches = []
            if self.vector_search_enabled:
                print("[INFO] 正在执行向量检索...")
                
                for entity in parsed_question.entities:
                    entity_text = entity["text"]
                    matches = self._vector_search(entity_text)
                    
                    if matches:
                        print(f"  ✓ 实体 '{entity_text}' 找到 {len(matches)} 个相似实体")
                        vector_matches.extend(matches)
                    else:
                        print(f"  ✗ 实体 '{entity_text}' 向量检索无结果")
                
                seen_ids = set()
                unique_matches = []
                for match in vector_matches:
                    if match["id"] not in seen_ids:
                        unique_matches.append(match)
                        seen_ids.add(match["id"])
                vector_matches = unique_matches
                
                if vector_matches:
                    print(f"[OK] 向量检索完成，共找到 {len(vector_matches)} 个实体")
            
            # ========== 传统关键词检索 ==========
            query = self._build_cypher_query(parsed_question, hop_count)
            result = self._execute_query(query)
            triples = self._parse_query_result(result)
            
            if len(triples) == 0 and self.driver:
                disease_entities = [e for e in parsed_question.entities if e.get("type") == "Disease"]
                if disease_entities:
                    disease_name = self._normalize_entity(disease_entities[0]["text"])
                    fallback_query = f"MATCH (d:Disease)-[r]-(m) WHERE d.name CONTAINS '{disease_name}' OR d.aligned_name = '{disease_name}' RETURN d, r, m LIMIT {self.max_triples}"
                    fallback_result = self._execute_query(fallback_query)
                    triples = self._parse_query_result(fallback_result)
                    if triples:
                        query = f"[主查询无结果，已用疾病子图回退] {fallback_query}"
            
            # ========== 融合向量检索结果 ==========
            if self.vector_search_enabled and vector_matches:
                for match in vector_matches:
                    entity_type = match["labels"][0] if match["labels"] else "Entity"
                    entity_name = match.get("aligned_name") or match.get("normalized_name") or match.get("name")
                    
                    # 构建基于向量匹配实体的查询
                    expansion_query = f"MATCH (n:{entity_type} {{id: '{match['id']}'}})-[r]-(m) RETURN n, r, m LIMIT 10"
                    expansion_result = self._execute_query(expansion_query)
                    expansion_triples = self._parse_query_result(expansion_result)
                    
                    if expansion_triples:
                        triples.extend(expansion_triples)
                        print(f"  → 基于向量匹配实体 '{entity_name}' 扩展 {len(expansion_triples)} 条关系")
                
                # 去重
                seen_triples = set()
                unique_triples = []
                for triple in triples:
                    key = (triple.head, triple.relation, triple.tail)
                    if key not in seen_triples:
                        unique_triples.append(triple)
                        seen_triples.add(key)
                triples = unique_triples
            
            triples = triples[:self.max_triples]
            
            matched_entities = []
            for entity in parsed_question.entities:
                normalized_name = self._normalize_entity(entity["text"])
                matched_entities.append(normalized_name)
            
            for match in vector_matches:
                entity_name = match.get("name", "Unknown")
                if entity_name not in matched_entities:
                    matched_entities.append(entity_name)
            
            return RetrievalResult(
                triples=triples,
                matched_entities=matched_entities,
                query_used=query,
                hop_count=hop_count
            )
        except Exception as e:
            print(f"检索失败：{e}")
            mock_triples = self._parse_query_result(self._get_mock_data())
            matched_entities = [self._normalize_entity(e["text"]) for e in parsed_question.entities]
            return RetrievalResult(
                triples=mock_triples,
                matched_entities=matched_entities,
                query_used="[Error: 检索失败，使用 Mock 数据]",
                hop_count=1
            )
    
    def close(self):
        """关闭 Neo4j 连接"""
        if self.driver:
            self.driver.close()
            print("[OK] Neo4j 连接已关闭")
