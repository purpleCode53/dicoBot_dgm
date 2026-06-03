import os, re, json, time, threading, hashlib, datetime, requests, discord
from discord.ext import commands, tasks
from bs4 import BeautifulSoup
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN      = os.environ["DISCORD_TOKEN"]
CHANNEL_ID = int(os.environ["DISCORD_CHANNEL_ID"])
CHECK_MIN  = 30
STATE_FILE = "last_idx.json"
LIST_URL   = "https://www.digimonrpg.com/Pages/Notice/Update"
VIEW_URL   = "https://www.digimonrpg.com/pages/Notice/Update_view?idx={}"
HEADERS    = {"User-Agent": "Mozilla/5.0"}


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_state(data):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)


def get_latest_post():
    resp = requests.get(LIST_URL, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    link = soup.find("a", href=re.compile(r"Update_view\?idx=(\d+)"))
    if not link:
        raise ValueError("no link")
    idx = int(re.search(r"idx=(\d+)", link["href"]).group(1))
    return idx, link.get_text(strip=True)


def get_world_buff(idx):
    resp = requests.get(VIEW_URL.format(idx), headers=HEADERS, timeout=10)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    soup = BeautifulSoup(resp.text, "lxml")
    pre = soup.find("pre")
    text = pre.get_text() if pre else soup.get_text()
    keyword = bytes([0xec,0x9b,0x94,0xeb,0x93,0x9c,0x20,0xeb,0xb2,0x84,0xed,0x94,0x84,0x20,0xeb,0xb3,0x80,0xea,0xb2,0xbd]).decode("utf-8")
    pattern = re.compile(r"(" + re.escape(keyword) + r".*?)(?=\n\d+\)|\n\d+\.|\Z)", re.DOTALL)
    m = pattern.search(text)
    if not m:
        return "section not found"
    return "\n".join(l for l in m.group(1).strip().splitlines() if l.strip())


def md5(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def build_msg(title, idx, changes):
    return "[Update] " + title + "\n" + VIEW_URL.format(idx) + "\n" + "-"*40 + "\n" + changes


async def send_msg(channel, text):
    for i in range(0, len(text), 1900):
        await channel.send(text[i:i+1900])


# Render health check
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
    def log_message(self, *a): pass

threading.Thread(
    target=lambda: HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 8080))), HealthHandler).serve_forever(),
    daemon=True
).start()

# Sleep prevention
def keep_alive():
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url: return
    while True:
        time.sleep(600)
        try: requests.get(url, timeout=10)
        except: pass

threading.Thread(target=keep_alive, daemon=True).start()


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print("ready: " + str(bot.user))
    check_update.start()
    weekly_buff.start()


# 30분마다 새 게시글 감지
@tasks.loop(minutes=CHECK_MIN)
async def check_update():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel: return
    try:
        idx, title = get_latest_post()
    except Exception as e:
        print("err: " + str(e)); return
    state = load_state()
    if state.get("idx") is not None and idx <= state["idx"]: return
    state["idx"] = idx
    save_state(state)
    try:
        changes = get_world_buff(idx)
    except Exception as e:
        await channel.send("err: " + str(e)); return
    if changes == "section not found":
        print("new post but no world buff section, skip")
        return
    await send_msg(channel, build_msg(title, idx, changes))


@check_update.before_loop
async def before_check():
    await bot.wait_until_ready()


# 매주 수요일 00:00 KST (화요일 15:00 UTC) 자동 전송
WEEKLY_TIME = datetime.time(hour=15, minute=0, tzinfo=datetime.timezone.utc)

@tasks.loop(time=WEEKLY_TIME)
async def weekly_buff():
    if datetime.datetime.now(datetime.timezone.utc).weekday() != 1:
        return
    channel = bot.get_channel(CHANNEL_ID)
    if not channel: return
    try:
        idx, title = get_latest_post()
        changes = get_world_buff(idx)
    except Exception as e:
        await channel.send("err: " + str(e)); return

    # 이전과 내용 동일하면 스킵
    state = load_state()
    curr_hash = md5(changes)
    if state.get("weekly_hash") == curr_hash:
        print("weekly: same content, skip")
        return
    state["weekly_hash"] = curr_hash
    save_state(state)

    await send_msg(channel, build_msg(title, idx, changes))


@weekly_buff.before_loop
async def before_weekly():
    await bot.wait_until_ready()


# 수동 명령어
@bot.command(name="worldbuff")
async def cmd_world_buff(ctx):
    async with ctx.typing():
        try:
            idx, title = get_latest_post()
            changes = get_world_buff(idx)
        except Exception as e:
            await ctx.send("err: " + str(e)); return
    await send_msg(ctx, build_msg(title, idx, changes))


bot.run(TOKEN)
