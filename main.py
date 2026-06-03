import os, re, json, time, threading, requests, discord
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

def load_last_idx():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("idx")
    return None

def save_last_idx(idx):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"idx": idx}, f)

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
    keyword = "월드 버프 변경"
    pattern = re.compile(r"(" + re.escape(keyword) + r".*?)(?=\n\d+\)|\n\d+\.|\Z)", re.DOTALL)
    m = pattern.search(text)
    if not m:
        return "section not found"
    return "\n".join(l for l in m.group(1).strip().splitlines() if l.strip())

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
    def log_message(self, *a): pass

threading.Thread(target=lambda: HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 8080))), HealthHandler).serve_forever(), daemon=True).start()

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

@tasks.loop(minutes=CHECK_MIN)
async def check_update():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel: return
    try:
        idx, title = get_latest_post()
    except Exception as e:
        print("err: " + str(e)); return
    last = load_last_idx()
    if last is not None and idx <= last: return
    save_last_idx(idx)
    try:
        changes = get_world_buff(idx)
    except Exception as e:
        await channel.send("err: " + str(e)); return
    msg = "[Update] " + title + "\n" + VIEW_URL.format(idx) + "\n" + "-"*40 + "\n" + changes
    for i in range(0, len(msg), 1900):
        await channel.send(msg[i:i+1900])

@check_update.before_loop
async def before_check():
    await bot.wait_until_ready()

@bot.command(name="월드버프")
async def cmd_world_buff(ctx):
    async with ctx.typing():
        try:
            idx, title = get_latest_post()
            changes = get_world_buff(idx)
        except Exception as e:
            await ctx.send("err: " + str(e)); return
    msg = "[Update] " + title + "\n" + VIEW_URL.format(idx) + "\n" + "-"*40 + "\n" + changes
    for i in range(0, len(msg), 1900):
        await ctx.send(msg[i:i+1900])

bot.run(TOKEN)
