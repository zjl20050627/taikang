# ============================================================
# pipeline.py - GraphRAG 问答系统主 Pipeline
# ============================================================
# 这是整个系统的核心调度文件，串联所有模块：
#
#   用户问题
#     → [问题理解] 提取实体、意图、年龄
#     → [图谱检索] 从知识图谱查询相关三元组
#     → [上下文构造] 把三元组翻译成自然语言
#     → [Prompt构建] 根据意图选择模板，组装完整Prompt
#     → [LLM调用] 发送给智谱AI生成回答
#     → [答案格式化] 清理输出，附加溯源信息
#     → 最终答案
#
# 目前使用 Mock 模块替代其他的部分（问题理解 + 图谱检索）。
# 这两部分完成后，只需修改下面 __init__ 中的两行即可对接。
# ============================================================

import sys
import os
import importlib.util

# ---- 路径设置 ----
# 获取 rag/ 根目录的绝对路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 把 rag/ 加入 Python 路径（让 data_models.py, mock_modules.py 可以被导入）
sys.path.insert(0, BASE_DIR)

# ---- 导入数据模型 ----
from data_models import ParsedQuestion, RetrievalResult, FormattedAnswer, Triple

# ---- 导入图谱检索模块 ----
from graph_retrieval.neo4j_retrieval import Neo4jGraphRetrieval

# ---- 导入已经实现的模块 ----
from answer_generation.context_builder import ContextBuilder       # answer-generation/
from answer_generation.prompt_templates import PromptTemplateManager  # answer-generation/
from answer_generation.answer_formatter import AnswerFormatter      # answer-generation/
from llm_integration.llm_factory import create_llm               # llm-integration/
from question_understanding.ner_module import QuestionUnderstanding

class GraphRAGPipeline:
    """
    GraphRAG 问答系统主 Pipeline。

    负责按顺序调用各模块，完成从「用户提问」到「生成回答」的完整流程。

    使用示例：
        pipeline = GraphRAGPipeline()
        result = pipeline.answer("70岁高血压能买护理险吗？")
        print(result.answer_text)
    """

    def __init__(self, config_path: str = None):
        """
        初始化所有模块。

        Args:
            config_path: config.yaml 的路径，默认为 rag/config.yaml

        =====================================================
        对接代码时，只需修改下面两行：
        
        替换前（Mock）：
            self.question_understanding = MockQuestionUnderstanding()
            self.graph_retrieval = MockGraphRetrieval()
        
        替换后（真实实现）：
            from 问题理解模块 import RealQuestionUnderstanding
            from 图谱检索模块 import RealGraphRetrieval
            self.question_understanding = RealQuestionUnderstanding()
            self.graph_retrieval = RealGraphRetrieval()
        
        要求：对接的类需要实现以下方法签名：
            - parse(question: str) -> ParsedQuestion
            - retrieve(parsed_question: ParsedQuestion) -> RetrievalResult
        =====================================================
        """
        # ---- 配置路径 ----
        if config_path is None:
            config_path = os.path.join(BASE_DIR, "config.yaml")

        print("=" * 50)
        print("  GraphRAG 问答系统 - 初始化")
        print("=" * 50)

        # ---- 模块1: 问题理解（目前用Mock） ----
        #self.question_understanding = MockQuestionUnderstanding()
        #print("[✓] 问题理解模块: Mock（等待对接）")
        self.question_understanding = QuestionUnderstanding()
        print("[✓] 问题理解模块: 已加载")
        # ---- 模块2: 图谱检索 ----
        self.graph_retrieval = Neo4jGraphRetrieval()
        print("[✓] 图谱检索模块: 已加载")
        # ---- 模块3: 上下文构造（已实现） ----
        self.context_builder = ContextBuilder()
        print("[✓] 上下文构造模块: 已加载")

        # ---- 模块4: Prompt模板（已实现） ----
        self.prompt_manager = PromptTemplateManager()
        print("[✓] Prompt模板模块: 已加载")

        # ---- 模块5: 答案格式化（已实现） ----
        self.answer_formatter = AnswerFormatter()
        print("[✓] 答案格式化模块: 已加载")

        # ---- 模块6: 大模型（已实现） ----
        self.llm = create_llm(config_path)

        print("=" * 50)
        print("  初始化完成，可以开始提问")
        print("=" * 50)
        print()

    def answer(self, question: str, verbose: bool = False) -> FormattedAnswer:
        """
        完整的 GraphRAG 问答流程。

        Args:
            question: 用户的自然语言问题
            verbose:  是否打印中间步骤（调试用）

        Returns:
            FormattedAnswer: 最终的格式化答案

        流程示意（对应课题要求的 GraphRAG 核心流程）：
            Step 1: 用户输入 → 实体识别 + 意图分类
            Step 2: 实体链接到图谱节点 → Cypher查询获取子图
            Step 3: 查询结果格式化为自然语言上下文
            Step 4: 构造 Prompt
            Step 5: 调用 LLM 生成答案
            Step 6: 格式化输出 + 附加溯源
        """
        # ========== Step 1: 问题理解 ==========
        # 从问题中提取实体（如"高血压"）、意图（如"能否投保"）、年龄等
        parsed = self.question_understanding.parse(question)
        if verbose:
            print(f"[Step 1/6] 问题理解:")
            print(f"  实体: {[e['text'] for e in parsed.entities]}")
            print(f"  意图: {parsed.intent}")
            print(f"  年龄: {parsed.age}")
            print()

        # ========== Step 2: 图谱检索 ==========
        # 用识别出的实体去知识图谱中查找相关三元组
        retrieval = self.graph_retrieval.retrieve(parsed)
        if verbose:
            print(f"[Step 2/6] 图谱检索:")
            print(f"  匹配实体: {retrieval.matched_entities}")
            print(f"  找到 {len(retrieval.triples)} 条三元组")
            for t in retrieval.triples[:5]:  # 最多显示5条
                print(f"    - {t.to_text()}")
            if len(retrieval.triples) > 5:
                print(f"    ... 还有 {len(retrieval.triples) - 5} 条")
            print()

        # ========== Step 3: 上下文构造 ==========
        # 把三元组翻译成大模型能理解的自然语言
        context = self.context_builder.build_context(parsed, retrieval)
        if verbose:
            print(f"[Step 3/6] 构造的上下文（前200字）:")
            print(f"  {context[:200]}...")
            print()

        # ========== Step 4: Prompt 构建 ==========
        # 根据意图选择模板，组装完整的 Prompt
        messages = self.prompt_manager.build_prompt(parsed, context)
        if verbose:
            print(f"[Step 4/6] Prompt 已构建（{len(messages)} 条消息）")
            print()

        # ========== Step 5: 调用大模型 ==========
        if verbose:
            print(f"[Step 5/6] 正在调用大模型...")

        llm_response = self.llm.chat(messages)

        if verbose:
            print(f"  模型: {llm_response.model}")
            print(f"  Token: {llm_response.usage}")
            print()

        # ========== Step 6: 答案格式化 ==========
        # 清理输出，评估置信度，附加溯源信息
        formatted = self.answer_formatter.format(
            llm_output=llm_response.content,
            triples=retrieval.triples,
            matched_entities=retrieval.matched_entities,
            intent=parsed.intent,
        )

        if verbose:
            print(f"[Step 6/6] 答案生成完成 (置信度: {formatted.confidence})")
            print()

        return formatted

    def answer_simple(self, question: str) -> str:
        """简化接口：直接返回纯文本答案（不含溯源等元信息）"""
        result = self.answer(question)
        return result.answer_text


# ============================================================
# 直接运行此文件可进行快速测试
# 使用方式：cd rag（或者你本地的这个目录） && python pipeline.py
# ============================================================
if __name__ == "__main__":
    # 创建 Pipeline
    pipeline = GraphRAGPipeline()

    # 测试问题列表（优先命中当前知识图谱中的医疗三元组）
    test_questions = [
        "霍乱属于哪一类疾病？",
        "戈谢病可以用哪些药物治疗？",
        "注射用维拉苷酶β主要是治疗什么疾病？",
        "注射用维拉苷酶β属于哪一类药物？",
    ]

    # 逐个测试
    for q in test_questions:
        print("=" * 60)
        print(f"问题: {q}")
        print("=" * 60)

        result = pipeline.answer(q, verbose=True)

        print("-" * 40)
        print(f"回答:\n{result.answer_text}")
        print("-" * 40)
        print(f"引用了 {len(result.source_triples)} 条知识图谱记录")
        print(f"置信度: {result.confidence}")
        print()