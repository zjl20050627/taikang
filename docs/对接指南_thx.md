# 对接指南

> 本文档说明「问题理解」和「图谱检索」模块如何与 RAG Pipeline 对接。
> 目前这两个模块使用 Mock 实现，对接时只需 **实现指定接口 + 修改 pipeline.py 两行代码**。

---

## 一、当前系统状态

Pipeline 已经可以完整运行（使用 Mock 数据）：

```bash
cd rag

# 安装依赖
pip install streamlit zhipuai pyyaml python-dotenv neo4j
# 或者pip install -r requirements.txt
# 运行测试
python pipeline.py

# 或启动网页界面
streamlit run interface/streamlit_app.py
```

如果万一但凡一切正常、能够正常跑通的话，应该是不需要改我的任何文件，只需要：在你的目录下写好你的模块，然后在 `pipeline.py` 里改两行就完成对接

---

## 二、数据结构说明

所有模块间传递的数据结构定义在 `data_models.py` 中，可以直接导入使用：

```python
# 在你的代码中这样导入：
import sys
sys.path.insert(0, "D:/Projects/taikang")  # 改成你的项目根目录
from data_models import Triple, ParsedQuestion, RetrievalResult
```

---

### 2.1 Triple（三元组）

```python
from data_models import Triple

# 一条知识：高血压的常用药物是硝苯地平，来源于医保目录
t = Triple(
    head="高血压",              # 头实体
    head_type="Disease",        # 头实体类型
    relation="常用药物",         # 关系
    tail="硝苯地平",            # 尾实体
    tail_type="Drug",           # 尾实体类型
    source="医保目录"           # 数据来源（用于溯源展示）
)
```

实体类型参考（可以根据图谱本体扩展）：

| 类型                   | 说明   | 示例          |
| -------------------- | ---- | ----------- |
| Disease              | 疾病   | 高血压、糖尿病     |
| Drug                 | 药物   | 硝苯地平、二甲双胍   |
| InsuranceProduct     | 保险产品 | 平安护理险、百万医疗险 |
| InsuranceType        | 保险类型 | 重疾险、医疗险     |
| EldercareInstitution | 养老机构 | 泰康之家        |
| DiseaseCategory      | 疾病类别 | 心血管疾病       |
| Coverage             | 保障内容 | 长期护理费用      |
| AgeRange             | 年龄范围 | 18-75岁      |
| Price                | 价格   | 2000-5000元  |
| Service              | 服务   | 医养结合护理      |
| Examination          | 检查项目 | 血压监测        |

---

### 2.2 ParsedQuestion（问题理解的输出）

```python
from data_models import ParsedQuestion

# 示例：用户问 "70岁高血压能买护理险吗？"
parsed = ParsedQuestion(
    original_question="70岁高血压能买护理险吗？",
    entities=[
        {"text": "高血压", "type": "Disease", "normalized": "高血压"},
        {"text": "护理险", "type": "InsuranceProduct", "normalized": "护理险"},
    ],
    intent="insurability",   # 意图分类，见下表
    age=70,                  # 从问题中提取的年龄（没有则为None）
    constraints={},          # 其他约束（如 {"gender": "男"}）
)
```

意图分类（`intent`）可选值：

| 值            | 含义   | 用户问题示例      |
| ------------ | ---- | ----------- |
| insurability | 能否投保 | "高血压能买护理险吗" |
| cost         | 费用   | "养老院多少钱"    |
| coverage     | 保障范围 | "重疾险保什么"    |
| treatment    | 治疗   | "高血压吃什么药"   |
| eligibility  | 资格条件 | "护理险有什么要求"  |
| general      | 通用   | 其他无法分类的问题   |

---

### 2.3 RetrievalResult（图谱检索的输出）

```python
from data_models import RetrievalResult, Triple

result = RetrievalResult(
    triples=[                                # 检索到的三元组列表
        Triple("高血压", "Disease", "常用药物", "硝苯地平", "Drug", "医保目录"),
        Triple("太平护理险", "InsuranceProduct", "可承保", "高血压I级", "Disease", "太平保险条款"),
    ],
    matched_entities=["高血压", "护理险"],     # 成功匹配到图谱的实体名
    query_used="MATCH (n)-[r]-(m) WHERE ...", # 实际执行的Cypher（可选，用于调试）
    hop_count=1,                              # 实际查询的跳数（可选）
)
```

---

## 三、「问题理解」模块对接

### 3.1 你需要实现什么

写一个类，包含一个 `parse` 方法：

```python
# question_understanding/your_module.py

import sys
sys.path.insert(0, "D:/Projects/taikang")  # 项目根目录
from data_models import ParsedQuestion


class QuestionUnderstanding:
    """
    问题理解模块。

    使用 HanLP / BERT-NER / 其他方法 实现实体识别和意图分类。
    """

    def __init__(self):
        # 在这里加载你的模型、词典等资源
        pass

    def parse(self, question: str) -> ParsedQuestion:
        """
        解析用户问题。

        Args:
            question: 用户输入的原始问题字符串
                      如 "70岁高血压能买护理险吗？"

        Returns:
            ParsedQuestion: 必须包含以下字段：
                - original_question: 原始问题（直接赋值 question）
                - entities: 实体列表，每个实体是字典：
                    {"text": "原文", "type": "实体类型", "normalized": "标准化名称"}
                - intent: 意图字符串（见上面的表格）
                - age: 年龄整数或None
                - constraints: 其他约束字典（可以为空 {}）
        """
        # ===== 你的实现 =====
        
        # 1. 实体识别（用 HanLP / BERT-NER / 规则 等）
        entities = []
        # entities.append({"text": "高血压", "type": "Disease", "normalized": "高血压"})

        # 2. 意图分类
        intent = "general"

        # 3. 年龄提取
        age = None

        # 4. 其他约束
        constraints = {}

        return ParsedQuestion(
            original_question=question,
            entities=entities,
            intent=intent,
            age=age,
            constraints=constraints,
        )
```

---

### 3.2 关键要求

| 要求          | 说明                                                                         |
| ----------- | -------------------------------------------------------------------------- |
| 方法签名        | `def parse(self, question: str) -> ParsedQuestion`                         |
| entities 格式 | 列表，每个元素必须是 `{"text": str, "type": str, "normalized": str}`                 |
| intent 取值   | 必须是以下之一：insurability / cost / coverage / treatment / eligibility / general |
| age         | int 或 None                                                                 |

---

### 3.3 怎么测试

```python
# 在你的目录下运行测试
from your_module import QuestionUnderstanding

qu = QuestionUnderstanding()
result = qu.parse("70岁高血压能买护理险吗？")

print(result.entities)   # 应该包含高血压和护理险
print(result.intent)     # 应该是 "insurability"
print(result.age)        # 应该是 70
```

---

## 四、「图谱检索」模块对接

### 4.1 你需要实现什么

写一个类，包含一个 `retrieve` 方法：

```python
# graph-retrieval/your_module.py

import os
import sys
sys.path.insert(0, "D:/Projects/taikang")  # 项目根目录
from data_models import ParsedQuestion, RetrievalResult, Triple

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()  # 加载 .env 中的 Neo4j 密钥


class GraphRetrieval:
    """
    图谱检索模块。

    连接 Neo4j Aura(我自己用的是这玩意，当然用本地的也行)，根据问题中的实体查询相关子图。
    """

    def __init__(self):
        # 连接 Neo4j Aura
        self.driver = GraphDatabase.driver(
            os.environ["NEO4J_URI"],
            auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
        )

    def retrieve(self, parsed_question: ParsedQuestion, max_hops: int = 2) -> RetrievalResult:
        """
        从知识图谱中检索与问题相关的三元组。

        Args:
            parsed_question: 问题理解模块的输出（ParsedQuestion）
                             重点使用其中的 entities 字段
            max_hops: 最大查询跳数（1跳 或 2跳）

        Returns:
            RetrievalResult: 必须包含以下字段：
                - triples: Triple 对象的列表（核心！）
                - matched_entities: 成功匹配到图谱的实体名列表
                - query_used: 执行的Cypher语句（可选，调试用）
                - hop_count: 实际查询跳数（可选）
        """
        triples = []
        matched_entities = []

        # 遍历问题中的每个实体
        for entity in parsed_question.entities:
            entity_name = entity["normalized"]  # 用标准化名称去匹配图谱

            # ===== 执行 Cypher 查询 =====
            # 示例：查找与该实体相关的所有1跳关系
            cypher = """
                MATCH (n)-[r]-(m)
                WHERE n.name = $name
                RETURN n.name AS head, labels(n)[0] AS head_type,
                       type(r) AS relation,
                       m.name AS tail, labels(m)[0] AS tail_type
                LIMIT 20
            """

            with self.driver.session() as session:
                result = session.run(cypher, name=entity_name)
                records = list(result)

                if records:
                    matched_entities.append(entity_name)

                for record in records:
                    triples.append(Triple(
                        head=record["head"],
                        head_type=record["head_type"],
                        relation=record["relation"],
                        tail=record["tail"],
                        tail_type=record["tail_type"],
                        source="Neo4j知识图谱",  # 可以更细化，标注具体来源
                    ))

        return RetrievalResult(
            triples=triples,
            matched_entities=matched_entities,
            query_used=cypher if triples else "",
            hop_count=1,
        )

    def close(self):
        """关闭数据库连接"""
        self.driver.close()
```

---

### 4.2 Neo4j Aura 连接信息

密钥存放在项目根目录的 `.env` 文件中：

```env
NEO4J_URI=your_neo4j_uri
NEO4J_USER=neo4j
NEO4J_PASSWORD=xxxxxx
```

使用方式：

```python
from dotenv import load_dotenv
import os
from neo4j import GraphDatabase

load_dotenv()  # 加载 .env

driver = GraphDatabase.driver(
    os.environ["NEO4J_URI"],
    auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
)

# 测试连接
with driver.session() as session:
    result = session.run("RETURN '连接成功' AS msg")
    print(result.single()["msg"])
```

---

### 4.3 关键要求

| 要求        | 说明                                                                                          |
| --------- | ------------------------------------------------------------------------------------------- |
| 方法签名      | `def retrieve(self, parsed_question: ParsedQuestion, max_hops: int = 2) -> RetrievalResult` |
| triples   | 必须是 Triple 对象的列表，不能是普通字典                                                                    |
| source 字段 | 建议填写数据来源（如"医保目录""XX保险条款"），用于前端溯源展示                                                          |
| 去重        | 同一条三元组不要重复返回                                                                                |

---

### 4.4 怎么测试

```python
from your_module import GraphRetrieval
from data_models import ParsedQuestion

gr = GraphRetrieval()
parsed = ParsedQuestion(
    original_question="高血压能买护理险吗",
    entities=[{"text": "高血压", "type": "Disease", "normalized": "高血压"}],
    intent="insurability",
)
result = gr.retrieve(parsed)

print(f"匹配实体: {result.matched_entities}")
print(f"三元组数: {len(result.triples)}")
for t in result.triples:
    print(f"  {t.to_text()}")

gr.close()
```

---

## 五、对接流程（3步完成）

### Step 1：你写好模块后通知我或者自己改

告诉我：

* 你的文件路径（如 `question-understanding/ner_module.py`）
* 你的类名（如 `NERQuestionUnderstanding`）

---

### Step 2：在 pipeline.py 中替换

我只需要改 `pipeline.py` 的 `__init__` 方法中的两行：

```python
# ===== 替换前（Mock） =====
self.question_understanding = MockQuestionUnderstanding()
self.graph_retrieval = MockGraphRetrieval()

# ===== 替换后（你的真实实现） =====
# 问题理解（假设你的文件是 question-understanding/ner_module.py，类名 NERQuestionUnderstanding）
sys.path.insert(0, os.path.join(BASE_DIR, "question-understanding"))
from ner_module import NERQuestionUnderstanding
self.question_understanding = NERQuestionUnderstanding()

# 图谱检索（假设你的文件是 graph-retrieval/neo4j_retrieval.py，类名 Neo4jRetrieval）
sys.path.insert(0, os.path.join(BASE_DIR, "graph-retrieval"))
from neo4j_retrieval import Neo4jRetrieval
self.graph_retrieval = Neo4jRetrieval()
```

---

### Step 3：联调测试

```bash
python pipeline.py
```

看到正常的回答就说明对接成功。

---

## 六、常见问题

**Q: 可以先只对接一个模块吗？**
A: 可以。比如你先完成「问题理解」，然后只替换问题理解，图谱检索继续用 Mock。

**Q: 我的实体类型和你定义的不一样怎么办？**
A: 没关系，entities 中的 type 字段是字符串，你用什么都行。不过建议和图谱本体设计一致。

**Q: 我的 Cypher 查询返回的字段名和 Triple 不完全对应怎么办？**
A: 在你的 retrieve 方法里做映射就行，只要最终返回的是 Triple 对象列表即可。

**Q: 三元组的 source 字段必须填吗？**
A: 不填也不会报错（默认空字符串），但建议填上，前端溯源展示会用到，也是课题要求的“答案溯源”功能。

**Q: 怎么判断对接成功？**
A: 运行 `python pipeline.py`，如果 Step 1 显示的实体和意图是正确的、Step 2 显示了从真实图谱检索的三元组，就说明对接成功。
