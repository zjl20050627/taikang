# ============================================================
# zhipuai_llm.py - 智谱AI (GLM) 大模型集成
# ============================================================
# 官网：https://open.bigmodel.cn/
# 注册后在控制台创建 API Key，glm-4-flash 模型完全免费，然后新用户有资源包所以我用的glm-4.7。
#
# 安装：pip install zhipuai
# ============================================================

import sys
import os

# 添加当前目录到路径，以便导入同目录下的 base_llm.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_llm import BaseLLM, LLMResponse
from typing import List, Dict


class ZhipuAILLM(BaseLLM):
    """
    智谱AI GLM 系列大模型。

    可用模型（截至 2024 年）：
        - glm-4-flash   : 免费，速度快，适合本项目
        - glm-4-air     : 便宜，有资源包，可用
        - glm-4.7       : 新用户资源包，能用，但不保证长期免费
    """

    def __init__(
        self,
        api_key: str,
        model: str = "glm-4-flash",
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ):
        """
        初始化智谱AI客户端。

        Args:
            api_key:     智谱AI的API密钥
            model:       模型名称，默认 glm-4-flash（免费）
            temperature: 温度参数，越低越稳定（0.0~1.0）
            max_tokens:  最大生成token数
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._available = False

        try:
            from zhipuai import ZhipuAI
            self.client = ZhipuAI(api_key=api_key)
            self._available = True
        except ImportError:
            print("⚠️  zhipuai 库未安装，请运行: pip install zhipuai")

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """
        调用智谱AI API 进行对话。

        Args:
            messages: [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
            **kwargs: 可覆盖 temperature, max_tokens

        Returns:
            LLMResponse: 包含回复内容、token用量等信息
        """
        if not self._available:
            return LLMResponse(content="[错误] zhipuai 库未安装", model=self.model)

        # 允许通过 kwargs 覆盖默认参数
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        try:
            # 调用智谱AI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # 解析返回结果
            choice = response.choices[0]

            # 提取 token 用量信息
            usage = {}
            if response.usage:
                usage = {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

            return LLMResponse(
                content=choice.message.content,
                model=self.model,
                usage=usage,
                finish_reason=choice.finish_reason or "stop",
            )

        except Exception as e:
            # 捕获所有异常，返回错误信息而不是崩溃
            error_msg = f"[智谱AI调用失败] {type(e).__name__}: {str(e)}"
            return LLMResponse(content=error_msg, model=self.model)

    def is_available(self) -> bool:
        """检查智谱AI是否可用"""
        return self._available