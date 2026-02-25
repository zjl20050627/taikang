# ============================================================
# question_understanding/ner_module.py
# ============================================================
# 问题理解模块：使用规则进行命名实体识别和意图分类
# ============================================================

import re
import sys
import os

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from data_models import ParsedQuestion
class QuestionUnderstanding:
    """
    问题理解模块。

    使用规则实现：
    1. 实体识别（Disease, Drug, InsuranceProduct 等）
    2. 意图分类（insurability, cost, coverage 等）
    3. 年龄提取
    4. 其他约束提取
    """

    # ---- 实体类型定义 ----
    #根据代码库里现有知识图谱设计
    ENTITY_TYPES: list[str] = [
        "Disease",           # 疾病实体（如：高血压、糖尿病）
        "Drug",              # 药品实体（如：硝苯地平、二甲双胍）
        "DrugCategory",      # 药品分类实体（如：降压药、降糖药）
        "DiseaseCategory",   # 疾病分类实体（如：心血管疾病、内分泌疾病）
        "InsuranceProduct",  # 保险产品实体（如：护理险、医疗险、重疾险）
        "MedicalService",    # 医疗服务实体（如：体检、康复）
        "AgeLimit",          # 年龄限制实体（如：18-75岁）
        "Institution",       # 机构实体（如：泰康之家、平安保险）
    ]

    def __init__(self):
        """
        初始化问题理解模块。
        """
        # 加载规则词典
        self._load_dictionaries()
        print("[OK] QuestionUnderstanding initialized (rule-based only)")

    def _load_dictionaries(self) -> None:
        """加载规则词典"""
        # 疾病词典
        self.diseases: list[str] = [
            # 常见疾病
            "高血压", "糖尿病", "冠心病", "心脏病", "中风", "脑梗",
            "肾病", "癌症", "肿瘤", "白血病", "肺炎", "哮喘",
            "关节炎", "骨质疏松", "阿尔茨海默", "帕金森", "痛风",
            "甲状腺", "抑郁症", "原发性高血压",
            # 高血压分级
            "高血压I级", "高血压II级", "高血压III级", "高血压1级", "高血压2级", "高血压3级",
            # 其他
            "心梗", "脑出血", "脑卒中", "心肌梗塞", "心力衰竭", "心衰",
            "糖尿病肾病", "糖尿病视网膜病变", "糖尿病足", "高血脂", "高脂血症",
        ]

        # 药品词典
        self.drugs: list[str] = [
            # 降压药
            "硝苯地平", "氨氯地平", "依那普利", "卡托普利", "美托洛尔", "阿替洛尔",
            "氢氯噻嗪", "吲达帕胺", "缬沙坦", "厄贝沙坦",
            # 降糖药
            "二甲双胍", "胰岛素", "格列美脲", "阿卡波糖", "瑞格列奈",
            # 其他
            "阿司匹林", "他汀", "阿托伐他汀", "辛伐他汀", "布洛芬",
        ]

        # 药品分类词典
        self.drug_categories: list[str] = [
            "降压药", "降糖药", "抗生素", "止痛药", "消炎药",
            "降脂药", "抗凝药", "激素药",
        ]

        # 疾病分类词典
        self.disease_categories: list[str] = [
            "心血管疾病", "内分泌疾病", "神经科疾病", "呼吸系统疾病",
            "消化系统疾病", "血液疾病", "癌症", "慢性病",
        ]

        # 保险产品词典
        self.insurance_products: list[str] = [
            "护理险", "医疗险", "重疾险", "意外险", "寿险", "养老险",
            "年金险", "防癌险", "长期护理", "百万医疗", "商业保险",
            "平安护理险", "太平养老护理险", "泰康护理险",
        ]

        # 医疗服务词典
        self.medical_services: list[str] = [
            "体检", "康复", "护理", "手术", "透析",
            "血压监测", "血糖监测", "心理咨询",
        ]

        # 机构词典
        self.institutions: list[str] = [
            "泰康之家", "平安保险", "太平保险", "中国人寿",
            "北京松堂关怀医院", "协和医院", "301医院",
            "养老院", "护理院", "康复医院",
        ]

    def _extract_entities(self, question: str) -> list[dict[str, str]]:
        """
        基于规则的实体提取。

        Args:
            question: 用户问题

        Returns:
            实体列表，每个实体格式：{"text": str, "type": str, "normalized": str}
        """
        entities: list[dict[str, str]] = []

        # 按词典匹配（优先匹配长实体，避免子实体重复）
        # 合并所有词典并按长度降序排序
        all_keywords: list[tuple[str, str]] = []
        for disease in self.diseases:
            all_keywords.append((disease, "Disease"))
        for drug in self.drugs:
            all_keywords.append((drug, "Drug"))
        for cat in self.drug_categories:
            all_keywords.append((cat, "DrugCategory"))
        for cat in self.disease_categories:
            all_keywords.append((cat, "DiseaseCategory"))
        for ins in self.insurance_products:
            all_keywords.append((ins, "InsuranceProduct"))
        for service in self.medical_services:
            all_keywords.append((service, "MedicalService"))
        for inst in self.institutions:
            all_keywords.append((inst, "Institution"))

        # 按长度降序排序，优先匹配长实体
        all_keywords.sort(key=lambda x: len(x[0]), reverse=True)

        # 匹配实体
        used_positions: set[int] = set()  # 记录已使用的位置，避免重复
        for keyword, entity_type in all_keywords:
            start = 0
            while True:
                pos = question.find(keyword, start)
                if pos == -1:
                    break

                # 检查是否已被其他实体占用
                keyword_positions = set(range(pos, pos + len(keyword)))
                if not keyword_positions & used_positions:
                    entities.append({
                        "text": keyword,
                        "type": entity_type,
                        "normalized": keyword
                    })
                    used_positions.update(keyword_positions)

                start = pos + 1

        return entities

    def _classify_intent(self, question: str, entities: list[dict[str, str]]) -> str:
        """
        意图分类。

        Args:
            question: 用户问题
            entities: 识别出的实体列表

        Returns:
            意图类型
        """
        # 意图关键词映射
        intent_patterns: dict[str, list[str]] = {
            "insurability": [
                "能买", "能不能买", "可以买", "能否投保", "能投保", "可以投保",
                "是否可以", "能投", "可以投", "能否购买", "可以购买吗",
                "能不能投保", "能保吗", "可以保吗"
            ],
            "cost": [
                "多少钱", "价格", "费用", "保费", "花费", "收费",
                "多少钱一个月", "每月多少钱", "年费", "年度保费",
                "贵不贵", "便宜吗"
            ],
            "coverage": [
                "保什么", "保障", "赔付", "理赔", "报销", "包含",
                "覆盖", "保障范围", "保障内容", "保哪些", "包含哪些"
            ],
            "treatment": [
                "怎么治", "治疗", "吃什么药", "用药", "方案",
                "治疗方法", "治疗方案", "药物", "吃药"
            ],
            "eligibility": [
                "条件", "要求", "资格", "限制", "门槛",
                "什么条件", "哪些要求", "什么资格", "什么限制"
            ],
        }

        # 优先级：先匹配明确的关键词
        for intent_type, keywords in intent_patterns.items():
            for kw in keywords:
                if kw in question:
                    return intent_type

        # 基于实体的简单推断
        entity_types = [e["type"] for e in entities]
        if "Disease" in entity_types or "Drug" in entity_types:
            return "treatment"
        elif "InsuranceProduct" in entity_types:
            return "insurability"

        return "general"

    def _extract_age(self, question: str) -> int | None:
        """
        提取年龄信息。

        Args:
            question: 用户问题

        Returns:
            年龄整数或 None
        """
        # 匹配 "XX岁" 或 "XX周岁"
        age_patterns: list[str] = [
            r"(\d{1,3})\s*岁",
            r"(\d{1,3})\s*周岁",
            r"年龄\s*[为:是]\s*(\d{1,3})",
        ]

        for pattern in age_patterns:
            match = re.search(pattern, question)
            if match:
                age = int(match.group(1))
                # 合理性检查
                if 0 <= age <= 120:
                    return age

        return None

    def _extract_constraints(self, question: str) -> dict[str, str]:
        """
        提取其他约束条件。

        Args:
            question: 用户问题

        Returns:
            约束字典
        """
        constraints: dict[str, str] = {}

        # 性别提取
        if "男" in question and "女" not in question:
            constraints["gender"] = "男"
        elif "女" in question and "男" not in question:
            constraints["gender"] = "女"

        # 城市提取（可选）
        city_patterns: list[str] = [
            r"(北京|上海|广州|深圳|杭州|南京|成都|武汉)",
        ]
        for pattern in city_patterns:
            match = re.search(pattern, question)
            if match:
                constraints["city"] = match.group(1)

        return constraints

    def parse(self, question: str) -> ParsedQuestion:
        """
        解析用户问题。

        Args:
            question: 用户输入的原始问题字符串

        Returns:
            ParsedQuestion: 结构化的问题解析结果
        """
        # 1. 实体识别（基于规则）
        entities = self._extract_entities(question)

        # 2. 意图分类
        intent = self._classify_intent(question, entities)

        # 3. 年龄提取
        age = self._extract_age(question)

        # 4. 约束提取
        constraints = self._extract_constraints(question)

        return ParsedQuestion(
            original_question=question,
            entities=entities,
            intent=intent,
            age=age,
            constraints=constraints,
        )