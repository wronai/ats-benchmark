# ats-benchmark


Głównym wyzwaniem w używaniu LLM do naprawy projektów jest dostarczenie precyzyjnego kontekstu kodu i przepływu danych bez przeciążania okna kontekstowego. Twój ATS z code2logic dobrze ekstrahuje strukturę logiczną z kodu, a nfo może rozszerzyć to o przepływ danych. Gotowe narzędzia jak callgraph-cli czy tree-sitter z grafami wywołań oferują alternatywy, integrując AST z data flow dla LLM. [perplexity](https://www.perplexity.ai/search/f7dc92f3-181b-4edd-bbe1-4e1338362c23)

## Porównanie narzędzi

| Narzędzie          | Funkcje kluczowe                          | Zalety dla LLM kontekstu                  | Wady                              | Języki wsparcia          | Integracja z ATS/nfo |
|--------------------|-------------------------------------------|-------------------------------------------|-----------------------------------|--------------------------|----------------------|
| code2logic (wronai) | Ekstrakcja logiki/AST z kodu do struktury | Zawężony kontekst bez surowego kodu, szybka analiza  [github](https://github.com/tongjingqi/code2logic) | Brak natywnego data flow         | Python głównie          | Bazowe (Twoje ATS)  |
| nfo (wronai)       | Opis przepływu danych, struktura projektu | Dodaje grafy danych do AST, edge computing  [github](https://github.com/wronai) | Potrzeba integracji z ATS        | Python, edge            | Rozszerzenie ATS    |
| callgraph-cli      | Grafy wywołań funkcji, relacje kodu       | CLI kopiuje kontekst do schowka dla LLM, precyzyjny flow  [github](https://github.com/vmotta8/callgraph-cli) | Mniej data flow niż call graph   | Multi (Python, JS+)     | Łatwa via CLI       |
| tree-sitter + py2ast | Parsowanie AST, serializacja do tekstu    | Hierarchiczne struktury dla RAG/LLM, niskie zużycie tokenów  [arxiv](https://arxiv.org/html/2507.00352v1) | Wymaga własnego grafu data flow  | 50+ języków             | Wysoka (parsery)    |
| JavaDataFlow       | Grafy data flow z pól/parametrów          | Precyzyjny tracking danych w metodach  [github](https://github.com/daanvdh/JavaDataFlow) | Tylko Java, statyczna analiza    | Java                    | Średnia (adaptacja) |
| semanticflowgraph  | Semantyczne grafy flow dla DS             | Wizualizacja + enrich z raw graph  [github](https://github.com/IBM/semanticflowgraph) | Skupione na data science         | Python/R                | Niska (DS focus)    |

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Author

Created by **Tom Sapletta** - [tom@sapletta.com](mailto:tom@sapletta.com)
