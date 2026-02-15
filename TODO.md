# TODO

Oto kompletny benchmark dla narzędzi analizy kodu (code2logic, nfo, callgraph-cli, tree-sitter) z LiteLLM, przygotowany w Dockerze. Każdy tool ma osobny folder z przykładowym kodem Pythona, Makefile uruchamia benchmark osobno, a `.env` jest wspólny z modelem z OpenRouter.

## Struktura projektu

```
code-benchmark/
├── .env                    # Wspólny: OPENROUTER_API_KEY, model
├── docker-compose.yml      # Uruchamia wszystkie projekty
├── sample-app/             # Przykładowy kod do analizy (1000 LOC)
├── benchmarks/
│   ├── code2logic/         # Benchmark code2logic
│   ├── nfo/               # Benchmark nfo  
│   ├── callgraph/         # Benchmark callgraph-cli
│   └── treesitter/        # Benchmark tree-sitter
└── Makefile               # make benchmark-all
```

## Pliki konfiguracyjne

**.env**
```bash
OPENROUTER_API_KEY=sk-or-...
MODEL_ID=openrouter/meta-llama/llama-3.2-vision:free
MAX_TOKENS=2048
TEMPERATURE=0.1
```

**docker-compose.yml**
```yaml
version: '3.8'
services:
  benchmark-base:
    image: python:3.12-slim
    env_file: .env
    volumes:
      - .:/workspace
      - ./sample-app:/sample-app:ro
    working_dir: /workspace
    environment:
      - PIP_NO_CACHE_DIR=1

  code2logic-bench:
    extends: benchmark-base
    command: make -C benchmarks/code2logic run

  nfo-bench:
    extends: benchmark-base
    command: make -C benchmarks/nfo run

  callgraph-bench:
    extends: benchmark-base
    command: make -C benchmarks/callgraph run

  treesitter-bench:
    extends: benchmark-base
    command: make -C benchmarks/treesitter run
```

## Przykładowa aplikacja (sample-app/)

**sample-app/main.py** (uproszczony przykład 1000 LOC):
```python
# Przykład: aplikacja e-commerce z zależnościami
class Product:
    def __init__(self, id, price): self.id, self.price = id, price
    
class Cart:
    def add(self, product): pass
    def checkout(self): return Payment().process()

class Payment:
    @staticmethod
    def process(): return True

def main():
    cart = Cart()
    cart.add(Product(1, 100))
    if cart.checkout(): print("OK")
```

## Benchmark: code2logic

**benchmarks/code2logic/requirements.txt**
```txt
litellm==1.44.7
code2logic  # Twoje repo
tree-sitter
networkx
```

**benchmarks/code2logic/benchmark.py**
```python
import litellm
import code2logic
import time
from pathlib import Path

def benchmark_code2logic():
    start = time.time()
    
    # Konwersja kodu do struktury logicznej
    logic_struct = code2logic.analyze(Path("/sample-app"))
    
    # Prompt z zawężonym kontekstem do LLM
    prompt = f"""
    Analizuj strukturę logiki aplikacji:
    {logic_struct}
    
    Znajdź potencjalne błędy w przepływie danych.
    """
    
    response = litellm.acompletion(
        model=os.getenv("MODEL_ID"),
        messages=[{"role": "user", "content": prompt}],
        max_tokens=int(os.getenv("MAX_TOKENS"))
    )
    
    tokens_in = len(litellm.token_counter(prompt))
    tokens_out = len(response.choices[0].message.content)
    duration = time.time() - start
    
    return {
        "tool": "code2logic",
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "duration_sec": duration,
        "context_size": len(str(logic_struct)),
        "compression_ratio": tokens_in / len(str(logic_struct))
    }

if __name__ == "__main__":
    result = benchmark_code2logic()
    print(result)
```

**benchmarks/code2logic/Makefile**
```makefile
run:
	pip install -r requirements.txt
	python benchmark.py > results.json
```

## Benchmark: callgraph-cli

**benchmarks/callgraph/Makefile**
```makefile
run:
	pip install litellm networkx
	callgraph-cli /sample-app --clipboard=false --json > callgraph.json
	python benchmark.py
```

**benchmarks/callgraph/benchmark.py**
```python
import json
import litellm
import time

def benchmark_callgraph():
    with open("callgraph.json") as f:
        graph = json.load(f)
    
    prompt = f"""
    Analiza grafu wywołań funkcji:
    {json.dumps(graph, indent=2)[:4000]}
    
    Znajdź cykle i nieoptymalne ścieżki.
    """
    
    # ... reszta jak wyżej
```

## Benchmark: tree-sitter

**benchmarks/treesitter/benchmark.py**
```python
import tree_sitter
from tree_sitter import Language, Parser
import litellm

def benchmark_treesitter():
    PYTHON_LANGUAGE = Language('build/my-languages.so', 'python')
    parser = Parser()
    parser.set_language(PYTHON_LANGUAGE)
    
    with open("/sample-app/main.py") as f:
        tree = parser.parse(f.read().encode())
    
    ast_serialized = serialize_node(tree.root_node)  # custom serializer
    
    prompt = f"AST struktura: {ast_serialized}"
    # ... LLM call
```

## Główny Makefile

**Makefile** (w root)
```makefile
.PHONY: all clean results

all: code2logic nfo callgraph treesitter

code2logic:
	docker-compose run --rm code2logic-bench

nfo:
	docker-compose run --rm nfo-bench

callgraph:
	docker-compose run --rm callgraph-bench

treesitter:
	docker-compose run --rm treesitter-bench

results:
	python analyze_results.py

analyze_results.py:
	cat benchmarks/*/results.json | jq -s 'map(.[]) | group_by(.tool) | map({tool: .[0].tool, avg_duration: (map(.duration_sec) | add / length), avg_tokens: (map(.tokens_in) | add / length)})'
```

## Uruchomienie

```bash
# 1. Skonfiguruj .env z kluczem OpenRouter
# 2. Stwórz strukturę + sample-app
# 3. docker-compose up --build  # buduje bazę

make all        # Uruchamia wszystkie benchmarki
make results    # Podsumowanie
```

## Oczekiwane wyniki (szacunkowe)

| Tool          | Tokens wej. | Czas [s] | Kompresja | Jakość kontekstu |
|---------------|-------------|----------|-----------|------------------|






## Poprawiony plan benchmarku

Rozróżniam: **code2logic** kompresuje strukturę kodu (AST/logika), **nfo** ma analizować przepływ danych z logów runtime (nie statyczny kod). Benchmark testuje różne metryki dla każdego.

### Nowa struktura
```
code-benchmark-v2/
├── .env                    # OPENROUTER_API_KEY, MODEL_ID=deepseek/deepseek-r1
├── sample-app/             # Statyczny kod Python (1000 LOC)
├── sample-runtime/         # Aplikacja + logi runtime z trace_id
├── benchmarks/
│   ├── code2logic/         # Kompresja AST → LLM kontekst
│   ├── nfo-runtime/        # Kompresja logów → data flow
│   ├── callgraph/          # Statyczne call graphs
│   └── baseline-raw/       # Surowy kod jako baseline
└── Makefile
```

### Metryki benchmarku
| Kategoria | Metryka | code2logic | nfo | callgraph | baseline |
|-----------|---------|------------|-----|-----------|----------|
| **Rozmiar** | Tokens wejściowe | AST struktura | Log flow graph | Call graph JSON | Raw kod |
| **Szybkość** | Czas generacji [s] | Parse → compress | Log parse → graph | CLI analiza | - |
| **Efektywność** | Kompresja % | 80-90% | 70-85% | 85-95% | 0% |
| **Jakość LLM** | BLEU/ROUGE score | Analiza błędów | Data flow issues | Dependency cycles | Generic |
| **Runtime** | Memory [MB] | Niskie | Średnie (logi) | Niskie | Wysokie |

## Plan rozwoju nfo: Data Flow z logów

### Faza 1: Core parser logów (2-3 dni)
```python
# nfo/parser.py - Nowy moduł
class LogFlowParser:
    def __init__(self):
        self.trace_patterns = [
            r'trace_id=(\w+)',      # OpenTelemetry
            r'req-?id=(\w+)',       # Custom
            r'correlation.?id=(\w+)' # Spring/etc
        ]
    
    def parse_logs(self, log_files: list) -> DataFlowGraph:
        """Ekstrahuje przepływ z logów z trace_id"""
        graph = nx.DiGraph()
        traces = self._group_by_trace(log_files)
        
        for trace_id, events in traces.items():
            flow = self._build_flow(events)
            graph.add_edges_from(flow)
        
        return graph.to_compressed_json()  # Dla LLM: 10x mniejszy niż raw logi
```

**Wejście**: Logi z trace_id (structured logs JSON lub multiline)
**Wyjście**: Graf `serviceA.request -> DB.query -> serviceB.process`

### Faza 2: Integracja z LiteLLM (1 dzień)
```python
# nfo/benchmark.py
def nfo_dataflow_benchmark():
    flow_graph = LogFlowParser().parse_logs(["sample-runtime/app.log"])
    
    prompt = f"""
    Data flow z runtime logów:
    {flow_graph.json()}
    
    Znajdź: latency bottlenecks, error propagation paths, missing traces
    """
    # litellm.acompletion(model="deepseek-r1", ...)
```

### Faza 3: Wizualizacja + eksport (2 dni)
```
nfo generate sample-runtime/app.log \
  --output flow.json --viz flow.png \
  --llm-context --compress=90%
```

**Format LLM-ready**:
```json
{
  "flows": [
    {"from": "api.checkout", "to": "payment.process", "duration_ms": 250, "error_rate": 0.02},
    {"from": "payment.process", "to": "db.order", "latency_p95": 180}
  ],
  "anomalies": ["checkout -> payment timeout 15% requests"]
}
```

## Poprawiony Makefile
```makefile
.PHONY: benchmark-all results

benchmark-all:
	docker-compose run code2logic-bench    # Statyczna struktura
	docker-compose run nfo-runtime-bench   # Dynamiczne logi  
	docker-compose run callgraph-bench
	docker-compose run baseline-bench

results:
	python analyze.py  # Tabela + wykres tokenów vs jakość
```

## sample-runtime/ - Przykładowe logi
```bash
# Uruchom app z tracingiem
SAMPLE_APP=1 TRACING=otlp python sample-app/main.py
# Generuje app.log z 10k linii, trace_id, spans
```

**Oczekiwane wyniki**:
