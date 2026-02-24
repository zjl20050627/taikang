# ============================================================
# zhipuai_llm.py - 智谱AI (GLM) 大模型集成
# ============================================================
# 官网：https://open.bigmodel.cn/
# 注册后在控制台创建 API Key，glm-4-flash 模型完全免费，然后新用户有资源包所以我用的glm-4.7。
# 兼容普通模型（glm-4-flash）和推理模型（glm-4.7）
# glm-4.7 的特殊之处：
#   - 返回中有 reasoning_content（思考过程）和 content（最终回答）
#   - 不支持 temperature 参数
#   - max_tokens 同时限制思考+回答，需要设大一些
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

    可用模型：
        - glm-4-flash   : 免费，速度快，适合本项目
        - glm-4.5-air     : 便宜，有资源包，可用
        - glm-4.7       : 新用户资源包，能用，但不保证长期免费
    """

    # ---- 推理模型列表（这些模型有 reasoning_content 字段） ----
    REASONING_MODELS = ["glm-4.7", "glm-z1", "glm-z1-air", "glm-z1-flash"]

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
            model:       模型名称
                         推荐 glm-4-flash（免费、稳定）
                         或 glm-4.7（推理模型，需要更大的 max_tokens）
            temperature: 温度参数（推理模型不支持此参数，会自动忽略）
            max_tokens:  最大生成token数
                         推理模型的 max_tokens 包含思考过程+最终回答
                         因此推理模型设置 4096+
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._available = False
        self._is_reasoning = any(rm in model.lower() for rm in self.REASONING_MODELS)

        # 推理模型 max_tokens 太小时自动调大并警告
        if self._is_reasoning and max_tokens < 2048:
            print(f"  ⚠️  推理模型 {model} 的 max_tokens={max_tokens} 较小")
            print(f"      推理过程会消耗大量 token，建议设置 4096+")
            print(f"      已自动调整为 4096")
            self.max_tokens = 4096

        try:
            from zhipuai import ZhipuAI
            self.client = ZhipuAI(api_key=api_key)
            self._available = True
        except ImportError:
            print("⚠️  zhipuai 库未安装，请运行: pip install zhipuai")

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """
        调用智谱AI API 进行对话。

        自动处理普通模型和推理模型的差异：
        - 普通模型：直接读 content
        - 推理模型：优先读 content，content为空时读 reasoning_content
        """
        if not self._available:
            return LLMResponse(content="[错误] zhipuai 库未安装", model=self.model)

        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        try:
            # ---- 构建 API 参数 ----
            api_params = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
            }

            # 推理模型不支持 temperature
            if not self._is_reasoning:
                api_params["temperature"] = kwargs.get("temperature", self.temperature)

            # ---- 调用 API ----
            response = self.client.chat.completions.create(**api_params)
            choice = response.choices[0]
            message = choice.message

            # ---- 提取回答内容 ----
            content = self._extract_content(message)

            # ---- 提取 token 用量 ----
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
            error_msg = f"[智谱AI调用失败] {type(e).__name__}: {str(e)}"
            print(f"  [DEBUG] {error_msg}")
            return LLMResponse(content=error_msg, model=self.model)
        
    def _extract_content(self, message) -> str:
        """
        从 message 中提取最终回答文本。

        提取优先级：
            1. message.content（普通回答，所有模型都有）
            2. message.reasoning_content（推理模型的思考过程，作为兜底）

        Args:
            message: API 返回的 choice.message 对象

        Returns:
            str: 提取到的文本内容
        """
        # ---- 优先取 content ----
        content = getattr(message, "content", None)
        if content and isinstance(content, str) and content.strip():
            return content.strip()

        # ---- content 为空时，尝试取 reasoning_content（推理模型） ----
        reasoning = getattr(message, "reasoning_content", None)
        if reasoning and isinstance(reasoning, str) and reasoning.strip():
            print(f"  [INFO] content 为空，使用 reasoning_content 作为回答")
            # 从推理过程中提取最后的结论部分
            extracted = self._extract_conclusion_from_reasoning(reasoning)
            return extracted

        # ---- 都没有 ----
        print(f"  [WARN] content 和 reasoning_content 均为空")
        return ""

    def _extract_conclusion_from_reasoning(self, reasoning: str) -> str:
        """
        从推理模型的思考过程中提取结论。

        推理模型的 reasoning_content 通常是完整的思考过程，
        最后一段往往是结论。如果 content 为空，就把reasoning_content 整理后作为回答。

        Args:
            reasoning: reasoning_content 的原始文本

        Returns:
            str: 整理后的回答文本
        """
        reasoning = reasoning.strip()

        # 尝试找到结论标记
        conclusion_markers = [
            "综上", "总结", "结论", "因此", "所以", "最终",
            "总的来说", "综合来看", "综合以上",
        ]

        # 从后往前找结论段落
        paragraphs = reasoning.split("\n\n")
        for marker in conclusion_markers:
            for i in range(len(paragraphs) - 1, -1, -1):
                if marker in paragraphs[i]:
                    # 找到结论，返回从这一段开始的所有内容
                    conclusion = "\n\n".join(paragraphs[i:])
                    return conclusion.strip()

        # 没找到明显的结论标记，就返回整个推理过程
        # 添加提示，让用户知道这是从推理过程中提取的
        return f"（以下内容提取自模型推理过程）\n\n{reasoning}"

    def is_available(self) -> bool:
        """检查智谱AI是否可用"""
        return self._available