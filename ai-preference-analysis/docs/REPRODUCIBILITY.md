# 复现状态 / Reproducibility

## 环境

代码原为Colab交互导出。依赖Python、兼容的Java和PySpark环境及中文字体，其他导入见requirements.txt。尚无经过实测的版本组合；不能承诺一次安装即可端到端运行。

## 数据

输入CSV至少应有“评论内容”列。原脚本也接受已有comment列，但缺列时会退回第一列，这有误读风险，后续应改为明确报错。CSV路径当前写为/content/comment.csv，需要改为自己的本地路径。MongoDB配置可选，用环境变量MONGODB_URI；未配置时走CSV。没有在本轮访问MongoDB。

## 运行顺序与边界

1. 准备去标识化CSV及依赖，在隔离的工作目录/Notebook中工作，避免生成文件覆盖现有结果。
2. 先审阅preprocessing_colab.py；它会执行读取、绘图、导出并停止Spark，不是可安全import的模块。
3. ml_extension.py依赖df_final、F、STOPWORDS、pd、plt、sns、chinese_font等共享变量。不可直接python单独运行；上游spark.stop()也需要先重构，才可继续进行Spark到Pandas转换。
4. 完成入口、路径、数据契约和方法修复后再重跑，记录版本、命令、样本数量与日志。

## 代码预期生成的文件（当前仓库未提供验证结果）

基础：wordcloud.png、statistics.png、classified_comments.csv、analysis_report.txt及分类统计CSV。

扩展：model_comparison.png、sentiment_confusion_matrix.png、topic_analysis.png、machine_learning_results.csv、topics_keywords.csv、模型pkl和machine_learning_report.txt。不要从文件名推断这些结果已经存在或有效。

## 本轮验证

仅进行Python语法编译检查、导入依赖清点和明文MongoDB凭据模式检查。没有真实数据，没有运行Spark、联网数据库、训练模型或生成研究图表。
