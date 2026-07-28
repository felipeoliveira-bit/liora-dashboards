#!/usr/bin/env python3
# photos_drive_sync.py - puxa as fotos do time da pasta do Google Drive
# "Fotos Time Liora" via SERVICE ACCOUNT (server-side, byte-exato) e injeta no
# SELLER_PHOTOS do mobile/index.html. Roda dentro do GitHub Actions.
#
# Auth: env GDRIVE_SA_KEY = JSON da chave do service account (secret do repo).
# Pasta: env GDRIVE_PHOTOS_FOLDER (default = id da "Fotos Time Liora").
# FAIL-SAFE: se faltar a key, a pasta nao abrir, ou der qualquer erro de rede,
# imprime aviso e sai 0 (NAO derruba o build) - as fotos ja no HTML sao preservadas.
#
# Uso: python3 build/photos_drive_sync.py <mobile/index.html>
import os, sys, re, io, json, base64, unicodedata, subprocess

FOLDER_ID = os.environ.get('GDRIVE_PHOTOS_FOLDER', '1e7dsCnPEwGsExp9PsNkgW1DltFJo3XP-')

def log(m): print("[fotos] " + m, flush=True)

def _bootstrap():
    # Garante google-auth + googleapiclient + Pillow no runner (pip em runtime).
    try:
        import google.oauth2.service_account  # noqa
        import googleapiclient.discovery       # noqa
        from PIL import Image                  # noqa
        return True
    except Exception:
        log("instalando dependencias (google-api-python-client, google-auth, Pillow)...")
        r = subprocess.run([sys.executable, '-m', 'pip', 'install', '-q',
                            'google-api-python-client', 'google-auth', 'Pillow'],
                           capture_output=True, text=True)
        if r.returncode != 0:
            log("pip falhou: " + (r.stderr or r.stdout)[-500:]); return False
        return True

def _norm_name(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = s.replace('_', ' ').lower()
    return re.sub(r'\s+', ' ', s).strip()

def fetch_photos():
    # Retorna dict {nome_arquivo: bytes} baixado do Drive. [] se indisponivel.
    key = os.environ.get('GDRIVE_SA_KEY', '').strip()
    if not key:
        log("GDRIVE_SA_KEY ausente - pulando sync de fotos (mantem as atuais)."); return None
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    try:
        info = json.loads(key)
    except Exception:
        log("GDRIVE_SA_KEY nao e JSON valido - pulando."); return None
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=['https://www.googleapis.com/auth/drive.readonly'])
    svc = build('drive', 'v3', credentials=creds, cache_discovery=False)
    q = "'%s' in parents and trashed=false" % FOLDER_ID
    files, tok = [], None
    while True:
        resp = svc.files().list(q=q, fields="nextPageToken, files(id,name,mimeType,size)",
                                pageSize=200, supportsAllDrives=True,
                                includeItemsFromAllDrives=True, pageToken=tok).execute()
        files += resp.get('files', [])
        tok = resp.get('nextPageToken')
        if not tok: break
    log("pasta tem %d item(ns)." % len(files))
    out = {}
    for f in files:
        mt = f.get('mimeType', '')
        if mt == 'application/vnd.google-apps.folder' or mt.startswith('application/vnd.google-apps'):
            continue  # ignora subpastas e Google Docs (ex.: o LEIA-ME)
        req = svc.files().get_media(fileId=f['id'])
        buf = io.BytesIO(); dl = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            _, done = dl.next_chunk()
        data = buf.getvalue()
        exp = f.get('size')
        if exp is not None and str(len(data)) != str(exp):
            log("  ! %s: bytes %d != Drive %s - descartado (download incompleto)." % (f['name'], len(data), exp))
            continue
        out[f['name']] = data
    return out

def inject(mobile_html, named_bytes):
    from PIL import Image
    t = open(mobile_html, encoding='utf-8').read()

    def obj_span(name):
        i = t.index(name); s = t.index('{', i); d = 0
        for j in range(s, len(t)):
            if t[j] == '{': d += 1
            elif t[j] == '}':
                d -= 1
                if d == 0: return s, j + 1
        raise SystemExit("obj nao fechou: " + name)

    pair = re.compile(r'([\'"])((?:\\.|(?!\1).)*)\1\s*:\s*([\'"])((?:\\.|(?!\3).)*)\3')
    def kv(seg): return [(m.group(2), m.group(4)) for m in pair.finditer(seg)]
    ps, pe = obj_span('SELLER_PHOTOS')
    photos = dict(kv(t[ps:pe]))
    rs, re_ = obj_span('SELLER_PRACA')
    roster = [k for k, _ in kv(t[rs:re_])]
    canon = {}
    for n in roster + list(photos.keys()):
        canon.setdefault(_norm_name(n), n)

    IMG_EXT = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp')
    added, updated, nomatch = [], [], []
    for fname in sorted(named_bytes):
        stem, ext = os.path.splitext(fname)
        if ext.lower() not in IMG_EXT:
            stem = fname
        try:
            im = Image.open(io.BytesIO(named_bytes[fname])); im.load(); im = im.convert('RGB')
        except Exception:
            log("  ! %s: nao abriu como imagem - ignorado." % fname); continue
        key = canon.get(_norm_name(stem))
        if not key:
            nomatch.append(fname); continue
        was = key in photos
        im.thumbnail((256, 256))
        b = io.BytesIO(); im.save(b, 'JPEG', quality=82)
        photos[key] = 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()
        (updated if was else added).append(key)

    new_obj = json.dumps(photos, ensure_ascii=False)
    json.loads(new_obj)  # sanidade
    t = t[:ps] + new_obj + t[pe:]
    open(mobile_html, 'w', encoding='utf-8').write(t)
    if added:   log("+ %d nova(s): %s" % (len(added), ', '.join(added)))
    if updated: log("~ %d atualizada(s): %s" % (len(updated), ', '.join(updated)))
    if nomatch: log("! nome nao bate: %s" % ', '.join(nomatch))
    if not (added or updated): log("nada novo (fotos ja estavam em dia).")

def main():
    if len(sys.argv) < 2:
        log("uso: photos_drive_sync.py <mobile/index.html>"); return 0
    mobile = sys.argv[1]
    if not os.path.isfile(mobile):
        log("mobile nao encontrado: " + mobile); return 0
    if not os.environ.get('GDRIVE_SA_KEY', '').strip():
        log("GDRIVE_SA_KEY ausente - pulando sync de fotos (mantem as atuais)."); return 0
    try:
        if not _bootstrap():
            log("deps indisponiveis - pulando (build segue)."); return 0
        nb = fetch_photos()
        if nb is None:
            return 0  # sem key/erro leve: preserva o que ja existe
        if not nb:
            log("nenhuma imagem baixavel na pasta."); return 0
        inject(mobile, nb)
    except Exception as e:
        # NUNCA derruba o build por causa de foto.
        log("erro nao-fatal: %r - fotos atuais preservadas." % e)
        return 0
    return 0

if __name__ == '__main__':
    sys.exit(main())
