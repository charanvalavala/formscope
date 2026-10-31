import os
import threading
import urllib.request
from functools import lru_cache
from pathlib import Path

import numpy as np

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
MODEL_FILE = "onnx/model_quint8_avx2.onnx"
LOCK = threading.Lock()


def download_model():
    root = Path(
        os.getenv(
            "FORMSCOPE_MODEL_DIR",
            str(Path(__file__).resolve().parents[2] / "data" / "runtime" / "models"),
        )
    )
    root.mkdir(parents=True, exist_ok=True)
    for remote, name in [
        (MODEL_FILE, "model.onnx"),
        ("tokenizer.json", "tokenizer.json"),
    ]:
        target = root / name
        if not target.exists():
            temporary = target.with_suffix(target.suffix + ".download")
            with urllib.request.urlopen(
                f"https://huggingface.co/{MODEL_ID}/resolve/{MODEL_REVISION}/{remote}",
                timeout=90,
            ) as response:
                with temporary.open("wb") as output:
                    while chunk := response.read(1024 * 1024):
                        output.write(chunk)
            temporary.replace(target)
    return root


@lru_cache(maxsize=1)
def runtime():
    import onnxruntime as ort
    from tokenizers import Tokenizer

    with LOCK:
        root = download_model()
    tokenizer = Tokenizer.from_file(str(root / "tokenizer.json"))
    tokenizer.enable_truncation(max_length=256)
    tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    session = ort.InferenceSession(
        str(root / "model.onnx"),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    return tokenizer, session


def embed(texts):
    tokenizer, session = runtime()
    vectors = []
    for start in range(0, len(texts), 16):
        with LOCK:
            encoded = tokenizer.encode_batch(texts[start : start + 16])
        ids = np.asarray([item.ids for item in encoded], dtype=np.int64)
        mask = np.asarray([item.attention_mask for item in encoded], dtype=np.int64)
        inputs = {
            "input_ids": ids,
            "attention_mask": mask,
            "token_type_ids": np.zeros_like(ids),
        }
        inputs = {item.name: inputs[item.name] for item in session.get_inputs()}
        tokens = session.run(None, inputs)[0]
        pooled = (tokens * mask[..., None]).sum(1) / mask.sum(1, keepdims=True).clip(
            min=1
        )
        pooled /= np.linalg.norm(pooled, axis=1, keepdims=True).clip(min=1e-9)
        vectors.extend(pooled)
    return np.asarray(vectors)


@lru_cache(maxsize=4)
def passage_vectors(passages):
    return embed(list(passages))


def rank_semantic(question, passages, top_k=5):
    if not passages:
        return []
    scores = passage_vectors(tuple(passages)) @ embed([question])[0]
    indices = np.argsort(-scores, kind="stable")[:top_k]
    return [
        {
            "rank": rank + 1,
            "score": float(scores[index]),
            "text": passages[index],
            "passage_index": int(index),
        }
        for rank, index in enumerate(indices)
        if scores[index] >= 0.28
    ]


def rank_hybrid(question, passages, top_k=5):
    from formscope.retrieval import rank_passages

    dense = rank_semantic(question, passages, 20)
    lexical = rank_passages(question, passages, 20)
    scores = {}
    for results in (lexical, dense):
        for rank, item in enumerate(results, 1):
            index = item["passage_index"]
            scores[index] = scores.get(index, 0) + 1 / (60 + rank)
    ids = sorted(scores, key=lambda index: (-scores[index], index))[:top_k]
    return [
        {
            "rank": rank + 1,
            "score": scores[index],
            "text": passages[index],
            "passage_index": index,
        }
        for rank, index in enumerate(ids)
    ]
