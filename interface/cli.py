# ============================================================
# cli.py - 命令行交互界面
# ============================================================
# 运行方式：cd rag && python interface/cli.py
#
# 功能：在终端中进行问答交互，支持查看溯源信息。
# 适合快速测试和演示。
# ============================================================

import sys
import os

# 把 rag/ 根目录加入路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import GraphRAGPipeline


def main():
    """命令行主函数"""
    print()
    print("=" * 60)
    print("  🏥 保险+医养 GraphRAG 问答系统（命令行版）")
    print("=" * 60)
    print()
    print("使用说明：")
    print("  - 直接输入问题开始对话")
    print("  - 输入 quit 或 exit 退出")
    print("  - 输入 test 运行预设测试")
    print()

    # 初始化 Pipeline
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config.yaml",
    )
    pipeline = GraphRAGPipeline(config_path=config_path)

    # 交互循环
    while True:
        try:
            question = input("\n❓ 您的问题: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 再见！")
            break

        # 空输入跳过
        if not question:
            continue

        # 退出命令
        if question.lower() in ("quit", "exit", "q"):
            print("👋 再见！")
            break

        # 预设测试命令
        if question.lower() == "test":
            _run_tests(pipeline)
            continue

        # 正常问答
        print("\n⏳ 正在检索知识图谱并生成回答...\n")
        result = pipeline.answer(question, verbose=True)

        # 显示回答
        print("=" * 50)
        print(f"💡 回答:\n")
        print(result.answer_text)
        print()

        # 显示溯源
        if result.source_triples:
            print("📚 知识来源:")
            for i, src in enumerate(result.source_triples, 1):
                source_tag = f" [{src['source']}]" if src.get("source") else ""
                print(f"  {i}. {src['head']} --[{src['relation']}]--> {src['tail']}{source_tag}")

        # 显示元信息
        entities_str = "、".join(result.matched_entities) if result.matched_entities else "无"
        print(f"\n📊 置信度: {result.confidence} | 意图: {result.intent} | 匹配实体: {entities_str}")
        print("=" * 50)


def _run_tests(pipeline):
    """运行预设测试问题"""
    test_questions = [
        "70岁高血压能买护理险吗？",
        "糖尿病可以买什么保险？",
        "养老院一个月多少钱？",
        "高血压吃什么药？",
    ]

    print("\n🧪 开始运行预设测试...\n")
    for i, q in enumerate(test_questions, 1):
        print(f"[测试 {i}/{len(test_questions)}] {q}")
        result = pipeline.answer(q, verbose=False)
        print(f"  → 置信度: {result.confidence} | 实体: {result.matched_entities}")
        print(f"  → 回答前50字: {result.answer_text[:50]}...")
        print()
    print("🧪 测试完成！\n")


if __name__ == "__main__":
    main()