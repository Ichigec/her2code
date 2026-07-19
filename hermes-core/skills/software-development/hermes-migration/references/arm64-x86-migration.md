# ARM64 ↔ x86_64 Migration

Процедура пересборки архитектурно-зависимых компонентов при переносе Hermes
между ARM64 (Jetson, Apple Silicon) и x86_64 (Intel/AMD).

## Что архитектурно-зависимо

```
✅ НЕ меняется (универсальное):
  46/60 Python wheels (py3-none-any)        — чистый Python
  3 GGUF модели (Nex-N2-mini и др.)         — формат универсальный
  Neo4j дамп (.dump)                        — бинарный формат графа
  Все .md/.yaml/.json/.sh                   — текст

🔄 МЕНЯЕТСЯ:
  14/60 Python wheels (aarch64.whl)         — нативный код (C/Rust)
  15 Docker образов                         — arm64 → amd64
  llama-server binary                       — C++/CUDA нативный код
```

## Шаг 1: Python wheels

14 из 60 wheels содержат нативный код (CFFI, cryptography, Pillow, etc.)
и архитектурно-специфичны:

```bash
# Какие wheels нужно заменить
ls pip-packages/ | grep -E 'aarch64|arm64'

# Вывод (14 штук):
# cffi, charset_normalizer, cryptography, httptools, jiter,
# markupsafe, pillow, psutil, pydantic_core, pyyaml,
# ruamel_yaml_clib, uvloop, watchfiles, websockets
```

**Перекачать под x86_64:**

```bash
pip download --platform manylinux2014_x86_64 --python-version 312 \
  --only-binary=:all: hermes-agent -d pip-packages-x86/
```

После загрузки заменить 14 aarch64-whl на их x86_64-аналоги.
Остальные 46 `py3-none-any.whl` переиспользовать.

## Шаг 2: Docker pull-образы (9 шт)

Образы с Docker Hub — достаточно перетянуть под другую архитектуру.
Фактические размеры проверены на Seagate 2026-07-06:

| Образ | Размер (arm64 tar) |
|-------|-------------------|
| `nvidia/cuda:13.0.0-devel-ubuntu24.04` | 6.1 GB |
| `nvidia/cuda:13.0.0-runtime-ubuntu24.04` | 2.4 GB |
| `ghcr.io/berriai/litellm-database:v1.83.7-stable` | 1.9 GB |
| `arizephoenix/phoenix:latest` | 809 MB |
| `neo4j:5-community` | 584 MB |
| `postgres:16-alpine` | 262 MB |
| `python:3.12-slim` | 142 MB |
| `python:3.12-alpine` | 53 MB |
| `alpine:latest` | 9 MB |
| **Итого pulls** | **~12.5 GB** |

```bash
for img in neo4j:5-community arizephoenix/phoenix:latest \
           postgres:16-alpine python:3.12-slim python:3.12-alpine \
           alpine:latest ghcr.io/berriai/litellm-database:v1.83.7-stable \
           nvidia/cuda:13.0.0-devel-ubuntu24.04 nvidia/cuda:13.0.0-runtime-ubuntu24.04; do
  docker pull --platform linux/amd64 "$img"
  docker save "$img" -o "docker-images/$(echo $img | tr '/:' '-').tar"
done
```

## Шаг 3: Docker локально собранные образы (6 шт)

Эти образы **не скачать** с Docker Hub — нужно пересобрать из Dockerfile-ов.
Фактический список проверен по `compose.agents-mesh.yml` и `compose.phoenix.yml`:

| Образ | Размер (arm64 tar) | Dockerfile |
|-------|-------------------|------------|
| `voice-assistant-openhands-adapter:local` | 989 MB | `docker/openhands-adapter/Dockerfile` |
| `voice-assistant-clawcode-adapter:local` | 301 MB | `docker/clawcode-adapter/Dockerfile` |
| `voice-assistant-opencode-adapter:local` | 301 MB | `docker/opencode-adapter/Dockerfile` |
| `voice-assistant-agent-registry:local` | 193 MB | `docker/agent-registry/Dockerfile` |
| `voice-assistant-skills-manager:local` | 193 MB | `docker/skills-manager/Dockerfile` |
| `voice-assistant-openai-stack-relay:local` | 54 MB | `docker/openai-stack-relay/Dockerfile` |
| **Итого local builds** | **~2.5 GB** |

```bash
# Сборка через buildx (amd64 на ARM64 через QEMU):
for svc in agent-registry clawcode-adapter opencode-adapter \
           openhands-adapter skills-manager openai-stack-relay; do
  docker buildx build --platform linux/amd64 --load \
    -t "voice-assistant-${svc}:local" \
    -f "docker/${svc}/Dockerfile" .
  docker save "voice-assistant-${svc}:local" \
    -o "docker-images/voice-assistant-${svc}.tar"
done
```

**⚠️ НЕ путать с runtime-образами:** `voice-assistant-opencode:local`,
`voice-assistant-clawcode:local`, `openwebui-searchbox:local`,
`openwebui-fsbox:local`, `openwebui-shellbox:local` — это образы
OpenWebUI/runtime, которые НЕ входят в codewar дистрибутив. Проверяй
фактический список по compose-файлам, а не по `docker images` на dev-машине.

**Риск:** если в Dockerfile зашит `--platform=linux/arm64` или используются
ARM64-специфичные base-образы, сборка упадёт. Нужен audit Dockerfile-ов.

## Шаг 4: llama-server binary

### ⚠️ CUDA_ARCH — КРИТИЧЕСКИЙ ПИТФОЛЛ

llamacpp Dockerfile в codewar хардкодит `CUDA_ARCH=121` (sm_121 = Blackwell,
Jetson DGX Spark). При сборке под x86_64 это **обязательно** нужно изменить
на compute capability целевого GPU:

| GPU | Compute Capability | CUDA_ARCH |
|-----|-------------------|-----------|
| Hopper (H100, H200) | sm_90 | 90 |
| Ada Lovelace (RTX 4090, L40S) | sm_89 | 89 |
| Ampere (A100, A30) | sm_80 | 80 |
| Turing (RTX 2080, T4) | sm_75 | 75 |
| Multi-arch (если GPU неизвестен) | — | `89;90` |

```dockerfile
# ❌ ТЕКУЩИЙ (ARM64/Jetson — хардкод Blackwell):
ARG CUDA_ARCH=121

# ✅ НУЖНО для x86_64 (пример — Ada Lovelace + Hopper):
ARG CUDA_ARCH=89;90
```

### Сборка через Docker buildx (amd64 на ARM64 через QEMU):

```bash
# Использовать llamacpp/Dockerfile с модифицированным CUDA_ARCH
docker buildx build --platform linux/amd64 --load \
  --build-arg CUDA_ARCH=89;90 \
  -t llama-x86-builder:latest \
  -f llm-stack/docker/llamacpp/Dockerfile .

# Извлечь бинарник
docker run --rm -v /tmp/x86-out:/out llama-x86-builder:latest \
  cp /usr/local/bin/llama-server /out/
docker run --rm -v /tmp/x86-out:/out llama-x86-builder:latest \
  cp /usr/local/lib/lib*.so* /out/

# Упаковать для офлайн-установки
cd /tmp/x86-out
tar czf llama-server-bin-x86_64.tar.gz llama-server lib*.so*
```

### Сборка на целевой x86_64 машине (если есть интернет):

```bash
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=89
cmake --build build -j --target llama-server

# Упаковать
cd build/bin
tar czf llama-server-bin-x86_64.tar.gz llama-server lib*.so*
```

Размер: ~83 MB (из них 61 MB — `libggml-cuda.so`).

**Проверка архитектуры бинарника:**
```bash
file llama-server
# Должно показать: ELF 64-bit LSB executable, x86-64
```

## Шаг 5: Пересобрать codewar-архив

```bash
cd /path/to/codewar
# Заменить pip-packages (aarch64 → x86_64)
# Заменить docker-images (arm64 → amd64)
# Заменить llama-server-bin.tar.gz
tar czf codewar-x86_64.tar.gz codewar/
```

## Итого: трудоёмкость

| Операция | Время | Размер |
|----------|-------|--------|
| pip download x86_64 | 2 мин | 38.8 MB |
| docker pull --platform amd64 (9 шт) | 15 мин | ~12.5 GB |
| docker buildx --platform amd64 (6 шт) | 20 мин | ~2.5 GB |
| сборка llama-server (buildx + CUDA_ARCH) | 15 мин | ~50 MB |
| копирование моделей + neo4j + конфиги | 5 мин | ~76 GB |
| **ВСЕГО** | **~60 мин** | **~89 GB** |

## Шаг 6: Верификация плана миграции (КРИТИЧНО)

Перед тем как представлять план миграции пользователю, **проверь фактические
артефакты на диске**. В сессии 2026-07-06 план содержал 5 ошибок, которые
верификация выявила:

| Что было в плане | Что оказалось реально |
|------------------|----------------------|
| 6 pull + 9 local Docker | **9 pull + 6 local** (перепутано местами) |
| searchbox, fsbox, shellbox как local | **НЕ в dist** — это OpenWebUI образы |
| Docker images ~5 GB | **~15 GB** (в 3 раза больше) |
| CUDA_ARCH не упомянут | Dockerfile хардкодит `CUDA_ARCH=121` (Blackwell) |
| codewar-x86/ создать с нуля | **Уже существует** с pip-packages |

### Команды верификации (быстрая проверка за 1 минуту)

```bash
SEAGATE="/media/pavel/One Touch/hermes"

# 1. Количество и платформенность wheels
echo "ARM64 wheels: $(ls "$SEAGATE/codewar/pip-packages/" | wc -l)"
echo "x86_64 wheels: $(ls "$SEAGATE/codewar-x86/pip-packages/" | wc -l)"
echo "ARM64 platform-specific: $(ls "$SEAGATE/codewar/pip-packages/" | grep aarch64 | wc -l)"
echo "x86_64 platform-specific: $(ls "$SEAGATE/codewar-x86/pip-packages/" | grep x86_64 | wc -l)"

# 2. Docker images: количество и архитектура
echo "Docker tars: $(ls "$SEAGATE/docker-images/"*.tar | wc -l)"
du -bc "$SEAGATE/docker-images/"*.tar | tail -1

# 3. llama-server: архитектура бинарника
cd /tmp && tar xzf "$SEAGATE/codewar/llm-stack/llama/llama-server-bin.tar.gz" 2>/dev/null
file /tmp/llama-server
# Должно показать: ELF 64-bit LSB ... ARM aarch64 (для ARM64 dist)

# 4. CUDA_ARCH в llamacpp Dockerfile
grep CUDA_ARCH "$SEAGATE/codewar/llm-stack/docker/llamacpp/Dockerfile"
# Должно показать: ARG CUDA_ARCH=121 (Blackwell — нужен другой для x86_64)

# 5. Compose-файлы: фактические сервисы
grep -E "^\s{2}[a-z_-]+:" "$SEAGATE/codewar/llm-stack/compose/compose.agents-mesh.yml" \
  | grep -v "build:\|environment:\|volumes:\|ports:\|healthcheck:" | sort -u

# 6. Размеры по каталогам
du -sh "$SEAGATE/codewar/" "$SEAGATE/codewar-x86/" \
       "$SEAGATE/docker-images/" "$SEAGATE/models/"
```

### Методология верификации

1. **Сравни список Docker-образов** из плана с `docker-images/*.tar` на диске.
   Не доверяй `docker images` на dev-машине — там есть образы, которые НЕ
   входят в дистрибутив (OpenWebUI sidecars, runtime containers).
2. **Проверь архитектуру бинарников** через `file` — `ELF aarch64` ≠ `ELF x86-64`.
3. **Проверь wheel platform tags** — `grep aarch64` / `grep x86_64` в имени файла.
4. **Проверь Dockerfile** на хардкоженный `CUDA_ARCH` — это частый источник
   тихих сборочных ошибок на другой архитектуре.
5. **Проверь compose-файлы** на фактические имена сервисов — не изобретай
   имена, которых там нет.
6. **Сравни размеры** через `du -bc` (точные байты), а не `du -sh` (округление).
