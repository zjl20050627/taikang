# ============================================================
# llm_factory.py - LLM 工厂函数
# ============================================================

import sys
import os
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(
    dotenv_path=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ".env",
    )
)

from base_llm import BaseLLM

_PLACEHOLDER_KEYS = {
    "ZHIPUAI_API_KEY",
    "DEEPSEEK_API_KEY",
    "your_zhipuai_api_key_here",
    "your_deepseek_api_key_here",
}


def _is_valid_api_key(key: str) -> bool:
    return bool(key and key not in _PLACEHOLDER_KEYS)


def create_llm(config_path: str = None) -> BaseLLM:
    """根据配置创建 LLM 实例。"""
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config.yaml",
        )

    config = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

    llm_config = config.get("llm", {})
    provider = llm_config.get("provider", "mock")
    print(f"[LLM Factory] 配置的 provider: {provider}")

    if provider == "deepseek":
        return _create_deepseek(llm_config.get("deepseek", {}))
    if provider == "zhipuai":
        return _create_zhipuai(llm_config.get("zhipuai", {}))

    print("[LLM Factory] 使用 Mock LLM（无需API，仅用于测试）")
    from mock_llm import MockLLM
    return MockLLM()


def _fallback_mock(reason: str) -> BaseLLM:
    print(f"[LLM Factory] [WARN] {reason}")
    print("  -> Falling back to Mock LLM")
    from mock_llm import MockLLM
    return MockLLM()


def _create_deepseek(deepseek_config: dict) -> BaseLLM:
    api_key = os.environ.get("DEEPSEEK_API_KEY") or deepseek_config.get("api_key", "")
    if not _is_valid_api_key(api_key):
        return _fallback_mock("DEEPSEEK_API_KEY not configured in .env")

    from deepseek_llm import DeepSeekLLM
    llm = DeepSeekLLM(
        api_key=api_key,
        model=deepseek_config.get("model", "deepseek-chat"),
        base_url=deepseek_config.get("base_url", "https://api.deepseek.com"),
        temperature=deepseek_config.get("temperature", 0.3),
        max_tokens=deepseek_config.get("max_tokens", 4096),
    )
    if llm.is_available():
        print(f"[LLM Factory] [OK] DeepSeek initialized, model: {llm.model}")
        return llm
    return _fallback_mock("DeepSeek SDK load failed")


def _create_zhipuai(zhipuai_config: dict) -> BaseLLM:
    api_key = os.environ.get("ZHIPUAI_API_KEY") or zhipuai_config.get("api_key", "")
    if not _is_valid_api_key(api_key):
        return _fallback_mock("ZHIPUAI_API_KEY not configured in .env")

    from zhipuai_llm import ZhipuAILLM
    llm = ZhipuAILLM(
        api_key=api_key,
        model=zhipuai_config.get("model", "glm-4-flash"),
        temperature=zhipuai_config.get("temperature", 0.3),
        max_tokens=zhipuai_config.get("max_tokens", 1024),
    )
    if llm.is_available():
        print(f"[LLM Factory] [OK] ZhipuAI initialized, model: {llm.model}")
        return llm
    return _fallback_mock("ZhipuAI SDK load failed")
