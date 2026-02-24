# ============================================================
# mock_llm.py - Mock 大模型（无需API，用于测试）
# ============================================================
# 作用：在没有智谱AI API Key 的情况下也能跑通整个流程。
#       返回预设的模板回答，可以测试上下文构造、界面展示等环节。
# ============================================================

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_llm import BaseLLM, LLMResponse
from typing import List, Dict


class MockLLM(BaseLLM):
    """
    Mock 大模型：不调用任何 API，返回模拟回答。

    使用场景：
        - 没有 API Key 时测试流程
        - 快速验证 Prompt 构造是否正确
        - CI/CD 自动测试
    """

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """
        根据输入的 messages 生成模拟回答。

        会尝试从 user message 中提取知识图谱信息并组织回答。
        """
        # 从 messages 中找到 user 的消息
        user_msg = ""
        for msg in messages:
            if msg["role"] == "user":
                user_msg = msg["content"]
                break

        # 生成模拟回答
        mock_answer = self._generate_mock_answer(user_msg)

        return LLMResponse(
            content=mock_answer,
            model="mock-llm（测试用，非真实模型）",
            usage={"input_tokens": len(user_msg), "output_tokens": len(mock_answer)},
            finish_reason="stop",
        )

    def is_available(self) -> bool:
        """Mock LLM 始终可用"""
        return True

    def _generate_mock_answer(self, user_msg: str) -> str:
        """
        从 Prompt 中提取要点，生成结构化的模拟回答。

        尝试找到知识图谱中的事实条目（以 • 开头的行），并组织成回答。
        """
        # 提取 prompt 中的知识图谱事实（以 • 开头的行）
        lines = user_msg.split("\n")
        facts = [line.strip().lstrip("• ") for line in lines if line.strip().startswith("•")]

        if facts:
            answer_parts = ["根据知识图谱中的信息，为您整理如下：\n"]
            for i, fact in enumerate(facts, 1):
                answer_parts.append(f"{i}. {fact}")
            answer_parts.append(
                "\n---\n"
                "以上信息来源于知识图谱数据库。具体情况请以保险公司官方条款和医疗机构实际信息为准。\n\n"
                "⚠️ **注意：这是 Mock LLM 的模拟回答。** "
                "请在 .env 中配置 ZHIPUAI_API_KEY 以获得真实的大模型回答。"
            )
            return "\n".join(answer_parts)
        else:
            return (
                "感谢您的提问。根据现有知识库信息，我为您整理以下参考：\n\n"
                "1. 该问题涉及保险和医疗健康领域的交叉知识\n"
                "2. 建议结合具体产品条款和个人健康状况综合判断\n"
                "3. 如需更详细信息，建议咨询专业保险顾问或医疗机构\n\n"
                "⚠️ **这是 Mock LLM 的模拟回答**，请配置真实 API Key 获得准确回答。"
            )