# exFAT Symlink Pitfall

## Проблема

exFAT не поддерживает POSIX symlinks. При `cp -r` на exFAT-диск
все symlinks **молча раскрываются** в полные копии файлов.

## Реальные цифры (Jetson ARM64, 2026-07-06)

| Директория | Реальный размер (ext4) | После `cp -r` на exFAT | Раздутие |
|---|---|---|---|
| `node_modules/` (npm) | 45 MB | 847 MB | **19×** |
| `llama.cpp/build/bin/` | 83 MB | 83 MB | 1× (мало symlinks) |

## Почему node_modules так сильно раздувается

npm активно использует symlinks:
- `node_modules/.bin/` — каждый бинарник это symlink на реальный файл
- Перекрёстные зависимости пакетов — symlink на соседний пакет
- `@scope/package` → symlink на `../package`

При `cp -r` каждый symlink становится полной копией файла.
Для `node_modules` с 101 пакетом это даёт 19× раздутие.

## Решение

**Всегда использовать tar для переноса на exFAT:**

```bash
# ✅ Правильно — tar сохраняет symlinks внутри архива
cd /source/dir
tar czf /mnt/exfat/node_modules.tar.gz node_modules/

# На целевой машине (с ext4/btrfs/zfs):
tar xzf node_modules.tar.gz -C /target/dir/

# ❌ НИКОГДА — cp раскрывает symlinks
cp -r /source/node_modules/ /mnt/exfat/node_modules/
```

## Проверка

```bash
# Сколько symlinks на источнике
find /source/node_modules -type l | wc -l

# Сколько symlinks на exFAT-копии (должно быть 0 если cp -r)
find /mnt/exfat/node_modules -type l | wc -l
```

## Также подвержены

- FAT32
- NTFS без `mfsymlinks` mount option
- CIFS/SMB без `mfsymlinks`
- Любая ФС без поддержки POSIX symlinks
