# ============================================================
# answer_formatter.py - 答案格式化与溯源处理
# ============================================================
# 作用：
#   1. 清理大模型的原始输出
#   2. 附加溯源信息（引用了哪些三元组）
#   3. 评估回答的置信度
#   4. 打包成 FormattedAnswer 供前端展示
# ============================================================

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_models import Triple, FormattedAnswer
from typing import List


class AnswerFormatter:
    """
    答案格式化器。

    职责：把 LLM 的原始输出 + 图谱三元组，包装成最终展示给用户的结构化答案。
    """

    def format(
        self,
        llm_output: str,
        triples: List[Triple],
        matched_entities: List[str],
        intent: str,
    ) -> FormattedAnswer:
        """
        格式化最终答案。

        Args:
            llm_output:       大模型生成的原始文本
            triples:          本次回答引用的三元组列表
            matched_entities: 匹配到图谱的实体名列表
            intent:           用户意图分类

        Returns:
            FormattedAnswer: 结构化的最终答案
        """
        # 1. 清理大模型输出（去除多余空行等）
        clean_text = self._clean_llm_output(llm_output)

        # 2. 评估置信度
        confidence = self._assess_confidence(clean_text, triples)

        # 3. 把三元组转为字典格式（方便JSON序列化给前端）
        source_dicts = [t.to_dict() for t in triples]

        # 4. 打包返回
        return FormattedAnswer(
            answer_text=clean_text,
            source_triples=source_dicts,
            intent=intent,
            matched_entities=matched_entities,
            confidence=confidence,
        )

    def format_sources_text(self, triples: List[Triple]) -> str:
        """
        把三元组格式化为人类可读的溯源文本（命令行展示用）。

        Returns:
            str: 格式化的来源文本，例如：
                 "知识来源：
                    1. 高血压 --[常用药物]--> 硝苯地平 [来源: 医保目录]
                    2. ..."
        """
        if not triples:
            return "暂无知识图谱来源信息。"

        lines = ["知识来源："]
        for i, t in enumerate(triples, 1):
            source_tag = f" [来源: {t.source}]" if t.source else ""
            lines.append(f"  {i}. {t.head} --[{t.relation}]--> {t.tail}{source_tag}")

        return "\n".join(lines)

    def _clean_llm_output(self, text: str) -> str:
        """
        清理大模型输出文本。

        处理：
            - 去除首尾空白
            - 压缩连续的空行（最多保留一个空行）
        """
        if not text:
            return "抱歉，未能生成有效回答。"

        # 去首尾空白
        text = text.strip()

        # 压缩连续空行
        lines = text.split("\n")
        cleaned_lines = []
        prev_empty = False
        for line in lines:
            if line.strip() == "":
                if not prev_empty:
                    cleaned_lines.append("")
                prev_empty = True
            else:
                cleaned_lines.append(line)
                prev_empty = False

        return "\n".join(cleaned_lines)

    def _assess_confidence(self, answer_text: str, triples: List[Triple]) -> str:
        """
        简单评估回答的置信度。

        规则：
            - 没有三元组支撑 → low（低）
            - 回答中出现不确定表述 → low
            - 有 3+ 条三元组支撑 → high（高）
            - 其他 → medium（中）

        Args:
            answer_text: 大模型的回答文本
            triples:     引用的三元组列表

        Returns:
            str: "high" / "medium" / "low"
        """
        # 没有检索到知识 → 低置信度
        if not triples:
            return "low"

        # 回答中包含不确定表述 → 低置信度
        uncertain_phrases = ["暂无法", "信息不足", "无法确定", "建议咨询", "无法给出", "不确定"]
        if any(phrase in answer_text for phrase in uncertain_phrases):
            return "low"

        # 有较多三元组支撑 → 高置信度
        if len(triples) >= 3:
            return "high"

        # 默认中等
        return "medium"