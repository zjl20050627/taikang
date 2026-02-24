# ============================================================
# llm_factory.py - LLM 工厂函数
# ============================================================
# 作用：根据 config.yaml 和 .env 的配置，自动创建对应的 LLM 实例。
#       上层代码（pipeline.py）只需调用 create_llm()，不关心具体用哪个模型。
# ============================================================

import sys
import os
import yaml

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # llm-integration/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # rag/

# 加载 .env 环境变量
from dotenv import load_dotenv
load_dotenv(
    dotenv_path=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ".env"
    )
)

from base_llm import BaseLLM


def create_llm(config_path: str = None) -> BaseLLM:
    """
    根据配置创建 LLM 实例（工厂函数）。

    优先级：
        1. .env 中的 API Key（最安全）
        2. config.yaml 中的配置
        3. 都没有 → 自动降级为 MockLLM

    Args:
        config_path: config.yaml 的路径，默认为 rag/config.yaml

    Returns:
        BaseLLM: 可用的 LLM 实例

    使用示例：
        llm = create_llm()
        response = llm.chat([{"role": "user", "content": "你好"}])
        print(response.content)
    """
    # ---- 1. 读取配置文件 ----
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config.yaml"
        )

    config = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

    # ---- 2. 确定使用哪个 provider ----
    llm_config = config.get("llm", {})
    provider = llm_config.get("provider", "mock")

    print(f"[LLM Factory] 配置的 provider: {provider}")

    # ---- 3. 根据 provider 创建实例 ----
    if provider == "zhipuai":
        return _create_zhipuai(llm_config.get("zhipuai", {}))
    else:
        print("[LLM Factory] 使用 Mock LLM（无需API，仅用于测试）")
        from mock_llm import MockLLM
        return MockLLM()


def _create_zhipuai(zhipuai_config: dict) -> BaseLLM:
    """
    创建智谱AI LLM 实例。

    Args:
        zhipuai_config: config.yaml 中 llm.zhipuai 下的配置

    Returns:
        ZhipuAILLM 或 MockLLM（如果没有API Key）
    """
    # API Key 优先从环境变量读，其次从 config.yaml 读
    api_key = os.environ.get("ZHIPUAI_API_KEY") or zhipuai_config.get("api_key", "")

    if not api_key:
        print("[LLM Factory] ⚠️  未找到 ZHIPUAI_API_KEY")
        print("  → 请在 .env 文件中设置: ZHIPUAI_API_KEY=你的密钥")
        print("  → 获取地址: https://open.bigmodel.cn/")
        print("  → 暂时使用 Mock LLM 代替")
        from mock_llm import MockLLM
        return MockLLM()

    from zhipuai_llm import ZhipuAILLM
    llm = ZhipuAILLM(
        api_key=api_key,
        model=zhipuai_config.get("model", "glm-4-flash"),
        temperature=zhipuai_config.get("temperature", 0.3),
        max_tokens=zhipuai_config.get("max_tokens", 1024),
    )

    if llm.is_available():
        print(f"[LLM Factory] ✅ 智谱AI 初始化成功，模型: {llm.model}")
    else:
        print("[LLM Factory] ⚠️  智谱AI SDK 加载失败，使用 Mock LLM")
        from mock_llm import MockLLM
        return MockLLM()

    return llm