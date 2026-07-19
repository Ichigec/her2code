# Eval Data Preparation

How to get evaluation datasets (wikitext-2, HellaSwag, Winogrande) for perplexity and benchmark testing.

## Wikitext-2

As of mid-2026, wikitext-2 is only available as parquet on HuggingFace. The raw zip URLs (S3, GitHub) are dead.

### Extraction via datasets library

Uses the jupyterlab venv which has `datasets` and `torch`:

```bash
/home/user/jupyterlab/.venv/bin/python3 -c "
from datasets import load_dataset
ds = load_dataset('Salesforce/wikitext', 'wikitext-2-raw-v1', split='test')
with open('/home/user/models/eval-data/wikitext-2-raw/wiki.test.raw', 'w') as f:
    for item in ds:
        if item['text'].strip():
            f.write(item['text'].strip() + '\n')
"
```

Expected output: ~2891 lines, ~1.28 MB.

### Perplexity evaluation

```bash
/home/user/dev/llama.cpp/build/bin/llama-perplexity \
  -m model.gguf \
  -f /home/user/models/eval-data/wikitext-2-raw/wiki.test.raw \
  -c 2048 -b 512 -ngl 99
```

Compare `Final estimate: PPL = X.XXX` between models/quants.

## HellaSwag & Winogrande

For downstream accuracy benchmarks, download eval data from standard sources:

```bash
mkdir -p /home/user/models/eval-data
curl -sS -L "https://raw.githubusercontent.com/rowanz/hellaswag/master/data/hellaswag_val_full.txt" -o /home/user/models/eval-data/hellaswag_val_full.txt
```

These are used by llama-perplexity with `--hellaswag --hellaswag-tasks 400` flags.
