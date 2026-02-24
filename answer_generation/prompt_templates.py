# ============================================================
# prompt_templates.py - Prompt 模板管理器
# ============================================================
# 作用：为不同类型的用户问题设计不同的 Prompt 模板。
#
# 输出格式：OpenAI 标准的 messages 列表
#   [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
#   智谱AI、OpenAI、通义千问都兼容这个格式。
# ============================================================

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_models import ParsedQuestion
from typing import List, Dict


class PromptTemplateManager:
    """
    Prompt 模板管理器：根据用户意图选择合适的 Prompt。

    设计思路：
        - system prompt：告诉大模型它是什么角色、该遵守什么规则
        - user prompt：包含用户问题 + 知识图谱上下文 + 回答要求
        - 不同意图（投保、费用、治疗等）使用不同的 user prompt 模板
    """

    # ============================================================
    # 系统提示词（所有问题共用）
    # ============================================================
    SYSTEM_PROMPT = (
        "你是一个专业的「保险+医养」领域智能助手。"
        "你的职责是基于知识图谱中的结构化知识，准确回答用户关于健康、保险、养老方面的问题。\n\n"
        "请遵循以下原则：\n"
        "1. **准确性**：只基于提供的知识图谱信息回答，不要编造不存在的产品或数据\n"
        "2. **完整性**：尽可能全面地回答用户问题的各个方面\n"
        "3. **可读性**：用通俗易懂的语言，必要时分点列出\n"
        "4. **溯源性**：在回答中提及信息来源（如「根据XX保险条款」）\n"
        "5. **诚实性**：如果信息不足以完整回答，请明确说明哪些部分无法确认\n\n"
        "重要：如果知识图谱中没有相关信息，请回答「根据现有知识库，暂无法提供该问题的确切答案」，"
        "不要凭空编造。"
    )

    # ============================================================
    # 各意图的 User Prompt 模板
    # ============================================================
    # {question} → 用户原始问题
    # {context}  → ContextBuilder 生成的知识上下文
    # {age}      → 用户年龄（如有）
    INTENT_TEMPLATES = {
        # ---- 可投保性：用户问"能不能买" ----
        "insurability": (
            "用户问题：{question}\n\n"
            "{context}\n\n"
            "请根据以上知识图谱信息，回答该用户是否可以投保。请重点分析：\n"
            "1. 用户年龄（{age}）是否在产品的投保年龄范围内\n"
            "2. 用户的既往疾病是否属于产品的除外责任\n"
            "3. 是否存在可以承保该疾病的替代产品\n"
            "4. 给出明确结论和投保建议\n\n"
            "请在回答末尾列出引用的信息来源。"
        ),
        # ---- 费用：用户问"多少钱" ----
        "cost": (
            "用户问题：{question}\n\n"
            "{context}\n\n"
            "请根据以上知识图谱信息，回答关于费用/价格的问题：\n"
            "1. 相关产品或服务的价格范围\n"
            "2. 影响价格的因素（年龄、保障范围等）\n"
            "3. 如有多个选择，进行简要对比\n\n"
            "请在回答末尾列出引用的信息来源。"
        ),
        # ---- 保障范围：用户问"保什么" ----
        "coverage": (
            "用户问题：{question}\n\n"
            "{context}\n\n"
            "请根据以上知识图谱信息，回答关于保障范围的问题：\n"
            "1. 具体保障哪些内容/疾病\n"
            "2. 有哪些除外责任（不保的情况）\n"
            "3. 与其他同类产品的区别（如有信息）\n\n"
            "请在回答末尾列出引用的信息来源。"
        ),
        # ---- 治疗：用户问"怎么治/吃什么药" ----
        "treatment": (
            "用户问题：{question}\n\n"
            "{context}\n\n"
            "请根据以上知识图谱信息，回答关于疾病治疗的问题：\n"
            "1. 常用治疗药物\n"
            "2. 需要的检查项目\n"
            "3. 相关医保报销信息（如有）\n\n"
            "⚠️ 请在回答末尾提醒用户：具体用药方案请遵医嘱。\n"
            "请列出引用的信息来源。"
        ),
        # ---- 资格条件：用户问"什么条件/有什么要求" ----
        "eligibility": (
            "用户问题：{question}\n\n"
            "{context}\n\n"
            "请根据以上知识图谱信息，回答关于资格/条件要求的问题：\n"
            "1. 年龄要求\n"
            "2. 健康状况要求\n"
            "3. 其他限制条件\n\n"
            "请在回答末尾列出引用的信息来源。"
        ),
        # ---- 通用：无法明确分类的问题 ----
        "general": (
            "用户问题：{question}\n\n"
            "{context}\n\n"
            "请根据以上知识图谱信息，全面回答用户的问题。\n"
            "如果信息不足，请说明哪些方面的信息缺失，并给出你能提供的部分回答。\n\n"
            "请在回答末尾列出引用的信息来源。"
        ),
    }

    def build_prompt(
        self,
        parsed_question: ParsedQuestion,
        context: str,
    ) -> List[Dict[str, str]]:
        """
        构建完整的 Prompt（messages 格式）。

        Args:
            parsed_question: 问题理解的输出
            context:         ContextBuilder 生成的知识上下文文本

        Returns:
            list: 符合 OpenAI/智谱AI 格式的 messages 列表
                  [{"role": "system", "content": ...}, {"role": "user", "content": ...}]
        """
        # 根据意图选择模板，找不到就用通用模板
        intent = parsed_question.intent
        template = self.INTENT_TEMPLATES.get(intent, self.INTENT_TEMPLATES["general"])

        # 填充模板变量
        age_str = f"{parsed_question.age}岁" if parsed_question.age else "未提及"
        user_content = template.format(
            question=parsed_question.original_question,
            context=context,
            age=age_str,
        )

        # 组装 messages
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        return messages