# ============================================================
# data_models.py - 共享数据结构定义
# ============================================================
# 作用：定义整个系统中各模块传递数据的统一格式。
# 说明：这里定义的类主要是为了在不同模块之间传递数据时保持一致性和清晰性，避免使用松散的字典或其他不明确的数据结构。
# ============================================================

from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class Triple:
    """
    知识图谱中的一条三元组（最小知识单元）。

    示例：
        Triple(
            head="高血压",
            head_type="Disease",
            relation="常用药物",
            tail="硝苯地平",
            tail_type="Drug",
            source="医保目录"
        )
        表示：高血压（疾病）--[常用药物]-->硝苯地平（药物），来源于医保目录
    """
    head: str           # 头实体名称，如 "高血压"
    head_type: str      # 头实体类型，如 "Disease"
    relation: str       # 关系名称，如 "常用药物"
    tail: str           # 尾实体名称，如 "硝苯地平"
    tail_type: str      # 尾实体类型，如 "Drug"
    source: str = ""    # 数据来源，如 "医保目录"、"平安保险条款"

    def to_text(self) -> str:
        """转为人类可读的文本格式"""
        return f"{self.head}({self.head_type}) --[{self.relation}]--> {self.tail}({self.tail_type})"

    def to_dict(self) -> dict:
        """转为字典格式（方便JSON序列化和前端展示）"""
        return {
            "head": self.head,
            "head_type": self.head_type,
            "relation": self.relation,
            "tail": self.tail,
            "tail_type": self.tail_type,
            "source": self.source,
        }


@dataclass
class ParsedQuestion:
    """
    问题理解模块的输出结构。

    示例：用户问 "70岁高血压能买护理险吗？"
        ParsedQuestion(
            original_question="70岁高血压能买护理险吗？",
            entities=[
                {"text": "高血压", "type": "Disease", "normalized": "高血压"},
                {"text": "护理险", "type": "InsuranceProduct", "normalized": "护理险"},
            ],
            intent="insurability",
            age=70,
            constraints={}
        )
    """
    original_question: str                                 # 用户原始问题
    entities: List[Dict] = field(default_factory=list)     # 识别出的实体列表
    # 每个实体格式: {"text": "原文", "type": "实体类型", "normalized": "标准化名称"}
    intent: str = "general"                                # 用户意图分类
    # 可选值: insurability(可投保性) / cost(费用) / coverage(保障范围)
    #         treatment(治疗) / eligibility(资格条件) / general(通用)
    age: Optional[int] = None                              # 提取的年龄（如有）
    constraints: Dict = field(default_factory=dict)        # 其他约束条件


@dataclass
class RetrievalResult:
    """
    图谱检索模块的输出结构。

    包含从知识图谱中查询到的相关三元组及元信息。
    """
    triples: List[Triple] = field(default_factory=list)        # 检索到的三元组列表
    matched_entities: List[str] = field(default_factory=list)  # 成功匹配到图谱的实体名
    query_used: str = ""                                        # 实际执行的Cypher查询语句
    hop_count: int = 1                                          # 查询的跳数


@dataclass
class FormattedAnswer:
    """
    最终输出给用户的格式化答案。

    包含答案文本、溯源信息、置信度等。
    """
    answer_text: str                                            # LLM生成的答案正文
    source_triples: List[Dict] = field(default_factory=list)   # 引用的三元组（溯源用）
    intent: str = "general"                                     # 识别的用户意图
    matched_entities: List[str] = field(default_factory=list)  # 匹配到的实体
    confidence: str = "medium"                                  # 置信度: high / medium / low

    def to_display_dict(self) -> dict:
        """转为前端展示用的字典"""
        return {
            "answer": self.answer_text,
            "sources": self.source_triples,
            "intent": self.intent,
            "entities": self.matched_entities,
            "confidence": self.confidence,
        }