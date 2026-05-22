#!/usr/bin/env python3
"""Build INNtelligence_Demo.html — a single self-contained file embedding
all 12 audio narrations + 12 screenshots as base64. Opens in any browser
with no server. Roughly 15-25 MB depending on image compression."""
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

STEPS = [
    {"id":1,  "title":"The Water Festival Alert",       "subtitle":"INNtelligence detects your biggest opportunities automatically",      "caption":"57 days to Water Festival — no premium applied yet"},
    {"id":2,  "title":"The 90-Day Rate Calendar",       "subtitle":"Every room, every day, every recommendation in one view",             "caption":"363 pending recommendations · Gold = festival dates"},
    {"id":3,  "title":"Plain-English Reasoning",        "subtitle":"No black box — every recommendation explains itself",                 "caption":"Demand 92/100 · Cuthbert SOLD OUT · $136 boutique premium"},
    {"id":4,  "title":"One Click — Seven Channels",     "subtitle":"Rate published to 7 OTAs in 2.3 seconds",                             "caption":"Booking.com · Expedia · Airbnb · VRBO · Hotels.com · Trip.com · Agoda"},
    {"id":5,  "title":"Approve All + Autopilot",        "subtitle":"363 recommendations across 90 days — one click",                      "caption":"Autopilot runs within your guardrails automatically every morning"},
    {"id":6,  "title":"Competitive Intelligence",       "subtitle":"39 properties monitored · Boutique inns only · STRs excluded",        "caption":"Cuthbert SOLD OUT $560 · Rhett SOLD OUT $510 · You: premium alternative"},
    {"id":7,  "title":"F&B Yield Management",           "subtitle":"The only platform that prices your restaurant and bar",               "caption":"Tue/Wed amber = yield gap · $24,000 annual opportunity identified"},
    {"id":8,  "title":"Guest CRM",                      "subtitle":"Know every guest · Draft campaigns automatically",                    "caption":"Margaret Whitfield · 6 stays · $7,250 revenue · Campaign ready"},
    {"id":9,  "title":"Documented ROI",                 "subtitle":"8.7× return on subscription — every win listed by date",             "caption":"$6,080 value · $699 cost · 8.7× ROI · Documented, not estimated"},
    {"id":10, "title":"Package Intelligence",           "subtitle":"20 package types with AI pricing and conversion data",                "caption":"Anniversary Package · 71% of boutique inns offer it · $4,095/month"},
    {"id":11, "title":"Always in Your Pocket",          "subtitle":"Progressive web app · No download · iOS and Android",                "caption":"Approve rates from the inn's front porch · Full dashboard on your phone"},
    {"id":12, "title":"Why I Built INNtelligence",      "subtitle":"Built by an innkeeper, for innkeepers",                              "caption":"14-day free trial · No credit card · Personal onboarding from Jim"},
]


def encode_image(path: Path) -> tuple[str, str]:
    if not path.exists():
        return "", "image/png"
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
            return base64.b64encode(buf.getvalue()).decode(), "image/jpeg"
        except Exception:
            pass
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode(), "image/png"


def encode_audio(path: Path) -> str:
    if not path.exists():
        return ""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def main() -> int:
    print("INNtelligence Standalone Demo Builder")
    print("=" * 50)

    missing_screens = sum(1 for i in range(1, 13)
                          if not (SCREENSHOTS / f"step-{i:02d}.png").exists())
    missing_audio   = sum(1 for i in range(1, 13)
                          if not (AUDIO / f"step-{i:02d}.mp3").exists())
    if missing_screens:
        print(f"⚠ {missing_screens} screenshot(s) missing — run capture_screenshots.py")
    if missing_audio:
        print(f"⚠ {missing_audio} audio file(s) missing — run generate_demo_audio.py")
    if not HAS_PIL:
        print("⚠ Pillow not installed — images embedded uncompressed (larger file)")

    print("\nEncoding files…")
    steps_data: list[dict] = []
    total_bytes = 0
    for s in STEPS:
        i = s["id"]
        img_data, img_mime = encode_image(SCREENSHOTS / f"step-{i:02d}.png")
        audio_data         = encode_audio(AUDIO / f"step-{i:02d}.mp3")
        img_kb   = len(img_data)   * 3 // 4 // 1024
        audio_kb = len(audio_data) * 3 // 4 // 1024
        total_bytes += img_kb * 1024 + audio_kb * 1024
        print(f"  Step {i:2d}: img={img_kb:>4}KB  audio={audio_kb:>5}KB")
        steps_data.append({
            **s,
            "img":   f"data:{img_mime};base64,{img_data}" if img_data else "",
            "audio": f"data:audio/mpeg;base64,{audio_data}" if audio_data else "",
        })
    print(f"\nTotal embedded: {total_bytes / 1024 / 1024:.1f} MB")

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
.screenshot{width:100%;height:100%;object-fit:contain;object-position:top center;display:block;transition:opacity 0.4s;}
.step-info{position:absolute;bottom:0;left:0;right:0;background:linear-gradient(transparent,rgba(15,39,68,0.97) 40%);padding:60px 32px 24px;pointer-events:none;}
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
.captions{position:absolute;bottom:140px;left:50%;transform:translateX(-50%);background:rgba(0,0,0,0.88);color:white;padding:12px 24px;border-radius:8px;max-width:680px;font-size:14px;line-height:1.6;text-align:center;display:none;pointer-events:none;}
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
  <div class="headline">22-Minute Interactive Demo</div>
  <div class="body-text">A complete walkthrough of INNtelligence — rate recommendations, competitive intelligence, F&amp;B yield, guest CRM, and ROI reporting. Click through each step at your own pace.</div>
  <button class="btn-gold" onclick="startDemo()">&#9654; Start Demo</button>
  <button class="btn-outline" onclick="window.open('https://app.graciouscollection.com/pricing','_blank')">Skip to pricing &rarr;</button>
  <div style="margin-top:24px;font-size:12px;color:#4B5563;">Enable sound for the best experience. Captions available when muted.</div>
</div>

<div id="demo">
  <div class="topbar">DEMO — INNtelligence for Anchorage 1770 Inn, Beaufort SC
    <button class="topbar-exit" onclick="exitDemo()">Exit</button>
  </div>
  <div class="stage">
    <img id="ss" class="screenshot" src="" alt="">
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
let cur=0,paused=false,muted=false,timer=null;
const aud=document.getElementById('aud');

function buildDots(){
  document.getElementById('pdots').innerHTML=
    STEPS.map(function(_,i){return '<div class="dot" id="d'+i+'" onclick="jumpTo('+i+')"></div>';}).join('');
}

function showStep(i){
  if(timer){clearTimeout(timer);timer=null;}
  var s=STEPS[i];
  if(!s){showComplete();return;}

  var img=document.getElementById('ss');
  img.style.opacity='0.7';
  if(s.img){img.src=s.img;img.onload=function(){img.style.opacity='1';};}

  document.getElementById('snum').textContent='STEP '+(i+1)+' OF '+STEPS.length;
  document.getElementById('stitle').textContent=s.title;
  document.getElementById('ssub').textContent=s.subtitle;
  document.getElementById('scap').textContent=s.caption;

  var pct=Math.round((i+1)/STEPS.length*100);
  document.getElementById('pfill').style.width=pct+'%';
  document.getElementById('plabel').textContent='Step '+(i+1)+' of '+STEPS.length;
  document.getElementById('ppct').textContent=pct+'%';
  document.querySelectorAll('.dot').forEach(function(d,j){
    d.className='dot'+(j<i?' done':j===i?' cur':'');
  });
  document.getElementById('prevbtn').style.opacity=i===0?'0.3':'1';

  var caps=document.getElementById('caps');
  if(muted){
    aud.pause();
    caps.textContent=s.subtitle+' — '+s.caption;
    caps.classList.add('on');
    timer=setTimeout(next,8000);
  } else if(s.audio){
    caps.classList.remove('on');
    aud.src=s.audio;
    aud.play().catch(function(){});
    aud.onended=function(){if(!paused){timer=setTimeout(next,1500);}};
  }
}

function next(){
  if(timer){clearTimeout(timer);timer=null;}
  aud.pause();aud.currentTime=0;
  if(cur<STEPS.length-1){cur++;showStep(cur);}
  else showComplete();
}
function prev(){
  if(timer){clearTimeout(timer);timer=null;}
  aud.pause();aud.currentTime=0;
  if(cur>0){cur--;showStep(cur);}
}
function jumpTo(i){
  if(timer){clearTimeout(timer);timer=null;}
  aud.pause();aud.currentTime=0;
  cur=i;showStep(cur);
}
function togglePause(){
  paused=!paused;
  var btn=document.getElementById('pausebtn');
  if(paused){aud.pause();if(timer){clearTimeout(timer);timer=null;}btn.innerHTML='&#9654;';}
  else{aud.play().catch(function(){});btn.innerHTML='&#9646;&#9646;';}
}
function toggleMute(){
  muted=!muted;
  var btn=document.getElementById('mutebtn');
  var caps=document.getElementById('caps');
  if(muted){
    aud.pause();aud.currentTime=0;
    btn.innerHTML='&#128263;';
    var s=STEPS[cur];
    caps.textContent=s.subtitle+' — '+s.caption;
    caps.classList.add('on');
    if(!timer)timer=setTimeout(next,8000);
  } else {
    btn.innerHTML='&#128266;';
    caps.classList.remove('on');
    if(timer){clearTimeout(timer);timer=null;}
    var s=STEPS[cur];
    if(s.audio){
      aud.src=s.audio;
      aud.play().catch(function(){});
      aud.onended=function(){if(!paused)timer=setTimeout(next,1500);};
    }
  }
}
function startDemo(){
  document.getElementById('entry').style.display='none';
  document.getElementById('demo').classList.add('active');
  buildDots();cur=0;showStep(0);
}
function exitDemo(){
  aud.pause();if(timer)clearTimeout(timer);
  document.getElementById('demo').classList.remove('active');
  document.getElementById('entry').style.display='flex';
}
function showComplete(){
  aud.pause();if(timer)clearTimeout(timer);
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
    print( "To share: email the file, drop it in Google Drive, or host as a static asset")
    print( "Controls: → or Space = next · ← = prev · M = mute · Esc = exit · click dots to jump")
    return 0


if __name__ == "__main__":
    sys.exit(main())
