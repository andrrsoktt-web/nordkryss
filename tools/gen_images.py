"""Generate Nordkryss illustrations with the xAI image API.
Key comes from env XAI_API_KEY (GitHub Secret). Writes img/<id>.webp; skips existing files."""
import os, sys, json, base64, io, time, urllib.request
from PIL import Image

KEY=os.environ.get('XAI_API_KEY','').strip()
if not KEY: sys.exit('XAI_API_KEY is not set')
BASE='https://api.x.ai/v1'
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT=os.path.join(ROOT,'img'); os.makedirs(OUT,exist_ok=True)
items=json.load(open(os.path.join(ROOT,'tools','concepts.json')))
only=set(sys.argv[1:])

def req(path,body=None):
    r=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body else None,
        headers={'Authorization':'Bearer '+KEY,'Content-Type':'application/json'})
    with urllib.request.urlopen(r,timeout=180) as f: return json.load(f)

def pick_model():
    pref=os.environ.get('XAI_IMAGE_MODEL')
    if pref: return pref
    try:
        ms=req('/image-generation-models').get('models',[])
        ids=[m.get('id') for m in ms if m.get('id')]
        print('image models:',ids)
        for want in ('grok-imagine-image','grok-2-image'):
            for i in ids:
                if i.startswith(want): return i
        if ids: return ids[0]
    except Exception as e: print('model list failed:',e)
    return 'grok-2-image'

STYLE=("flat Scandinavian folk-art illustration, simple bold rounded shapes, the subject in its natural "
       "instantly recognizable colors, small Nordic folk ornament accents (tiny dots, leaves, hearts), "
       "subtle paper grain, friendly and clean, clearly readable at small icon size, single centered subject "
       "with generous empty margin, plain solid very light blue-grey background #E7EEF6, no text, no letters, "
       "no numbers, no border, no frame")
def prompt(it):
    k=it.get('kind')
    if k=='hero':
        return f"{it['subject']}. Wide landscape. {STYLE.replace('single centered subject with generous empty margin, plain solid very light blue-grey background #E7EEF6, ','')}"
    return f"{it['subject']}, {STYLE}"

def unbg(im, tol=34):
    """flood-fill the near-background colour from the borders into transparency"""
    im=im.convert('RGBA'); w,h=im.size; px=im.load()
    from collections import deque
    seen=set(); q=deque()
    for x in range(w): q.append((x,0)); q.append((x,h-1))
    for y in range(h): q.append((0,y)); q.append((w-1,y))
    ref=[px[2,2],px[w-3,2],px[2,h-3],px[w-3,h-3]]
    def near(c): return any(abs(c[0]-r[0])+abs(c[1]-r[1])+abs(c[2]-r[2])<tol for r in ref)
    while q:
        x,y=q.popleft()
        if (x,y) in seen or not(0<=x<w and 0<=y<h): continue
        seen.add((x,y)); c=px[x,y]
        if not near(c): continue
        px[x,y]=(c[0],c[1],c[2],0)
        q.extend(((x+1,y),(x-1,y),(x,y+1),(x,y-1)))
    return im

def save(it,raw):
    im=Image.open(io.BytesIO(raw))
    if it.get('kind')=='hero':
        im=im.convert('RGB'); im.thumbnail((1200,1200)); im.save(os.path.join(OUT,it['id']+'.webp'),'WEBP',quality=80); return
    im=im.convert('RGB'); s=min(im.size); l=(im.width-s)//2; t=(im.height-s)//2
    im=im.crop((l,t,l+s,t+s)).resize((384,384),Image.LANCZOS)
    im=unbg(im)
    bb=im.getbbox()
    if bb:
        im=im.crop(bb); side=int(max(im.size)*1.08)
        c=Image.new('RGBA',(side,side),(0,0,0,0)); c.paste(im,((side-im.width)//2,(side-im.height)//2)); im=c
    size=256 if it.get('kind')=='mascot' else 160
    im=im.resize((size,size),Image.LANCZOS)
    im.save(os.path.join(OUT,it['id']+'.webp'),'WEBP',quality=82,method=6)

model=pick_model(); print('model:',model)
done=fail=0
for it in items:
    if only and it['id'] not in only: continue
    path=os.path.join(OUT,it['id']+'.webp')
    if os.path.exists(path) and not only: continue
    for attempt in range(3):
        try:
            r=req('/images/generations',{'model':model,'prompt':prompt(it),'n':1,'response_format':'b64_json'})
            save(it,base64.b64decode(r['data'][0]['b64_json'])); done+=1; print('ok',it['id']); break
        except Exception as e:
            print('retry',it['id'],e); time.sleep(4*(attempt+1))
    else: fail+=1
    time.sleep(0.6)
print('generated',done,'failed',fail)
