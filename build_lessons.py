# -*- coding: utf-8 -*-
"""단어 300개 + 문법 패턴 37종 → 학습 데이터(lessons.json) 생성
각 레슨 = 단어 1개 + 그 단어가 들어간 문장 1개 (총 300 레슨)
"""
import json
import re
from data.words import WORDS
from data.patterns import PATTERNS
from kana import to_korean, breakdown, josa

JOSA_RE = re.compile(r"\{J:(..)\}")


def resolve_josa(template: str, word_kr: str) -> str:
    def rep(m):
        pair = m.group(1)  # 예: '을를'
        return josa(word_kr, pair)
    return JOSA_RE.sub(rep, template)


def is_katakana(word: str) -> bool:
    return any(0x30A0 <= ord(c) <= 0x30FF for c in word)


def build():
    # 카테고리별 사용 가능한 패턴 인덱스
    cat_patterns = {}
    for pi, p in enumerate(PATTERNS):
        for c in p["cats"]:
            cat_patterns.setdefault(c, []).append(pi)

    usage = [0] * len(PATTERNS)  # 패턴별 사용 횟수 (고르게 분배)
    lessons = []

    for wi, (jp, mean, cat) in enumerate(WORDS):
        cands = cat_patterns.get(cat)
        if not cands:
            raise ValueError(f"카테고리 '{cat}' 에 맞는 패턴 없음: {jp}")
        # 가장 적게 쓰인 패턴 선택 → 문법이 골고루 반복됨
        pi = min(cands, key=lambda i: usage[i])
        usage[pi] += 1
        p = PATTERNS[pi]

        sent_jp = p["jp"].replace("{w}", jp)
        sent_pron_kana = p["pron"].replace("{w}", jp)
        sent_kr = to_korean(sent_pron_kana).replace(" .", ".").strip()
        if sent_jp.endswith("か。"):
            sent_kr = sent_kr.rstrip(".") + "?"
        sent_mean = resolve_josa(p["mean"].replace("{m}", mean), mean)

        lessons.append(dict(
            id=wi + 1,
            word=dict(
                jp=jp,
                kr=to_korean(jp),
                mean=mean,
                script="가타카나" if is_katakana(jp) else "히라가나",
                breakdown=breakdown(jp),
            ),
            sentence=dict(
                jp=sent_jp,
                kr=sent_kr,
                mean=sent_mean,
                grammar=p["grammar"],
                note=p["note"],
            ),
        ))

    with open("data/lessons.json", "w", encoding="utf-8") as f:
        json.dump(lessons, f, ensure_ascii=False, indent=1)

    print(f"✅ 레슨 {len(lessons)}개 생성 완료 → data/lessons.json")
    print(f"   사용된 문법 패턴: {sum(1 for u in usage if u > 0)}/{len(PATTERNS)}종")


if __name__ == "__main__":
    build()
