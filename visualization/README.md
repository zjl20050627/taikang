# 图谱可视化

此目录用于存放图谱可视化相关的配置和脚本。

## 功能模块

- `app.py`: Streamlit 可视化应用主程序
- `graph_viz.py`: 基于 PyVis 的图谱渲染逻辑

## 使用说明

### 1. 安装依赖

确保已安装 `requirements.txt` 中的依赖：

```bash
pip install -r requirements.txt
```

### 2. 启动应用

在项目根目录下运行：

```bash
streamlit run visualization/app.py
```

### 3. 功能

- **实体搜索**: 支持通过名称搜索疾病、药品等实体
- **图谱浏览**: 查看选定实体的关联子图（直接邻居）
- **属性查看**: 显示实体的详细属性信息