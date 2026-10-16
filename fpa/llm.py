"""Thin wrapper around the OpenAI client so the rest of the code stays simple."""
from __future__ import annotations

import json
import re

from openai import OpenAI

from . import config


def parse_json(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise


class LLM:
    def __init__(self, model: str | None = None):
        if not config.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is missing. Copy .env.example to .env and add your key.")
        self.client = OpenAI(api_key=config.OPENAI_API_KEY, max_retries=3)
        self.model = model or config.OPENAI_MODEL

    def _kwargs(self, **extra):
        kw = {"model": self.model, **extra}
        if config.TEMPERATURE is not None:
            kw["temperature"] = config.TEMPERATURE
        return kw

    def chat(self, messages: list, tools: list | None = None):
        """One chat turn. Returns the assistant message (may contain tool_calls)."""
        extra = {"messages": messages}
        if tools:
            extra.update(tools=tools, tool_choice="auto")
        return self.client.chat.completions.create(**self._kwargs(**extra)).choices[0].message

    def json_chat(self, system: str, user: str) -> dict:
        """One turn that must return a JSON object."""
        resp = self.client.chat.completions.create(**self._kwargs(
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_object"}))
        return parse_json(resp.choices[0].message.content)
