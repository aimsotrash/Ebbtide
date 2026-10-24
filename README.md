# Engram

[![CI](https://github.com/aimsotrash/Engram/actions/workflows/ci.yml/badge.svg)](https://github.com/aimsotrash/Engram/actions/workflows/ci.yml)

**Long-term memory for AI agents that forgets on purpose.**

Engram began as a notes app. I retired the notes app in October 2026; its last version is
the git tag [`notes-app`](https://github.com/aimsotrash/Engram/tree/notes-app).

**Live:** [aimsotrash-engram.vercel.app](https://aimsotrash-engram.vercel.app)

## Memory for AI agents

[`engram_mcp/`](engram_mcp/README.md) is an MCP server that gives an agent such as Claude
Code long-term memory across sessions, through four tools: `remember`, `recall`, `forget`
and `memory_stats`. Each memory fades along a forgetting curve unless it is recalled, and
every recall makes it last longer. When the store reaches its budget, 1000 memories by
default, the weakest one goes first. The memories live in a SQLite file on your machine,
and only what a recall returns enters the agent's context.

A local panel lists the memories and how strong each one is, with a slider that looks
ahead to show which ones are fading. Setup is three commands; see
[`engram_mcp/README.md`](engram_mcp/README.md).

### Should an agent forget?

I replayed six memory policies on two public long-conversation benchmarks and measured
whether the memory still finds the evidence each question needs.
[LongMemEval](bench/RESULTS.md) has 500 questions with histories of about 490 turns;
its 30 abstention questions have no evidence to find, so 470 are scored. Settings were picked on
92 dev questions and fixed before the other 378 were first scored.
[LoCoMo](bench/RESULTS-locomo.md) has 10 conversations that span 5 to 10 months, and
nothing was tuned on it.

- **Keeping everything wins when you can afford it.** With room for half the history, the
  best forgetting policy finds all the evidence in its top 10 results for 37% of LongMemEval
  questions and 27% of LoCoMo questions. Keeping everything does for 58.5% and 44.6%.
- **No forgetting rule wins everywhere.** On LongMemEval, keeping what gets used beats
  keeping the newest. On LoCoMo, keeping the newest does best at the turn level.
- **Strengthening on recall beats plain LRU, modestly.** engram-count, the server's
  default, keeps up to 4 points more of the evidence than LRU on LongMemEval, and ranks every
  answer session in its top 10 up to 14 points more often; I chose these comparisons after
  seeing the results. On LoCoMo, where I chose the comparison before running it, both gains
  held but were smaller (up to 1.6 and 3.4 points), and it found all the evidence in its top
  10 about as often as LRU.
- **Strengthening too hard backfires on facts that change.** FSRS-style spacing made old
  facts stick: on LongMemEval's knowledge-update questions it found the newest fact 12 to
  17 points less often than LRU.
- **Fading didn't help as a ranking signal.** Tuning picked similarity alone almost
  everywhere, so the gains come from what is kept, not from how it is ranked.

MemoryBank (Zhong et al., 2023) already applied an Ebbinghaus curve to LLM memory. What is
new here is the measured comparison with simple baselines, losses included.

## Stack

Python · MCP · sentence-transformers · NumPy · SQLite · React · TypeScript · Vite ·
Tailwind CSS · Motion

## Run it locally

To run the MCP server, follow the setup in [`engram_mcp/README.md`](engram_mcp/README.md).

To reproduce the benchmarks, in the `.venv` from that setup:

```bash
.venv/bin/python -m bench.longmemeval embed   # downloads the data and embeds it once, ~45 min on a laptop CPU
.venv/bin/python -m bench.longmemeval run     # writes bench/RESULTS.md
.venv/bin/python -m bench.locomo              # writes bench/RESULTS-locomo.md
```

The landing page for the MCP server lives in `site/` (Vite, React and Tailwind):

```bash
cd site && npm install && npm run dev   # http://localhost:5173
```

The Python tests (18: 12 intelligence, 2 MCP server, 4 benchmark) stub the embedding model,
so they need only `requirements-test.txt`, which adds pytest:

```bash
.venv/bin/pip install -r requirements-test.txt
.venv/bin/python -m pytest intelligence/tests engram_mcp/tests bench
```

## References

- Di Wu et al. *LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory.*
  2024. [arXiv:2410.10813](https://arxiv.org/abs/2410.10813)
- Adyasha Maharana et al. *Evaluating Very Long-Term Conversational Memory of LLM Agents.*
  ACL 2024. [arXiv:2402.17753](https://arxiv.org/abs/2402.17753). The LoCoMo data is
  CC BY-NC 4.0; it is downloaded, never committed, and used here for non-commercial research.
- Wanjun Zhong et al. *MemoryBank: Enhancing Large Language Models with Long-Term Memory.*
  2023. [arXiv:2305.10250](https://arxiv.org/abs/2305.10250)
- FSRS, the spaced-repetition scheduler whose default weights the spaced rule uses:
  [open-spaced-repetition](https://github.com/open-spaced-repetition)

## License

[MIT](LICENSE).
