"""
디지몬RPG 업데이트 알림 봇
- 30분마다 업데이트 공지 페이지를 확인
- 새 게시글 발견 시 "게임 내 변경사항" 섹션을 Discord로 전송

환경변수 (Railway에서 설정):
  DISCORD_TOKEN      봇 토큰
  DISCORD_CHANNEL_ID 알림을 보낼 채널 ID
"""

import os
import re
import json
import requests
import discord
from discord.ext import commands, tasks
from bs4 import BeautifulSoup

# ── 설정 ──────────────────────────────────────────────────
TOKEN      = os.environ["DISCORD_TOKEN"]
CHANNEL_ID = int(os.environ["DISCORD_CHANNEL_ID"])
CHECK_MIN  = 30          # 확인 주기 (분)
STATE_FILE = "last_idx.json"
LIST_URL   = "https://www.digimonrpg.com/Pages/Notice/Update"
VIEW_URL   = "https://www.digimonrpg.com/pages/Notice/Update_view?idx={}"
# ──────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}


# ── 상태 저장/로드 ─────────────────────────────────────────
def load_last_idx() -> int | None:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f).get("idx")
    return None


def save_last_idx(idx: int):
    with open(STATE_FILE, "w") as f:
        json.dump({"idx": idx}, f)


# ── 크롤링 ─────────────────────────────────────────────────
def get_latest_post() -> tuple[int, str]:
    """목록 페이지에서 가장 최신 게시글 (idx, 제목) 반환."""
    resp = requests.get(LIST_URL, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    # href 에 Update_view?idx= 가 포함된 첫 번째 링크
    link = soup.find("a", href=re.compile(r"Update_view\?idx=(\d+)"))
    if not link:
        raise ValueError("게시글 링크를 찾을 수 없습니다.")

    idx   = int(re.search(r"idx=(\d+)", link["href"]).group(1))
    title = link.get_text(strip=True)
    return idx, title


def get_game_changes(idx: int) -> str:
    """게시글에서 '게임 내 변경사항' 섹션 텍스트 반환."""
    resp = requests.get(VIEW_URL.format(idx), headers=HEADERS, timeout=10)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    soup = BeautifulSoup(resp.text, "lxml")

    # 본문 전체 텍스트 (pre 또는 body 기반)
    pre = soup.find("pre")
    body_text = pre.get_text() if pre else soup.get_text()

    # "게임 내 변경사항" ~ 다음 숫자 섹션 사이를 추출
    pattern = re.compile(
        r"(?:\d+\.\s*게임\s*내\s*변경사항)(.*?)(?=\n\d+\.\s|\Z)",
        re.DOTALL,
    )
    m = pattern.search(body_text)
    if not m:
        return "⚠️ '게임 내 변경사항' 섹션을 찾지 못했습니다."

    section = m.group(1).strip()
    # 빈 줄 압축
    lines   = [l for l in section.splitlines() if l.strip()]
    return "\n".join(lines)


# ── 봇 ────────────────────────────────────────────────────
intents = discord.Intents.default()
bot     = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"✅ 봇 시작: {bot.user}")
    check_update.start()


@tasks.loop(minutes=CHECK_MIN)
async def check_update():
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        print(f"❌ 채널 {CHANNEL_ID} 를 찾을 수 없습니다.")
        return

    try:
        idx, title = get_latest_post()
    except Exception as e:
        print(f"목록 조회 실패: {e}")
        return

    last = load_last_idx()

    if last is not None and idx <= last:
        print(f"새 게시글 없음 (최신 idx={idx})")
        return

    print(f"새 게시글 발견: idx={idx} / {title}")
    save_last_idx(idx)

    try:
        changes = get_game_changes(idx)
    except Exception as e:
        await channel.send(f"⚠️ 게시글 크롤링 실패: {e}")
        return

    url     = VIEW_URL.format(idx)
    header  = f"🎮 **디지몬RPG 업데이트** | [{title}]({url})\n{'━'*40}\n**📋 게임 내 변경사항**\n"
    content = header + changes

    # Discord 2000자 제한 처리
    for i in range(0, len(content), 1900):
        await channel.send(content[i:i+1900])


@check_update.before_loop
async def before_check():
    await bot.wait_until_ready()


@bot.command(na