# Yandex Metrika Domain Rules

Excerpts from official Yandex Metrika documentation (https://yandex.ru/support/metrica/general/creating-counter.html).

## Адрес сайта (Site Address) Field

> Основной домен сайта. Поле обязательно для заполнения. **Префикс схемы/протокола (http://, https://) указывать не следует.**
> В этом поле вы можете указать путь сайта (path в структуре URL). Например, `example.com/category/`.
> При этом **не указывайте адрес до определенного файла** или фрагмента страницы (символа «#») — эти указания вызовут ошибку в поле для ввода.
> Кроме того, не будут учитываться переданные в URL параметры (часть адреса после символа «?»).

## Valid Formats

```
✅ example.com
✅ example.com/category/
✅ ichigec.github.io/<YOUR_PROJECT>/
✅ сайт.рф
❌ https://example.com           (no protocol!)
❌ example.com/index.html        (no file names!)
❌ example.com/page#section      (no fragments!)
❌ example.com/?utm_source=test  (no query params!)
❌ xn--80aswg.xn--p1ai           (use Cyrillic, not Punycode!)
```

## Counter Creation

- Counter is created **immediately** — no site accessibility check during creation
- Max 100,000 counters per user
- Site verification is a separate step: Настройка → Проверка счетчика
- After installing code, data starts collecting immediately

## Blocked/Suspicious Domains

Yandex Metrika may reject or silently fail for:
- Temporary tunnel domains (`*.trycloudflare.com`)
- URL shortener domains
- Free subdomain services with high abuse rates
- Domains with no content / parked pages

**Safe choices:** GitHub Pages (`*.github.io`), custom domains, well-known hosting.
