# ============================================================
# graph_retrieval/neo4j_retrieval.py
# ============================================================
# 图谱检索模块：连接Neo4j并执行Cypher查询
# ============================================================

import os
import sys
import yaml
from typing import List, Dict, Optional

# 尝试导入neo4j模块，如果失败则使用Mock数据
try:
    from neo4j import GraphDatabase, basic_auth
    NEO4J_AVAILABLE = True
except ImportError:
    print("警告: neo4j模块未安装，将使用Mock数据")
    NEO4J_AVAILABLE = False

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv

# 加载 .env（图谱检索模块独立启动时也需要）
load_dotenv(os.path.join(BASE_DIR, ".env"))

from data_models import Triple, ParsedQuestion, RetrievalResult
from storage.neo4j_settings import get_neo4j_settings


def _as_node_dict(node) -> Dict:
    """将 Neo4j 节点（dict / Node / 元组）统一为属性字典。"""
    if node is None:
        return {}
    if isinstance(node, dict):
        return node
    if isinstance(node, tuple) and node:
        return _as_node_dict(node[0])
    if hasattr(node, "_properties"):
        return dict(node._properties)
    if hasattr(node, "items"):
        return dict(node)
    return {}


def _node_name(node, default: str = "Unknown") -> str:
    props = _as_node_dict(node)
    return props.get("name") or props.get("label") or props.get("id") or default


def _node_label(node, default: str = "Entity") -> str:
    props = _as_node_dict(node)
    if props.get("type"):
        return props["type"]
    if hasattr(node, "labels") and node.labels:
        return list(node.labels)[0]
    return default


def _relation_type(rel, default: str = "RELATED_TO") -> str:
    """
    解析关系类型。
    多关系 Cypher（如 :COVERS|EXCLUDES）时，Neo4j 可能返回 (起点, 类型, 终点) 元组。
    """
    if rel is None:
        return default
    if isinstance(rel, str):
        return rel
    if isinstance(rel, dict):
        return rel.get("type", default)
    if isinstance(rel, tuple):
        if len(rel) >= 2 and isinstance(rel[1], str):
            return rel[1]
        if len(rel) >= 2:
            return _relation_type(rel[1], default)
    return getattr(rel, "type", default) or default


class Neo4jGraphRetrieval:
    """
    基于Neo4j的图谱检索模块。
    负责将问题中的实体匹配到图谱节点，执行Cypher查询获取相关子图。
    """
    
    def __init__(self, config_path: str = None):
        """
        初始化Neo4j连接。
        
        Args:
            config_path: config.yaml的路径，默认为项目根目录下的config.yaml
        """
        # 加载配置
        if config_path is None:
            config_path = os.path.join(BASE_DIR, "config.yaml")
        self.config = self._load_config(config_path)
        
        # 加载系统配置
        self.max_hops = self.config.get("system", {}).get("max_hops", 2)
        self.max_triples = self.config.get("system", {}).get("max_triples", 20)
        
        # 连接 Neo4j
        self.neo4j_settings = get_neo4j_settings()
        self.database = self.neo4j_settings["database"]
        self.driver = self._connect_neo4j()
        
        # 初始化实体对齐映射
        self.entity_alignments = self._load_entity_alignments()
        
        print("[OK] Neo4jGraphRetrieval initialized")
    
    def _load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"警告: 加载配置文件失败: {e}")
            # 返回默认配置
            return {
                "neo4j": {
                    "uri": "bolt://localhost:7687",
                    "user": "neo4j",
                    "password": "password"
                }
            }
    
    def _connect_neo4j(self):
        """连接Neo4j数据库"""
        if not NEO4J_AVAILABLE:
            print("警告: neo4j模块未安装，将使用Mock数据")
            return None
        
        try:
            settings = self.neo4j_settings
            uri = settings["uri"]
            user = settings["user"]
            password = settings["password"]

            driver = GraphDatabase.driver(uri, auth=basic_auth(user, password))

            with driver.session(database=self.database) as session:
                session.run("RETURN 1")

            print(f"[OK] 成功连接到Neo4j: {uri} (db={self.database})")
            return driver
        except Exception as e:
            print(f"警告: 连接Neo4j失败: {e}")
            print("将使用Mock数据进行测试")
            return None
    
    def _load_entity_alignments(self) -> Dict[str, str]:
        """加载实体对齐映射"""
        # 常见同义词映射
        return {
            "高血压": "高血压",
            "原发性高血压": "高血压",
            "继发性高血压": "高血压",
            "高血压病": "高血压",
            "糖尿病": "糖尿病",
            "2型糖尿病": "糖尿病",
            "1型糖尿病": "糖尿病",
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
        # 移除括号内容
        entity_name = entity_name.replace("（", "(").replace("）", ")")
        import re
        entity_name = re.sub(r'\([^)]*\)', '', entity_name)
        
        # 移除数字和特殊字符
        entity_name = re.sub(r'[0-9]+', '', entity_name)
        entity_name = re.sub(r'[^\u4e00-\u9fa5a-zA-Z]', '', entity_name)
        
        # 去除首尾空格
        entity_name = entity_name.strip()
        
        # 转换为小写
        entity_name = entity_name.lower()
        
        # 应用对齐映射
        for key, value in self.entity_alignments.items():
            if key in entity_name:
                return value
        
        return entity_name
    
    def _build_cypher_query(self, parsed_question: ParsedQuestion, max_hops: int = 2) -> str:
        """构建Cypher查询语句"""
        entities = parsed_question.entities
        intent = parsed_question.intent
        
        # 处理疾病实体
        disease_entities = [e for e in entities if e["type"] == "Disease"]
        if disease_entities:
            disease_name = self._normalize_entity(disease_entities[0]["text"])
        
        # 处理保险产品实体
        insurance_entities = [e for e in entities if e["type"] == "InsuranceProduct"]
        if insurance_entities:
            insurance_name = self._normalize_entity(insurance_entities[0]["text"])
        
        # insurability 在 retrieve() 中拆成多条 Cypher（疾病承保 + 年龄限制）
        if intent == "insurability":
            queries = self._build_insurability_queries(parsed_question)
            return queries[0] if queries else "MATCH (n)-[r]-(m) RETURN n, r, m LIMIT 10"
        elif intent == "treatment":
            # 治疗意图（用 CONTAINS 匹配，图中可能是「原发性高血压」等）
            if disease_entities:
                return f"MATCH (d:Disease)-[r:TREATED_BY]->(dr:Drug) WHERE d.name CONTAINS '{disease_name}' OR d.aligned_name = '{disease_name}' RETURN d, r, dr LIMIT 20"
        elif intent == "cost":
            institution_entities = [e for e in entities if e["type"] == "Institution"]
            if institution_entities:
                inst_name = self._normalize_entity(institution_entities[0]["text"])
                return (
                    f"MATCH (i:Institution)-[r:CHARGE]->(pr:Price) "
                    f"WHERE i.name CONTAINS '{inst_name}' RETURN i, r, pr LIMIT 20"
                )
            if insurance_entities:
                return (
                    f"MATCH (p:InsuranceProduct)-[r:PRICE]->(pr:Price) "
                    f"WHERE p.name CONTAINS '{insurance_name}' OR p.short_name CONTAINS '{insurance_name}' "
                    f"RETURN p, r, pr LIMIT 20"
                )
        elif intent == "coverage":
            if insurance_entities:
                return (
                    f"MATCH (p:InsuranceProduct)-[r:COVERAGE|COVERS]->(c) "
                    f"WHERE (p.name CONTAINS '{insurance_name}' OR p.short_name CONTAINS '{insurance_name}') "
                    f"RETURN p, r, c LIMIT 20"
                )
            institution_entities = [e for e in entities if e["type"] == "Institution"]
            if institution_entities:
                inst_name = self._normalize_entity(institution_entities[0]["text"])
                return (
                    f"MATCH (i:Institution)-[r:PROVIDES]->(s:MedicalService) "
                    f"WHERE i.name CONTAINS '{inst_name}' RETURN i, r, s LIMIT 20"
                )
        elif intent == "eligibility":
            if insurance_entities:
                return (
                    f"MATCH (p:InsuranceProduct)-[r:HAS_AGE_LIMIT]->(al:AgeLimit) "
                    f"WHERE p.name CONTAINS '{insurance_name}' OR p.short_name CONTAINS '{insurance_name}' "
                    f"RETURN p, r, al LIMIT 20"
                )
            institution_entities = [e for e in entities if e["type"] == "Institution"]
            if institution_entities:
                inst_name = self._normalize_entity(institution_entities[0]["text"])
                return (
                    f"MATCH (i:Institution)-[r:ADMISSION]->(a:AdmissionRequirement) "
                    f"WHERE i.name CONTAINS '{inst_name}' RETURN i, r, a LIMIT 20"
                )
        
        # 默认查询：基于所有实体的1-2跳关系
        if entities:
            entity = entities[0]
            entity_name = self._normalize_entity(entity["text"])
            entity_type = entity["type"]
            if max_hops == 1:
                return f"MATCH (n:{entity_type})-[r]-(m) WHERE n.name CONTAINS '{entity_name}' RETURN n, r, m LIMIT 20"
            else:
                return f"MATCH (n:{entity_type})-[r1]-(m)-[r2]-(o) WHERE n.name CONTAINS '{entity_name}' RETURN n, r1, m, r2, o LIMIT 30"
        
        # 兜底查询
        return "MATCH (n)-[r]-(m) RETURN n, r, m LIMIT 10"

    def _build_insurability_queries(self, parsed_question: ParsedQuestion) -> List[str]:
        """投保可行性检索：承保/除外关系与年龄限制分查（HAS_AGE_LIMIT 指向 AgeLimit 而非 Disease）。"""
        entities = parsed_question.entities
        disease_entities = [e for e in entities if e.get("type") == "Disease"]
        insurance_entities = [e for e in entities if e.get("type") == "InsuranceProduct"]

        disease_name = None
        if disease_entities:
            disease_name = self._normalize_entity(disease_entities[0]["text"])

        product_clauses = []
        if insurance_entities:
            raw_product = insurance_entities[0]["text"]
            insurance_name = self._normalize_entity(raw_product)
            product_clauses.append(
                f"(p.name CONTAINS '{insurance_name}' OR p.short_name CONTAINS '{insurance_name}')"
            )
            if "护理" in raw_product or "护理" in insurance_name:
                product_clauses.append(
                    "(p.name CONTAINS '护理' OR p.short_name CONTAINS '护理' OR p.type CONTAINS '护理')"
                )

        product_filter = " OR ".join(product_clauses) if product_clauses else None
        disease_filter = None
        if disease_name:
            disease_filter = (
                f"(d.aligned_name CONTAINS '{disease_name}' OR d.name CONTAINS '{disease_name}')"
            )

        queries: List[str] = []

        if disease_filter:
            coverage_where = disease_filter
            if product_filter:
                coverage_where += f" AND ({product_filter})"
            queries.append(
                "MATCH (p:InsuranceProduct)-[r:COVERS|EXCLUDES]->(d:Disease) "
                f"WHERE {coverage_where} RETURN p, r, d LIMIT 20"
            )
        elif product_filter:
            queries.append(
                "MATCH (p:InsuranceProduct)-[r:COVERS|EXCLUDES]->(d:Disease) "
                f"WHERE {product_filter} RETURN p, r, d LIMIT 20"
            )

        if product_filter:
            queries.append(
                "MATCH (p:InsuranceProduct)-[r:HAS_AGE_LIMIT]->(al:AgeLimit) "
                f"WHERE {product_filter} RETURN p, r, al LIMIT 20"
            )
        elif disease_filter:
            queries.append(
                "MATCH (p:InsuranceProduct)-[r:HAS_AGE_LIMIT]->(al:AgeLimit) "
                f"WHERE EXISTS {{ MATCH (p)-[:COVERS|EXCLUDES]->(d:Disease) WHERE {disease_filter} }} "
                "RETURN p, r, al LIMIT 20"
            )

        if not queries:
            queries.append(
                "MATCH (p:InsuranceProduct)-[r:COVERS|EXCLUDES]->(d:Disease) "
                "RETURN p, r, d LIMIT 10"
            )
        return queries
    
    def _execute_query(self, query: str, parameters: Dict = None) -> List[Dict]:
        """执行Cypher查询"""
        if not self.driver:
            # 使用Mock数据
            return self._get_mock_data()
        
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            print(f"查询失败: {e}")
            # 使用Mock数据作为 fallback
            return self._get_mock_data()
    
    def _get_mock_data(self) -> List[Dict]:
        """获取Mock数据"""
        # 模拟数据，与mock_modules.py中的数据保持一致
        mock_data = [
            {
                'd': {'name': '高血压', 'type': 'Disease'},
                'r': {'type': 'TREATED_BY'},
                'dr': {'name': '硝苯地平', 'type': 'Drug'}
            },
            {
                'd': {'name': '高血压', 'type': 'Disease'},
                'r': {'type': 'TREATED_BY'},
                'dr': {'name': '氨氯地平', 'type': 'Drug'}
            },
            {
                'p': {'name': '太平养老护理险', 'type': 'InsuranceProduct'},
                'r': {'type': 'AGE_LIMIT'},
                'al': {'min_age': 18, 'max_age': 75, 'type': 'AgeLimit'}
            },
            {
                'p': {'name': '平安护理险', 'type': 'InsuranceProduct'},
                'r': {'type': 'AGE_LIMIT'},
                'al': {'min_age': 18, 'max_age': 65, 'type': 'AgeLimit'}
            },
            {
                'p': {'name': '太平养老护理险', 'type': 'InsuranceProduct'},
                'r': {'type': 'COVERAGE'},
                'c': {'content': '长期护理费用', 'type': 'Coverage'}
            },
        ]
        return mock_data
    
    def _parse_query_result(self, result: List[Dict]) -> List[Triple]:
        """解析查询结果为 Triple 对象（兼容 dict / Node / Relationship / tuple）。"""
        triples = []

        def add(head_node, tail_node, rel, head_type="Entity", tail_type="Entity", tail_text=None):
            relation = _relation_type(rel)
            tail = tail_text if tail_text is not None else _node_name(tail_node)
            triples.append(Triple(
                head=_node_name(head_node),
                head_type=head_type or _node_label(head_node),
                relation=relation,
                tail=tail,
                tail_type=tail_type or _node_label(tail_node),
            ))

        for record in result:
            if "d" in record and "r" in record and "dr" in record:
                add(record["d"], record["dr"], record["r"], "Disease", "Drug")
            elif "p" in record and "r" in record and "d" in record:
                add(record["p"], record["d"], record["r"], "InsuranceProduct", "Disease")
            elif "p" in record and "r" in record and "al" in record:
                al = _as_node_dict(record["al"])
                age_text = al.get("label") or f"{al.get('min_age', 0)}-{al.get('max_age', 100)}岁"
                add(record["p"], record["al"], record["r"], "InsuranceProduct", "AgeLimit", age_text)
            elif "p" in record and "r" in record and "c" in record:
                c = _as_node_dict(record["c"])
                tail = c.get("label") or c.get("content") or c.get("name") or c.get("value", "Unknown")
                add(record["p"], record["c"], record["r"], "InsuranceProduct", "Coverage", tail)
            elif "p" in record and "r" in record and "pr" in record:
                pr = _as_node_dict(record["pr"])
                tail = pr.get("label") or pr.get("value") or pr.get("amount", "Unknown")
                add(record["p"], record["pr"], record["r"], "InsuranceProduct", "Price", tail)
            elif "i" in record and "r" in record and "pr" in record:
                pr = _as_node_dict(record["pr"])
                tail = pr.get("label") or pr.get("value", "Unknown")
                add(record["i"], record["pr"], record["r"], "Institution", "Price", tail)
            elif "i" in record and "r" in record and "s" in record:
                add(record["i"], record["s"], record["r"], "Institution", "MedicalService")
            elif "i" in record and "r" in record and "a" in record:
                a = _as_node_dict(record["a"])
                tail = a.get("label") or a.get("value") or a.get("requirements", "Unknown")
                add(record["i"], record["a"], record["r"], "Institution", "AdmissionRequirement", tail)
            elif "d" in record and "r" in record and "m" in record and "dr" not in record:
                add(record["d"], record["m"], record["r"], "Disease", "Entity")
            elif "n" in record and "r" in record and "m" in record:
                add(record["n"], record["m"], record["r"])

        return triples
    
    def retrieve(self, parsed_question: ParsedQuestion, max_hops: int = None) -> RetrievalResult:
        """
        根据解析后的问题，从知识图谱中检索相关三元组。
        
        Args:
            parsed_question: 问题理解的输出
            max_hops: 最大跳数，默认为配置文件中的值
            
        Returns:
            RetrievalResult: 检索到的三元组和匹配信息
        """
        try:
            # 使用配置中的max_hops或传入的值
            hop_count = max_hops if max_hops is not None else self.max_hops
            
            # 投保可行性：分多条 Cypher 检索（疾病关系 + 年龄限制）
            if parsed_question.intent == "insurability":
                queries = self._build_insurability_queries(parsed_question)
                result = []
                for q in queries:
                    result.extend(self._execute_query(q))
                query = " | ".join(queries)
            else:
                query = self._build_cypher_query(parsed_question, hop_count)
                result = self._execute_query(query)

            triples = self._parse_query_result(result)
            # 去重
            seen = set()
            deduped = []
            for t in triples:
                key = (t.head, t.relation, t.tail)
                if key not in seen:
                    seen.add(key)
                    deduped.append(t)
            triples = deduped
            
            # 若图中没有 InsuranceProduct/Institution 等，主查询会返回 0 条；用疾病相关子图回退
            if len(triples) == 0 and self.driver:
                disease_entities = [e for e in parsed_question.entities if e.get("type") == "Disease"]
                if disease_entities:
                    disease_name = self._normalize_entity(disease_entities[0]["text"])
                    fallback_query = f"MATCH (d:Disease)-[r]-(m) WHERE d.name CONTAINS '{disease_name}' OR d.aligned_name = '{disease_name}' RETURN d, r, m LIMIT {self.max_triples}"
                    fallback_result = self._execute_query(fallback_query)
                    triples = self._parse_query_result(fallback_result)
                    if triples:
                        query = f"[主查询无结果，已用疾病子图回退] {fallback_query}"
            
            # 限制返回的三元组数量
            triples = triples[:self.max_triples]
            
            # 提取匹配的实体
            matched_entities = []
            for entity in parsed_question.entities:
                normalized_name = self._normalize_entity(entity["text"])
                matched_entities.append(normalized_name)
            
            return RetrievalResult(
                triples=triples,
                matched_entities=matched_entities,
                query_used=query,
                hop_count=hop_count
            )
        except Exception as e:
            print(f"检索失败: {e}")
            # 返回Mock数据作为fallback
            mock_triples = self._parse_query_result(self._get_mock_data())
            matched_entities = []
            for entity in parsed_question.entities:
                normalized_name = self._normalize_entity(entity["text"])
                matched_entities.append(normalized_name)
            return RetrievalResult(
                triples=mock_triples,
                matched_entities=matched_entities,
                query_used="[Error: 检索失败，使用Mock数据]",
                hop_count=1
            )
    
    def close(self):
        """关闭Neo4j连接"""
        if self.driver:
            self.driver.close()
            print("[OK] Neo4j连接已关闭")

if __name__ == "__main__":
    # 测试图谱检索模块
    retrieval = Neo4jGraphRetrieval()
    
    # 创建测试问题
    test_question = ParsedQuestion(
        original_question="70岁高血压能买护理险吗？",
        entities=[
            {"text": "高血压", "type": "Disease", "normalized": "高血压"},
            {"text": "护理险", "type": "InsuranceProduct", "normalized": "护理险"}
        ],
        intent="insurability",
        age=70
    )
    
    # 执行检索
    result = retrieval.retrieve(test_question)
    
    # 打印结果
    print(f"匹配的实体: {result.matched_entities}")
    print(f"找到 {len(result.triples)} 条三元组:")
    for triple in result.triples:
        print(f"  - {triple.to_text()}")
    
    # 关闭连接
    retrieval.close()