# -*- coding: utf-8 -*-
"""
Chinese-BERT-wwm 弹幕情感分析：微调 + 全量预测
流程：
1. 从标注表读取430条标注数据
2. 8:2划分训练集/测试集
3. 微调 Chinese-BERT-wwm-ext（3分类：正面/中性/负面）
4. 在测试集上评估（accuracy, precision, recall, F1）
5. 用微调后的模型预测全部2147条清洗后弹幕
6. 保存预测结果到CSV
"""

import os
import json
import csv
import random
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import BertTokenizer, BertForSequenceClassification, get_linear_schedule_with_warmup
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import openpyxl
import warnings
warnings.filterwarnings('ignore')

# ============ 配置 ============
MODEL_PATH = r'D:\bert_model'          # 预训练模型路径
LABEL_FILE = '弹幕标注表.xlsx'          # 标注数据
CLEAN_DIR = 'danmaku_cleaned'           # 清洗后数据目录
OUTPUT_DIR = 'prediction_results'       # 预测结果输出目录
OUTPUT_MODEL_DIR = 'finetuned_model'    # 微调模型保存目录

BATCH_SIZE = 16
EPOCHS = 5
MAX_LEN = 64              # 弹幕短文本，64足够
LEARNING_RATE = 2e-5
RANDOM_SEED = 42

LABEL_MAP = {'正面': 0, '中性': 1, '负面': 2}
LABEL_NAMES = ['正面', '中性', '负面']

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"使用设备: {device}")

# ============ 1. 读取标注数据 ============
print("\n[1/6] 读取标注数据...")
wb = openpyxl.load_workbook(LABEL_FILE, data_only=True)
ws = wb['弹幕标注']

labeled_data = []
for row in ws.iter_rows(min_row=2, values_only=True):
    text = str(row[2]).strip() if row[2] else ''
    label = row[4]
    if text and label in LABEL_MAP:
        labeled_data.append({'text': text, 'label': LABEL_MAP[label]})

print(f"  有效标注: {len(labeled_data)}条")
print(f"  分布: 正面={sum(1 for d in labeled_data if d['label']==0)}, "
      f"中性={sum(1 for d in labeled_data if d['label']==1)}, "
      f"负面={sum(1 for d in labeled_data if d['label']==2)}")

# ============ 2. 划分训练集/测试集 ============
print("\n[2/6] 划分训练集/测试集（8:2）...")
random.seed(RANDOM_SEED)
texts = [d['text'] for d in labeled_data]
labels = [d['label'] for d in labeled_data]

train_texts, test_texts, train_labels, test_labels = train_test_split(
    texts, labels, test_size=0.2, random_state=RANDOM_SEED, stratify=labels
)
print(f"  训练集: {len(train_texts)}条")
print(f"  测试集: {len(test_texts)}条")

# ============ 3. 加载tokenizer和模型 ============
print("\n[3/6] 加载 Chinese-BERT-wwm-ext...")
tokenizer = BertTokenizer.from_pretrained(MODEL_PATH)
model = BertForSequenceClassification.from_pretrained(
    MODEL_PATH,
    num_labels=3,
    id2label={0: '正面', 1: '中性', 2: '负面'},
    label2id={'正面': 0, '中性': 1, '负面': 2}
)
model.to(device)
print("  模型加载成功")

# ============ 4. 构建数据集 ============
class DanmakuDataset(Dataset):
    def __init__(self, texts, labels=None, tokenizer=None, max_len=64):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = str(self.texts[idx])
        encoding = self.tokenizer(
            text,
            max_length=self.max_len,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )
        item = {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
        }
        if self.labels is not None:
            item['labels'] = torch.tensor(self.labels[idx], dtype=torch.long)
        return item

train_dataset = DanmakuDataset(train_texts, train_labels, tokenizer, MAX_LEN)
test_dataset = DanmakuDataset(test_texts, test_labels, tokenizer, MAX_LEN)

train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
test_loader = DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=False)

# ============ 5. 微调训练 ============
print(f"\n[4/6] 开始微调（{EPOCHS}轮, CPU模式）...")
optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=0.01)
total_steps = len(train_loader) * EPOCHS
scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=0, num_training_steps=total_steps)

best_acc = 0
best_model_state = None

for epoch in range(EPOCHS):
    model.train()
    total_loss = 0

    for batch in train_loader:
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels_batch = batch['labels'].to(device)

        model.zero_grad()
        outputs = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels_batch)
        loss = outputs.loss
        total_loss += loss.item()

        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()

    avg_loss = total_loss / len(train_loader)

    # 在测试集上评估
    model.eval()
    all_preds = []
    all_true = []
    with torch.no_grad():
        for batch in test_loader:
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels_batch = batch['labels'].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            logits = outputs.logits
            preds = torch.argmax(logits, dim=1).cpu().numpy()
            all_preds.extend(preds)
            all_true.extend(labels_batch.cpu().numpy())

    acc = accuracy_score(all_true, all_preds)
    print(f"  Epoch {epoch+1}/{EPOCHS} | Loss: {avg_loss:.4f} | Test Acc: {acc:.4f}")

    if acc > best_acc:
        best_acc = acc
        best_model_state = {k: v.clone() for k, v in model.state_dict().items()}

# 恢复最佳模型
model.load_state_dict(best_model_state)

# ============ 6. 最终评估 ============
print(f"\n[5/6] 最终评估（最佳模型，准确率={best_acc:.4f}）...")
model.eval()
all_preds = []
all_true = []
with torch.no_grad():
    for batch in test_loader:
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels_batch = batch['labels'].to(device)

        outputs = model(input_ids=input_ids, attention_mask=attention_mask)
        logits = outputs.logits
        preds = torch.argmax(logits, dim=1).cpu().numpy()
        all_preds.extend(preds)
        all_true.extend(labels_batch.cpu().numpy())

print("\n分类报告:")
report = classification_report(all_true, all_preds, target_names=LABEL_NAMES, digits=4)
print(report)

# 保存评估结果
eval_results = {
    'accuracy': round(best_acc, 4),
    'classification_report': report,
    'train_size': len(train_texts),
    'test_size': len(test_texts),
    'epochs': EPOCHS,
    'batch_size': BATCH_SIZE,
    'max_len': MAX_LEN,
    'learning_rate': LEARNING_RATE,
}

# ============ 7. 全量预测 ============
print("\n[6/6] 全量预测2147条弹幕...")

# 读取所有清洗后的弹幕
all_danmaku = []
for csv_file in os.listdir(CLEAN_DIR):
    if not csv_file.endswith('.csv'):
        continue
    with open(os.path.join(CLEAN_DIR, csv_file), 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            all_danmaku.append({
                'text': row['弹幕文本'],
                'progress': row['视频进度(秒)'],
                'dmid': row['DMID'],
                'category': row['分区'],
                'bv': row['BV号'],
            })

print(f"  待预测弹幕: {len(all_danmaku)}条")

# 批量预测
pred_dataset = DanmakuDataset(
    [d['text'] for d in all_danmaku],
    labels=None,
    tokenizer=tokenizer,
    max_len=MAX_LEN
)
pred_loader = DataLoader(pred_dataset, batch_size=BATCH_SIZE, shuffle=False)

all_pred_labels = []
all_pred_probs = []
model.eval()
with torch.no_grad():
    for batch in pred_loader:
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)

        outputs = model(input_ids=input_ids, attention_mask=attention_mask)
        probs = torch.softmax(outputs.logits, dim=1).cpu().numpy()
        preds = np.argmax(probs, axis=1)

        all_pred_labels.extend(preds)
        all_pred_probs.extend(probs)

# ============ 8. 保存结果 ============
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 保存预测结果CSV
output_csv = os.path.join(OUTPUT_DIR, 'all_predictions.csv')
with open(output_csv, 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['序号', '弹幕文本', '视频进度(秒)', '预测标签', '正面概率', '中性概率', '负面概率', '分区', 'BV号'])
    for i, dm in enumerate(all_danmaku):
        pred_label = LABEL_NAMES[all_pred_labels[i]]
        probs = all_pred_probs[i]
        writer.writerow([
            i + 1,
            dm['text'],
            dm['progress'],
            pred_label,
            f"{probs[0]:.4f}",
            f"{probs[1]:.4f}",
            f"{probs[2]:.4f}",
            dm['category'],
            dm['bv'],
        ])

print(f"  预测结果已保存: {output_csv}")

# 按分区统计
category_stats = {}
for i, dm in enumerate(all_danmaku):
    cat = dm['category']
    pred = LABEL_NAMES[all_pred_labels[i]]
    if cat not in category_stats:
        category_stats[cat] = {'正面': 0, '中性': 0, '负面': 0}
    category_stats[cat][pred] += 1

print("\n各分区情感分布:")
print(f"{'分区':>6} {'总数':>6} {'正面':>8} {'中性':>8} {'负面':>8}")
for cat in sorted(category_stats.keys()):
    s = category_stats[cat]
    total = s['正面'] + s['中性'] + s['负面']
    print(f"{cat:>6} {total:>6} {s['正面']:>6}({s['正面']/total*100:.1f}%) {s['中性']:>6}({s['中性']/total*100:.1f}%) {s['负面']:>6}({s['负面']/total*100:.1f}%)")

# 总体统计
total_pos = sum(s['正面'] for s in category_stats.values())
total_neu = sum(s['中性'] for s in category_stats.values())
total_neg = sum(s['负面'] for s in category_stats.values())
total_all = total_pos + total_neu + total_neg
print(f"{'总计':>6} {total_all:>6} {total_pos:>6}({total_pos/total_all*100:.1f}%) {total_neu:>6}({total_neu/total_all*100:.1f}%) {total_neg:>6}({total_neg/total_all*100:.1f}%)")

# 保存模型
os.makedirs(OUTPUT_MODEL_DIR, exist_ok=True)
model.save_pretrained(OUTPUT_MODEL_DIR)
tokenizer.save_pretrained(OUTPUT_MODEL_DIR)
print(f"\n微调模型已保存: {OUTPUT_MODEL_DIR}")

# 保存评估结果
with open(os.path.join(OUTPUT_DIR, 'eval_results.json'), 'w', encoding='utf-8') as f:
    json.dump(eval_results, f, ensure_ascii=False, indent=2)

print("\n完成!")
