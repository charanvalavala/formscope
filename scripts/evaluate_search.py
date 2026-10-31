import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from formscope.retrieval import rank_passages
from formscope.semantic import rank_hybrid, rank_semantic, MODEL_ID, MODEL_REVISION


def run():
    passages = json.loads((ROOT / "data/eval/filing-passages.json").read_text())
    cases = json.loads((ROOT / "data/eval/filing-queries.json").read_text())
    texts = [item["text"] for item in passages]
    report = {
        "scope": "Thirty manually authored questions over twenty cropped SEC filing excerpts from ten issuers, selected from competition-related lexical results. This selection biases the benchmark and does not measure full-filing retrieval, unseen issuers or financial reasoning. No settings were tuned on these questions.",
        "model": MODEL_ID,
        "revision": MODEL_REVISION,
        "passages": len(texts),
        "queries": len(cases),
        "issuers": len({item["ticker"] for item in passages}),
        "methods": {},
    }
    for name, search in [
        ("lexical", rank_passages),
        ("semantic", rank_semantic),
        ("hybrid", rank_hybrid),
    ]:
        rows = []
        for case in cases:
            start = time.perf_counter()
            results = search(case["question"], texts, 5)
            ids = [passages[item["passage_index"]]["id"] for item in results]
            ranks = [i + 1 for i, value in enumerate(ids) if value in case["expected"]]
            rows.append(
                {
                    "id": case["id"],
                    "expected": case["expected"],
                    "retrieved": ids,
                    "hit1": bool(ranks and ranks[0] == 1),
                    "mrr": 1 / min(ranks) if ranks else 0,
                    "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                }
            )
        times = sorted(row["latency_ms"] for row in rows)
        report["methods"][name] = {
            "hit1": sum(row["hit1"] for row in rows) / len(rows),
            "mrr": sum(row["mrr"] for row in rows) / len(rows),
            "p50_ms": times[len(times) // 2],
            "p95_ms": times[int((len(times) - 1) * 0.95)],
            "details": rows,
        }
    path = ROOT / "reports/search-evaluation.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                name: {key: value for key, value in result.items() if key != "details"}
                for name, result in report["methods"].items()
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    run()
