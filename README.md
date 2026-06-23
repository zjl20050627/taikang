## 面向“保险 + 医养”生态的 GraphRAG 问答系统

本项目实现了一个基于 **知识图谱 + 大语言模型（GraphRAG）** 的问答系统，面向“保险 + 医疗 + 养老”跨域场景。  
整体流程：**用户提问 → 规则 NER/意图识别 → Neo4j 图谱检索 → 构造上下文 Prompt → 调用 LLM → 生成带溯源的回答**。

---

### 一、项目整体结构

- `question_understanding/`：**问题理解模块**  
  - 规则词典 + 正则实现实体识别（疾病、药品、保险产品、养老机构等）  
  - 意图分类（可投保性 insurability / 费用 cost / 保障 coverage / 治疗 treatment / 资格 eligibility / 通用 general）  
  - 年龄、性别、城市等关键信息抽取，输出 `ParsedQuestion` 数据结构
- `graph_retrieval/`：**图谱检索（Neo4j）**  
  - 从 `config.yaml` 读取 Neo4j 连接配置（URI / 用户 / 密码）  
  - 根据解析后的实体和意图构造 Cypher 查询  
  - 支持：  
    - 疾病治疗关系：`(Disease)-[TREATED_BY]->(Drug)`  
    - 疾病 / 药品分类：`BELONGS_TO`  
    - 保险产品年龄限制 / 保障内容：`AGE_LIMIT`、`COVERAGE`（以及统一成 `HAS_AGE_LIMIT` / `COVERS` 的本体设计）
  - 当图中缺少保险或机构标签时，会自动回退到“疾病中心 1–2 跳子图”
- `answer_generation/`：**答案生成模块**  
  - `ContextBuilder`：将三元组按 head 分组，转成自然语言描述，构造知识上下文  
  - `PromptTemplateManager`：为不同意图设计不同的 Prompt 模板（中文），输出标准 `messages` 列表  
  - `AnswerFormatter`：整理大模型输出，附带引用三元组和置信度
- `llm_integration/`：**大模型集成** 
  - `BaseLLM` / `LLMResponse`：统一 LLM 接口  
  - `MockLLM`：默认使用的本地模拟模型，方便无 Key 调试  
  - `ZhipuAILLM`：对接智谱 AI（GLM 系列），支持推理模型与普通模型  
  - `llm_factory.create_llm()`：根据 `config.yaml` 和 `.env` 自动选择 Mock 或 ZhipuAI
- `storage/`：**图谱存储与导入**  
  - `neo4j_config.py`：封装 Neo4j 连接，优先从项目根目录 `config.yaml` 读取配置  
  - `import_data.py`：读取处理后的实体和三元组 JSON，批量导入 Neo4j（节点 + 关系 + 索引）  
  - `query.py`：按 id 搜索实体、获取 1 跳子图等查询接口
- `extraction/`（来自 `kg` 分支）：**知识图谱构建**  
  - `extract_icd11.py`：从 ICD‑11 文本抽取疾病和疾病分类  
  - `extract_pdf.py`：从“商业健康保险创新药品目录”等 PDF 抽取药品和药品分类  
  - `generate_triples.py`：  
    - 实体标准化与同义词对齐（高血压 / 原发性高血压 / 2 型糖尿病等）  
    - 生成 `BELONGS_TO` / `INDICATED_FOR` / `TREATED_BY` / `ALIGNED_WITH` 等三元组
- `ontology/`：**本体设计文档**  
  - 定义 Disease / Drug / DiseaseCategory / DrugCategory / InsuranceProduct / AgeLimit / Institution / MedicalService 等实体  
  - 定义 TREATED_BY、BELONGS_TO、HAS_AGE_LIMIT、COVERS、PROVIDED_BY、ALIGNED_WITH 等关系
- `visualization/`：**图谱可视化**  
  - `visualization/app.py`：基于 Streamlit + PyVis 的图谱浏览工具，可搜索实体并查看 1 跳子图
- `pipeline.py`：**GraphRAG 主流程入口文件**  
  - 串联上述所有模块，实现从自然语言问题到最终回答的完整流水线。

---

### 二、GraphRAG 问答流程说明

1. **问题理解（QuestionUnderstanding）**
  - 输入：用户自然语言问句（中文）  
  - 输出：`ParsedQuestion`，包含：  
    - 实体列表（`entities`）：如“高血压”“护理险”“养老院”等及其类型  
    - 意图（`intent`）：如 `insurability` / `treatment` / `cost` 等  
    - 年龄（`age`）：解析“70岁”等表达  
    - 其他约束（`constraints`）：性别、城市等
2. **图谱检索（Neo4jGraphRetrieval）**
  - 根据意图构造不同的 Cypher 查询：  
    - 可投保性：保险产品与疾病关系 / 年龄限制  
    - 费用：产品价格 / 养老机构收费（需要在图谱中补充对应关系）  
    - 治疗：疾病与药物的 `TREATED_BY` / 药品适应症 `INDICATED_FOR`
  - 使用实体标准化与同义词映射，提高疾病匹配的鲁棒性  
  - 对 Neo4j 查询结果进行解析，统一为 `Triple` 对象列表  
  - 若主查询结果为空，自动回退到“疾病相关局部子图”作为兜底
3. **上下文构造（ContextBuilder）**
  - 从检索到的三元组中，截取最多 `system.max_triples` 条（默认可在 `config.yaml` 中配置）  
  - 按头实体分组，如【关于高血压】【关于太平养老护理险】等  
  - 使用中文模板将 (head, relation, tail) 转为自然语言句子，拼接成一段“知识背景”说明
4. **Prompt 构建与 LLM 调用**
  - `PromptTemplateManager` 根据意图选取不同的用户 Prompt 模板，填入：  
    - 用户原始问题  
    - 知识图谱上下文文本  
    - 用户年龄等信息
  - 生成标准的 `messages` 列表（system + user），兼容 OpenAI / 智谱等对话接口  
  - 调用 `llm.chat(messages)` 获取大模型回复（默认为 MockLLM，可配置为 ZhipuAI）
5. **答案格式化与溯源（AnswerFormatter）**
  - 对 LLM 输出进行简单清洗和结构化  
  - 附带：引用的三元组列表（用于前端溯源展示）  
  - 计算并输出一个简单的置信度（high / medium / low）  
  - 提供 `answer_simple` 接口直接返回纯文本回答。

---

### 三、本地运行指南

> 以下命令均在项目根目录 `c:\Users\asus\taikang` 执行。

#### 1. 安装依赖

```bash
pip install -r requirements.txt
```

#### 2. 配置并启动本地 Neo4j

1）在 Neo4j Desktop 中：  

- 创建一个 Local DBMS，设置密码（记住即可）  
- 启动该 DBMS，确认 Bolt 地址：如 `bolt://localhost:7687`

2）修改项目根目录的 `config.yaml`：

```yaml
neo4j:
  uri: "bolt://localhost:7687"
  user: "neo4j"
  password: "你的密码"

system:
  max_hops: 2
  max_triples: 50
  enable_source: true
```

#### 3. 构建并导入医疗知识图谱

```bash
python extraction/extract_icd11.py
python extraction/extract_pdf.py
python extraction/generate_triples.py
python storage/import_data.py
```

上述脚本会：  

- 从原始 ICD‑11 文本和药品 PDF 中抽取结构化实体  
- 生成 `aligned_entities.json` 与 `triples.json`  
- 调用 `storage/import_data.py` 将节点和关系批量写入 Neo4j

#### 4. 运行 GraphRAG 问答主流水线

```bash
python pipeline.py
```

你将在终端看到每个测试问题的 6 个步骤：  

1. 实体与意图识别结果
2. 图谱检索的 Cypher 与返回的三元组数量
3. 构造的上下文文本片段
4. 构建的 Prompt 条数
5. LLM 调用信息（模型名、tokens 等）
6. 最终回答、引用三元组数量与置信度

你可以直接修改 `pipeline.py` 末尾的 `test_questions` 列表，替换为你自己的问题。

#### 5. 图谱可视化（可选）

```bash
python -m streamlit run visualization/app.py
```

浏览器中即可：  

- 搜索实体（如“霍乱”“糖尿病”“高血压”）  
- 查看实体的 1 跳子图及关系类型  
- 查看中心节点的属性详情。

---

### 四、配置真实智谱 LLM（可选）

项目默认使用 MockLLM，**无需任何 Key 就能完成整个流程**。  
若想接入智谱 GLM 模型：

1. 在项目根目录创建 `.env` 文件：

```env
ZHIPUAI_API_KEY=你的智谱APIKey
```

1. 在 `config.yaml` 中设置：

```yaml
llm:
  provider: "zhipuai"
```

1. 确认已安装：

```bash
pip install zhipuai
```

再次运行 `python pipeline.py`，即可看到真实模型返回的答案与 token 统计。

---

### 五、注意事项与后续扩展

- 本 README 使用 UTF‑8 编码，只包含常规中英文字符，可在任何现代编辑器中正常显示。  
- 当前图谱中医疗域数据较为丰富（疾病、药品、分类、适应症、治疗关系等），保险与养老域的数据量相对较少；要在“护理险能否投保”“养老院费用”等问题上得到更精准、更多溯源的回答，需要进一步补充：  
  - `InsuranceProduct`、`AgeLimit`、`Coverage`、`COVERS` / `EXCLUDES` 等实体与关系  
  - `Institution`、`MedicalService`、费用与入住条件等实体与关系
- 本项目已经具备：本体设计 + 图谱构建 + Neo4j 存储 + GraphRAG 问答 + 可视化 + LLM 对接的完整工程链路，可直接用于课程/课题的技术报告与演示。

## GraphRAG Question Answering System

This repository implements a **GraphRAG** (knowledge-graph-based Retrieval-Augmented Generation) pipeline for the ��insurance + medical + elderly care�� domain.

### Directory overview

- `question_understanding/`: rule-based question parsing (entities, intent, age, constraints).
- `graph_retrieval/`: Neo4j-based subgraph retrieval (Cypher queries, entity alignment, fallbacks).
- `answer_generation/`: context building from triples, prompt templates, answer formatting.
- `llm_integration/`: LLM abstraction and factory (Mock LLM / ZhipuAI).
- `storage/`: knowledge graph storage utilities (Neo4j config, import scripts, query helpers).
- `extraction/` (from `kg` branch): raw data extraction and triple generation.
- `ontology/`: ontology and entity�Crelationship design docs.
- `visualization/`: Streamlit + PyVis graph explorer.

### End-to-end QA flow

1. **Question understanding**
  `QuestionUnderstanding.parse()` extracts:
  - entities (Disease, Drug, InsuranceProduct, Institution, etc.)
  - intent (insurability, treatment, cost, coverage, eligibility, general)
  - age and simple constraints (gender, city).
2. **Graph retrieval (Neo4j)**
  `Neo4jGraphRetrieval.retrieve()`:
  - builds an intent-aware Cypher query from the parsed question
  - executes it against Neo4j
  - parses records into `Triple` objects
  - if no result for insurance / institution labels, falls back to disease-centered subgraphs.
3. **Context construction**
  `ContextBuilder.build_context()` groups triples by head entity and converts them into readable Chinese sentences, used as knowledge context.
4. **Prompt building & LLM call**
  `PromptTemplateManager.build_prompt()` chooses a template by intent and builds `messages` for the LLM.  
   `create_llm()` returns either:
  - a Mock LLM (no API needed), or  
  - a real ZhipuAI client (when configured).
5. **Answer formatting & traceability**
  The final answer includes:
  - natural-language response
  - referenced triples for traceability
  - a simple confidence score.

### How to run locally

1. **Install dependencies**

```bash
pip install -r requirements.txt
```

1. **Configure Neo4j**

Edit `config.yaml` at the repo root:

```yaml
neo4j:
  uri: "bolt://localhost:7687"
  user: "neo4j"
  password: "your_password"

system:
  max_hops: 2
  max_triples: 50
  enable_source: true
```

Start a local Neo4j DBMS in Neo4j Desktop with the same URI/user/password.

1. **Build and import the medical KG (from `kg` branch code)**

From the project root:

```bash
python extraction/extract_icd11.py
python extraction/extract_pdf.py
python extraction/generate_triples.py
python storage/import_data.py
```

This will create and import:

- `data/processed/medical/aligned_entities.json`
- `data/processed/medical/triples.json`
into your Neo4j instance.

1. **Run the GraphRAG QA pipeline**

```bash
python pipeline.py
```

`pipeline.py` runs several test questions end-to-end and prints:

- intermediate steps (parsing, retrieval, context, prompt, LLM call)
- final answer
- number of referenced triples.

1. **(Optional) Graph visualization**

```bash
python -m streamlit run visualization/app.py
```

Then open the local URL printed in the terminal to:

- search entities by name
- explore their 1-hop neighborhood
- inspect node properties and relationships.

### LLM configuration (ZhipuAI)

By default, the system uses a Mock LLM so that it works without any API keys.

To enable ZhipuAI:

1. Create `.env` in the repo root with:

```env
ZHIPUAI_API_KEY=your_zhipuai_api_key_here
```

1. In `config.yaml`, set:

```yaml
llm:
  provider: "zhipuai"
```

On the next run, `create_llm()` will attempt to use ZhipuAI; if the SDK or key is missing, it gracefully falls back to the Mock LLM.