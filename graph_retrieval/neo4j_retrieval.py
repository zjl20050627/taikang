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

from data_models import Triple, ParsedQuestion, RetrievalResult

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
        
        # 连接Neo4j
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
            neo4j_config = self.config.get("neo4j", {})
            uri = neo4j_config.get("uri", "bolt://localhost:7687")
            user = neo4j_config.get("user", "neo4j")
            password = neo4j_config.get("password", "password")
            
            driver = GraphDatabase.driver(uri, auth=basic_auth(user, password))
            
            # 测试连接
            with driver.session() as session:
                session.run("MATCH (n) RETURN count(n) LIMIT 1")
            
            print(f"[OK] 成功连接到Neo4j: {uri}")
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
        
        # 根据意图构建查询（图中若无 InsuranceProduct，会在 retrieve 里用疾病子图回退）
        if intent == "insurability":
            if disease_entities and insurance_entities:
                return f"MATCH (p:InsuranceProduct)-[r]-(d:Disease) WHERE d.name CONTAINS '{disease_name}' AND p.name CONTAINS '{insurance_name}' RETURN p, r, d LIMIT 20"
            elif disease_entities:
                return f"MATCH (p:InsuranceProduct)-[r]-(d:Disease) WHERE d.name CONTAINS '{disease_name}' RETURN p, r, d LIMIT 20"
            elif insurance_entities:
                return f"MATCH (p:InsuranceProduct)-[r]-(d:Disease) WHERE p.name CONTAINS '{insurance_name}' RETURN p, r, d LIMIT 20"
        elif intent == "treatment":
            # 治疗意图（用 CONTAINS 匹配，图中可能是「原发性高血压」等）
            if disease_entities:
                return f"MATCH (d:Disease)-[r:TREATED_BY]->(dr:Drug) WHERE d.name CONTAINS '{disease_name}' OR d.aligned_name = '{disease_name}' RETURN d, r, dr LIMIT 20"
        elif intent == "cost":
            # 费用意图
            if insurance_entities:
                # 保险产品的价格
                return f"MATCH (p:InsuranceProduct)-[r:PRICE]->(pr:Price) WHERE p.name CONTAINS '{insurance_name}' RETURN p, r, pr LIMIT 20"
        elif intent == "coverage":
            # 保障范围意图
            if insurance_entities:
                # 保险产品的保障内容
                return f"MATCH (p:InsuranceProduct)-[r:COVERAGE]->(c:Coverage) WHERE p.name CONTAINS '{insurance_name}' RETURN p, r, c LIMIT 20"
        elif intent == "eligibility":
            # 资格条件意图
            if insurance_entities:
                # 保险产品的年龄限制
                return f"MATCH (p:InsuranceProduct)-[r:AGE_LIMIT]->(al:AgeLimit) WHERE p.name CONTAINS '{insurance_name}' RETURN p, r, al LIMIT 20"
        
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
    
    def _execute_query(self, query: str, parameters: Dict = None) -> List[Dict]:
        """执行Cypher查询"""
        if not self.driver:
            # 使用Mock数据
            return self._get_mock_data()
        
        try:
            with self.driver.session() as session:
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
        """解析查询结果为Triple对象"""
        triples = []
        
        for record in result:
            # 提取节点和关系
            if 'd' in record and 'r' in record and 'dr' in record:
                # 疾病-药物关系
                head = record['d'].get('name', 'Unknown')
                head_type = record['d'].get('type', 'Entity')
                relation = record['r'].get('type', 'RELATED_TO')
                tail = record['dr'].get('name', 'Unknown')
                tail_type = record['dr'].get('type', 'Entity')
                triples.append(Triple(head=head, head_type=head_type, relation=relation, tail=tail, tail_type=tail_type))
            elif 'p' in record and 'r' in record and 'd' in record:
                # 保险产品-疾病关系
                head = record['p'].get('name', 'Unknown')
                head_type = record['p'].get('type', 'Entity')
                relation = record['r'].get('type', 'RELATED_TO')
                tail = record['d'].get('name', 'Unknown')
                tail_type = record['d'].get('type', 'Entity')
                triples.append(Triple(head=head, head_type=head_type, relation=relation, tail=tail, tail_type=tail_type))
            elif 'p' in record and 'r' in record and 'al' in record:
                # 保险产品-年龄限制关系
                head = record['p'].get('name', 'Unknown')
                head_type = record['p'].get('type', 'Entity')
                relation = record['r'].get('type', 'RELATED_TO')
                tail = f"{record['al'].get('min_age', 0)}-{record['al'].get('max_age', 100)}岁"
                tail_type = record['al'].get('type', 'Entity')
                triples.append(Triple(head=head, head_type=head_type, relation=relation, tail=tail, tail_type=tail_type))
            elif 'p' in record and 'r' in record and 'c' in record:
                # 保险产品-保障内容关系
                head = record['p'].get('name', 'Unknown')
                head_type = record['p'].get('type', 'Entity')
                relation = record['r'].get('type', 'RELATED_TO')
                tail = record['c'].get('content', 'Unknown')
                tail_type = record['c'].get('type', 'Entity')
                triples.append(Triple(head=head, head_type=head_type, relation=relation, tail=tail, tail_type=tail_type))
            elif 'd' in record and 'r' in record and 'm' in record and 'dr' not in record:
                # 疾病-关系-任意节点（回退查询，如 Disease-BELONGS_TO-Category 等）
                rel = record.get('r')
                relation = (rel.get('type') if isinstance(rel, dict) else getattr(rel, 'type', None)) or 'RELATED_TO'
                tail_val = record['m']
                tail = tail_val.get('name', str(tail_val)) if isinstance(tail_val, dict) else getattr(tail_val, 'name', 'Unknown')
                triples.append(Triple(
                    head=record['d'].get('name', 'Unknown'),
                    head_type='Disease',
                    relation=relation,
                    tail=tail,
                    tail_type='Entity'
                ))
            elif 'n' in record and 'r' in record and 'm' in record:
                # 通用关系
                head = record['n'].get('name', 'Unknown')
                head_type = record['n'].get('type', 'Entity')
                relation = record['r'].get('type', 'RELATED_TO')
                tail = record['m'].get('name', 'Unknown')
                tail_type = record['m'].get('type', 'Entity')
                triples.append(Triple(head=head, head_type=head_type, relation=relation, tail=tail, tail_type=tail_type))
        
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
            
            # 构建Cypher查询
            query = self._build_cypher_query(parsed_question, hop_count)
            
            # 执行查询
            result = self._execute_query(query)
            triples = self._parse_query_result(result)
            
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