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
import datetime as dt
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
)

# ─────────── 설정 ───────────
TZ = ZoneInfo("Asia/Seoul")
LESSON_HOURS = [8, 10, 12, 14, 16, 18, 20]   # 2시간 간격 발송 시각
SUMMARY_TIME = dt.time(21, 30, tzinfo=TZ)     # 총정리 시각
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
        lines.append(f"  • <b>{w['jp']}</b> [{w['kr']}] — {w['mean']}")
    lines.append("")
    lines.append("✏️ <b>오늘 배운 문장</b>")
    for l in lessons:
        s = l["sentence"]
        lines.append(f"  • {s['jp']}")
        lines.append(f"     🗣 {s['kr']} — {s['mean']}")
    grammars = []
    for l in lessons:
        g = l["sentence"]["grammar"]
        if g not in grammars:
            grammars.append(g)
    lines.append("")
    lines.append("📖 <b>오늘의 문법</b>: " + " / ".join(grammars))
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
        "🌙 <b>총정리</b>: 매일 밤 9시 30분\n"
        "📚 단어 300개 + 문장 300개, 끝나면 자동 복습 반복\n\n"
        "<b>명령어</b>\n"
        "/now — 지금 바로 레슨 받기\n"
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
    app.add_handler(CommandHandler("help", cmd_start))

    jq = app.job_queue
    for h in LESSON_HOURS:
        jq.run_daily(job_send_lessons, time=dt.time(h, 0, tzinfo=TZ),
                     name=f"lesson_{h}")
    jq.run_daily(job_send_summary, time=SUMMARY_TIME, name="summary")

    print(f"🗾 일본어 한 입 봇 시작! 레슨 {TOTAL}개 로드됨.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
