# -*- coding: utf-8 -*-
"""
弹幕数据清洗脚本 v3
策略：只去除完全相同的行 + 无意义弹幕 + 刷屏，不做激进去重
原始数据: danmaku_data/ (不动)
清洗后数据: danmaku_cleaned/
"""

import csv
import re
import os
import json

RAW_DIR = "danmaku_data"
CLEAN_DIR = "danmaku_cleaned"
SPAM_TIME_WINDOW = 3
SPAM_THRESHOLD = 3

# 繁简映射
TRAD_TO_SIMP = {
    '們': '们', '來': '来', '說': '说', '過': '过', '還': '还',
    '對': '对', '開': '开', '關': '关', '時': '时', '問': '问',
    '這': '这', '樣': '样', '點': '点', '會': '会', '機': '机',
    '長': '长', '將': '将', '實': '实', '現': '现', '發': '发',
    '動': '动', '無': '无', '觀': '观', '場': '场', '經': '经',
    '傳': '传', '學': '学', '書': '书', '讓': '让', '給': '给',
    '當': '当', '與': '与', '為': '为', '從': '从', '進': '进',
    '電': '电', '話': '话', '網': '网', '絡': '络', '質': '质',
    '際': '际', '條': '条', '約': '约', '參': '参', '風': '风',
    '氣': '气', '飛': '飞', '達': '达', '運': '运', '結': '结',
    '論': '论', '調': '调', '創': '创', '幾': '几', '歲': '岁',
    '歷': '历', '厲': '厉', '義': '义', '東': '东', '車': '车',
    '軍': '军', '輕': '轻', '勢': '势', '產': '产', '區': '区',
    '狀': '状', '記': '记', '評': '评', '視': '视', '認': '认',
    '識': '识', '減': '减', '線': '线', '試': '试', '語': '语',
    '誤': '误', '證': '证', '護': '护', '間': '间', '題': '题',
    '響': '响', '應': '应', '檢': '检', '備': '备', '環': '环',
    '節': '节', '養': '养', '錢': '钱', '鐵': '铁', '門': '门',
    '顯': '显', '驚': '惊', '個': '个', '資': '资', '費': '费',
    '損': '损', '營': '营', '職': '职', '聯': '联', '極': '极',
    '積': '积', '獲': '获', '據': '据', '擊': '击', '監': '监',
    '盤': '盘', '著': '著', '異': '异', '導': '导', '雖': '虽',
    '藝': '艺', '體': '体', '險': '险', '頭': '头', '壓': '压',
    '亂': '乱', '複': '复', '雜': '杂', '離': '离', '難': '难',
    '聽': '听', '變': '变', '權': '权', '歡': '欢', '歸': '归',
    '殺': '杀', '獨': '独', '類': '类', '舊': '旧', '蓋': '盖',
    '隻': '只', '裡': '里', '塊': '块', '幹': '干', '夠': '够',
    '鬥': '斗', '歐': '欧', '準': '准', '補': '补', '處': '处',
    '選': '选', '邊': '边', '適': '适', '劇': '剧', '標': '标',
    '欄': '栏', '橋': '桥', '惡': '恶', '聲': '声', '請': '请',
    '諸': '诸', '賽': '赛', '贊': '赞', '贏': '赢', '軟': '软',
    '層': '层', '屬': '属', '嚴': '严', '豐': '丰', '專': '专',
    '該': '该', '詳': '详', '讀': '读', '設': '设', '邏': '逻',
    '輯': '辑', '鍵': '键', '鏈': '链', '閉': '闭', '陳': '陈',
    '階': '阶', '雙': '双', '顧': '顾', '麵': '面', '麼': '么',
    '黨': '党', '買': '买', '賣': '卖', '負': '负', '價': '价',
    '優': '优', '務': '务', '單': '单', '賺': '赚', '搶': '抢',
    '灣': '湾', '島': '岛', '羨': '羡', '慕': '慕', '醫': '医',
    '藥': '药', '驗': '验', '譯': '译', '慣': '惯', '練': '练',
    '構': '构', '態': '态', '績': '绩', '確': '确', '編': '编',
    '輯': '辑', '談': '谈', '見': '见', '規': '规', '廣': '广',
    '強': '强', '彈': '弹', '臺': '台', '穫': '获', '離': '离',
}


def trad_to_simp(text):
    return ''.join(TRAD_TO_SIMP.get(c, c) for c in text)


def normalize_text(text):
    text = text.strip()
    text = trad_to_simp(text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)
    return text.strip()


def is_meaningless(text):
    """只去除真正无价值的弹幕"""
    s = text.strip()
    if not s:
        return True
    # 纯数字
    if re.match(r'^\d+$', s):
        return True
    # 纯空白/零宽
    if re.match(r'^[\s\u200b\u200c\u200d\ufeff]+$', s):
        return True
    # 去除所有非汉字、非字母字符后，看是否还有实质内容
    has_hanzi = bool(re.search(r'[\u4e00-\u9fff]', s))
    has_letter = bool(re.search(r'[a-zA-Z]', s))
    if not has_hanzi and not has_letter:
        return True
    return False


def detect_spam(rows):
    """检测刷屏弹幕：同一用户在短时间内发相同内容>=3次"""
    user_text_times = {}
    for row in rows:
        key = (row['DMID'], row['_cleaned_text'])
        if key not in user_text_times:
            user_text_times[key] = []
        user_text_times[key].append(float(row['视频进度(秒)']))

    spam_indices = set()
    for (dmid, text), times in user_text_times.items():
        if len(times) < SPAM_THRESHOLD:
            continue
        times_sorted = sorted(times)
        burst_count = 0
        for i in range(1, len(times_sorted)):
            if times_sorted[i] - times_sorted[i-1] <= SPAM_TIME_WINDOW:
                burst_count += 1
            if burst_count >= SPAM_THRESHOLD - 1:
                # 标记所有匹配的
                for j, row in enumerate(rows):
                    if row['DMID'] == dmid and row['_cleaned_text'] == text:
                        spam_indices.add(j)
                break

    return spam_indices


def clean_csv(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))

    original_count = len(rows)

    # Step 1: 完全相同行去重 (DMID + 文本 + 进度 三字段联合)
    seen_keys = set()
    unique_rows = []
    exact_dup_count = 0
    for row in rows:
        key = (row['DMID'], row['弹幕文本'].strip(), row['视频进度(秒)'])
        if key in seen_keys:
            exact_dup_count += 1
        else:
            seen_keys.add(key)
            unique_rows.append(row)

    # Step 2: 文本规范化
    for row in unique_rows:
        row['_cleaned_text'] = normalize_text(row['弹幕文本'])

    # Step 3: 去除无意义弹幕
    valid_rows = []
    meaningless_count = 0
    removed_samples = []
    for row in unique_rows:
        if is_meaningless(row['_cleaned_text']):
            meaningless_count += 1
            if len(removed_samples) < 10:
                removed_samples.append(row['_cleaned_text'])
        else:
            valid_rows.append(row)

    # Step 4: 去除刷屏弹幕
    spam_indices = detect_spam(valid_rows)
    spam_count = len(spam_indices)
    clean_rows = [row for i, row in enumerate(valid_rows) if i not in spam_indices]

    # 按视频进度排序
    clean_rows.sort(key=lambda x: float(x['视频进度(秒)']))
    final_count = len(clean_rows)

    # 写入
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        fieldnames = ['序号', '弹幕文本', '视频进度(秒)', '模式', '字号', '颜色', '时间戳', 'DMID', '分区', 'BV号']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, row in enumerate(clean_rows, 1):
            writer.writerow({
                '序号': i,
                '弹幕文本': row['_cleaned_text'],
                '视频进度(秒)': row['视频进度(秒)'],
                '模式': row['模式'],
                '字号': row['字号'],
                '颜色': row['颜色'],
                '时间戳': row['时间戳'],
                'DMID': row['DMID'],
                '分区': row['分区'],
                'BV号': row['BV号'],
            })

    return {
        'original': original_count,
        'exact_dup': exact_dup_count,
        'meaningless': meaningless_count,
        'spam': spam_count,
        'final': final_count,
        'removed': original_count - final_count,
        'retention': round(final_count / original_count * 100, 1) if original_count > 0 else 0,
        'removed_samples': removed_samples,
    }


def main():
    os.makedirs(CLEAN_DIR, exist_ok=True)
    csv_files = [f for f in os.listdir(RAW_DIR) if f.endswith('.csv')]
    if not csv_files:
        print("未找到CSV文件！")
        return

    all_stats = {}
    total_original = 0
    total_final = 0

    print("=" * 60)
    print("弹幕数据清洗报告（v3）")
    print("策略: 完全行去重 + 无意义去除 + 刷屏去除")
    print("=" * 60)

    for csv_file in sorted(csv_files):
        input_path = os.path.join(RAW_DIR, csv_file)
        output_path = os.path.join(CLEAN_DIR, csv_file)
        category = csv_file.split('_')[1].replace('.csv', '')

        stats = clean_csv(input_path, output_path)
        all_stats[category] = stats
        total_original += stats['original']
        total_final += stats['final']

        print(f"\n--- {category} ---")
        print(f"  原始弹幕数:     {stats['original']}")
        print(f"  完全重复行:     -{stats['exact_dup']}")
        print(f"  无意义弹幕:     -{stats['meaningless']}")
        print(f"  刷屏弹幕:       -{stats['spam']}")
        print(f"  清洗后弹幕数:   {stats['final']}")
        print(f"  保留率:         {stats['retention']}%")
        if stats['removed_samples']:
            print(f"  删除样本:       {stats['removed_samples'][:5]}")

    print(f"\n{'=' * 60}")
    print(f"总计: {total_original} -> {total_final} (保留 {round(total_final/total_original*100, 1)}%)")
    print(f"共去除 {total_original - total_final} 条弹幕")
    print(f"原始数据备份: {RAW_DIR}/")
    print(f"清洗后数据:   {CLEAN_DIR}/")

    report = {
        'date': '2026-04-21',
        'version': 'v3',
        'strategy': 'exact_row_dedup + meaningless + spam',
        'total_original': total_original,
        'total_final': total_final,
        'categories': all_stats,
    }
    with open(os.path.join(CLEAN_DIR, 'clean_report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n清洗统计已保存: {CLEAN_DIR}/clean_report.json")


if __name__ == '__main__':
    main()
