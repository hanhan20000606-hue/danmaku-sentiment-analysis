# Danmaku Sentiment Analysis with Chinese-BERT-wwm

Code repository for the Master's thesis: **"Аналитика аудитории с помощью нейросетей в китайских социальных медиа"** (Audience Analytics Using Neural Networks in Chinese Social Media).

St. Petersburg State University, School of Journalism and Mass Communications, 2026.

## Overview

This repository contains the complete pipeline for Bilibili (B站) danmaku sentiment analysis using the **Chinese-BERT-wwm-ext** pre-trained model:

1. **Data Collection** — Fetch danmaku from Bilibili videos via the XML API
2. **Data Cleaning** — Deduplication, spam removal, traditional-to-simplified Chinese conversion
3. **Annotation** — Generate stratified random samples for manual labeling
4. **Model Fine-tuning** — Fine-tune Chinese-BERT-wwm-ext on 430 annotated danmaku samples (3-class sentiment: positive / neutral / negative)
5. **Statistical Analysis** — Hypothesis testing (H1: model effectiveness, H2: temporal sentiment evolution, H3: cross-category sentiment differences)
6. **Appendix Generation** — Auto-generate thesis appendices (annotation examples, video metadata, training parameters)

## Files

| File | Description |
|------|-------------|
| `fetch_danmaku_v3.py` | Collect danmaku from Bilibili videos via XML API |
| `clean_danmaku.py` | Clean raw danmaku: dedup, remove spam, normalize text |
| `generate_labels.py` | Generate stratified sampling table for manual annotation |
| `finetune_predict.py` | Fine-tune Chinese-BERT-wwm-ext and predict on full dataset |
| `statistical_analysis.py` | Hypothesis testing and visualization for thesis |
| `generate_appendix.py` | Auto-generate thesis appendices (DOCX) |

## Model

- **Model**: [hfl/chinese-bert-wwm-ext](https://huggingface.co/hfl/chinese-bert-wwm-ext)
- **Reference**: Cui, Y., Che, W., Liu, T., Qin, B., & Yang, Z. (2021). Pre-Training with Whole Word Masking for Chinese BERT. *IEEE Transactions on Audio, Speech and Language Processing*, 29, 3504–3514. DOI: [10.1109/TASLP.2021.3124365](https://doi.org/10.1109/TASLP.2021.3124365)

## Dataset

- **Platform**: Bilibili (bilibili.com)
- **Videos**: 6 videos across 3 categories (Technology, Entertainment, Automobile)
- **Raw danmaku**: 8,104
- **Cleaned danmaku**: 6,314
- **Annotated samples**: 430 (positive: 78, neutral: 133, negative: 219)

## Results

- **Test accuracy**: 70.93% (weighted F1 = 0.70)
- **Cross-category difference**: χ² = 186.63, p < 0.001, Cramer's V = 0.21
- **Temporal evolution**: Spearman ρ = -0.72, p = 0.019 (Entertainment category)

## Requirements

```bash
pip install torch transformers openpyxl scikit-learn pandas scipy matplotlib seaborn python-docx
```

## License

This repository is part of an academic thesis. Please cite appropriately if you use the code.
