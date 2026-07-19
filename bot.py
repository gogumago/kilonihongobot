# -*- coding: utf-8 -*-
"""
🗾 일본어 한 입 — 텔레그램 학습 봇
- 2시간 간격(기본 08:00~20:00)으로 단어+문장 레슨 발송
- 매일 21:30 그날 배운 내용 총정리
- 300개 레슨을 다 돌면 처음부터 자동 반복 (2회차부터는 복습 회차 표시)

실행:
  1) 텔레그램에서 @BotFather 에게 /newbot → 토큰 발급
  2) pip install "python-telegram-bot[job-queue]"
  3) export BOT_TOKEN="발급받은토큰"   (윈도우: set BOT_TOKEN=토큰)
  4) python bot.py
"""
import json
import os
import random
import datetime as dt
from zoneinfo import ZoneInfo

from telegram import Update, Poll
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
)

# ─────────── 설정 ───────────
TZ = ZoneInfo("Asia/Seoul")
LESSON_HOURS = [8, 10, 12, 14, 16, 18, 20]   # 2시간 간격 발송 시각
SUMMARY_TIME = dt.time(21, 30, tzinfo=TZ)     # 총정리 시각
QUIZ_HOURS = [11, 15, 19]                     # 퀴즈 발송 시각 (하루 3회)
ITEMS_PER_MESSAGE = 2                          # 메시지당 레슨 수
STATE_FILE = os.environ.get("STATE_FILE", "state.json")
LESSONS_FILE = os.path.join("data", "lessons.json")

with open(LESSONS_FILE, encoding="utf-8") as f:
    LESSONS = json.load(f)
TOTAL = len(LESSONS)

# ─────────── 상태 저장 ───────────
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"chats": {}}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)


def get_chat(state, chat_id):
    cid = str(chat_id)
    if cid not in state["chats"]:
        state["chats"][cid] = {
            "idx": 0,            # 다음에 보낼 레슨 인덱스 (누적)
            "today": [],         # 오늘 보낸 레슨 id 목록
            "today_date": "",
            "active": True,
        }
    return state["chats"][cid]


def today_str():
    return dt.datetime.now(TZ).strftime("%Y-%m-%d")


def reset_if_new_day(chat):
    if chat["today_date"] != today_str():
        chat["today_date"] = today_str()
        chat["today"] = []


# ─────────── 메시지 포맷 ───────────
def fmt_lesson(lesson, seq_no, cycle):
    w, s = lesson["word"], lesson["sentence"]
    cycle_tag = f" · {cycle}회차 복습" if cycle > 1 else ""
    return (
        f"┏━━━━━━━━━━━━━━┓\n"
        f"  🗾 <b>일본어 한 입</b>  #{seq_no:03d}{cycle_tag}\n"
        f"┗━━━━━━━━━━━━━━┛\n"
        f"\n"
        f"📌 <b>{w['jp']}</b>  [{w['kr']}]\n"
        f"      뜻: <b>{w['mean']}</b>  <i>({w['script']})</i>\n"
        f"      🔤 {w['breakdown']}\n"
        f"\n"
        f"✏️ <b>{s['jp']}</b>\n"
        f"      🗣 {s['kr']}\n"
        f"      💡 {s['mean']}\n"
        f"\n"
        f"📖 <b>{s['grammar']}</b>\n"
        f"      {s['note']}"
    )


def fmt_summary(lesson_ids):
    if not lesson_ids:
        return "🌙 오늘은 발송된 레슨이 없어요. 내일 아침 8시에 만나요!"
    lessons = [LESSONS[(i - 1) % TOTAL] for i in lesson_ids]
    lines = [
        "┏━━━━━━━━━━━━━━┓",
        f"  🌙 <b>오늘의 총정리</b> ({today_str()})",
        f"  단어 {len(lessons)}개 · 문장 {len(lessons)}개",
        "┗━━━━━━━━━━━━━━┛",
        "",
        "📚 <b>오늘 배운 단어</b>",
    ]
    for l in lessons:
        w = l["word"]
        lines.append(f"  • <b>{w['jp']}</b> — <tg-spoiler>[{w['kr']}] {w['mean']}</tg-spoiler>")
    lines.append("")
    lines.append("✏️ <b>오늘 배운 문장</b>")
    for l in lessons:
        s = l["sentence"]
        lines.append(f"  • {s['jp']}")
        lines.append(f"     <tg-spoiler>🗣 {s['kr']} — {s['mean']}</tg-spoiler>")
    grammars = []
    for l in lessons:
        g = l["sentence"]["grammar"]
        if g not in grammars:
            grammars.append(g)
    lines.append("")
    lines.append("📖 <b>오늘의 문법</b>: " + " / ".join(grammars))
    lines.append("")
    lines.append("👆 가려진 부분을 탭하면 정답이 보여요. 먼저 떠올려 보세요!")
    lines.append("")
    lines.append("💤 잘 자요! おやすみなさい (오야스미나사이)")
    return "\n".join(lines)


# ─────────── 발송 로직 ───────────
async def send_lessons_to_chat(bot, state, chat_id, count=ITEMS_PER_MESSAGE):
    chat = get_chat(state, chat_id)
    reset_if_new_day(chat)
    blocks = []
    for _ in range(count):
        idx = chat["idx"]
        lesson = LESSONS[idx % TOTAL]
        cycle = idx // TOTAL + 1
        blocks.append(fmt_lesson(lesson, (idx % TOTAL) + 1, cycle))
        chat["today"].append(lesson["id"])
        chat["idx"] = idx + 1
    text = "\n\n\n".join(blocks)
    await bot.send_message(chat_id=int(chat_id), text=text,
                           parse_mode=ParseMode.HTML)


async def job_send_lessons(context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    for cid, chat in list(state["chats"].items()):
        if not chat.get("active"):
            continue
        try:
            await send_lessons_to_chat(context.bot, state, cid)
        except Exception as e:
            print(f"[발송 실패] chat={cid}: {e}")
    save_state(state)


async def job_send_summary(context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    for cid, chat in list(state["chats"].items()):
        if not chat.get("active"):
            continue
        reset_if_new_day(chat)
        try:
            await context.bot.send_message(
                chat_id=int(cid), text=fmt_summary(chat["today"]),
                parse_mode=ParseMode.HTML)
        except Exception as e:
            print(f"[총정리 실패] chat={cid}: {e}")
    save_state(state)




# ─────────── 퀴즈 (텔레그램 Quiz Poll 활용) ───────────
def _josa(word, pair):
    """한국어 조사 자동 선택 pair='을를' 등"""
    last = ""
    for ch in reversed(word):
        if 0xAC00 <= ord(ch) <= 0xD7A3:
            last = ch; break
    if not last:
        return pair[1]
    return pair[0] if (ord(last) - 0xAC00) % 28 != 0 else pair[1]


def _learned_pool(chat):
    """지금까지 배운 레슨 범위에서 출제 (최소 16개 확보)"""
    idx = chat.get("idx", 0)
    if idx >= TOTAL:            # 1회차 완주 후엔 전체에서 출제
        return LESSONS
    n = max(16, idx)            # 초반에는 앞부분 16개로 시작
    return LESSONS[:min(n, TOTAL)]


def _pick_distractors(pool, lesson, key, count=3):
    """같은 카테고리 우선으로 오답 후보 뽑기. key: 표시 문자열 추출 함수"""
    correct = key(lesson)
    same, others = [], []
    for l in pool:
        if l["id"] == lesson["id"]:
            continue
        v = key(l)
        if not v or v == correct:
            continue
        (same if l["word"].get("cat") == lesson["word"].get("cat") else others).append(v)
    random.shuffle(same); random.shuffle(others)
    picks = []
    for v in same + others + [key(l) for l in LESSONS if key(l) != correct]:
        if v not in picks and v != correct:
            picks.append(v)
        if len(picks) >= count:
            break
    return picks


def make_quiz(chat):
    """퀴즈 1개 생성 → dict(question, options, correct_id, explanation)"""
    pool = _learned_pool(chat)
    lesson = random.choice(pool)
    w, s = lesson["word"], lesson["sentence"]
    # 빈칸 퀴즈에 부적합한 문법(아무 명사나 들어가 단서가 없는 문형)은 blank 제외
    BLANK_UNFIT = ("〜です", "〜ですか", "〜でした", "〜じゃないです")
    grammar = s.get("grammar", "")
    allow_blank = not any(g in grammar for g in BLANK_UNFIT)
    qtypes = ["mean", "jp", "read"] + (["blank"] if allow_blank else [])
    qtype = random.choice(qtypes)

    if qtype == "mean":      # 단어 → 뜻
        question = f"🧩 「{w['jp']}」의 뜻은?"
        correct = w["mean"]
        wrongs = _pick_distractors(pool, lesson, lambda l: l["word"]["mean"])
    elif qtype == "jp":      # 뜻 → 단어
        question = f"🧩 '{w['mean']}'{_josa(w['mean'], '을를')} 일본어로 하면?"
        correct = w["jp"]
        wrongs = _pick_distractors(pool, lesson, lambda l: l["word"]["jp"])
    elif qtype == "read":    # 단어 → 발음
        question = f"🔊 「{w['jp']}」의 발음은?"
        correct = w["kr"]
        wrongs = _pick_distractors(pool, lesson, lambda l: l["word"]["kr"])
    else:                    # 문장 빈칸 (뜻을 단서로 제시)
        blank_jp = s["jp"].replace(w["jp"], "◯◯", 1)
        question = f"✏️ ◯◯에 들어갈 일본어는?\n{blank_jp}\n💡 뜻: {s['mean']}"
        correct = w["jp"]
        wrongs = _pick_distractors(pool, lesson, lambda l: l["word"]["jp"])

    options = wrongs[:3] + [correct]
    random.shuffle(options)
    correct_id = options.index(correct)
    explanation = f"{w['jp']} [{w['kr']}] = {w['mean']}\n예문: {s['jp']} ({s['kr']})"
    return dict(question=question[:290], options=[o[:95] for o in options],
                correct_id=correct_id, explanation=explanation[:195])


async def send_quiz_to_chat(bot, state, chat_id):
    chat = get_chat(state, chat_id)
    q = make_quiz(chat)
    await bot.send_poll(
        chat_id=int(chat_id),
        question=q["question"],
        options=q["options"],
        type=Poll.QUIZ,
        correct_option_id=q["correct_id"],
        explanation=q["explanation"],
        is_anonymous=False,          # 그룹에서 누가 맞혔는지 보이게
    )


async def job_send_quiz(context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    for cid, chat in list(state["chats"].items()):
        if not chat.get("active"):
            continue
        try:
            await send_quiz_to_chat(context.bot, state, cid)
        except Exception as e:
            print(f"[퀴즈 실패] chat={cid}: {e}")
    save_state(state)


# ─────────── 명령어 ───────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    chat = get_chat(state, update.effective_chat.id)
    chat["active"] = True
    save_state(state)
    hours = ", ".join(f"{h}시" for h in LESSON_HOURS)
    await update.message.reply_text(
        "🗾 <b>일본어 한 입</b>에 오신 걸 환영합니다!\n\n"
        "한국인이 이미 아는 외래어·기초 단어로\n"
        "히라가나·가타카나를 자연스럽게 익히는 봇이에요.\n\n"
        f"⏰ <b>레슨 발송</b>: 매일 {hours} (2시간 간격)\n"
        "🧩 <b>퀴즈</b>: 매일 11시, 15시, 19시 (객관식, 그날까지 배운 범위)\n"
        "🌙 <b>총정리</b>: 매일 밤 9시 30분 (뜻 가리기 셀프 퀴즈!)\n"
        "📚 단어 300개 + 문장 300개, 끝나면 자동 복습 반복\n\n"
        "<b>명령어</b>\n"
        "/now — 지금 바로 레슨 받기\n"
        "/quiz — 즉석 퀴즈 풀기\n"
        "/today — 오늘 배운 내용 다시 보기\n"
        "/progress — 진도 확인\n"
        "/stop — 발송 중지  /start — 재개",
        parse_mode=ParseMode.HTML)
    # 가입 직후 첫 레슨 맛보기
    await send_lessons_to_chat(context.bot, state, update.effective_chat.id, count=1)
    save_state(state)


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    chat = get_chat(state, update.effective_chat.id)
    chat["active"] = False
    save_state(state)
    await update.message.reply_text(
        "⏸ 발송을 중지했어요. /start 로 언제든 재개할 수 있어요.")


async def cmd_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    await send_lessons_to_chat(context.bot, state, update.effective_chat.id, count=1)
    save_state(state)


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    chat = get_chat(state, update.effective_chat.id)
    reset_if_new_day(chat)
    save_state(state)
    await update.message.reply_text(fmt_summary(chat["today"]),
                                    parse_mode=ParseMode.HTML)


async def cmd_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    chat = get_chat(state, update.effective_chat.id)
    save_state(state)
    idx = chat["idx"]
    cycle = idx // TOTAL + 1
    pos = idx % TOTAL
    bar_len = 20
    filled = round(bar_len * pos / TOTAL)
    bar = "▓" * filled + "░" * (bar_len - filled)
    await update.message.reply_text(
        f"📊 <b>학습 진도</b>\n\n"
        f"{bar}  {pos}/{TOTAL}\n"
        f"현재 {cycle}회차 · 누적 레슨 {idx}개",
        parse_mode=ParseMode.HTML)



async def cmd_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    await send_quiz_to_chat(context.bot, state, update.effective_chat.id)
    save_state(state)


def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise SystemExit("환경변수 BOT_TOKEN 을 설정해 주세요. (BotFather에서 발급)")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("now", cmd_now))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("progress", cmd_progress))
    app.add_handler(CommandHandler("quiz", cmd_quiz))
    app.add_handler(CommandHandler("help", cmd_start))

    jq = app.job_queue
    for h in LESSON_HOURS:
        jq.run_daily(job_send_lessons, time=dt.time(h, 0, tzinfo=TZ),
                     name=f"lesson_{h}")
    for h in QUIZ_HOURS:
        jq.run_daily(job_send_quiz, time=dt.time(h, 0, tzinfo=TZ),
                     name=f"quiz_{h}")
    jq.run_daily(job_send_summary, time=SUMMARY_TIME, name="summary")

    print(f"🗾 일본어 한 입 봇 시작! 레슨 {TOTAL}개 로드됨.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
