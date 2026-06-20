#!/usr/bin/env python3
"""Hermes Stack Sanitizer — удаление персональных данных из копии стека Hermes."""
import os, re, shutil, json, sqlite3, sys
from pathlib import Path

HER2CODE = Path("/home/user/dev/codemes/pavel_20260619_200039/her2code")

REPLACEMENTS = [
    # Пути
    (r'/home/user/', '/home/user/'),
    # API ключи
    (r'sk-proj-[A-Za-z0-9_-]{20,}', '<YOUR_OPENAI_KEY>'),
    (r'Bearer [A-Za-z0-9+/=_-]{20,}', 'Bearer <YOUR_API_SERVER_KEY>'),
    # IP адреса
    (r'64\.188\.64\.52', '<YOUR_VPS_IP>'),
    (r'95\.24\.31\.191', '<YOUR_PUBLIC_IP>'),
    (r'95\.24\.32\.220', '<YOUR_HOME_IP>'),
    (r'192\.168\.0\.48', '<YOUR_LOCAL_IP>'),
    (r'192\.168\.0\.1', '<YOUR_ROUTER_IP>'),
    (r'10\.4\.\d+\.\d+', '<YOUR_PHONE_IP>'),
    # Telegram
    (r'<YOUR_CHAT_ID>', '<YOUR_CHAT_ID>'),
    (r'<YOUR_USER_ID>', '<YOUR_USER_ID>'),
    (r'<YOUR_BOT_USERNAME>', '<YOUR_BOT_USERNAME>'),
    (r'<YOUR_CHANNEL>', '<YOUR_CHANNEL>'),
    # Имена
    (r'user@localhost', 'user@localhost'),
    (r'name\s*=\s*User', 'name = User'),
    (r'User', 'User'),  # осторожно — может задеть код
    (r'<YOUR_GITHUB_USER>', '<YOUR_GITHUB_USER>'),
    # Телефон
    (r'<YOUR_PHONE_ID>', '<YOUR_PHONE_ID>'),
    # VPN
    (r'<YOUR_VLESS_UUID>', '<YOUR_VLESS_UUID>'),
    (r'vpn1\.play2go\.cloud', '<YOUR_VPS_HOSTNAME>'),
    # WiFi
    (r'<YOUR_WIFI_SSID>', '<YOUR_WIFI_SSID>'),
    # Туннели
    (r'[a-z0-9]+\.lhr\.life', '<YOUR_TUNNEL_URL>'),
    (r'[a-z0-9-]+\.trycloudflare\.com', '<YOUR_TUNNEL_URL>'),
    # Sudo
    (r'<YOUR_SUDO_PASSWORD>', '<YOUR_SUDO_PASSWORD>'),
    # Имя в systemd
    (r'User=user', 'User=user'),
]

EXCLUDE_DIRS = {'venv', '__pycache__', '.git', 'node_modules', 'build', '.gradle',
                'logs', 'sessions', 'memories', 'plans', 'bin', '.ssh'}

EXCLUDE_FILES = {'.env', 'auth.json', '.sudo_pass', 'id_ed25519', 'id_ed25519.pub',
                 'known_hosts', 'state.db', 'audit.db', 'kanban.db', 'metrics.db',
                 'response_store.db', '*.apk', '*.pyc', '*.AppImage'}

def should_process(path):
    parts = set(path.parts)
    if parts & EXCLUDE_DIRS:
        return False
    for pat in EXCLUDE_FILES:
        if path.match(pat):
            return False
    return True

def sanitize_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        return 0

    original = content
    for pattern, replacement in REPLACEMENTS:
        content = re.sub(pattern, replacement, content)

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return 1
    return 0

def clean_db(path):
    """Extract schema only, drop data."""
    if not path.exists():
        return
    conn = sqlite3.connect(str(path))
    schema = '\n'.join(conn.iterdump())
    conn.close()
    # Extract only CREATE statements
    creates = [l for l in schema.split('\n') if l.strip().upper().startswith('CREATE')]
    schema_sql = ';\n'.join(creates) + ';\n'
    schema_path = path.with_suffix('.schema.sql')
    with open(schema_path, 'w') as f:
        f.write(schema_sql)
    path.unlink()  # Remove .db with data

def main():
    print("🧹 Hermes Stack Sanitizer")
    print(f"   Target: {HER2CODE}")
    
    # Удалить __pycache__ если есть
    pycache = HER2CODE / '__pycache__'
    if pycache.exists():
        shutil.rmtree(pycache)
    
    # Удалить явно исключённые файлы
    for pattern in ['**/state.db', '**/audit.db', '**/kanban.db', '**/metrics.db', 
                    '**/response_store.db', '**/.sudo_pass', '**/*.apk',
                    '**/sessions/*.json', '**/logs/*.log', '**/plans/*.md',
                    '**/memories/*.md', '**/request_dump_*.json']:
        for f in HER2CODE.glob(pattern):
            print(f"   🗑️  Deleting: {f.relative_to(HER2CODE)}")
            f.unlink()
    
    # Удалить pavel-environment skill
    pe = HER2CODE / 'config' / 'skills' / 'pavel-environment'
    if pe.exists():
        print(f"   🗑️  Deleting skill: pavel-environment")
        shutil.rmtree(pe)
    
    # Удалить sing-box-vpn-setup
    for sb in HER2CODE.glob('**/sing-box-vpn-setup*'):
        print(f"   🗑️  Deleting: {sb.relative_to(HER2CODE)}")
        sb.unlink()
    
    # Санитизация текстовых файлов
    changed = 0
    total = 0
    for filepath in HER2CODE.rglob('*'):
        if not filepath.is_file():
            continue
        if not should_process(filepath):
            continue
        if filepath.suffix in {'.db', '.pyc', '.apk', '.jar', '.png', '.jpg', '.mp3', '.wav', '.ogg', '.gguf', '.bin', '.AppImage'}:
            continue
        total += 1
        try:
            changed += sanitize_file(filepath)
        except Exception as e:
            print(f"   ⚠️  Error: {filepath}: {e}")
    
    print(f"\n✅ Sanitized {changed}/{total} files")
    
    # Очистить MEMORY.md и USER.md
    for mem in HER2CODE.glob('**/MEMORY.md'):
        mem.write_text("# Memory (template)\n\n> Replace this with your agent's memory. See Hermes documentation for format.\n")
    for user in HER2CODE.glob('**/USER.md'):
        user.write_text("# User Profile (template)\n\n> Replace this with your profile. See Hermes documentation for format.\n")
    
    # Очистить .compactor log
    for comp in HER2CODE.glob('**/.compactor/log.jsonl'):
        comp.write_text('')
    
    print("✅ Memory/User files templated")
    print("✅ Sanitization complete")

if __name__ == '__main__':
    main()
