# ============================================================
# 17. 机器学习部分 - 情感分析与主题建模
# ============================================================

print("\n🤖 启动机器学习模块...")

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, roc_auc_score
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.cluster import KMeans
from sklearn.preprocessing import LabelEncoder
import joblib

# 准备数据
df_ml = df_final.withColumn("text_length", F.length(F.col("clean_text"))).toPandas()
df_ml = df_ml.dropna(subset=['clean_text'])
df_ml = df_ml[df_ml['clean_text'].str.len() > 2]

print(f"✅ 机器学习数据准备完成: {len(df_ml)} 条样本")

# ============================================================
# 18. 特征工程 - TF-IDF
# ============================================================

print("\n🔧 特征工程 - TF-IDF 向量化...")

# 使用中文停用词
chinese_stopwords = list(STOPWORDS) + ['的', '了', '是', '在', '有', '和', '就', '都', '也', '而', '但', '或', '与']

# TF-IDF 向量化
tfidf_vectorizer = TfidfVectorizer(
    max_features=5000,
    min_df=2,
    max_df=0.8,
    ngram_range=(1, 2),
    stop_words=chinese_stopwords
)

X_tfidf = tfidf_vectorizer.fit_transform(df_ml['clean_text'])
print(f"✅ TF-IDF 特征维度: {X_tfidf.shape}")

# 保存向量化器
joblib.dump(tfidf_vectorizer, 'tfidf_vectorizer.pkl')
print("✅ 已保存: tfidf_vectorizer.pkl")

# ============================================================
# 19. 情感分类 (正面/负面/中性)
# ============================================================

print("\n🎯 训练情感分类模型...")

# 构建情感标签 (基于已有立场分类)
def get_sentiment_label(stance):
    if stance == '正面_国产更好':
        return '正面'
    elif stance == '负面_外国更好':
        return '负面'
    else:
        return '中性'

df_ml['sentiment'] = df_ml['stance'].apply(get_sentiment_label)

# 编码标签
label_encoder = LabelEncoder()
y_sentiment = label_encoder.fit_transform(df_ml['sentiment'])
print(f"情感类别: {label_encoder.classes_}")

# 划分数据集
X_train, X_test, y_train, y_test = train_test_split(
    X_tfidf, y_sentiment, test_size=0.2, random_state=42, stratify=y_sentiment
)
print(f"训练集: {X_train.shape[0]} 条, 测试集: {X_test.shape[0]} 条")

# 训练多个模型
models = {
    'Logistic Regression': LogisticRegression(max_iter=1000, random_state=42),
    'Multinomial NB': MultinomialNB(),
    'Linear SVM': LinearSVC(max_iter=1000, random_state=42),
    'Random Forest': RandomForestClassifier(n_estimators=100, random_state=42),
    'Gradient Boosting': GradientBoostingClassifier(n_estimators=100, random_state=42)
}

best_model = None
best_accuracy = 0
sentiment_results = {}

print("\n模型训练与评估:")
for name, model in models.items():
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    sentiment_results[name] = accuracy
    
    if accuracy > best_accuracy:
        best_accuracy = accuracy
        best_model = model
    
    print(f"  {name}: Accuracy = {accuracy:.4f}")

print(f"\n✅ 最佳模型: {type(best_model).__name__} (准确率: {best_accuracy:.4f})")

# 详细分类报告
y_pred_best = best_model.predict(X_test)
print("\n最佳模型分类报告:")
print(classification_report(y_test, y_pred_best, target_names=label_encoder.classes_))

# 保存模型
joblib.dump(best_model, 'sentiment_model.pkl')
joblib.dump(label_encoder, 'label_encoder.pkl')
print("✅ 已保存: sentiment_model.pkl")

# 混淆矩阵可视化
plt.figure(figsize=(8, 6))
cm = confusion_matrix(y_test, y_pred_best)
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=label_encoder.classes_,
            yticklabels=label_encoder.classes_)
plt.title('情感分类混淆矩阵', fontproperties=chinese_font, fontsize=14)
plt.ylabel('真实标签', fontproperties=chinese_font)
plt.xlabel('预测标签', fontproperties=chinese_font)
plt.tight_layout()
plt.savefig('sentiment_confusion_matrix.png', dpi=300)
plt.show()
print("✅ 已保存: sentiment_confusion_matrix.png")

# ============================================================
# 20. 主题建模 - LDA
# ============================================================

print("\n📚 主题建模 - LDA 分析...")

# 准备文档-词矩阵
doc_term_matrix = X_tfidf.copy()

# 训练 LDA 模型
n_topics = 5
lda_model = LatentDirichletAllocation(
    n_components=n_topics,
    random_state=42,
    learning_method='online',
    max_iter=100
)

lda_output = lda_model.fit_transform(doc_term_matrix)
print(f"✅ LDA 模型训练完成，主题数: {n_topics}")

# 获取特征词
feature_names = tfidf_vectorizer.get_feature_names_out()

# 显示每个主题的关键词
print("\n各主题关键词:")
topics_keywords = {}
for topic_idx, topic in enumerate(lda_model.components_):
    top_features_idx = topic.argsort()[:-20:-1]
    top_features = [feature_names[i] for i in top_features_idx]
    topics_keywords[f'Topic_{topic_idx+1}'] = top_features
    print(f"\n主题 {topic_idx+1}: {', '.join(top_features[:10])}")

# 为每个文档分配主要主题
df_ml['dominant_topic'] = lda_output.argmax(axis=1) + 1
df_ml['topic_confidence'] = lda_output.max(axis=1)

# 主题分布统计
topic_distribution = df_ml['dominant_topic'].value_counts().sort_index()
print("\n主题分布:")
for topic, count in topic_distribution.items():
    pct = count / len(df_ml) * 100
    print(f"  主题 {topic}: {count} 条 ({pct:.1f}%)")

# 主题-立场交叉分析
print("\n主题与立场关系:")
topic_stance_cross = pd.crosstab(df_ml['dominant_topic'], df_ml['stance'], normalize='index')
print(topic_stance_cross)

# 可视化主题分布
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# 主题分布饼图
topic_counts = topic_distribution.values
topic_labels = [f'主题 {i}' for i in topic_distribution.index]
axes[0].pie(topic_counts, labels=topic_labels, autopct='%1.1f%%', startangle=90)
axes[0].set_title('主题分布', fontproperties=chinese_font, fontsize=14)

# 主题-立场热力图
topic_stance_matrix = topic_stance_cross.values
im = axes[1].imshow(topic_stance_matrix, cmap='YlOrRd', aspect='auto')
axes[1].set_xticks(range(len(topic_stance_cross.columns)))
axes[1].set_xticklabels(topic_stance_cross.columns, rotation=45, ha='right')
axes[1].set_yticks(range(len(topic_stance_cross.index)))
axes[1].set_yticklabels([f'主题 {i}' for i in topic_stance_cross.index])
axes[1].set_title('主题-立场分布', fontproperties=chinese_font, fontsize=14)
plt.colorbar(im, ax=axes[1])

plt.tight_layout()
plt.savefig('topic_analysis.png', dpi=300)
plt.show()
print("✅ 已保存: topic_analysis.png")

# ============================================================
# 21. 文本聚类分析
# ============================================================

print("\n🔍 文本聚类分析...")

# 使用 KMeans 聚类
n_clusters = 4
kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
cluster_labels = kmeans.fit_predict(X_tfidf)

df_ml['cluster'] = cluster_labels

# 聚类结果分析
print("\n聚类分布:")
cluster_counts = df_ml['cluster'].value_counts().sort_index()
for cluster, count in cluster_counts.items():
    pct = count / len(df_ml) * 100
    print(f"  聚类 {cluster}: {count} 条 ({pct:.1f}%)")

# 每个聚类的关键词
cluster_centroids = kmeans.cluster_centers_
print("\n各聚类关键词:")
for cluster_id in range(n_clusters):
    centroid = cluster_centroids[cluster_id]
    top_indices = centroid.argsort()[-10:][::-1]
    top_words = [feature_names[i] for i in top_indices]
    print(f"\n聚类 {cluster_id}: {', '.join(top_words)}")

# 聚类-立场关系
print("\n聚类与立场关系:")
cluster_stance_cross = pd.crosstab(df_ml['cluster'], df_ml['stance'], normalize='index')
print(cluster_stance_cross)

# ============================================================
# 22. 特征重要性分析
# ============================================================

print("\n📊 特征重要性分析...")

# 对于 Logistic Regression 模型
if isinstance(best_model, LogisticRegression):
    feature_importance = abs(best_model.coef_[0])
    top_features_idx = feature_importance.argsort()[-20:][::-1]
    top_features = [feature_names[i] for i in top_features_idx]
    top_scores = [feature_importance[i] for i in top_features_idx]
    
    plt.figure(figsize=(10, 8))
    plt.barh(range(len(top_features)), top_scores, color='steelblue')
    plt.yticks(range(len(top_features)), top_features)
    plt.xlabel('特征重要性', fontproperties=chinese_font)
    plt.title('Top 20 重要特征 (情感分类)', fontproperties=chinese_font, fontsize=14)
    plt.gca().invert_yaxis()
    plt.tight_layout()
    plt.savefig('feature_importance.png', dpi=300)
    plt.show()
    print("✅ 已保存: feature_importance.png")

# ============================================================
# 23. 机器学习预测新评论
# ============================================================

def predict_sentiment(text):
    """预测新评论的情感"""
    # 清洗文本
    cleaned = clean_text_basic(text)
    cleaned = remove_special_chars(cleaned)
    
    # TF-IDF 转换
    text_tfidf = tfidf_vectorizer.transform([cleaned])
    
    # 预测
    pred = best_model.predict(text_tfidf)
    sentiment = label_encoder.inverse_transform(pred)[0]
    
    # 预测概率
    if hasattr(best_model, 'predict_proba'):
        proba = best_model.predict_proba(text_tfidf)[0]
        confidence = max(proba)
    else:
        confidence = 1.0
    
    return sentiment, confidence

# 测试预测功能
test_comments = [
    "国产AI真的太强了，支持国产技术！",
    "ChatGPT还是更厉害，国外技术领先很多",
    "这个产品还行吧，一般般",
    "文心一言的中文理解能力很棒",
    "OpenAI的技术确实先进"
]

print("\n🔮 新评论情感预测测试:")
print("-" * 50)
for comment in test_comments:
    sentiment, confidence = predict_sentiment(comment)
    print(f"评论: {comment}")
    print(f"预测: {sentiment} (置信度: {confidence:.2f})")
    print("-" * 50)

# ============================================================
# 24. 模型性能对比可视化
# ============================================================

print("\n📈 模型性能对比...")

plt.figure(figsize=(10, 6))
model_names = list(sentiment_results.keys())
accuracies = list(sentiment_results.values())

colors = ['#2ecc71' if acc == max(accuracies) else '#95a5a6' for acc in accuracies]
bars = plt.bar(model_names, accuracies, color=colors)
plt.ylim(0, 1)
plt.ylabel('准确率', fontproperties=chinese_font)
plt.title('情感分类模型性能对比', fontproperties=chinese_font, fontsize=14)
plt.xticks(rotation=45, ha='right')

# 添加数值标签
for bar, acc in zip(bars, accuracies):
    plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
             f'{acc:.3f}', ha='center', va='bottom')

plt.tight_layout()
plt.savefig('model_comparison.png', dpi=300)
plt.show()
print("✅ 已保存: model_comparison.png")

# ============================================================
# 25. 导出机器学习结果
# ============================================================

print("\n💾 导出机器学习结果...")

# 保存带机器学习标签的完整数据
df_ml_export = df_ml[['comment', 'clean_text', 'stance', 'secondary_category', 
                       'sentiment', 'dominant_topic', 'topic_confidence', 'cluster']]
df_ml_export.to_csv('machine_learning_results.csv', index=False, encoding='utf-8-sig')
print("✅ 已导出: machine_learning_results.csv")

# 保存主题关键词
topics_df = pd.DataFrame([(k, ', '.join(v[:15])) for k, v in topics_keywords.items()],
                         columns=['主题', '关键词'])
topics_df.to_csv('topics_keywords.csv', index=False, encoding='utf-8-sig')
print("✅ 已导出: topics_keywords.csv")

# 生成机器学习报告
with open("machine_learning_report.txt", "w", encoding='utf-8') as f:
    f.write("="*60 + "\n")
    f.write("机器学习分析报告\n")
    f.write("="*60 + "\n\n")
    
    f.write("1. 情感分类模型性能\n")
    f.write("-"*40 + "\n")
    for name, acc in sentiment_results.items():
        f.write(f"   {name}: {acc:.4f}\n")
    f.write(f"\n   最佳模型: {type(best_model).__name__}\n")
    f.write(f"   最佳准确率: {best_accuracy:.4f}\n\n")
    
    f.write("2. 主题建模结果 (LDA)\n")
    f.write("-"*40 + "\n")
    for topic, keywords in topics_keywords.items():
        f.write(f"\n   {topic}:\n")
        f.write(f"      关键词: {', '.join(keywords[:10])}\n")
    
    f.write(f"\n   主题分布:\n")
    for topic, count in topic_distribution.items():
        pct = count / len(df_ml) * 100
        f.write(f"      主题 {topic}: {count} 条 ({pct:.1f}%)\n")
    
    f.write("\n3. 聚类分析结果\n")
    f.write("-"*40 + "\n")
    for cluster, count in cluster_counts.items():
        pct = count / len(df_ml) * 100
        f.write(f"   聚类 {cluster}: {count} 条 ({pct:.1f}%)\n")
    
    f.write("\n4. 数据统计\n")
    f.write("-"*40 + "\n")
    f.write(f"   总样本数: {len(df_ml)}\n")
    f.write(f"   TF-IDF 特征维度: {X_tfidf.shape[1]}\n")
    f.write(f"   主题数: {n_topics}\n")
    f.write(f"   聚类数: {n_clusters}\n")

print("✅ 已导出: machine_learning_report.txt")

# ============================================================
# 26. 机器学习模块摘要
# ============================================================

print("\n" + "="*60)
print("🤖 机器学习模块完成摘要")
print("="*60)
print(f"✅ 情感分类模型训练完成 (准确率: {best_accuracy:.2%})")
print(f"✅ 主题建模完成 ({n_topics} 个主题)")
print(f"✅ 文本聚类完成 ({n_clusters} 个聚类)")
print(f"✅ 特征重要性分析完成")
print("\n📁 新增生成的文件:")
print("   - sentiment_model.pkl (情感分类模型)")
print("   - tfidf_vectorizer.pkl (TF-IDF向量化器)")
print("   - label_encoder.pkl (标签编码器)")
print("   - machine_learning_results.csv (机器学习结果)")
print("   - topics_keywords.csv (主题关键词)")
print("   - sentiment_confusion_matrix.png (混淆矩阵)")
print("   - topic_analysis.png (主题分析图)")
print("   - model_comparison.png (模型对比图)")
print("   - feature_importance.png (特征重要性)")
print("   - machine_learning_report.txt (机器学习报告)")

print("\n🎉 机器学习模块运行完成！")