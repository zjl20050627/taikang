# ============================================================
# streamlit_app.py - Streamlit 网页界面
# ============================================================
# 运行方式：
#   cd rag
#   streamlit run interface/streamlit_app.py
#
# 功能：
#   - 聊天式问答界面
#   - 侧边栏示例问题（一键提问）
#   - 答案溯源展示（可展开查看引用的三元组）
#   - 置信度和意图标签
#   - 对话历史记录
# ============================================================

import sys
import os

# 把 rag/ 根目录加入路径，以便导入 pipeline.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from pipeline import GraphRAGPipeline


# ============================================================
# 页面基础配置
# ============================================================
st.set_page_config(
    page_title="保险+医养 智能问答",
    page_icon="🏥",  #先用着emoji吧，之后用AI搞点图标啥的
    layout="wide",
)


@st.cache_resource
def load_pipeline():
    """
    加载 GraphRAG Pipeline（只在首次访问时执行一次）。
    @st.cache_resource 装饰器确保不会重复初始化。
    """
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config.yaml",
    )
    return GraphRAGPipeline(config_path=config_path)


def main():
    """Streamlit 主函数"""

    # ===== 页面标题 =====
    st.title("🏥 保险+医养 GraphRAG 智能问答系统")
    st.caption("基于知识图谱的检索增强生成（GraphRAG），提供准确、可溯源的问答服务")

    # ===== 侧边栏 =====
    with st.sidebar:
        st.header("显示设置")
        show_sources = st.checkbox("显示知识来源（溯源）", value=True)
        show_debug = st.checkbox("显示调试信息", value=False)

        st.markdown("---")

        st.header("试试这些问题")
        example_questions = [
            "70岁高血压能买护理险吗？",
            "糖尿病可以买什么保险？",
            "养老院一个月多少钱？",
            "高血压吃什么药？",
            "重疾险保哪些疾病？",
        ]
        # 点击示例问题按钮 → 自动填入输入框
        for eq in example_questions:
            if st.button(eq, key=f"ex_{eq}", use_container_width=True):
                st.session_state["pending_question"] = eq

        st.markdown("---")
        st.markdown(
            "### 关于系统\n"
            "- **架构**: GraphRAG\n"
            "- **图谱**: Neo4j Aura\n"
            "- **大模型**: 智谱AI GLM\n"
            "- **框架**: Streamlit\n"
        )

    # ===== 加载 Pipeline =====
    pipeline = load_pipeline()

    # ===== 初始化对话历史 =====
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # ===== 显示历史对话 =====
    for entry in st.session_state.chat_history:
        # 用户消息
        with st.chat_message("user"):
            st.write(entry["question"])
        # 助手回答
        with st.chat_message("assistant"):
            st.write(entry["answer"])
            # 溯源展示
            if show_sources and entry.get("sources"):
                with st.expander("查看知识来源（点击展开）", expanded=False):
                    _render_sources(entry["sources"])

    # ===== 处理输入 =====
    # 检查是否有来自示例按钮的待处理问题
    pending = st.session_state.pop("pending_question", None)
    question = st.chat_input("请输入您的问题，例如：70岁高血压能买护理险吗？")

    # 优先处理示例按钮的问题
    if pending and not question:
        question = pending

    if question:
        # 显示用户消息
        with st.chat_message("user"):
            st.write(question)

        # 生成并显示回答
        with st.chat_message("assistant"):
            # 显示加载状态
            with st.spinner("正在检索知识图谱并生成回答..."):
                result = pipeline.answer(question, verbose=False)

            # 显示答案正文
            st.write(result.answer_text)

            # 显示元信息标签
            confidence_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}
            emoji = confidence_emoji.get(result.confidence, "🟡")
            entities_str = "、".join(result.matched_entities) if result.matched_entities else "无"
            st.caption(
                f"{emoji} 置信度: {result.confidence} | "
                f"意图: {result.intent} | "
                f"匹配实体: {entities_str}"
            )

            # 溯源信息
            if show_sources and result.source_triples:
                with st.expander("查看知识来源（点击展开）", expanded=False):
                    _render_sources(result.source_triples)

            # 调试信息
            if show_debug:
                with st.expander("调试信息", expanded=False):
                    st.json(result.to_display_dict())

        # 保存到对话历史
        st.session_state.chat_history.append({
            "question": question,
            "answer": result.answer_text,
            "sources": result.source_triples,
            "confidence": result.confidence,
        })


def _render_sources(sources: list):
    """
    渲染溯源三元组列表。

    Args:
        sources: 三元组字典列表
    """
    for i, src in enumerate(sources, 1):
        source_tag = f"  *[{src['source']}]*" if src.get("source") else ""
        st.markdown(
            f"`{i}.` **{src['head']}** "
            f"--[{src['relation']}]--> "
            f"**{src['tail']}**"
            f"{source_tag}"
        )


if __name__ == "__main__":
    main()