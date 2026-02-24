# RAG 模块部分任务开发工作总结

> 模块：GraphRAG 问答系统 —— 答案生成、大模型集成、用户界面、系统 Pipeline

---

## 一、工作概述

已完成 GraphRAG 问答系统中以下部分的设计与实现：

| 模块          | 目录                                    | 职责                                                    |
| ----------- | ------------------------------------- | ----------------------------------------------------- |
| 答案生成        | `answer_generation/`                  | 将图谱三元组转为自然语言上下文、设计 Prompt 模板、格式化输出并附加溯源               |
| 大模型集成       | `llm_integration/`                    | 接入智谱 AI GLM 大模型 API，支持多模型切换，兼容推理模型                    |
| 用户界面        | `interface/`                          | Streamlit 网页问答界面 + 命令行交互工具                            |
| 系统 Pipeline | `pipeline.py`                         | 串联所有模块的核心调度流程，定义模块间数据流转                               |
| 数据结构        | `data_models.py`                      | 定义全系统共享的数据格式（Triple、ParsedQuestion、RetrievalResult 等） |
| Mock 实现     | `mock_modules.py`                     | 为其他模块（问题理解、图谱检索）提供 Mock 替代，支持独立开发测试                   |
| 工程基础        | `.env` / `config.yaml` / `.gitignore` | 密钥隔离、配置管理、Git 安全                                      |

---

## 二、系统架构设计

### 2.1 整体流程（GraphRAG 核心）

```text
      用户提问
         │
         ▼
┌──────────────────┐
│ Step 1: 问题理解 │ ← 目前用Mock
│ · 实体识别       │
│ · 意图分类       │
│ · 年龄/约束提取  │
└────────┬─────────┘
         │ ParsedQuestion
         ▼
┌──────────────────┐
│ Step 2: 图谱检索 │ ←目前用Mock
│ · 实体链接       │
│ · Cypher子图查询 │
│ · 三元组返回     │
└────────┬─────────┘
         │ RetrievalResult (三元组列表)
         ▼
┌───────────────────┐
│ Step 3: 上下文构造│ ←已实现
│ · 三元组分组      │
│ · 关系→自然语言   │
│ · 标注来源        │
└────────┬──────────┘
         │ 自然语言上下文文本
         ▼
┌───────────────────┐
│ Step 4: Prompt构建│ ←已实现
│ · 选择意图模板    │
│ · 填充上下文      │
│ · 组装messages    │
└────────┬──────────┘
         │ messages列表
         ▼
┌──────────────────┐
│ Step 5: LLM调用  │ ←已实现
│ · 智谱AI API     │
│ · 兼容推理模型   │
│ · 错误处理       │
└────────┬─────────┘
         │ LLM原始输出
         ▼
┌───────────────────┐
│ Step 6: 答案格式化│ ←已实现
│ · 清理文本        │
│ · 评估置信度      │
│ · 附加溯源三元组  │
└────────┬──────────┘
         │ FormattedAnswer
         ▼
┌──────────────────┐
│ 用户界面展示     │ ←已实现
│ · Streamlit网页  │
│ · 命令行CLI      │
│ · 溯源可展开     │
└──────────────────┘
```

---

### 2.2 文件结构

```text
rag/
├── .env                       # 密钥文件（git仅提交模版文件）
├── .gitignore                 # git忽略规则
├── requirements.txt           # Python依赖
├── config.yaml                # 系统配置（非敏感）
├── data_models.py             # 全系统共享数据结构
├── mock_modules.py            # 其他模块的Mock实现
├── pipeline.py                # 主Pipeline（核心调度）
├── debug_llm.py               # 大模型API诊断工具
│
├── answer_generation/         # 答案生成模块
│   ├── context_builder.py     # 三元组 → 自然语言上下文
│   ├── prompt_templates.py    # Prompt模板管理（目前是6种意图）
│   └── answer_formatter.py    # 答案清理+溯源+置信度
│
├── llm_integration/           # 大模型集成模块
│   ├── base_llm.py            # LLM抽象基类
│   ├── zhipuai_llm.py         # 智谱AI API接入
│   ├── mock_llm.py            # Mock LLM（测试用）
│   └── llm_factory.py         # 工厂函数（根据配置创建LLM）
│
├── interface/                 # ★ 用户界面
│   ├── streamlit_app.py       # Streamlit网页界面
│   └── cli.py                 # 命令行交互工具
│
├── question_understanding/    # 未修改
├── graph_retrieval/           # 未修改
│
└── docs/                      # 文档
    ├── RAG模块开发总结_thx.md
    └── 对接指南_thx.md
```

---

## 三、各模块详细设计

### 3.1 数据结构设计 (`data_models.py`)

因为我开始写的时候项目库还是空的，所以我就先自行定义了四个核心数据类，作为模块间传递数据的统一契约：

| 数据类               | 用途          | 关键字段                                                  |
| ----------------- | ----------- | ----------------------------------------------------- |
| `Triple`          | 知识图谱中的一条三元组 | head, head_type, relation, tail, tail_type, source    |
| `ParsedQuestion`  | 问题理解的输出     | original_question, entities, intent, age, constraints |
| `RetrievalResult` | 图谱检索的输出     | triples, matched_entities, query_used, hop_count      |
| `FormattedAnswer` | 最终展示给用户的答案  | answer_text, source_triples, intent, confidence       |

**设计原则：**

* 使用 Python `dataclass`，轻量且易于序列化
* 每个类都提供 `to_dict()` 方法，方便 JSON 传输和前端展示
* `Triple` 额外提供 `to_text()` 方法，用于调试输出

#### 意图分类体系（`ParsedQuestion.intent`）

| 意图值            | 含义      | 触发词示例           |
| -------------- | ------- | --------------- |
| `insurability` | 能否投保    | "能买""能不能""可以投保" |
| `cost`         | 费用价格    | "多少钱""保费""收费"   |
| `coverage`     | 保障范围    | "保什么""赔付""报销"   |
| `treatment`    | 疾病治疗    | "怎么治""吃什么药"     |
| `eligibility`  | 资格条件    | "条件""要求""限制"    |
| `general`      | 通用/无法分类 | 其他情况            |

---

### 3.2 上下文构造 (`answer_generation/context_builder.py`)

**功能：**
把图谱检索返回的结构化三元组，翻译成大模型能理解的自然语言段落。

**核心设计：**

1. **关系模板映射：** 预定义了 14 种关系到自然语言的翻译模板

```python
# 例：三元组 (高血压, 常用药物, 硝苯地平)
# 模板："{head}的常用治疗药物包括{tail}"
# 输出："高血压的常用治疗药物包括硝苯地平"
```

2. **按头实体分组：** 将三元组按 head 分组，让信息更有组织

```text
【关于高血压】
  • 高血压的常用治疗药物包括硝苯地平（来源：医保目录）
  • 高血压属于心血管疾病类疾病（来源：ICD-10）

【关于平安护理险】
  • 平安护理险的年龄限制为18-65岁（来源：平安保险条款）
```

3. **截断保护：** 参数 `max_triples` 限制最多使用的三元组数量，防止上下文超出大模型的 token 限制

4. **通用兜底：** 对于未预定义的关系类型，使用通用模板

```
"{head}的「{relation}」为{tail}"
```

---

### 3.3 Prompt 模板设计 (`answer_generation/prompt_templates.py`)

**功能：**
根据用户意图，选择最合适的 Prompt 模板，将知识上下文和问题组装成大模型输入。

#### 设计思路

1. **System Prompt（所有问题共用）：**

* 设定角色："保险+医养"领域智能助手
* 五大原则：准确性、完整性、可读性、溯源性、诚实性
* 关键约束：禁止编造，信息不足时明确告知

2. **Intent-specific User Prompt（6种意图各一套）：**

| 意图           | Prompt重点               |
| ------------ | ---------------------- |
| insurability | 分析年龄范围、除外疾病、替代产品       |
| cost         | 价格范围、影响因素、性价比对比        |
| coverage     | 保障内容、除外责任、产品对比         |
| treatment    | 药物方案、检查项目、医保信息 + 提醒遵医嘱 |
| eligibility  | 年龄要求、健康条件、其他限制         |
| general      | 全面回答 + 指出信息缺失部分        |

输出格式：标准 `messages` 列表

```python
[{"role": "system", ...}, {"role": "user", ...}]
```

兼容智谱AI、OpenAI 等所有主流 API。

---

### 3.4 答案格式化 (`answer_generation/answer_formatter.py`)

**功能：** 后处理大模型的原始输出，附加元信息。

#### 处理流程

1. 文本清理：去除首尾空白、压缩连续空行、处理 None/空值

2. 置信度评估（简单规则）：

   * 无三元组支撑 → low
   * 回答中含 "暂无法""信息不足" 等 → low
   * 有 3+ 条三元组支撑 → high
   * 其他 → medium

3. 溯源打包：将引用的三元组转为字典列表，嵌入 `FormattedAnswer`

4. 命令行溯源格式化：提供 `format_sources_text()` 方法，输出带编号和来源标签的文本

---

### 3.5 大模型集成 (`llm_integration/`)

#### 架构设计

```text
BaseLLM（抽象基类）
  ├── ZhipuAILLM（智谱AI，生产环境使用）
  ├── MockLLM（无API时测试用）
  └── llm_factory.create_llm()（工厂函数，根据配置自动选择）
```

#### 智谱AI接入 (`zhipuai_llm.py`) 关键设计

* 推理模型兼容：自动识别 `glm-4.7` 等推理模型
* 推理模型不支持 temperature 参数 → 自动跳过
* 推理模型的 max_tokens 包含思考+回答 → 自动调大到4096
* 推理模型可能 content 为空 → 从 reasoning_content 提取结论

#### 多层内容提取（`_extract_content`）

* 优先读 `message.content`
* content 为空时读 `reasoning_content`
* 从推理文本中自动提取结论段落

#### 错误处理

API异常不会导致程序崩溃，返回错误信息字符串。

#### 工厂函数 (`llm_factory.py`)

* 自动加载 `.env` 环境变量
* API Key 优先级：`.env` > `config.yaml`
* 缺少 API Key 时自动降级为 `MockLLM`，不中断流程

---

### 3.6 用户界面 (`interface/`)

#### Streamlit 网页界面 (`streamlit_app.py`)

**功能清单：**

* ✅ 聊天式对话界面（`st.chat_message`）
* ✅ 对话历史记录（`st.session_state`）
* ✅ 侧边栏示例问题（一键点击提问）
* ✅ 答案溯源展示（可折叠 `st.expander`，显示引用的三元组）
* ✅ 置信度标签（🟢高 / 🟡中 / 🔴低）
* ✅ 意图和匹配实体标签
* ✅ 调试信息开关（可查看完整的 JSON 结构）
* ✅ Pipeline 单例缓存（`@st.cache_resource`，避免重复初始化）

**启动方式：**

```bash
streamlit run interface/streamlit_app.py
```

---

#### 命令行工具 (`cli.py`)

**功能清单：**

* ✅ 交互式对话循环
* ✅ 每次回答显示溯源信息
* ✅ 输入 `test` 运行预设测试
* ✅ 输入 `quit` / `exit` / `q` 退出

**启动方式：**

```bash
python interface/cli.py
```

---

### 3.7 主 Pipeline (`pipeline.py`)

**设计亮点：**

* 模块解耦：各模块通过数据结构（ParsedQuestion → RetrievalResult → FormattedAnswer）连接，互不依赖具体实现
* Mock替换机制：尚未实现的模块使用 Mock，对接时只需改 `__init__` 中两行
* verbose 模式：传入 `verbose=True` 可打印每个步骤的中间结果，方便调试和演示
* 双接口：`answer()` 返回完整结构体，`answer_simple()` 直接返回文本

---

### 3.8 Mock 模块 (`mock_modules.py`)

因为问题理解和图谱检索还没做，所以先用的Mock 实现，覆盖以下测试场景：

| 实体  | 包含的Mock数据                       |
| --- | ------------------------------- |
| 高血压 | 常用药物、疾病分类、检查项目、2款护理险的承保/除外/年龄信息 |
| 糖尿病 | 常用药物、并发症、疾病分类、医疗险除外、防癌险可保       |
| 护理险 | 2款产品的保障内容、年保费、年龄限制              |
| 养老院 | 2家机构的服务内容、收费、入住条件               |
| 重疾险 | 3种保障疾病                          |

**Mock问题理解支持：**

* 20种疾病、11种保险产品、8种养老服务的关键词识别
* 5种意图分类
* 正则提取年龄
* 性别约束提取

---

### 3.9 工程配置

#### 密钥管理

* `.env` 文件存放 ZHIPUAI_API_KEY 和 NEO4J_URI/USER/PASSWORD
* `.gitignore` 排除 `.env`，防止密钥泄露
* `config.yaml` 只放非敏感配置（模型名、温度参数等）
* 代码中优先读环境变量，再读配置文件

#### 依赖管理

```text
streamlit     → 网页界面
zhipuai       → 智谱AI API
pyyaml        → 配置文件解析
python-dotenv → .env 加载
neo4j         → Neo4j 数据库（图谱检索用）
```

---

## 四、遇到的问题与解决

### 问题1：glm-4.7 推理模型返回空内容

**现象：**
Pipeline 所有步骤正常执行，但最终回答为 "未能生成有效回答"。

**原因：**
glm-4.7 是推理模型，刚开始按照以往经验设置的`max_tokens=1024` 同时限制思考过程和最终回答。复杂 Prompt 的思考过程消耗完所有 token，导致 `content` 字段为空字符串。

**解决：**

* 在 `zhipuai_llm.py` 中增加推理模型识别逻辑
* 推理模型自动跳过 temperature 参数
* max_tokens < 2048 时自动调大到 4096
* content 为空时从 reasoning_content 提取结论
* 推荐使用 glm-4-flash（免费、稳定、无此问题）

---

## 五、测试验证

### 测试方式

```bash
# 方式1：自动测试4个预设问题
cd rag && python pipeline.py

# 方式2：命令行交互
cd rag && python interface/cli.py

# 方式3：网页界面
cd rag && streamlit run interface/streamlit_app.py
```

---

### 测试覆盖的典型问题

| 问题              | 意图           | 匹配实体    | 预期行为               |
| --------------- | ------------ | ------- | ------------------ |
| "70岁高血压能买护理险吗？" | insurability | 高血压、护理险 | 分析年龄范围+除外疾病，给出投保建议 |
| "糖尿病可以买什么保险？"   | insurability | 糖尿病     | 列出可承保和除外的产品        |
| "养老院一个月多少钱？"    | cost         | 养老院     | 给出收费范围和机构信息        |
| "高血压吃什么药？"      | treatment    | 高血压     | 列出常用药物+提醒遵医嘱       |
| "重疾险保哪些疾病？"     | coverage     | 重疾险     | 列出保障的疾病种类          |

---

## 六、后续工作

* 与其他模块的对接：等「问题理解」和「图谱检索」完成后，在 `pipeline.py` 中替换 Mock 为真实实现
* 对比实验：实现“纯 LLM 回答 vs GraphRAG 回答”的对比（课题加分项）
* 多轮对话：试一下支持上下文追问（如 "那如果我有肾病呢？"），不过最近有点忙，之前都是langchain框架实现的，然后这会儿为了赶时间就手搓了，没用框架，所以可能腾不出来时间（）
* 答案溯源高亮：在网页界面中点击答案可高亮对应的三元组（课题加分项）