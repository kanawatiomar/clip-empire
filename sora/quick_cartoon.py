import os, time, requests
from pathlib import Path

env = Path(r"C:\Users\kanaw\.openclaw\workspace\ventures\clip_empire\.env")
if env.exists():
    for line in env.read_text().splitlines():
        if '=' in line and not line.strip().startswith('#'):
            k,v = line.split('=',1)
            os.environ.setdefault(k.strip(), v.strip())

key = os.environ.get('OPENAI_API_KEY')
assert key, 'missing OPENAI_API_KEY'
headers = {'Authorization': f'Bearer {key}', 'Content-Type':'application/json'}

prompt = "Colorful 2D cartoon animation style, cheerful fox character walking through a bright futuristic city with glowing signs, smooth camera pan, cinematic lighting, vertical frame, family friendly"

r = requests.post('https://api.openai.com/v1/videos', headers=headers, json={
    'model':'sora-2',
    'prompt':prompt,
    'size':'720x1280',
    'seconds':'8'
}, timeout=60)
print('submit', r.status_code)
print(r.text[:400])
r.raise_for_status()
vid = r.json()['id']
print('video_id', vid)

for i in range(60):
    s = requests.get(f'https://api.openai.com/v1/videos/{vid}', headers=headers, timeout=30)
    s.raise_for_status()
    data = s.json()
    print(i, data.get('status'), data.get('progress'))
    if data.get('status') == 'completed':
        break
    if data.get('status') in ('failed','cancelled'):
        raise RuntimeError(data)
    time.sleep(15)

out = Path(r"C:\Users\kanaw\.openclaw\workspace\ventures\clip_empire\sora\footage\prototype_cartoon_ep1_scene1.mp4")
out.parent.mkdir(parents=True, exist_ok=True)
with requests.get(f'https://api.openai.com/v1/videos/{vid}/content', headers=headers, stream=True, timeout=120) as d:
    d.raise_for_status()
    with open(out,'wb') as f:
        for c in d.iter_content(8192):
            if c: f.write(c)
print('saved', out, out.stat().st_size)
