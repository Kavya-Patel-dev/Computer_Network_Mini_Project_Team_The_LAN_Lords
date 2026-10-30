"""Hard split guard for every Day 4 topology load."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SplitLeakageError(ValueError):
    pass


def read_partitions(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    train = {row["name"] for row in data["train"]}
    val = {row["name"] for row in data["val"]}
    holdout = {row["name"] for row in data["test"]}
    if train & val or train & holdout or val & holdout:
        raise SplitLeakageError("split graph partitions overlap")
    return data


def guard_graph_request(entry: dict[str, Any], requested_split: str,
                        partitions: dict[str, list[dict[str, Any]]]) -> None:
    """Reject a holdout graph before its topology path can be opened."""
    name = str(entry.get("name", ""))
    holdout_names = {row["name"] for row in partitions["test"]}
    if name in holdout_names:
        raise SplitLeakageError(f"locked holdout graph {name!r} cannot be loaded by Day 4")
    if requested_split not in {"train", "val"}:
        raise SplitLeakageError("Day 4 graph loads are limited to train and validation")
    allowed_names = {row["name"] for row in partitions[requested_split]}
    if name not in allowed_names or entry.get("split", requested_split) != requested_split:
        raise SplitLeakageError(
            f"graph {name!r} is not in the requested {requested_split} partition")

