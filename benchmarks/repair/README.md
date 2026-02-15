# repair pipeline

Pipeline naprawczy (refaktoryzacja przez LLM) dla: `code2logic`, `nfo`, `baseline`.

## Struktura folderu

- [repair_pipeline.py](./repair_pipeline.py) — logika pipeline'u
- [code2logic/repair_result.json](./code2logic/repair_result.json) — wynik naprawy (jeśli uruchomiono)
- [nfo/repair_result.json](./nfo/repair_result.json) — wynik naprawy (jeśli uruchomiono)
- [baseline/repair_result.json](./baseline/repair_result.json) — wynik naprawy (jeśli uruchomiono)
- [llm/system.txt](./llm/system.txt) — agregowany system prompt ostatniego przebiegu
- [llm/input.txt](./llm/input.txt) — agregowany ostatni prompt repair
- [llm/context.txt](./llm/context.txt) — agregowany kontekst ostatniego przebiegu
- [llm/output.txt](./llm/output.txt) — agregowana odpowiedź LLM (ostatni przebieg)
- [llm/metadata.json](./llm/metadata.json) — agregowane metadane ostatniego przebiegu
- [llm/timeline.log](./llm/timeline.log) — harmonogram kolejnych przebiegów repair
- [code2logic/llm/system.txt](./code2logic/llm/system.txt) — system prompt naprawy
- [code2logic/llm/input.txt](./code2logic/llm/input.txt) — prompt naprawy wysłany do LLM
- [code2logic/llm/context.txt](./code2logic/llm/context.txt) — kontekst użyty do naprawy
- [code2logic/llm/output.txt](./code2logic/llm/output.txt) — odpowiedź LLM
- [code2logic/llm/metadata.json](./code2logic/llm/metadata.json) — tokeny/czas/model/target
- [code2logic/llm/timeline.log](./code2logic/llm/timeline.log) — harmonogram wywołań LLM

## Jak odtworzyć artefakty

```bash
make repair
```
