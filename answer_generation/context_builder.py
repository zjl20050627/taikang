# ============================================================
# context_builder.py - 上下文构造器
# ============================================================
# 作用：将图谱检索到的三元组，转换为大模型能理解的自然语言上下文。
#
# 输入：三元组列表 + 问题信息
# 输出：一段自然语言文本，作为 Prompt 的一部分
# ============================================================

import sys
import os

# 把 rag/ 根目录加入 Python 路径，这样可以导入 data_models.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_models import Triple, ParsedQuestion, RetrievalResult
from typing import List, Dict


class ContextBuilder:
    """
    上下文构造器：将图谱三元组转为 LLM 可理解的自然语言。

    工作流程：
        1. 接收检索到的三元组列表
        2. 按头实体分组（如所有关于"高血压"的信息放一起）
        3. 用预定义模板把每条三元组翻译成一句话
        4. 拼接成完整的上下文文本

    使用示例：
        builder = ContextBuilder()
        context_text = builder.build_context(parsed_question, retrieval_result)
    """

    # ---- 关系 → 自然语言模板 ----
    # 把图谱中的关系名映射为通顺的中文句子
    RELATION_TEMPLATES = {
        "常用药物": "{head}的常用治疗药物包括{tail}",
        "属于":     "{head}属于{tail}类疾病",
        "并发症":   "{head}可能引发的并发症包括{tail}",
        "需要检查": "{head}患者需要进行{tail}",
        "除外疾病": "{head}的除外责任中包含{tail}（即患有该病可能不予承保）",
        "可承保":   "{head}可以承保{tail}患者",
        "年龄限制": "{head}的投保年龄范围为{tail}",
        "保障内容": "{head}的保障内容包括{tail}",
        "年保费":   "{head}的年保费大约为{tail}",
        "提供服务": "{head}提供{tail}服务",
        "收费标准": "{head}的收费标准约为{tail}",
        "接收条件": "{head}的入住/接收条件为{tail}",
        "保障疾病": "{head}的保障范围覆盖{tail}",
        "治疗方案": "{head}的推荐治疗方案包括{tail}",
    }

    def build_context(
        self,
        parsed_question: ParsedQuestion,
        retrieval_result: RetrievalResult,
        max_triples: int = 20,
    ) -> str:
        """
        构建提供给 LLM 的知识上下文文本。

        Args:
            parsed_question:  问题理解的输出结果
            retrieval_result: 图谱检索的输出结果
            max_triples:      最多使用多少条三元组（避免超出token限制）

        Returns:
            str: 格式化的自然语言上下文，例如：
                 "以下是从知识图谱中检索到的相关事实信息：
                  【关于高血压】
                    • 高血压的常用治疗药物包括硝苯地平（来源：医保目录）
                    • ..."
        """
        # 如果没有检索到任何三元组，返回提示信息
        if not retrieval_result.triples:
            return "未从知识图谱中检索到与该问题相关的信息。"

        # 截取前 max_triples 条，防止上下文过长
        triples = retrieval_result.triples[:max_triples]

        # 按头实体分组，让信息更有组织
        grouped = self._group_by_head(triples)

        # 拼接上下文
        lines = ["以下是从知识图谱中检索到的相关事实信息：\n"]
        for topic, topic_triples in grouped.items():
            lines.append(f"【关于{topic}】")
            for triple in topic_triples:
                # 把三元组翻译成自然语言
                sentence = self._triple_to_sentence(triple)
                # 标注来源
                source_tag = f"（来源：{triple.source}）" if triple.source else ""
                lines.append(f"  • {sentence}{source_tag}")
            lines.append("")  # 各组之间空一行

        return "\n".join(lines)

    def build_structured_context(self, retrieval_result: RetrievalResult) -> List[Dict]:
        """
        构建结构化上下文（用于前端溯源展示，不是给LLM的）。

        Returns:
            List[Dict]: 三元组的字典列表
        """
        return [t.to_dict() for t in retrieval_result.triples]

    def _triple_to_sentence(self, triple: Triple) -> str:
        """
        把一条三元组翻译成自然语言句子。

        优先使用预定义模板，如果关系类型没有对应模板，就用通用格式。

        Args:
            triple: 一条三元组

        Returns:
            str: 自然语言描述，如 "高血压的常用治疗药物包括硝苯地平"
        """
        template = self.RELATION_TEMPLATES.get(triple.relation)
        if template:
            return template.format(head=triple.head, tail=triple.tail)
        else:
            # 通用模板：兜底方案
            return f"{triple.head}的「{triple.relation}」为{triple.tail}"

    def _group_by_head(self, triples: List[Triple]) -> Dict[str, List[Triple]]:
        """
        按头实体分组三元组。

        例如：所有 head="高血压" 的三元组归为一组，head="平安护理险" 的归为另一组。

        Returns:
            Dict: {实体名: [三元组列表]}，保持插入顺序
        """
        grouped: Dict[str, List[Triple]] = {}
        for triple in triples:
            if triple.head not in grouped:
                grouped[triple.head] = []
            grouped[triple.head].append(triple)
        return grouped