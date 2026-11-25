# صوت سلمى المصري لكل الكلام العربي عبر Azure TTS — مفتاح Azure من GitHub Secrets
# بيسجّل الجمل الناقصة بس، ويحفظ التقدم كل شوية، علشان الخطة المجانية (20 طلب في الدقيقة)
import json, os, sys, time, base64, subprocess, urllib.request, urllib.error
from xml.sax.saxutils import escape

KEY = os.environ.get('AZURE_KEY', '').strip()
REGION = os.environ.get('AZURE_REGION', '').strip().lower().replace(' ', '')
VOICE = 'ar-EG-SalmaNeural'  # تثبيت صوت سلمى المصري فقط
TEXTS = sys.argv[1] if len(sys.argv) > 1 else 'ar-texts.json'
OUT = 'voix-a-salma.json'
BUDGET = float(os.environ.get('BUDGET_MIN', '330')) * 60   # أقصى وقت للتشغيل الواحد
SAVE_EVERY = int(os.environ.get('SAVE_EVERY', '600'))

if not KEY or not REGION:
    print('AZURE_KEY / AZURE_REGION مش موجودين في Secrets'); sys.exit(1)

T = json.load(open(TEXTS, encoding='utf-8'))
B = json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) else {}
todo = [t for t in T if t not in B]
print(f'texts {len(T)}  done {len(B)}  todo {len(todo)}')

URL = os.environ.get('AZURE_URL') or f'https://{REGION}.tts.speech.microsoft.com/cognitiveservices/v1'
FIX={'و':'وَاو','ا':'أَلِف','أ':'أَلِف','ألف':'أَلِف','ة':'تَاء مَرْبُوطَة'}
def synth(text):
    text=FIX.get(text,text)
    ssml = (f"<speak version='1.0' xml:lang='ar-EG'><voice name='{VOICE}'>"
            f"<prosody rate='-25%'>{escape(text)}</prosody></voice></speak>")
    req = urllib.request.Request(URL, data=ssml.encode('utf-8'), method='POST', headers={
        'Ocp-Apim-Subscription-Key': KEY,
        'Content-Type': 'application/ssml+xml',
        'X-Microsoft-OutputFormat': 'audio-16khz-32kbitrate-mono-mp3',
        'User-Agent': 'coccinelle-cp'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def save(final=False):
    json.dump(B, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    subprocess.run(['git', 'add', OUT])
    if subprocess.run(['git', 'diff', '--cached', '--quiet']).returncode != 0:
        subprocess.run(['git', 'commit', '-q', '-m', f'صوت سلمى: {len(B)} من {len(T)}'])
        for _ in range(3):
            subprocess.run(['git', 'pull', '-q', '--rebase', '-X', 'theirs'])
            if subprocess.run(['git', 'push', '-q']).returncode == 0: break
            time.sleep(5)
    print(('FINAL ' if final else '') + f'saved {len(B)}/{len(T)}', flush=True)

start = time.time(); n = 0; last = 0.0; fails = 0
for t in todo:
    if time.time() - start > BUDGET: print('time budget reached'); break
    wait = 3.2 - (time.time() - last)          # 20 طلب في الدقيقة
    if wait > 0: time.sleep(wait)
    for attempt in range(6):
        last = time.time()
        try:
            mp3 = synth(t)
            if len(mp3) > 300:
                B[t] = base64.b64encode(mp3).decode(); n += 1; fails = 0
            break
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                print('المفتاح أو المنطقة غلط (HTTP %d)' % e.code); save(True); sys.exit(1)
            if e.code == 429 or e.code >= 500:
                time.sleep(15 * (attempt + 1)); continue
            print('HTTP', e.code, t[:40]); fails += 1; break
        except Exception as e:
            print('err', e); time.sleep(10 * (attempt + 1))
    if fails > 30: print('too many failures'); break
    if n and n % SAVE_EVERY == 0: save()
save(True)
if n: open('/tmp/voice_changed','w').write(str(n))
print('ALL DONE' if all(t in B for t in T) else 'NOT FINISHED — شغّله تاني يكمّل')
