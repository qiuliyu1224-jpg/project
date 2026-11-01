# 国内外 AI 偏好探索 / AI Preference Analysis

## 目标

探索所收集中文评论如何提及国内外AI，以及讨论技术性能、使用体验、中文适配、数据安全等方面。用户提供的项目目标是“中国用户对国内外AI使用偏好”；当前代码只能支撑评论层面的探索，不能直接推断真实使用行为或整个中国用户群体。

## 现有流程

1. 从MongoDB读取评论；未配置连接时尝试CSV。
2. 基础清洗：移除HTML、URL、部分表情及特殊字符，过滤过短文本。
3. jieba分词与停用词过滤，统计词频。
4. 关键词规则生成国内/国外相关标签和讨论类别。
5. 导出词云、图表、分类CSV和文字报告。
6. 扩展脚本尝试TF-IDF、五种分类器、LDA主题和KMeans聚类。

这些是**代码中包含的步骤**，不是此次重新运行验证过的结果。现有基础脚本用PySpark清洗和统计；ML脚本转Pandas并使用scikit-learn，不是分布式Spark ML训练。

## 文件

| 文件 | 用途与状态 |
|---|---|
| legacy/preprocessing_colab.py | 原spark分析.py，保留原分析逻辑；已移除硬编码凭据和私有notebook链接，将两条notebook shell命令改成注释 |
| legacy/ml_extension.py | 原spark_ml.py，依赖上游共享变量，不可独立执行 |
| requirements.txt | 根据代码导入整理的依赖清单，未锁定/未实测兼容版本 |
| .env.example | MongoDB配置示例，不含真实连接信息 |
| docs/METHODOLOGY.md | 研究方法局限和改进顺序 |
| docs/REPRODUCIBILITY.md | 环境、输入、输出和运行边界 |
| data/README.md | 数据契约和隐私要求，无真实数据 |

## 下一步

先补数据来源、采样范围和人工标注样本，再重构可复现的命令行入口；随后修正特征与评估。不要把整理仓库误写为已完成算法修复。

## 凭据处理

MongoDB连接从MONGODB_URI环境变量读取。旧版公开代码曾含凭据，账号拥有者应更换该数据库密码/撤销旧凭据。此分支只修复当前文件，不会删除旧提交。不要上传原始连接信息、个人评论数据或私有notebook访问链接。
