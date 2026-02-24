# ============================================================
# base_llm.py - 大模型抽象基类
# ============================================================
# 作用：定义所有 LLM 实现必须遵循的统一接口。
#       这样切换不同大模型（智谱、通义千问等）时，上层代码不用改。
# ============================================================

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class LLMResponse:
    """
    大模型的返回结果。

    Attributes:
        content:       生成的文本内容
        model:         使用的模型名称（如 "glm-4.7"）
        usage:         token 使用统计（如 {"input_tokens": 100, "output_tokens": 50}）
        finish_reason: 停止原因（如 "stop" 表示正常结束）
    """
    content: str = ""
    model: str = ""
    usage: Dict = field(default_factory=dict)
    finish_reason: str = ""


class BaseLLM(ABC):
    """
    大模型抽象基类。

    所有 LLM 实现（智谱AI、Mock 等）都必须继承此类并实现 chat() 方法。

    使用示例：
        llm = ZhipuAILLM(api_key="xxx")
        messages = [
            {"role": "system", "content": "你是助手"},
            {"role": "user", "content": "你好"}
        ]
        response = llm.chat(messages)
        print(response.content)
    """

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """
        发送对话消息，获取模型回复。

        Args:
            messages: 对话消息列表，格式：
                      [{"role": "system"/"user"/"assistant", "content": "文本"}]
            **kwargs: 可选参数（temperature, max_tokens 等）

        Returns:
            LLMResponse: 模型回复
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查该 LLM 后端是否可用（SDK已安装、API Key已配置等）"""
        pass

    def simple_chat(self, user_message: str, system_message: str = "") -> str:
        """
        简化的对话接口：直接传文本，返回文本。

        适合快速测试，不需要手动构造 messages。
        """
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": user_message})

        response = self.chat(messages)
        return response.content