# Chinese-language AI Preference Analysis

中文网络评论中的国内外 AI 偏好探索 | Python · PySpark · scikit-learn

本项目探索所收集中文评论中对国内外 AI 工具的提及、讨论主题和潜在偏好。现有代码包括 MongoDB/CSV 导入、清洗、jieba 分词、关键词规则标签、统计图，以及探索性的分类、LDA 和聚类。

**研究原型，不是已验证的人群偏好调查。**中文评论不等于中国用户的代表性样本；品牌提及不等于支持，支持国外产品也不等于负面情感。仓库没有数据集和本次可核验的运行结果，因此不展示样本数、准确率或研究结论。

## 项目结构

- [AI分析项目](ai-preference-analysis/README.md)：流程、依赖、数据要求与限制。
- [现有分析代码](ai-preference-analysis/legacy/)：整理后的历史 Colab 导出脚本。
- [方法问题与改进](ai-preference-analysis/docs/METHODOLOGY.md)：标签、中文特征及评估问题。
- [复现清单](ai-preference-analysis/docs/REPRODUCIBILITY.md)：缺少什么、怎样继续。

投票系统是另一个 COMP3500 项目，当前位于 [独立开发分支](https://github.com/qiuliyu1224-jpg/project/tree/codex/voting-increment-1/voting-system)，尚未合入本主分支。
