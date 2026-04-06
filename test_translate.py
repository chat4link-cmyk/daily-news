import requests, time

def translate_to_zh(text: str) -> str:
    """用 MyMemory 免费翻译接口，英文 → 中文，无需注册"""
    if not text or not text.strip():
        return text
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    if chinese_chars / max(len(text), 1) > 0.3:
        return text
    try:
        r = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": text[:500], "langpair": "en|zh"},
            timeout=10, headers={"User-Agent": "Mozilla/5.0"}
        )
        data = r.json()
        if data.get("responseStatus") == 200:
            return data["responseData"]["translatedText"].strip()
        return text
    except Exception:
        return text

# 测试
samples = [
    "AI is changing how small online sellers decide what to make",
    "Super Mario Galaxy Movie Helped Break A 106-Year Record",
    "OpenAI's vision for the AI economy: public wealth funds and robot taxes",
    "Iran threatens OpenAI's Stargate data center in Abu Dhabi",
]
for s in samples:
    zh = translate_to_zh(s)
    print(f"原文: {s}")
    print(f"译文: {zh}")
    print()
    time.sleep(0.3)
