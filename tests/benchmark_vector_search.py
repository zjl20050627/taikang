# ============================================================
# tests/benchmark_vector_search.py - 向量检索性能对比测试
# ============================================================
# 功能：对比传统关键词检索和向量检索的性能差异
#       并生成可视化图表展示优化效果
#
# 使用方法：
#   python tests/benchmark_vector_search.py
# ============================================================

import os
import sys
import time
import json
from typing import List, Dict, Tuple
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei']  # 支持中文
matplotlib.rcParams['axes.unicode_minus'] = False

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from data_models import ParsedQuestion
from graph_retrieval.neo4j_retrieval import Neo4jGraphRetrieval
from graph_retrieval.neo4j_retrieval_with_vector import Neo4jGraphRetrievalWithVector


class BenchmarkTester:
    """性能对比测试器"""
    
    def __init__(self):
        self.traditional_retrieval = Neo4jGraphRetrieval()
        self.vector_retrieval = Neo4jGraphRetrievalWithVector()
        
        # 测试问题集
        self.test_questions = [
            {
                "question": "高血压用什么药治疗？",
                "parsed": ParsedQuestion(
                    original_question="高血压用什么药治疗？",
                    entities=[{"text": "高血压", "type": "Disease"}],
                    intent="treatment"
                )
            },
            {
                "question": "糖尿病可以买哪些保险？",
                "parsed": ParsedQuestion(
                    original_question="糖尿病可以买哪些保险？",
                    entities=[{"text": "糖尿病", "type": "Disease"}],
                    intent="insurability"
                )
            },
            {
                "question": "护理险保障什么内容？",
                "parsed": ParsedQuestion(
                    original_question="护理险保障什么内容？",
                    entities=[{"text": "护理险", "type": "InsuranceProduct"}],
                    intent="coverage"
                )
            },
            {
                "question": "70 岁能买什么保险？",
                "parsed": ParsedQuestion(
                    original_question="70 岁能买什么保险？",
                    entities=[],
                    intent="insurability",
                    age=70
                )
            },
            {
                "question": "原发性高血压怎么治疗？",
                "parsed": ParsedQuestion(
                    original_question="原发性高血压怎么治疗？",
                    entities=[{"text": "原发性高血压", "type": "Disease"}],
                    intent="treatment"
                )
            }
        ]
        
        self.results = {
            "traditional": [],
            "vector": []
        }
    
    def benchmark_single(self, test_case: Dict, retrieval_method, method_name: str) -> Dict:
        """测试单个问题的性能"""
        question = test_case["question"]
        parsed = test_case["parsed"]
        
        start_time = time.time()
        result = retrieval_method.retrieve(parsed)
        end_time = time.time()
        
        return {
            "question": question,
            "method": method_name,
            "time_seconds": end_time - start_time,
            "num_triples": len(result.triples),
            "num_entities": len(result.matched_entities),
            "query_used": result.query_used
        }
    
    def run_benchmark(self, num_iterations: int = 3):
        """运行完整性能测试"""
        print("=" * 70)
        print("  向量检索性能对比测试")
        print("=" * 70)
        
        print(f"\n测试问题数量：{len(self.test_questions)}")
        print(f"迭代次数：{num_iterations}")
        print()
        
        # 测试传统方法
        print("[1/2] 测试传统关键词检索...")
        self.traditional_retrieval.vector_search_enabled = False
        
        for i, test_case in enumerate(self.test_questions, 1):
            times = []
            for _ in range(num_iterations):
                result = self.benchmark_single(test_case, self.traditional_retrieval, "traditional")
                times.append(result["time_seconds"])
            
            avg_time = sum(times) / len(times)
            self.results["traditional"].append({
                "question": test_case["question"],
                "avg_time": avg_time,
                "min_time": min(times),
                "max_time": max(times),
                "num_triples": result["num_triples"],
                "num_entities": result["num_entities"]
            })
            print(f"  ✓ 问题{i}: {test_case['question'][:20]:<20} 平均耗时 {avg_time*1000:.2f}ms")
        
        print()
        
        # 测试向量方法
        print("[2/2] 测试向量检索...")
        self.vector_retrieval.vector_search_enabled = True
        
        for i, test_case in enumerate(self.test_questions, 1):
            times = []
            for _ in range(num_iterations):
                result = self.benchmark_single(test_case, self.vector_retrieval, "vector")
                times.append(result["time_seconds"])
            
            avg_time = sum(times) / len(times)
            self.results["vector"].append({
                "question": test_case["question"],
                "avg_time": avg_time,
                "min_time": min(times),
                "max_time": max(times),
                "num_triples": result["num_triples"],
                "num_entities": result["num_entities"]
            })
            print(f"  ✓ 问题{i}: {test_case['question'][:20]:<20} 平均耗时 {avg_time*1000:.2f}ms")
        
        print()
        print("=" * 70)
        print("  测试完成")
        print("=" * 70)
    
    def analyze_results(self) -> Dict:
        """分析测试结果"""
        analysis = {
            "avg_time_traditional": 0,
            "avg_time_vector": 0,
            "avg_triples_traditional": 0,
            "avg_triples_vector": 0,
            "avg_entities_traditional": 0,
            "avg_entities_vector": 0,
            "speedup": 0,
            "recall_improvement": 0
        }
        
        if self.results["traditional"] and self.results["vector"]:
            analysis["avg_time_traditional"] = sum(r["avg_time"] for r in self.results["traditional"]) / len(self.results["traditional"])
            analysis["avg_time_vector"] = sum(r["avg_time"] for r in self.results["vector"]) / len(self.results["vector"])
            
            analysis["avg_triples_traditional"] = sum(r["num_triples"] for r in self.results["traditional"]) / len(self.results["traditional"])
            analysis["avg_triples_vector"] = sum(r["num_triples"] for r in self.results["vector"]) / len(self.results["vector"])
            
            analysis["avg_entities_traditional"] = sum(r["num_entities"] for r in self.results["traditional"]) / len(self.results["traditional"])
            analysis["avg_entities_vector"] = sum(r["num_entities"] for r in self.results["vector"]) / len(self.results["vector"])
            
            if analysis["avg_time_vector"] > 0:
                analysis["speedup"] = analysis["avg_time_traditional"] / analysis["avg_time_vector"]
            
            if analysis["avg_entities_traditional"] > 0:
                analysis["recall_improvement"] = (analysis["avg_entities_vector"] - analysis["avg_entities_traditional"]) / analysis["avg_entities_traditional"] * 100
        
        return analysis
    
    def plot_results(self, output_path: str = None):
        """生成可视化图表"""
        if not self.results["traditional"] or not self.results["vector"]:
            print("错误：没有测试数据，请先运行 benchmark")
            return
        
        analysis = self.analyze_results()
        
        # 创建图表
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('向量检索 vs 传统关键词检索 - 性能对比分析', fontsize=16, fontweight='bold')
        
        # 图 1: 平均响应时间对比
        ax1 = axes[0, 0]
        methods = ['传统检索', '向量检索']
        times = [analysis["avg_time_traditional"] * 1000, analysis["avg_time_vector"] * 1000]
        colors = ['#FF6B6B', '#4ECDC4']
        bars1 = ax1.bar(methods, times, color=colors, alpha=0.8)
        ax1.set_ylabel('平均响应时间 (ms)')
        ax1.set_title('平均响应时间对比')
        ax1.grid(axis='y', alpha=0.3)
        
        for bar, time_val in zip(bars1, times):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, 
                    f'{time_val:.2f}ms', ha='center', va='bottom', fontsize=10)
        
        # 图 2: 检索到的三元组数量对比
        ax2 = axes[0, 1]
        triples = [analysis["avg_triples_traditional"], analysis["avg_triples_vector"]]
        bars2 = ax2.bar(methods, triples, color=colors, alpha=0.8)
        ax2.set_ylabel('平均三元组数量')
        ax2.set_title('检索覆盖率对比')
        ax2.grid(axis='y', alpha=0.3)
        
        for bar, triple_val in zip(bars2, triples):
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, 
                    f'{triple_val:.1f}', ha='center', va='bottom', fontsize=10)
        
        # 图 3: 匹配实体数量对比
        ax3 = axes[1, 0]
        entities = [analysis["avg_entities_traditional"], analysis["avg_entities_vector"]]
        bars3 = ax3.bar(methods, entities, color=colors, alpha=0.8)
        ax3.set_ylabel('平均匹配实体数')
        ax3.set_title('实体召回率对比')
        ax3.grid(axis='y', alpha=0.3)
        
        for bar, entity_val in zip(bars3, entities):
            ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2, 
                    f'{entity_val:.1f}', ha='center', va='bottom', fontsize=10)
        
        # 图 4: 性能提升统计
        ax4 = axes[1, 1]
        ax4.axis('off')
        
        stats_text = f"""
        性能提升统计
        
        响应时间:
          传统检索：{analysis["avg_time_traditional"]*1000:.2f} ms
          向量检索：{analysis["avg_time_vector"]*1000:.2f} ms
          提升倍数：{analysis["speedup"]:.2f}x
        
        检索覆盖率:
          传统检索：{analysis["avg_triples_traditional"]:.1f} 条三元组
          向量检索：{analysis["avg_triples_vector"]:.1f} 条三元组
          提升：{(analysis["avg_triples_vector"] - analysis["avg_triples_traditional"])/analysis["avg_triples_traditional"]*100:.1f}%
        
        实体召回率:
          传统检索：{analysis["avg_entities_traditional"]:.1f} 个实体
          向量检索：{analysis["avg_entities_vector"]:.1f} 个实体
          提升：{analysis["recall_improvement"]:.1f}%
        """
        
        ax4.text(0.1, 0.5, stats_text, fontsize=11, verticalalignment='center',
                family='monospace', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.tight_layout()
        
        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            print(f"✓ 图表已保存到：{output_path}")
        else:
            output_path = os.path.join(BASE_DIR, "tests", "benchmark_results.png")
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            print(f"✓ 图表已保存到：{output_path}")
        
        plt.show()
    
    def save_results(self, output_path: str = None):
        """保存测试结果到 JSON 文件"""
        if not output_path:
            output_path = os.path.join(BASE_DIR, "tests", "benchmark_results.json")
        
        analysis = self.analyze_results()
        
        results_data = {
            "summary": analysis,
            "detailed_results": {
                "traditional": self.results["traditional"],
                "vector": self.results["vector"]
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 测试结果已保存到：{output_path}")
    
    def print_summary(self):
        """打印测试摘要"""
        analysis = self.analyze_results()
        
        print("\n" + "=" * 70)
        print("  性能对比分析摘要")
        print("=" * 70)
        print(f"\n【响应时间】")
        print(f"  传统检索：{analysis['avg_time_traditional']*1000:.2f} ms")
        print(f"  向量检索：{analysis['avg_time_vector']*1000:.2f} ms")
        print(f"  性能提升：{analysis['speedup']:.2f}x")
        
        print(f"\n【检索覆盖率】")
        print(f"  传统检索：{analysis['avg_triples_traditional']:.1f} 条三元组")
        print(f"  向量检索：{analysis['avg_triples_vector']:.1f} 条三元组")
        print(f"  提升：{(analysis['avg_triples_vector'] - analysis['avg_triples_traditional'])/analysis['avg_triples_traditional']*100:.1f}%")
        
        print(f"\n【实体召回率】")
        print(f"  传统检索：{analysis['avg_entities_traditional']:.1f} 个实体")
        print(f"  向量检索：{analysis['avg_entities_vector']:.1f} 个实体")
        print(f"  提升：{analysis['recall_improvement']:.1f}%")
        
        print("\n" + "=" * 70)


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("  GraphRAG 向量检索性能对比测试")
    print("=" * 70)
    
    # 确保 tests 目录存在
    tests_dir = os.path.join(BASE_DIR, "tests")
    os.makedirs(tests_dir, exist_ok=True)
    
    tester = BenchmarkTester()
    
    # 运行测试
    tester.run_benchmark(num_iterations=3)
    
    # 打印摘要
    tester.print_summary()
    
    # 保存结果
    tester.save_results()
    
    # 生成图表
    tester.plot_results()
    
    print("\n✓ 所有测试完成！")
    print(f"\n输出文件:")
    print(f"  - {os.path.join(tests_dir, 'benchmark_results.json')}")
    print(f"  - {os.path.join(tests_dir, 'benchmark_results.png')}")


if __name__ == "__main__":
    main()
