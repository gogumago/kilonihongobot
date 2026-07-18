# -*- coding: utf-8 -*-
"""가나(히라가나/가타카나) → 한글 발음 변환 모듈"""

# 기본 히라가나 → 한글
_BASE = {
    "あ": "아", "い": "이", "う": "우", "え": "에", "お": "오",
    "か": "카", "き": "키", "く": "쿠", "け": "케", "こ": "코",
    "さ": "사", "し": "시", "す": "스", "せ": "세", "そ": "소",
    "た": "타", "ち": "치", "つ": "츠", "て": "테", "と": "토",
    "な": "나", "に": "니", "ぬ": "누", "ね": "네", "の": "노",
    "は": "하", "ひ": "히", "ふ": "후", "へ": "헤", "ほ": "호",
    "ま": "마", "み": "미", "む": "무", "め": "메", "も": "모",
    "や": "야", "ゆ": "유", "よ": "요",
    "ら": "라", "り": "리", "る": "루", "れ": "레", "ろ": "로",
    "わ": "와", "を": "오",
    "が": "가", "ぎ": "기", "ぐ": "구", "げ": "게", "ご": "고",
    "ざ": "자", "じ": "지", "ず": "즈", "ぜ": "제", "ぞ": "조",
    "だ": "다", "ぢ": "지", "づ": "즈", "で": "데", "ど": "도",
    "ば": "바", "び": "비", "ぶ": "부", "べ": "베", "ぼ": "보",
    "ぱ": "파", "ぴ": "피", "ぷ": "푸", "ぺ": "페", "ぽ": "포",
}

# 요음(작은 ゃゅょ) 결합
_COMBO = {
    "きゃ": "캬", "きゅ": "큐", "きょ": "쿄",
    "しゃ": "샤", "しゅ": "슈", "しょ": "쇼",
    "ちゃ": "챠", "ちゅ": "츄", "ちょ": "쵸",
    "にゃ": "냐", "にゅ": "뉴", "にょ": "뇨",
    "ひゃ": "햐", "ひゅ": "휴", "ひょ": "효",
    "みゃ": "먀", "みゅ": "뮤", "みょ": "묘",
    "りゃ": "랴", "りゅ": "류", "りょ": "료",
    "ぎゃ": "갸", "ぎゅ": "규", "ぎょ": "교",
    "じゃ": "쟈", "じゅ": "쥬", "じょ": "죠",
    "びゃ": "뱌", "びゅ": "뷰", "びょ": "뵤",
    "ぴゃ": "퍄", "ぴゅ": "퓨", "ぴょ": "표",
}

# 가타카나 확장 표기
_KATA_EXTRA = {
    "ファ": "파", "フィ": "피", "フェ": "페", "フォ": "포",
    "ティ": "티", "ディ": "디", "デュ": "듀", "トゥ": "투", "ドゥ": "두",
    "ウィ": "위", "ウェ": "웨", "ウォ": "워",
    "シェ": "셰", "ジェ": "제", "チェ": "체", "イェ": "예",
    "ツァ": "차", "ツェ": "체", "ツォ": "초", "ヴ": "부",
}

_SMALL_Y = "ゃゅょャュョ"
_O_ROW = set("おこそとのほもよろごぞどぼぽょ")  # お단 (+ 요음 ょ)
_E_ROW = set("えけせてねへめれげぜでべぺ")      # え단


def _kata_to_hira(ch: str) -> str:
    o = ord(ch)
    if 0x30A1 <= o <= 0x30F6:  # ァ~ヶ
        return chr(o - 0x60)
    return ch


def _add_jong(syl: str, jong_idx: int) -> str:
    """한글 음절에 받침 추가 (ㄴ=4, ㅅ=19)"""
    o = ord(syl)
    if 0xAC00 <= o <= 0xD7A3 and (o - 0xAC00) % 28 == 0:
        return chr(o + jong_idx)
    return syl + ("ㄴ" if jong_idx == 4 else "ㅅ")


def to_korean(text: str) -> str:
    """가나 문자열을 한글 발음으로 변환.
    - ん → 앞 음절에 ㄴ받침, っ → 앞 음절에 ㅅ받침
    - ー / おう / えい → 장음 '-'
    """
    out = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        pair = text[i:i + 2]

        # 가타카나 확장 (2글자 우선)
        if pair in _KATA_EXTRA:
            out.append(_KATA_EXTRA[pair]); i += 2; continue
        if ch in _KATA_EXTRA:
            out.append(_KATA_EXTRA[ch]); i += 1; continue

        h = _kata_to_hira(ch)
        h2 = _kata_to_hira(text[i + 1]) if i + 1 < n else ""

        # 요음 결합
        if h2 and (h + h2) in _COMBO:
            out.append(_COMBO[h + h2]); i += 2; continue

        if ch == "ー":
            out.append("-"); i += 1; continue

        if h in ("ん",):
            if out:
                out[-1] = _add_jong(out[-1], 4)
            else:
                out.append("ㄴ")
            i += 1; continue

        if h in ("っ",):
            # 다음 글자 발음의 받침으로 ㅅ을 앞 음절에 붙임
            nxt = None
            # 그냥 앞 음절에 ㅅ받침 (교과서식: がっこう→갓코-)
            if out:
                out[-1] = _add_jong(out[-1], 19)
            i += 1; continue

        # 장음 처리: お단+う, え단+い
        if h == "う" and out and _prev_kana_row(text, i) == "o":
            out.append("-"); i += 1; continue
        if h == "い" and out and _prev_kana_row(text, i) == "e":
            out.append("-"); i += 1; continue

        if h in _BASE:
            out.append(_BASE[h]); i += 1; continue

        # 구두점/공백/기타
        if ch == "。":
            out.append("."); i += 1; continue
        if ch == "、":
            out.append(","); i += 1; continue
        if ch == "・":
            out.append(" "); i += 1; continue
        out.append(ch); i += 1
    return "".join(out)


def _prev_kana_row(text: str, i: int) -> str:
    """i 위치 직전의 (실제 발음되는) 가나가 お단이면 'o', え단이면 'e'"""
    j = i - 1
    while j >= 0:
        h = _kata_to_hira(text[j])
        if h in ("ー", "っ", "ん"):
            j -= 1; continue
        if h in _O_ROW:
            return "o"
        if h in _E_ROW:
            return "e"
        return ""
    return ""


def breakdown(word: str) -> str:
    """글자별 발음 분해: サウナ → サ(사)・ウ(우)・ナ(나)"""
    parts = []
    i, n = 0, len(word)
    while i < n:
        ch = word[i]
        pair = word[i:i + 2]
        h = _kata_to_hira(ch)
        h2 = _kata_to_hira(word[i + 1]) if i + 1 < n else ""

        if pair in _KATA_EXTRA:
            parts.append(f"{pair}({_KATA_EXTRA[pair]})"); i += 2; continue
        if ch in _KATA_EXTRA:
            parts.append(f"{ch}({_KATA_EXTRA[ch]})"); i += 1; continue
        if h2 and (h + h2) in _COMBO:
            parts.append(f"{pair}({_COMBO[h + h2]})"); i += 2; continue
        if ch == "ー":
            parts.append("ー(장음~)"); i += 1; continue
        if h == "ん":
            parts.append(f"{ch}(ㄴ받침)"); i += 1; continue
        if h == "っ":
            parts.append(f"{ch}(받침·촉음)"); i += 1; continue
        if h in _BASE:
            parts.append(f"{ch}({_BASE[h]})"); i += 1; continue
        parts.append(ch); i += 1
    return "・".join(parts)


def josa(word: str, pair: str) -> str:
    """한국어 조사 자동 선택. pair: '을를'|'은는'|'이가'|'과와'"""
    last = ""
    for ch in reversed(word):
        if 0xAC00 <= ord(ch) <= 0xD7A3:
            last = ch; break
    if not last:
        return pair[1]
    has_jong = (ord(last) - 0xAC00) % 28 != 0
    return pair[0] if has_jong else pair[1]
