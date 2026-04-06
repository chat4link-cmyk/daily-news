#!/usr/bin/env python3
"""
Daily News Fetcher
抓取 AI / 游戏 / 科技 / 金融市场（黄金、原油、港股、美股）24h 重大新闻
输出: data/YYYY-MM-DD.json  +  更新 web/index.html
"""

import feedparser
import requests
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from bs4 import BeautifulSoup

# ── 路径 ──────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
WEB_DIR  = BASE_DIR / "web"
DATA_DIR.mkdir(exist_ok=True)
WEB_DIR.mkdir(exist_ok=True)

# ── 时区 ──────────────────────────────────────────────
CST = timezone(timedelta(hours=8))
NOW = datetime.now(CST)
CUTOFF = NOW - timedelta(hours=24)

# ── RSS 源 ─────────────────────────────────────────────
# 每个分类：(名称, URL)
RSS_SOURCES = {
    "AI": [
        ("MIT Technology Review – AI", "https://www.technologyreview.com/feed/"),
        ("VentureBeat AI",             "https://venturebeat.com/category/ai/feed/"),
        ("The Verge – AI",             "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
        ("Wired AI",                   "https://www.wired.com/feed/tag/ai/latest/rss"),
    ],
    "游戏": [
        ("IGN News",                   "https://feeds.feedburner.com/ign/news"),
        ("GameSpot",                   "https://www.gamespot.com/feeds/mashup/"),
        ("Eurogamer",                  "https://www.eurogamer.net/?format=rss"),
    ],
    "科技": [
        ("TechCrunch",                 "https://techcrunch.com/feed/"),
        ("Ars Technica",               "https://feeds.arstechnica.com/arstechnica/index"),
        ("The Verge",                  "https://www.theverge.com/rss/index.xml"),
        ("Hacker News Front Page",     "https://hnrss.org/frontpage?points=100"),
    ],
    "金融市场": [
        ("Reuters Business",           "https://feeds.reuters.com/reuters/businessNews"),
        ("Reuters Markets",            "https://feeds.reuters.com/reuters/marketsNews"),
        ("CNBC Markets",               "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258"),
        ("Bloomberg Markets (WSJ)",    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
        ("Investing.com Gold",         "https://www.investing.com/rss/news_301.rss"),
        ("Seeking Alpha",              "https://seekingalpha.com/market_currents.xml"),
    ],
}

# ── 关键词过滤（金融市场分类额外过滤） ──────────────────
FINANCE_KEYWORDS = [
    "gold", "黄金", "oil", "crude", "原油", "WTI", "Brent",
    "Hang Seng", "港股", "HSI", "HKEX",
    "S&P", "Dow", "Nasdaq", "美股", "NYSE", "Wall Street",
    "Fed", "Federal Reserve", "interest rate", "CPI", "inflation",
    "stock", "market", "rally", "selloff", "earnings",
]

def is_recent(entry) -> bool:
    """判断条目是否在 24h 内"""
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            dt = datetime(*t[:6], tzinfo=timezone.utc)
            return dt >= CUTOFF
    return True  # 无时间戳则保留

def fetch_feed(name: str, url: str) -> list[dict]:
    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
        items = []
        for e in feed.entries:
            if not is_recent(e):
                continue
            title   = e.get("title", "").strip()
            link    = e.get("link", "").strip()
            summary = e.get("summary", e.get("description", "")).strip()
            # 去 HTML 标签
            summary = BeautifulSoup(summary, "html.parser").get_text(" ", strip=True)
            summary = summary[:300] + ("…" if len(summary) > 300 else "")
            if title and link:
                items.append({"title": title, "link": link, "summary": summary, "source": name})
        return items
    except Exception as ex:
        print(f"  ⚠ {name}: {ex}", file=sys.stderr)
        return []

def finance_relevant(item: dict) -> bool:
    text = (item["title"] + " " + item["summary"]).lower()
    return any(kw.lower() in text for kw in FINANCE_KEYWORDS)

def fetch_all() -> dict[str, list[dict]]:
    result = {}
    for category, sources in RSS_SOURCES.items():
        print(f"📡 抓取 [{category}]...")
        items = []
        for name, url in sources:
            batch = fetch_feed(name, url)
            print(f"   {name}: {len(batch)} 条")
            items.extend(batch)
        # 金融市场额外过滤
        if category == "金融市场":
            items = [i for i in items if finance_relevant(i)]
        # 去重（按标题）
        seen, deduped = set(), []
        for it in items:
            key = it["title"].lower()[:60]
            if key not in seen:
                seen.add(key)
                deduped.append(it)
        result[category] = deduped[:15]   # 每类最多 15 条
        print(f"   ✅ {category}: {len(result[category])} 条（去重后）")
    return result

def save_json(data: dict) -> Path:
    date_str = NOW.strftime("%Y-%m-%d")
    out_path = DATA_DIR / f"{date_str}.json"
    payload = {
        "date": date_str,
        "generated_at": NOW.isoformat(),
        "categories": data,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"💾 JSON 已保存: {out_path}")
    return out_path

def build_html(data: dict) -> Path:
    date_str = NOW.strftime("%Y-%m-%d")
    # 读取历史存档列表
    history = sorted([f.stem for f in DATA_DIR.glob("*.json")], reverse=True)[:30]

    cat_icons = {"AI": "🤖", "游戏": "🎮", "科技": "💻", "金融市场": "📈"}

    sections = ""
    for cat, items in data.items():
        icon = cat_icons.get(cat, "📰")
        cards = ""
        for it in items:
            src = it.get("source", "")
            cards += f"""
        <article class="card">
          <h3><a href="{it['link']}" target="_blank" rel="noopener">{it['title']}</a></h3>
          <p class="meta">📌 {src}</p>
          <p class="summary">{it['summary']}</p>
          <a class="more" href="{it['link']}" target="_blank" rel="noopener">阅读全文 →</a>
        </article>"""
        sections += f"""
    <section id="{cat}">
      <h2>{icon} {cat}</h2>
      <div class="grid">{cards}
      </div>
    </section>"""

    hist_links = "".join(
        f'<li><a href="archive/{d}.html">{d}</a></li>' for d in history if d != date_str
    )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>每日要闻 · {date_str}</title>
  <style>
    :root {{
      --bg: #0f1117; --card: #1a1d2e; --accent: #7c6af7;
      --text: #e2e8f0; --sub: #94a3b8; --border: #2d3148;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: var(--bg); color: var(--text); font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }}
    header {{ background: linear-gradient(135deg,#1e1b4b,#312e81); padding: 2rem; text-align: center; }}
    header h1 {{ font-size: 2rem; letter-spacing: .05em; }}
    header p  {{ color: var(--sub); margin-top: .4rem; }}
    nav {{ display: flex; justify-content: center; gap: 1rem; padding: 1rem; flex-wrap: wrap; }}
    nav a {{ color: var(--accent); text-decoration: none; padding: .4rem .9rem;
             border: 1px solid var(--border); border-radius: 999px; font-size: .9rem; }}
    nav a:hover {{ background: var(--accent); color: #fff; }}
    main {{ max-width: 1200px; margin: 0 auto; padding: 2rem 1rem; }}
    section {{ margin-bottom: 3rem; }}
    section h2 {{ font-size: 1.4rem; margin-bottom: 1rem; padding-bottom: .5rem;
                  border-bottom: 2px solid var(--border); }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill,minmax(320px,1fr)); gap: 1rem; }}
    .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px;
             padding: 1.2rem; display: flex; flex-direction: column; gap: .6rem; }}
    .card h3 {{ font-size: 1rem; line-height: 1.5; }}
    .card h3 a {{ color: var(--text); text-decoration: none; }}
    .card h3 a:hover {{ color: var(--accent); }}
    .meta {{ font-size: .75rem; color: var(--sub); }}
    .summary {{ font-size: .85rem; color: var(--sub); line-height: 1.6; flex: 1; }}
    .more {{ font-size: .8rem; color: var(--accent); text-decoration: none; align-self: flex-start; }}
    .more:hover {{ text-decoration: underline; }}
    aside {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px;
             padding: 1.2rem; margin-top: 2rem; }}
    aside h3 {{ margin-bottom: .8rem; color: var(--sub); font-size: .9rem; }}
    aside ul {{ list-style: none; display: flex; flex-wrap: wrap; gap: .5rem; }}
    aside ul li a {{ color: var(--sub); font-size: .8rem; }}
    aside ul li a:hover {{ color: var(--accent); }}
    footer {{ text-align: center; padding: 2rem; color: var(--sub); font-size: .8rem; }}
  </style>
</head>
<body>
  <header>
    <h1>📰 每日要闻</h1>
    <p>{date_str} · AI · 游戏 · 科技 · 金融市场</p>
  </header>
  <nav>
    <a href="#AI">🤖 AI</a>
    <a href="#游戏">🎮 游戏</a>
    <a href="#科技">💻 科技</a>
    <a href="#金融市场">📈 金融市场</a>
  </nav>
  <main>
{sections}
    <aside>
      <h3>📅 历史存档</h3>
      <ul>{hist_links or '<li style="color:var(--sub)">暂无历史</li>'}</ul>
    </aside>
  </main>
  <footer>由 OpenClaw 自动生成 · {NOW.strftime('%Y-%m-%d %H:%M')} CST</footer>
</body>
</html>"""

    out = WEB_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"🌐 HTML 已生成: {out}")
    return out

SERVERCHAN_KEY = os.environ.get("SERVERCHAN_KEY", "SCT334469TlCdNfNyvYBqD87hbelmDKu82")
SITE_URL = os.environ.get("SITE_URL", "https://chat4link-cmyk.github.io/daily-news/")

# ── 短链接 ────────────────────────────────────────────
def shorten_url(long_url: str) -> str:
    """用 tinyurl 生成短链接，失败则返回原链接"""
    try:
        r = requests.get(
            "https://tinyurl.com/api-create.php",
            params={"url": long_url},
            timeout=8
        )
        short = r.text.strip()
        return short if short.startswith("http") else long_url
    except Exception:
        return long_url

# ── 翻译 ──────────────────────────────────────────────
def translate_to_zh(text: str) -> str:
    """MyMemory 免费翻译，无需注册 Key，英文→中文"""
    if not text or not text.strip():
        return text
    # 已是中文则跳过
    if sum(1 for c in text if '\u4e00' <= c <= '\u9fff') / max(len(text), 1) > 0.3:
        return text
    try:
        r = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": text[:400], "langpair": "en|zh-CN"},
            timeout=8, headers={"User-Agent": "Mozilla/5.0"}
        )
        data = r.json()
        if data.get("responseStatus") == 200:
            result = data["responseData"]["translatedText"].strip()
            if result and result != text:
                return result
    except Exception:
        pass
    return text  # 失败则保留原文

def truncate_zh(text: str, max_chars: int = 50) -> str:
    """裁剪到指定字数，在标点处断句，末尾加省略号"""
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) <= max_chars:
        return text
    # 尝试在标点处截断
    cut = text[:max_chars]
    for punct in "。！？，、；":
        idx = cut.rfind(punct)
        if idx > max_chars // 2:
            return cut[:idx + 1]
    return cut.rstrip() + "…"

def translate_and_summarize(items: list[dict]) -> list[dict]:
    """翻译标题 + 摘要（50字内），使用 MyMemory 免费接口"""
    for it in items:
        # 翻译标题
        it["zh_title"] = translate_to_zh(it["title"])
        time.sleep(0.2)
        # 翻译摘要（取原文前200字翻译，再裁剪到50字）
        raw_summary = it.get("summary", "").strip()
        if raw_summary:
            zh = translate_to_zh(raw_summary[:200])
            it["zh_summary"] = truncate_zh(zh, 50)
        else:
            it["zh_summary"] = ""
        time.sleep(0.2)
    return items

# ── 推送摘要构建 ───────────────────────────────────────
def build_digest(data: dict) -> str:
    """生成 Server酱推送正文（Markdown，美化格式）"""
    date_str  = NOW.strftime("%Y-%m-%d")
    weekdays  = ["周一","周二","周三","周四","周五","周六","周日"]
    weekday   = weekdays[NOW.weekday()]

    cat_icons = {"AI": "🤖", "游戏": "🎮", "科技": "💻", "金融市场": "📈"}
    cat_labels = {
        "AI":     "人工智能",
        "游戏":   "游戏动态",
        "科技":   "科技资讯",
        "金融市场": "金融市场",
    }

    blocks = []
    for cat, items in data.items():
        if not items:
            continue
        icon  = cat_icons.get(cat, "📰")
        label = cat_labels.get(cat, cat)
        items = translate_and_summarize(items[:3])

        lines = [f"### {icon} {label}"]
        lines.append("")
        for it in items:
            zh_title   = it.get("zh_title",   it["title"])
            zh_summary = it.get("zh_summary", "")
            short_link = shorten_url(it["link"])
            source     = it.get("source", "")

            lines.append(f"**{zh_title}**")
            if zh_summary:
                lines.append(f"> {zh_summary}")
            lines.append(f"来源：{source}　[阅读原文]({short_link})")
            lines.append("")

        blocks.append("\n".join(lines))

    header = f"# 📰 每日要闻\n\n**{date_str} {weekday}**　共 {sum(len(v) for v in data.values())} 条新闻\n"
    footer = f"\n---\n[📖 查看完整网页版]({SITE_URL})\n*由 OpenClaw 自动生成*"

    return header + "\n---\n\n" + "\n---\n\n".join(blocks) + footer

# ── Server酱推送 ───────────────────────────────────────
def push_serverchan(desp: str) -> bool:
    date_str = NOW.strftime("%Y-%m-%d")
    weekdays = ["周一","周二","周三","周四","周五","周六","周日"]
    title    = f"📰 {date_str} {weekdays[NOW.weekday()]} 每日要闻"

    try:
        resp   = requests.post(
            f"https://sctapi.ftqq.com/{SERVERCHAN_KEY}.send",
            data={"title": title, "desp": desp},
            timeout=15
        )
        result = resp.json()
        if result.get("code") == 0:
            print(f"✅ Server酱推送成功！pushid={result.get('data',{}).get('pushid','')}")
            return True
        else:
            print(f"⚠ Server酱推送失败: {result}", file=sys.stderr)
            return False
    except Exception as ex:
        print(f"⚠ Server酱推送异常: {ex}", file=sys.stderr)
        return False

if __name__ == "__main__":
    print(f"⏰ 开始抓取 [{NOW.strftime('%Y-%m-%d %H:%M')} CST]")
    data = fetch_all()
    save_json(data)
    build_html(data)
    digest = build_digest(data)
    digest_path = BASE_DIR / "latest_digest.txt"
    digest_path.write_text(digest, encoding="utf-8")
    print(f"\n{'='*60}")
    print(digest)
    print(f"{'='*60}")
    print("\n📲 推送到微信...")
    push_serverchan(digest)
    print("\n✅ 完成！")
