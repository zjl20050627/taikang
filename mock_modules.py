# ============================================================
# mock_modules.py - 其他模块的 Mock 实现
# ============================================================
# 模拟「问题理解」和「图谱检索」两个模块的行为，
# ============================================================

import re
from typing import List
from data_models import Triple, ParsedQuestion, RetrievalResult


# ============================================================
# Mock 问题理解
# ============================================================

class MockQuestionUnderstanding:
    """
    基于关键词规则的简易问题理解（Mock）。

    真实版本应使用 HanLP / BERT-NER 做实体识别 + 意图分类。
    这里用正则和关键词匹配来模拟，足够测试其余模块。
    """

    # ---- 实体词典 ----
    DISEASE_KEYWORDS = [
        "高血压", "糖尿病", "冠心病", "心脏病", "中风", "脑梗",
        "肾病", "癌症", "肿瘤", "白血病", "肺炎", "哮喘",
        "关节炎", "骨质疏松", "阿尔茨海默", "帕金森", "痛风",
        "甲状腺", "抑郁症", "原发性高血压",
    ]
    INSURANCE_KEYWORDS = [
        "护理险", "医疗险", "重疾险", "意外险", "寿险", "养老险",
        "年金险", "防癌险", "长期护理", "百万医疗", "商业保险",
    ]
    ELDERCARE_KEYWORDS = [
        "养老院", "护理院", "养老机构", "居家养老", "社区养老",
        "养老服务", "日间照料", "康复中心",
    ]

    # ---- 意图关键词映射 ----
    INTENT_PATTERNS = {
        "insurability": ["能买", "能不能买", "可以买", "能否投保", "能投保", "可以投保", "是否可以"],
        "cost":         ["多少钱", "价格", "费用", "保费", "花费", "收费"],
        "coverage":     ["保什么", "保障", "赔付", "理赔", "报销", "包含", "覆盖"],
        "treatment":    ["怎么治", "治疗", "吃什么药", "用药", "方案"],
        "eligibility":  ["条件", "要求", "资格", "限制", "门槛"],
    }

    def parse(self, question: str) -> ParsedQuestion:
        """
        解析用户问题，返回 ParsedQuestion。

        Args:
            question: 用户输入的自然语言问题，如 "70岁高血压能买护理险吗？"

        Returns:
            ParsedQuestion: 结构化的问题解析结果
        """
        entities = []

        # 1. 用关键词匹配提取实体
        for disease in self.DISEASE_KEYWORDS:
            if disease in question:
                entities.append({"text": disease, "type": "Disease", "normalized": disease})

        for ins in self.INSURANCE_KEYWORDS:
            if ins in question:
                entities.append({"text": ins, "type": "InsuranceProduct", "normalized": ins})

        for elder in self.ELDERCARE_KEYWORDS:
            if elder in question:
                entities.append({"text": elder, "type": "EldercareService", "normalized": elder})

        # 2. 用正则提取年龄
        age = None
        age_match = re.search(r"(\d{1,3})\s*岁", question)
        if age_match:
            age = int(age_match.group(1))

        # 3. 用关键词匹配识别意图
        intent = "general"
        for intent_type, keywords in self.INTENT_PATTERNS.items():
            if any(kw in question for kw in keywords):
                intent = intent_type
                break

        # 4. 提取其他约束（性别等）
        constraints = {}
        if "男" in question:
            constraints["gender"] = "男"
        elif "女" in question:
            constraints["gender"] = "女"

        return ParsedQuestion(
            original_question=question,
            entities=entities,
            intent=intent,
            age=age,
            constraints=constraints,
        )


# ============================================================
# Mock 图谱检索
# ============================================================

class MockGraphRetrieval:
    """
    模拟图谱检索：使用预定义数据模拟 Neo4j 查询结果。

    真实版本应连接 Neo4j Aura，用 Cypher 查询子图。
    这里用字典模拟，覆盖几个典型场景。
    """

    # ---- 模拟知识图谱数据 ----
    # 格式：{实体名: [Triple, Triple, ...]}
    MOCK_GRAPH = {
        "高血压": [
            Triple("高血压", "Disease", "常用药物", "硝苯地平", "Drug", "医保目录"),
            Triple("高血压", "Disease", "常用药物", "氨氯地平", "Drug", "医保目录"),
            Triple("高血压", "Disease", "属于", "心血管疾病", "DiseaseCategory", "ICD-10"),
            Triple("高血压", "Disease", "需要检查", "血压监测", "Examination", "临床指南"),
            Triple("平安护理险", "InsuranceProduct", "除外疾病", "高血压III级", "Disease", "平安保险条款"),
            Triple("太平养老护理险", "InsuranceProduct", "可承保", "高血压I级", "Disease", "太平保险条款"),
            Triple("太平养老护理险", "InsuranceProduct", "年龄限制", "18-75岁", "AgeRange", "太平保险条款"),
            Triple("平安护理险", "InsuranceProduct", "年龄限制", "18-65岁", "AgeRange", "平安保险条款"),
        ],
        "糖尿病": [
            Triple("糖尿病", "Disease", "常用药物", "二甲双胍", "Drug", "医保目录"),
            Triple("糖尿病", "Disease", "常用药物", "胰岛素", "Drug", "医保目录"),
            Triple("糖尿病", "Disease", "并发症", "糖尿病肾病", "Disease", "临床指南"),
            Triple("糖尿病", "Disease", "属于", "内分泌疾病", "DiseaseCategory", "ICD-10"),
            Triple("百万医疗险", "InsuranceProduct", "除外疾病", "糖尿病", "Disease", "某保险条款"),
            Triple("防癌险", "InsuranceProduct", "可承保", "糖尿病", "Disease", "某保险条款"),
        ],
        "护理险": [
            Triple("太平养老护理险", "InsuranceProduct", "保障内容", "长期护理费用", "Coverage", "太平保险条款"),
            Triple("太平养老护理险", "InsuranceProduct", "年保费", "2000-5000元", "Price", "太平保险条款"),
            Triple("太平养老护理险", "InsuranceProduct", "年龄限制", "18-75岁", "AgeRange", "太平保险条款"),
            Triple("平安护理险", "InsuranceProduct", "保障内容", "护理服务费用", "Coverage", "平安保险条款"),
            Triple("平安护理险", "InsuranceProduct", "年龄限制", "18-65岁", "AgeRange", "平安保险条款"),
        ],
        "养老院": [
            Triple("北京松堂关怀医院", "EldercareInstitution", "提供服务", "医养结合护理", "Service", "民政部名单"),
            Triple("北京松堂关怀医院", "EldercareInstitution", "收费标准", "3000-8000元/月", "Price", "民政部名单"),
            Triple("北京松堂关怀医院", "EldercareInstitution", "接收条件", "60岁以上", "AgeRange", "民政部名单"),
            Triple("泰康之家", "EldercareInstitution", "提供服务", "高端养老社区", "Service", "公开信息"),
        ],
        "重疾险": [
            Triple("重疾险", "InsuranceType", "保障疾病", "癌症", "Disease", "行业标准"),
            Triple("重疾险", "InsuranceType", "保障疾病", "心肌梗塞", "Disease", "行业标准"),
            Triple("重疾险", "InsuranceType", "保障疾病", "中风", "Disease", "行业标准"),
        ],
    }

    def retrieve(self, parsed_question: ParsedQuestion, max_hops: int = 2) -> RetrievalResult:
        """
        根据解析后的问题，从 Mock 图谱中检索相关三元组。

        Args:
            parsed_question: 问题理解的输出
            max_hops: 最大跳数（Mock中未实际使用，占位）

        Returns:
            RetrievalResult: 检索到的三元组和匹配信息
        """
        triples = []
        matched_entities = []

        # 遍历问题中识别出的所有实体，在Mock图谱中查找
        for entity in parsed_question.entities:
            entity_text = entity["text"]
            if entity_text in self.MOCK_GRAPH:
                matched_entities.append(entity_text)
                triples.extend(self.MOCK_GRAPH[entity_text])

        # 去重（同一条三元组可能被多个实体命中）
        seen = set()
        unique_triples = []
        for t in triples:
            key = (t.head, t.relation, t.tail)
            if key not in seen:
                seen.add(key)
                unique_triples.append(t)

        return RetrievalResult(
            triples=unique_triples,
            matched_entities=matched_entities,
            query_used="[Mock查询 - 未连接真实Neo4j]",
            hop_count=1,
        )