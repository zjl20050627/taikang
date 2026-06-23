# ============================================================
# deepseek_llm.py - DeepSeek 大模型集成（OpenAI 兼容接口）
# ============================================================
# 官网：https://platform.deepseek.com/
# API 文档：https://api-docs.deepseek.com/
# 安装：pip install openai
# ============================================================

import os
import sys
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_llm import BaseLLM, LLMResponse


class DeepSeekLLM(BaseLLM):
    """DeepSeek 大模型（deepseek-chat / deepseek-reasoner）。"""

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._available = False
        self.client = None

        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key, base_url=self.base_url)
            self._available = True
        except ImportError:
            print("[WARN] openai 库未安装，请运行: pip install openai")

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        if not self._available or not self.client:
            return LLMResponse(content="[错误] DeepSeek 客户端未初始化", model=self.model)

        try:
            response = self.client.chat.completions.create(
                model=kwargs.get("model", self.model),
                messages=messages,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
            )
            choice = response.choices[0]
            content = (choice.message.content or "").strip()

            usage = {}
            if response.usage:
                usage = {
                    "input_tokens": getattr(response.usage, "prompt_tokens", 0),
                    "output_tokens": getattr(response.usage, "completion_tokens", 0),
                    "total_tokens": getattr(response.usage, "total_tokens", 0),
                }

            return LLMResponse(
                content=content,
                model=self.model,
                usage=usage,
                finish_reason=getattr(choice, "finish_reason", "") or "stop",
            )
        except Exception as e:
            error_msg = f"[DeepSeek调用失败] {type(e).__name__}: {str(e)}"
            print(f"  [DEBUG] {error_msg}")
            return LLMResponse(content=error_msg, model=self.model)

    def is_available(self) -> bool:
        return self._available
