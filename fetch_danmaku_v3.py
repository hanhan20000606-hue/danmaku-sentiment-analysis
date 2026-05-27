"""
B站弹幕采集 v3 - 纯XML API，增加重试和timeout
针对XML API不稳定的情况增加重试机制
"""
import requests, time, sys, io, csv, json, os, xml.etree.ElementTree as ET
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.bilibili.com',
}

# 6个采集视频（2026年4月采集，实际采集量因B站API限制低于平台总量）
VIDEOS = [
    {'bvid': 'BV171Paz2ESZ', 'category': '科技',   'author': 'Ai商业慢谈',        'cid': 36523673864, 'expected': 897,  'title': '全民养虾，OpenClaw杀疯了！GPT-5.4降维突袭！丨深扒2026 AI全自动代理'},
    {'bvid': 'BV1ojfDBSEPv', 'category': '科技',   'author': '飞天闪客',           'cid': 35800812006, 'expected': 1800, 'title': '【闪客】名词诈骗！一口气拆穿Skill/MCP/RAG/Agent/OpenClaw底层逻辑'},
    {'bvid': 'BV1SvZyBJENz', 'category': '娱乐',   'author': '山茶爱讲话',         'cid': 25965760762, 'expected': 1161, 'title': '作为人类，有点看不懂了？【2026春晚乐子杂谈】'},
    {'bvid': 'BV1xi6kBFEmZ', 'category': '娱乐',   'author': '山茶爱讲话',         'cid': 25955278054, 'expected': 1153, 'title': '顶级公关？是把人当傻子吧！'},
    {'bvid': 'BV1Mpd5BFEk1', 'category': '汽车',   'author': 'Upspeed盛嘉成',      'cid': 37580377631, 'expected': 948,  'title': '公路之王挑战赛，保时捷真的不可战胜吗？'},
    {'bvid': 'BV1cZXKBpENC', 'category': '汽车',   'author': '极速拍档-Jacky',     'cid': 37019320808, 'expected': 2145, 'title': '这就是人类史上最好开的SUV！'},
]

def fetch_xml_danmaku(oid, retries=5):
    """XML API带重试"""
    for attempt in range(retries):
        try:
            url = f'https://comment.bilibili.com/{oid}.xml'
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.encoding = 'utf-8'
            
            if r.status_code != 200:
                print(f"    尝试 {attempt+1}: HTTP {r.status_code}")
                time.sleep(3)
                continue
                
            if len(r.text) < 50:
                print(f"    尝试 {attempt+1}: 响应太短 ({len(r.text)} bytes)")
                time.sleep(3)
                continue
            
            root = ET.fromstring(r.text)
            results = []
            for d in root.findall('.//d'):
                p_attr = d.get('p', '')
                text = d.text.strip() if d.text else ''
                if text:
                    p_parts = p_attr.split(',')
                    results.append({
                        'progress': float(p_parts[0]) if p_parts else 0,
                        'mode': p_parts[1] if len(p_parts) > 1 else '1',
                        'fontsize': p_parts[2] if len(p_parts) > 2 else '25',
                        'color': p_parts[3] if len(p_parts) > 3 else '16777215',
                        'timestamp': int(p_parts[4]) if len(p_parts) > 4 else 0,
                        'pool': p_parts[5] if len(p_parts) > 5 else '0',
                        'dmid': p_parts[6] if len(p_parts) > 6 else '',
                        'text': text,
                    })
            return results
        except ET.ParseError as e:
            print(f"    尝试 {attempt+1}: XML解析失败")
            time.sleep(3)
        except requests.Timeout:
            print(f"    尝试 {attempt+1}: 超时")
            time.sleep(5)
        except Exception as e:
            print(f"    尝试 {attempt+1}: {e}")
            time.sleep(3)
    
    return []

def main():
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'danmaku_data')
    os.makedirs(output_dir, exist_ok=True)
    
    for video in VIDEOS:
        print(f"\n{'='*60}")
        print(f"[{video['category']}] BV:{video['bvid']} (目标:{video['expected']})")
        print(f"{'='*60}")
        
        print(f"\n  请求XML弹幕API (CID:{video['cid']})...")
        danmaku = fetch_xml_danmaku(video['cid'])
        
        print(f"  获取: {len(danmaku)} 条弹幕")
        
        if len(danmaku) < video['expected'] * 0.8:
            print(f"  低于预期 ({video['expected']}), 再次尝试...")
            time.sleep(3)
            danmaku2 = fetch_xml_danmaku(video['cid'])
            # 合并去重
            existing = set(d['text'] for d in danmaku)
            added = 0
            for d in danmaku2:
                if d['text'] not in existing:
                    existing.add(d['text'])
                    danmaku.append(d)
                    added += 1
            print(f"  二次采集补充: {added} 条, 总计: {len(danmaku)} 条")
        
        # 保存CSV
        csv_path = os.path.join(output_dir, f"{video['bvid']}_{video['category']}.csv")
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['序号', '弹幕文本', '视频进度(秒)', '模式', '字号', '颜色', '时间戳', 'DMID', '分区', 'BV号'])
            for i, dm in enumerate(danmaku, 1):
                writer.writerow([
                    i, dm['text'], dm['progress'],
                    dm.get('mode', ''), dm.get('fontsize', ''), dm.get('color', ''),
                    dm.get('timestamp', ''), dm.get('dmid', ''),
                    video['category'], video['bvid'],
                ])
        
        rate = len(danmaku) / video['expected'] * 100
        print(f"  采集率: {rate:.0f}%")
        print(f"  已保存: {csv_path}")
    
    # 汇总
    total = 0
    files = {}
    for fname in sorted(os.listdir(output_dir)):
        if fname.endswith('.csv'):
            fpath = os.path.join(output_dir, fname)
            with open(fpath, 'r', encoding='utf-8-sig') as f:
                count = sum(1 for _ in f) - 1
            total += count
            files[fname] = count
    
    print(f"\n{'='*60}")
    print("采集汇总")
    print(f"{'='*60}")
    for fname, count in files.items():
        print(f"  {fname}: {count} 条")
    print(f"\n  总计: {total} 条弹幕")

if __name__ == '__main__':
    main()
