"""FactStore: every tool result gets an id (F1, F2, ...). Ids are what the narrative cites."""
from __future__ import annotations

import json

from . import data_tools, guardrails


class FactStore:
    def __init__(self):
        self.facts: dict[str, dict] = {}
        self._index: dict[tuple, str] = {}

    def call(self, data, tool: str, args: dict) -> str:
        """Run a tool (deduplicated by tool + normalised args) and store the result."""
        args = data_tools.normalize_args(tool, args)
        key = (tool, json.dumps(args, sort_keys=True))
        if key in self._index:
            return self._index[key]
        result = data_tools.call_tool(data, tool, args)
        if "error" in result:
            return ""  # failed calls are not facts
        fid = f"F{len(self.facts) + 1}"
        self.facts[fid] = {"fact_id": fid, "tool": tool, "args": args, "result": result}
        self._index[key] = fid
        return fid

    def ids(self) -> set:
        return set(self.facts)

    def numbers(self) -> list:
        return guardrails.collect_numbers([f["result"] for f in self.facts.values()] +
                                          [f["args"] for f in self.facts.values()])

    def as_list(self) -> list:
        return list(self.facts.values())

    def as_json(self) -> str:
        return json.dumps(self.as_list(), separators=(",", ":"))
