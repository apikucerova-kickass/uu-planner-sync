# UU Planner Sync

Synchronizuje úkoly z Plus4U (Unicorn University) do Google Tasks a větší
úkoly navíc zapisuje jako události do Google Kalendáře. Každý týden tak mám
termíny v kalendáři a nemusím je hlídat v Plus4U ručně.

## Co to dělá

- Stáhne aktivní záznamy z Plus4U (`uuDwRecord/listActiveRecords`).
- **Google Tasks:** každý úkol s termínem založí jako úkol. Když se v Plus4U
  změní termín, upraví ho, a když se úkol uzavře, odškrtne ho.
- **Google Kalendář:** úkoly, které v názvu obsahují klíčové slovo
  (semestrální, projekt, zkouška, test, esej, prezentace, zápočet, …), zapíše
  jako dvouhodinový blok končící v termínu. Připomínky nastaví 7, 3 a 1 den
  předem. Hotové úkoly přejmenuje na `✅ [HOTOVO]` a vypne u nich připomínky.
- Neodevzdané úkoly s termínem starším než 21 dní přeskočí.
- Do `sync_cache.json` ukládá vazbu mezi ID v Plus4U a v Googlu, aby úkoly
  nezakládal dvakrát. Cache obsahuje jen ID, stavy a termíny, ne názvy úkolů.

## Jak to běží

GitHub Action [`sync.yml`](.github/workflows/sync.yml) spouští `sync.py`
každé pondělí v 5:00 UTC. Ručně jde spustit přes **Actions → Run workflow**.
Po doběhnutí commitne aktualizovanou `sync_cache.json` zpátky do repa.

Potřebuje tyhle repository secrets:

| Secret | Obsah |
|---|---|
| `UU_ENDPOINT` | URL endpointu `listActiveRecords` mého Plus4U teritoria |
| `UU_AUTH_HEADER` | `Bearer <token>` k Plus4U |
| `CALENDAR_ID` | ID Google Kalendáře, do kterého se zapisují události |
| `GOOGLE_CREDENTIALS` | obsah `token.json` (OAuth token Googlu s refresh tokenem) |

## Lokální spuštění

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib requests
```

1. V Google Cloud Console vytvořit OAuth klienta typu *Desktop app*
   se zapnutým Tasks a Calendar API a stáhnout ho jako `credentials.json`.
2. Vytvořit `.env`:
   ```
   UU_ENDPOINT=https://uuapp.plus4u.net/...
   UU_AUTH_HEADER=Bearer ...
   CALENDAR_ID=...@group.calendar.google.com
   ```
3. `python sync.py`. Při prvním spuštění se otevře prohlížeč s přihlášením
   do Googlu a vznikne `token.json`. Jeho obsah pak patří do secretu
   `GOOGLE_CREDENTIALS`.

`credentials.json`, `token.json` a `.env` jsou v `.gitignore` a do repa
nepatří.

## Známá omezení

- **Plus4U token platí jen krátce** (cca 30 minut). Plus4U nenabízí trvalý
  API klíč, takže před spuštěním je potřeba token v `UU_AUTH_HEADER` obnovit,
  jinak synchronizace skončí chybou 401.
- Rozpoznání „velkého“ úkolu podle klíčových slov v názvu je jen odhad.
  Seznam je v `BIG_TASK_KEYWORDS` v `sync.py`.
- Smazání úkolu v Plus4U se do Googlu nepropíše.
