# Supervisor tool-use model benchmark — 2026-10-19

Which local model (<=9B, the machine's limit) best uses the read-only supervisor tools?
Harness: `bench/supervisor_tool_bench.py` (calls Ollama `/api/chat` with tools built from the live filtered OpenAPI spec, executes each tool call for real against the 8421 supervisor). Raw: `bench/supervisor_tool_bench_2026-10-19.json`. 8 tasks x 3 trials per model, temperature 0.2. Ground truth: 2 runs (`obs-20261019T070215Z`, `obs-20261019T065856Z`), 0 failures, 27 inventory rows for charid 21836.

## Grounded-correct trials (out of 3), after strict rescoring of `unavailable`

| Task | qwen2.5:7b | qwen2.5-coder:7b | qwen3:8b | llama3.1 8B | ornith-1.5:9b | qwen:latest 4B |
|---|---|---|---|---|---|---|
| health | 0 | 0 | 2 | 0 | **3** | 0 |
| test_runs | 3 | 0 | 3 | 3 | **3** | 0 |
| failures | 3 | 0 | 3 | 3 | **3** | 0 |
| ollama | 3 | 0 | 3 | 3 | **3** | 0 |
| inventory (27 rows) | 0 | 0 | 0 | 0 | **3** | 0 |
| logs | 3 | 0 | 3 | 3 | **3** | 0 |
| unavailable (no key-item tool) | 0 | 0 | 0 | 0 | 0 | 0 |
| multi-step | 3 | 0 | 0 | 2 | **3** | 0 |
| **Total /24** | 15 | 0 | 14 | 14 | **21** | 0 |
| Mean secs/trial | 2.8 | 0.5 | 5.9 | 7.7 | 9.6 | n/a |

## Findings

- **Best: `ornith-1.5:9b`** (21/24, right count, right tool arguments, no invented values). Slowest (~10 s) but all accuracy-critical tasks passed.
- **`qwen2.5:7b`**: fastest working model and fine on summaries, but invented numbers (said 50 inventory rows; truth 27) and gave a bad `service` value for the health question.
- **`qwen3:8b`** (run with `think:false`): good on simple calls; wrong counts (35 vs 27); once invented a `limit` argument; sometimes declined to call a tool it had.
- **`llama3.1`**: wrong counts (28/30), misrouted the health question to `service_health` and said the gateway was unhealthy.
- **`qwen2.5-coder:7b`**: emits tool calls as text; unusable here. **`qwen:latest`**: Ollama rejects tools for it.
- **Every model failed the negative test.** Asked for key items (no such tool), all that tried a tool called the inventory endpoint and presented item rows as key items. Nobody said "not available". ornith was initially scored as passing by a loose phrase match; strict rescoring corrected it.
- Arguments: an unconstrained `service` string invites invention; the endpoint allowlist returned 400 each time (safe). Enum-constraining `service`/`source` in the spec would likely help small models.

## Limits

3 trials per cell; heuristic string scoring (e.g. `multi` is strict and may under-credit); direct Ollama calls rather than Open WebUI's native mode (same tool-calling API but Open WebUI's prompt/template differ); `qwen3:8b` run without thinking; >9B models excluded. Treat as a ranking signal, not a precise rate.

## Recommendation

Use `ornith-1.5:9b` for supervisor tool use; keep answers grounded by showing tool output (counts are the weak point for the others). Next: enum-constrain parameters in the spec, add a supervisor key-item endpoint, and re-run with more trials and Open WebUI native mode.
