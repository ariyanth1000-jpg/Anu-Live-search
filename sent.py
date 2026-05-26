import re
import asyncio
import os
from aiohttp import web
from telethon import TelegramClient

# ================= CONFIG =================

api_id = int(os.getenv("API_ID", "123456"))
api_hash = os.getenv("API_HASH", "your_api_hash")

SESSION_NAME = "tamim_session"

GROUP_IDS = [
    "-1003771161345",
    "-1002531902737",
    "-1002567258773",
    "-1002652123574",
    "-1003861246919",
    "-1003435291410",
    "-1003775658194",
    "-1002898987582",
    "-1003463811076",
    "-1003357916577",
]

LIMIT = 100
ACTIVE_GROUP = GROUP_IDS[0]

client = TelegramClient(SESSION_NAME, api_id, api_hash)

CACHE = {gid: [] for gid in GROUP_IDS}

# ================= HELPERS =================

def clean_number(x):
    return re.sub(r'[^0-9Xx*]', '', x or '')

def is_invalid_number(text):
    return bool(
        re.search(r'\d{4}-\d{2}-\d{2}', text) or
        re.search(r'\d{2}:\d{2}:\d{2}', text)
    )

def extract_number(text):

    text = text.replace("\n", " ")

    matches = re.findall(r'[#\+\dXx*][\dXx*#\-\s]{7,}', text)

    for m in matches:

        if is_invalid_number(m):
            continue

        pure = re.sub(r'[^0-9Xx*]', '', m)

        if len(re.findall(r'[\dXx*]', pure)) >= 10:
            return m.strip().strip("#")

    return None

def extract_otp(text):
    m = re.findall(r'\b\d{5,8}\b', text)
    return m[-1] if m else ""

def parse(text):

    n = extract_number(text)
    if not n:
        return None

    return {"number": n, "otp": extract_otp(text)}

# ================= CACHE =================

async def build_cache(gid):

    items = []
    seen = set()

    try:
        async for msg in client.iter_messages(int(gid), limit=LIMIT):

            text = (msg.message or "") + "\n" + (msg.raw_text or "")

            item = parse(text)

            if not item:
                continue

            key = clean_number(item["number"])

            if key in seen:
                continue

            seen.add(key)
            items.append(item)

    except Exception as e:
        print("CACHE ERROR:", e)

    CACHE[gid] = items

# ================= BACKGROUND =================

async def background_refresh():
    while True:
        await build_cache(ACTIVE_GROUP)
        await asyncio.sleep(1)

# ================= API =================

async def data(request):
    gid = request.query.get("gid")
    return web.json_response({"items": CACHE.get(gid, [])})

async def set_active(request):
    global ACTIVE_GROUP
    gid = request.query.get("gid")

    if gid in GROUP_IDS:
        ACTIVE_GROUP = gid

    return web.json_response({"ok": True})

# ================= HTML =================

HTML = """

<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>LIVE OTP</title>

<style>

body{
margin:0;
background:#0f172a;
color:white;
font-family:sans-serif;
}

.header{
text-align:center;
padding:14px;
font-size:22px;
font-weight:bold;
}

select{
width:95%;
padding:12px;
margin:5px;
border-radius:10px;
font-size:16px;
}

.searchbox{
display:flex;
padding:5px;
gap:5px;
}

textarea{
flex:1;
height:120px;
padding:10px;
border-radius:10px;
border:none;
resize:none;
font-size:16px;
outline:none;
}

button{
background:red;
color:white;
border:none;
padding:10px;
border-radius:10px;
font-weight:bold;
cursor:pointer;
}

.item{
margin:6px;
padding:10px;
border-radius:10px;
border:2px solid red;
display:flex;
gap:10px;
align-items:center;
}

.num{
flex:2;
background:#3b82f6;
color:black;
padding:10px;
border-radius:10px;
text-align:center;
font-weight:bold;
cursor:pointer;
word-break:break-word;
}

.otp{
flex:1;
background:#4ade80;
color:black;
padding:10px;
border-radius:10px;
text-align:center;
font-weight:bold;
cursor:pointer;
}

.pending{
flex:1;
background:#facc15;
color:black;
padding:10px;
border-radius:10px;
text-align:center;
font-weight:bold;
}

.toast{
position:fixed;
top:20px;
left:50%;
transform:translateX(-50%);
background:#22c55e;
color:black;
padding:10px 20px;
border-radius:10px;
display:none;
font-weight:bold;
z-index:9999;
}

</style>

</head>

<body>

<div class="header">🖥️ TA LIVE CODE 📊</div>

<center>
<select id="gid" onchange="changeGroup()"></select>
</center>

<div class="searchbox">

<textarea id="search"
placeholder=" ⛶ Paste Numbers...⎙"
oninput="saveSearch(); filter();"></textarea>

<button onclick="clearSearch()">Clear</button>

</div>

<div id="data"></div>

<div id="toast" class="toast"> ⧉ COPIED ✅ </div>

<script>

let all = [];
let gid = "";

// ================= RULES (EDITABLE) =================

const RULES = {

    "-1003771161345": { start: 3, end: 2 },
    "-1002531902737": { start: 4, end: 4 },
    "-1002567258773": { start: 2, end: 4 },
    "-1002652123574": { start: 5, end: 3 },
    "-1003861246919": { start: 2, end: 5 },
    "-1003435291410": { start: 0, end: 0 },
    "-1003775658194": { start: 0, end: 0 },
    "-1002898987582": { start: 0, end: 0 },
    "-1003463811076": { start: 0, end: 0 },
    "-1003357916577": { start: 0, end: 0 }

};

// ================= STORAGE (IMPORTANT) =================

function saveSearch(){
    localStorage.setItem("search_box", document.getElementById("search").value);
}

function loadSearch(){
    let v = localStorage.getItem("search_box");
    if(v !== null){
        document.getElementById("search").value = v;
    }
}

// ================= NORMALIZE =================

function normalize(x){
    return (x||"").replace(/[^0-9Xx*]/g,'');
}

// ================= MATCH =================

function match(num, query){

    let n = normalize(num);
    let q = normalize(query);

    if(!q) return false;

    let rule = RULES[gid];

    if(!rule) return n.includes(q);

    if(rule.start === 0 && rule.end === 0){
        return n.includes(q);
    }

    let okStart = rule.start ? n.slice(0, rule.start) === q.slice(0, rule.start) : true;
    let okEnd = rule.end ? n.slice(-rule.end) === q.slice(-rule.end) : true;

    return okStart && okEnd;
}

// ================= TOAST =================

function showToast(){
    let t = document.getElementById("toast");
    t.style.display = "block";
    setTimeout(()=>t.style.display="none",1000);
}

// ================= COPY =================

function copyText(t){
    if(!t) return;
    navigator.clipboard?.writeText(t);
    showToast();
}

// ================= RENDER =================

function render(){

    let raw = document.getElementById("search").value;
    let queries = raw.split(/\s+/).filter(x=>x.trim());

    let html = "";

    if(queries.length === 0){

        all.forEach(i=>{
            html += `
            <div class="item">

                <div class="num" onclick="copyText('${i.number}')">${i.number}</div>

                <div class="otp" onclick="copyText('${i.otp || ''}')">
                    ${i.otp || "NO OTP"}
                </div>

            </div>`;
        });

    }else{

        queries.forEach(q=>{

            let found = all.find(i=>match(i.number,q));

            if(found){

                html += `
                <div class="item">

                    <div class="num" onclick="copyText('${found.number}')">${found.number}</div>

                    <div class="otp" onclick="copyText('${found.otp || ''}')">
                        ${found.otp || "NO OTP"}
                    </div>

                </div>`;

            }else{

                html += `
                <div class="item">

                    <div class="num" onclick="copyText('${q}')">${q}</div>

                    <div class="pending">Waiting🌀</div>

                </div>`;
            }

        });

    }

    document.getElementById("data").innerHTML = html;
}

// ================= FILTER =================

function filter(){
    render();
}

// ================= CLEAR =================

function clearSearch(){
    document.getElementById("search").value = "";
    localStorage.removeItem("search_box");
    render();
}

// ================= LOAD =================

async function load(){

    let r = await fetch("/data?gid="+gid);
    let d = await r.json();

    all = d.items || [];
    render();
}

// ================= GROUP =================

async function changeGroup(){

    gid = document.getElementById("gid").value;

    localStorage.setItem("selectedGroup", gid);

    await fetch("/set-active?gid="+gid);

    load();
}

// ================= INIT =================

function init(){

    let groups = %GROUPS%;

    let sel = document.getElementById("gid");

    groups.forEach((g,i)=>{
        let o = document.createElement("option");
        o.value = g;
        o.innerText = "TA Range ID " + String(i+1).padStart(2,"0");
        sel.appendChild(o);
    });

    gid = localStorage.getItem("selectedGroup") || groups[0];

    sel.value = gid;

    loadSearch();   // restore search
    changeGroup();

    setInterval(load,1000);
}

init();

</script>

</body>
</html>

"""

# ================= START =================

async def main():

    await client.start()

    app = web.Application()

    html = HTML.replace("%GROUPS%", str(GROUP_IDS))

    app.router.add_get("/", lambda r: web.Response(text=html, content_type="text/html"))
    app.router.add_get("/data", data)
    app.router.add_get("/set-active", set_active)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080)))
    await site.start()

    asyncio.create_task(background_refresh())

    print("RUNNING...")

    while True:
        await asyncio.sleep(10)

asyncio.run(main())
