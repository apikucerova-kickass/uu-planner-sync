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

Původně byla synchronizace plánovaná přes GitHub Actions (každé pondělí). Kvůli tomu, že Plus4U používá krátkodobé `Bearer` tokeny (cca 30 minut) a nemá možnost trvalého API klíče ani přímého přihlášení přes skript, cloudové spouštění selhávalo na chybě 401.

**Aktuální poloautomatický režim:**
Skript se spouští ručně na Macu podle potřeby. Stačí mít v prohlížeči otevřené Plus4U, zkopírovat aktuální token a spustit skript lokálně.

## Spuštění synchronizace

1. V prohlížeči na Plus4U otevřít DevTools (**Cmd + Option + I**) → záložka **Network** → obnovit stránku (**Cmd + R**).
2. Najít požadavek `listActiveRecords`, zkopírovat hodnotu hlavičky `authorization` a vložit ji do `.env`:
