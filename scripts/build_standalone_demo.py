#!/usr/bin/env python3
"""Build INNtelligence_Demo.html — a single self-contained file embedding
all 12 audio narrations + 17 screenshots (12 base + 5 "after") as base64.
Opens in any browser with no server. Roughly 25-35 MB.

Each action step (2/3/4/6/8) has:
  - a "before" image shown while the narrator sets up the click
  - target percentage coordinates (x%, y%) on the screenshot for where
    the animated cursor should land
  - delayMs from audio start to begin the cursor animation
  - an "after" image that crossfades in when the cursor clicks

Step 3 uses step-02-after as its "before" because the drawer is still
open from step 2's narrative click."""
from __future__ import annotations

import base64
import io
import json
import sys
from pathlib import Path

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

ROOT        = Path(__file__).resolve().parent.parent
SCREENSHOTS = ROOT / "scripts" / "demo-screenshots"
AUDIO       = ROOT / "dashboard" / "public" / "demo-audio"
OUTPUT      = ROOT / "INNtelligence_Demo.html"

# action.targetX / targetY are percentage-based coords on the BEFORE image —
# they tell the standalone player where the animated cursor should land,
# independent of any real DOM. Estimated against the 1440x900 captures.
STEPS = [
    {"id":1,  "img":"step-01.png", "title":"The Water Festival Alert",       "subtitle":"INNtelligence detects your biggest opportunities automatically",      "caption":"57 days to Water Festival — no premium applied yet"},
    {"id":2,  "img":"step-02.png", "title":"The 90-Day Rate Calendar",       "subtitle":"Every room, every day, every recommendation in one view",             "caption":"363 pending recommendations · Gold = festival dates",
     "action":{"delayMs":4000, "targetX":68, "targetY":40, "afterImg":"step-02-after.png"}},
    {"id":3,  "img":"step-02-after.png", "title":"Plain-English Reasoning",  "subtitle":"No black box — every recommendation explains itself",                 "caption":"Demand 92/100 · Cuthbert SOLD OUT · $136 boutique premium",
     "action":{"delayMs":6000, "targetX":86, "targetY":62, "afterImg":"step-03-after.png"}},
    {"id":4,  "img":"step-04.png", "title":"One Click — Seven Channels",     "subtitle":"Rate published to 7 OTAs in 2.3 seconds",                             "caption":"Booking.com · Expedia · Airbnb · VRBO · Hotels.com · Trip.com · Agoda",
     "action":{"delayMs":3000, "targetX":92, "targetY":13, "afterImg":"step-04-after.png"}},
    {"id":5,  "img":"step-04-after.png", "title":"Approve All + Autopilot",  "subtitle":"363 recommendations across 90 days — one click",                      "caption":"Autopilot runs within your guardrails automatically every morning"},
    {"id":6,  "img":"step-06.png", "title":"Competitive Intelligence",       "subtitle":"39 properties monitored · Boutique inns only · STRs excluded",        "caption":"Cuthbert SOLD OUT $560 · Rhett SOLD OUT $510 · You: premium alternative",
     "action":{"delayMs":3000, "targetX":24, "targetY":21, "afterImg":"step-06-after.png"}},
    {"id":7,  "img":"step-07.png", "title":"F&B Yield Management",           "subtitle":"The only platform that prices your restaurant and bar",               "caption":"Tue/Wed amber = yield gap · $24,000 annual opportunity identified"},
    {"id":8,  "img":"step-08.png", "title":"Guest CRM",                      "subtitle":"Know every guest · Draft campaigns automatically",                    "caption":"Margaret Whitfield · 6 stays · $7,250 revenue · Campaign ready",
     "action":{"delayMs":4000, "targetX":38, "targetY":52, "afterImg":"step-08-after.png"}},
    {"id":9,  "img":"step-09.png", "title":"Documented ROI",                 "subtitle":"8.7× return on subscription — every win listed by date",             "caption":"$6,080 value · $699 cost · 8.7× ROI · Documented, not estimated"},
    {"id":10, "img":"step-10.png", "title":"Package Intelligence",           "subtitle":"20 package types with AI pricing and conversion data",                "caption":"Anniversary Package · 71% of boutique inns offer it · $4,095/month"},
    {"id":11, "img":"step-11.png", "title":"Always in Your Pocket",          "subtitle":"Progressive web app · No download · iOS and Android",                "caption":"Approve rates from the inn's front porch · Full dashboard on your phone"},
    {"id":12, "img":"step-12.png", "title":"Why I Built INNtelligence",      "subtitle":"Built by an innkeeper, for innkeepers",                              "caption":"14-day free trial · No credit card · Personal onboarding from Jim"},
]


def encode_image(name: str) -> str:
    path = SCREENSHOTS / name
    if not path.exists():
        return ""
    if HAS_PIL:
        try:
            img = Image.open(path)
            if img.width > 1280:
                ratio = 1280 / img.width
                img = img.resize((1280, int(img.height * ratio)), Image.LANCZOS)
            if img.mode == "RGBA":
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80, optimize=True)
            return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        except Exception:
            pass
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def encode_audio(idx: int) -> str:
    path = AUDIO / f"step-{idx:02d}.mp3"
    if not path.exists():
        return ""
    return "data:audio/mpeg;base64," + base64.b64encode(path.read_bytes()).decode()


def main() -> int:
    print("INNtelligence Standalone Demo Builder (self-driving cursor edition)")
    print("=" * 70)
    if not HAS_PIL:
        print("⚠ Pillow not installed — images embedded uncompressed (larger file)")

    print("\nEncoding files…")
    # Cache so duplicate image references (step-02-after used as both step-02's
    # after and step-03's before) aren't encoded twice.
    img_cache: dict[str, str] = {}
    def cached_img(name: str) -> str:
        if name not in img_cache:
            img_cache[name] = encode_image(name)
        return img_cache[name]

    steps_data: list[dict] = []
    total = 0
    for s in STEPS:
        i = s["id"]
        img_data   = cached_img(s["img"])
        audio_data = encode_audio(i)
        item = {
            "id": i, "title": s["title"], "subtitle": s["subtitle"],
            "caption": s["caption"], "img": img_data, "audio": audio_data,
        }
        sizes = f"img={len(img_data)*3//4//1024:>4}KB  audio={len(audio_data)*3//4//1024:>5}KB"
        total += len(img_data)*3//4 + len(audio_data)*3//4

        if "action" in s:
            after_data = cached_img(s["action"]["afterImg"])
            total += len(after_data)*3//4
            item["action"] = {
                "delayMs": s["action"]["delayMs"],
                "targetX": s["action"]["targetX"],
                "targetY": s["action"]["targetY"],
                "afterImg": after_data,
            }
            sizes += f"  after={len(after_data)*3//4//1024:>4}KB"

        print(f"  Step {i:2d}: {sizes}")
        steps_data.append(item)

    print(f"\nTotal embedded: {total / 1024 / 1024:.1f} MB")

    steps_json = json.dumps(steps_data)

    head = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>INNtelligence — Revenue Intelligence for Boutique Inns</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{background:#0F2744;font-family:'Inter',system-ui,sans-serif;color:white;overflow:hidden;height:100vh;}
#entry{position:fixed;inset:0;background:linear-gradient(135deg,#1A3A5C,#0F2744);display:flex;align-items:center;justify-content:center;flex-direction:column;text-align:center;padding:40px;z-index:100;}
.logo{font-family:'Playfair Display',Georgia,serif;font-size:clamp(48px,8vw,80px);font-weight:700;color:#A07830;margin-bottom:8px;}
.byline{font-size:16px;color:#6B7280;margin-bottom:48px;}
.headline{font-size:clamp(18px,3vw,26px);font-weight:600;margin-bottom:12px;}
.body-text{font-size:15px;color:#9CA3AF;max-width:520px;margin:0 auto 48px;line-height:1.6;}
.btn-gold{background:#A07830;color:#1A3A5C;border:none;padding:18px 56px;border-radius:8px;font-size:18px;font-weight:700;cursor:pointer;font-family:'Playfair Display',Georgia,serif;display:block;width:320px;margin:0 auto 12px;transition:background 0.2s;}
.btn-gold:hover{background:#C9A84C;}
.btn-outline{background:transparent;color:#6B7280;border:1px solid #374151;padding:12px 32px;border-radius:8px;font-size:14px;cursor:pointer;display:block;width:320px;margin:0 auto;}
#demo{position:fixed;inset:0;display:none;flex-direction:column;}
#demo.active{display:flex;}
.topbar{background:#A07830;color:#1A3A5C;padding:6px 20px;font-size:12px;font-weight:700;text-align:center;flex-shrink:0;letter-spacing:0.5px;position:relative;}
.topbar-exit{position:absolute;right:12px;top:50%;transform:translateY(-50%);background:none;border:1px solid rgba(26,58,92,0.4);color:#1A3A5C;padding:2px 10px;border-radius:4px;font-size:12px;cursor:pointer;}
.stage{flex:1;position:relative;overflow:hidden;background:#0F2744;}
.shot{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;object-position:top center;transition:opacity 0.45s ease-out;}
.shot.fade-out{opacity:0;}
.cursor-svg{position:absolute;width:34px;height:34px;left:50%;top:50%;margin-left:-17px;margin-top:-17px;opacity:0;pointer-events:none;z-index:20;}
.cursor-svg.visible{opacity:1;}
.cursor-svg.moving{transition:left 1.2s cubic-bezier(0.4,0,0.2,1), top 1.2s cubic-bezier(0.4,0,0.2,1), opacity 0.25s ease-out;}
.cursor-svg.fading{transition:opacity 0.35s ease-out;opacity:0;}
.ring{position:absolute;left:50%;top:50%;width:34px;height:34px;margin-left:-17px;margin-top:-17px;border:2px solid #A07830;border-radius:50%;opacity:0;pointer-events:none;z-index:19;}
.ring.pulse{animation:cursor-ring 0.8s ease-out forwards;}
@keyframes cursor-ring{0%{transform:scale(0.6);opacity:0.85;}100%{transform:scale(2.1);opacity:0;}}
.step-info{position:absolute;bottom:0;left:0;right:0;background:linear-gradient(transparent,rgba(15,39,68,0.97) 40%);padding:60px 32px 24px;pointer-events:none;z-index:15;}
.step-num{font-size:11px;color:#A07830;font-weight:600;letter-spacing:2px;text-transform:uppercase;margin-bottom:6px;}
.step-title{font-family:'Playfair Display',Georgia,serif;font-size:clamp(20px,3vw,30px);font-weight:700;margin-bottom:6px;}
.step-sub{font-size:14px;color:#9CA3AF;margin-bottom:6px;}
.step-cap{font-size:12px;color:#A07830;font-weight:500;}
.controls{background:rgba(15,39,68,0.98);padding:10px 20px;display:flex;align-items:center;gap:12px;border-top:1px solid rgba(160,120,48,0.2);flex-shrink:0;}
.cbtn{background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.12);color:white;border-radius:6px;padding:7px 14px;font-size:15px;cursor:pointer;min-width:40px;transition:background 0.15s;}
.cbtn:hover{background:rgba(255,255,255,0.15);}
.cbtn.gold{background:#A07830;border-color:#A07830;color:#1A3A5C;font-weight:700;}
.cbtn.gold:hover{background:#C9A84C;}
.prog{flex:1;margin:0 8px;}
.prog-label{display:flex;justify-content:space-between;font-size:10px;color:#6B7280;margin-bottom:4px;}
.prog-bg{height:3px;background:rgba(255,255,255,0.1);border-radius:2px;overflow:hidden;margin-bottom:6px;}
.prog-fill{height:100%;background:#A07830;transition:width 0.4s;}
.dots{display:flex;gap:4px;justify-content:center;}
.dot{width:5px;height:5px;border-radius:50%;background:rgba(255,255,255,0.15);transition:background 0.3s;cursor:pointer;}
.dot.done{background:#A07830;}
.dot.cur{background:#F0D080;}
.captions{position:absolute;bottom:140px;left:50%;transform:translateX(-50%);background:rgba(0,0,0,0.88);color:white;padding:12px 24px;border-radius:8px;max-width:680px;font-size:14px;line-height:1.6;text-align:center;display:none;pointer-events:none;z-index:18;}
.captions.on{display:block;}
#complete{position:fixed;inset:0;background:rgba(0,0,0,0.88);display:none;align-items:center;justify-content:center;z-index:200;}
#complete.on{display:flex;}
.card{background:white;border-radius:16px;padding:48px 40px;max-width:480px;width:90%;text-align:center;}
.card-title{font-family:'Playfair Display',Georgia,serif;font-size:28px;font-weight:700;color:#1A3A5C;margin-bottom:12px;}
.card-body{color:#6B7280;margin-bottom:32px;font-size:15px;line-height:1.5;}
.cinput{width:100%;padding:12px 16px;margin-bottom:12px;border:1px solid #E8E4DC;border-radius:8px;font-size:15px;font-family:Inter,sans-serif;}
.ccta{background:#A07830;color:white;border:none;padding:16px;width:100%;border-radius:8px;font-size:17px;font-weight:700;cursor:pointer;font-family:'Playfair Display',Georgia,serif;margin-bottom:12px;}
.clink{display:block;color:#6B7280;font-size:13px;text-decoration:none;margin-bottom:8px;}
.crestart{background:none;border:none;color:#9CA3AF;font-size:12px;cursor:pointer;padding:4px;}
</style>
</head>
<body>
<div id="entry">
  <div class="logo">INNtelligence</div>
  <div class="byline">by The Gracious Collection</div>
  <div class="headline">22-Minute Guided Demo</div>
  <div class="body-text">A complete walkthrough of INNtelligence — rate recommendations, competitive intelligence, F&amp;B yield, guest CRM, and ROI reporting. Sit back and watch; the demo drives itself.</div>
  <button class="btn-gold" onclick="startDemo()">&#9654; Start Demo</button>
  <button class="btn-outline" onclick="window.open('https://app.graciouscollection.com/pricing','_blank')">Skip to pricing &rarr;</button>
  <div style="margin-top:24px;font-size:12px;color:#4B5563;">Enable sound for the best experience. Captions available when muted.</div>
</div>

<div id="demo">
  <div class="topbar">DEMO — INNtelligence for Anchorage 1770 Inn, Beaufort SC
    <button class="topbar-exit" onclick="exitDemo()">Exit</button>
  </div>
  <div class="stage" id="stage">
    <img id="shotA" class="shot" alt="">
    <img id="shotB" class="shot fade-out" alt="">
    <div class="ring" id="ring"></div>
    <svg class="cursor-svg" id="cursor" viewBox="0 0 34 34">
      <defs>
        <filter id="cshadow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur in="SourceAlpha" stdDeviation="2"/>
          <feOffset dx="0" dy="2" result="off"/>
          <feComponentTransfer><feFuncA type="linear" slope="0.55"/></feComponentTransfer>
          <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>
      <circle cx="13" cy="13" r="12" fill="#A07830" stroke="white" stroke-width="2.5" filter="url(#cshadow)"/>
      <polygon points="20,20 32,24 24,32" fill="#A07830" stroke="white" stroke-width="1.5" filter="url(#cshadow)"/>
    </svg>
    <div class="step-info">
      <div class="step-num" id="snum">STEP 1 OF 12</div>
      <div class="step-title" id="stitle"></div>
      <div class="step-sub" id="ssub"></div>
      <div class="step-cap" id="scap"></div>
    </div>
    <div class="captions" id="caps"></div>
  </div>
  <div class="controls">
    <button class="cbtn" onclick="prev()" id="prevbtn">&laquo;</button>
    <button class="cbtn" onclick="togglePause()" id="pausebtn">&#9646;&#9646;</button>
    <button class="cbtn gold" onclick="next()">&#9654; Next</button>
    <div class="prog">
      <div class="prog-label"><span id="plabel">Step 1 of 12</span><span id="ppct">8%</span></div>
      <div class="prog-bg"><div class="prog-fill" id="pfill" style="width:8%"></div></div>
      <div class="dots" id="pdots"></div>
    </div>
    <button class="cbtn" onclick="toggleMute()" id="mutebtn">&#128266;</button>
    <button class="cbtn" onclick="exitDemo()" style="font-size:12px;padding:7px 12px;">&times; Exit</button>
  </div>
</div>

<div id="complete">
  <div class="card">
    <div class="card-title">Ready to see INNtelligence<br>on your property?</div>
    <div class="card-body">14-day free trial. No credit card required.<br>Personal onboarding from Jim Williams — innkeeper and founder.</div>
    <input class="cinput" type="text" placeholder="Your property name">
    <input class="cinput" type="email" placeholder="Your email address">
    <button class="ccta" onclick="window.open('https://app.graciouscollection.com/pricing','_blank')">Start My Free Trial &rarr;</button>
    <a class="clink" href="mailto:jwilliams8559@gmail.com?subject=INNtelligence Demo - I want to learn more">Schedule a call with Jim &rarr;</a>
    <button class="crestart" onclick="restart()">Watch demo again</button>
  </div>
</div>

<audio id="aud" preload="auto"></audio>

<script>
const STEPS='''

    tail = r''';
let cur=0,paused=false,muted=false,timers=[],advanceTimer=null;
const aud=document.getElementById('aud');
const shotA=document.getElementById('shotA');
const shotB=document.getElementById('shotB');
const cursor=document.getElementById('cursor');
const ring=document.getElementById('ring');

let activeShot=shotA;
let bgShot=shotB;

function clearTimers(){timers.forEach(clearTimeout);timers=[];if(advanceTimer){clearTimeout(advanceTimer);advanceTimer=null;}}
function tm(fn,ms){const t=setTimeout(fn,ms);timers.push(t);return t;}

function setImage(src,crossfade){
  if(!crossfade){
    activeShot.src=src;activeShot.classList.remove('fade-out');
    bgShot.classList.add('fade-out');
    return;
  }
  bgShot.src=src;
  void bgShot.offsetWidth;
  bgShot.classList.remove('fade-out');
  activeShot.classList.add('fade-out');
  const tmp=activeShot;activeShot=bgShot;bgShot=tmp;
}

function resetCursor(){
  cursor.classList.remove('moving','fading','visible');
  cursor.style.left='50%';cursor.style.top='50%';
  ring.classList.remove('pulse');
}

function runAction(a){
  tm(()=>{
    resetCursor();
    cursor.classList.add('visible');
    requestAnimationFrame(()=>requestAnimationFrame(()=>{
      cursor.classList.add('moving');
      cursor.style.left=a.targetX+'%';
      cursor.style.top=a.targetY+'%';
    }));
    tm(()=>{
      ring.style.left=a.targetX+'%';
      ring.style.top=a.targetY+'%';
      ring.classList.remove('pulse');
      void ring.offsetWidth;
      ring.classList.add('pulse');
    },1200);
    tm(()=>{
      setImage(a.afterImg,true);
      cursor.classList.remove('visible');
      cursor.classList.add('fading');
    },1200+800);
  },a.delayMs);
}

function buildDots(){
  document.getElementById('pdots').innerHTML=
    STEPS.map(function(_,i){return '<div class="dot" id="d'+i+'" onclick="jumpTo('+i+')"></div>';}).join('');
}

function showStep(i){
  clearTimers();
  const s=STEPS[i];
  if(!s){showComplete();return;}

  resetCursor();
  setImage(s.img,false);

  document.getElementById('snum').textContent='STEP '+(i+1)+' OF '+STEPS.length;
  document.getElementById('stitle').textContent=s.title;
  document.getElementById('ssub').textContent=s.subtitle;
  document.getElementById('scap').textContent=s.caption;

  const pct=Math.round((i+1)/STEPS.length*100);
  document.getElementById('pfill').style.width=pct+'%';
  document.getElementById('plabel').textContent='Step '+(i+1)+' of '+STEPS.length;
  document.getElementById('ppct').textContent=pct+'%';
  document.querySelectorAll('.dot').forEach(function(d,j){
    d.className='dot'+(j<i?' done':j===i?' cur':'');
  });
  document.getElementById('prevbtn').style.opacity=i===0?'0.3':'1';

  const caps=document.getElementById('caps');
  if(muted){
    aud.pause();
    caps.textContent=s.subtitle+' — '+s.caption;
    caps.classList.add('on');
    if(s.action) runAction(s.action);
    advanceTimer=setTimeout(next,8000);
  } else if(s.audio){
    caps.classList.remove('on');
    aud.src=s.audio;
    aud.play().catch(function(){});
    if(s.action) runAction(s.action);
    aud.onended=function(){if(!paused) advanceTimer=setTimeout(next,1200);};
  } else {
    advanceTimer=setTimeout(next,4000);
  }
}

function next(){
  clearTimers();aud.pause();aud.currentTime=0;
  if(cur<STEPS.length-1){cur++;showStep(cur);}
  else showComplete();
}
function prev(){
  clearTimers();aud.pause();aud.currentTime=0;
  if(cur>0){cur--;showStep(cur);}
}
function jumpTo(i){
  clearTimers();aud.pause();aud.currentTime=0;
  cur=i;showStep(cur);
}
function togglePause(){
  paused=!paused;
  const btn=document.getElementById('pausebtn');
  if(paused){aud.pause();clearTimers();btn.innerHTML='&#9654;';}
  else{aud.play().catch(function(){});btn.innerHTML='&#9646;&#9646;';}
}
function toggleMute(){
  muted=!muted;
  const btn=document.getElementById('mutebtn');
  const caps=document.getElementById('caps');
  if(muted){
    aud.pause();aud.currentTime=0;
    btn.innerHTML='&#128263;';
    const s=STEPS[cur];
    caps.textContent=s.subtitle+' — '+s.caption;
    caps.classList.add('on');
    if(!advanceTimer) advanceTimer=setTimeout(next,8000);
  } else {
    btn.innerHTML='&#128266;';
    caps.classList.remove('on');
    clearTimers();
    const s=STEPS[cur];
    if(s.audio){
      aud.src=s.audio;
      aud.play().catch(function(){});
      aud.onended=function(){if(!paused) advanceTimer=setTimeout(next,1200);};
    }
  }
}
function startDemo(){
  document.getElementById('entry').style.display='none';
  document.getElementById('demo').classList.add('active');
  buildDots();cur=0;showStep(0);
}
function exitDemo(){
  aud.pause();clearTimers();
  document.getElementById('demo').classList.remove('active');
  document.getElementById('entry').style.display='flex';
}
function showComplete(){
  aud.pause();clearTimers();
  document.getElementById('complete').classList.add('on');
}
function restart(){
  document.getElementById('complete').classList.remove('on');
  cur=0;showStep(0);
}
document.addEventListener('keydown',function(e){
  if(e.key==='ArrowRight'||e.key===' ')next();
  if(e.key==='ArrowLeft')prev();
  if(e.key==='m'||e.key==='M')toggleMute();
  if(e.key==='Escape')exitDemo();
});
</script>
</body>
</html>'''

    OUTPUT.write_text(head + steps_json + tail, encoding="utf-8")
    size_mb = OUTPUT.stat().st_size / 1024 / 1024
    print(f"\n✓ Built: {OUTPUT.name} ({size_mb:.1f} MB)")
    print()
    print(f"To open:  open {OUTPUT.name}")
    print( "Self-driving: animated gold cursor moves to target, pauses, clicks, screenshot crossfades.")
    print( "Controls: → or Space = next · ← = prev · M = mute · Esc = exit · click dots to jump")
    return 0


if __name__ == "__main__":
    sys.exit(main())
