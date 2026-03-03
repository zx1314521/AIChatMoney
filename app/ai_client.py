from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from app.config import settings


@dataclass
class ProviderStatus:
    name: str
    enabled_in_list: bool
    configured: bool
    model: str
    base_url: str
    active: bool


class OpenAICompatibleProvider:
    def __init__(self, name: str, api_key: str, base_url: str, model: str) -> None:
        self.name = name
        self.api_key = api_key.strip()
        self.base_url = base_url.strip().rstrip("/")
        self.model = model.strip()

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
        if not self.configured:
            raise RuntimeError(f"AI provider {self.name} 未配置完整")

        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            "temperature": temperature,
        }
        resp = requests.post(url, headers=headers, json=body, timeout=25)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("AI返回为空")
        content = (choices[0].get("message") or {}).get("content")
        if not content:
            raise RuntimeError("AI返回空内容")
        return content


class AIClient:
    def __init__(self) -> None:
        cfg = settings.provider_configs
        self.providers: dict[str, OpenAICompatibleProvider] = {
            "deepseek": OpenAICompatibleProvider("deepseek", **cfg["deepseek"]),
            "openai": OpenAICompatibleProvider("openai", **cfg["openai"]),
            "qwen": OpenAICompatibleProvider("qwen", **cfg["qwen"]),
        }
        self.enabled = settings.enabled_ai_providers or ["deepseek"]
        self.active_provider_name = settings.ai_provider if settings.ai_provider in self.providers else "deepseek"

    def list_providers(self) -> list[ProviderStatus]:
        statuses: list[ProviderStatus] = []
        for name, p in self.providers.items():
            statuses.append(
                ProviderStatus(
                    name=name,
                    enabled_in_list=name in self.enabled,
                    configured=p.configured,
                    model=p.model,
                    base_url=p.base_url,
                    active=name == self.active_provider_name,
                )
            )
        return statuses

    def set_active_provider(self, name: str) -> str:
        key = name.strip().lower()
        if key not in self.providers:
            raise ValueError(f"不支持的provider: {name}")
        if key not in self.enabled:
            raise ValueError(f"provider未在 AI_PROVIDERS 中启用: {name}")
        if not self.providers[key].configured:
            raise ValueError(f"provider配置不完整: {name}")
        self.active_provider_name = key
        return key

    def _resolve_provider(self) -> OpenAICompatibleProvider | None:
        candidate = self.providers.get(self.active_provider_name)
        if candidate and candidate.name in self.enabled and candidate.configured:
            return candidate
        for name in self.enabled:
            p = self.providers.get(name)
            if p and p.configured:
                self.active_provider_name = name
                return p
        return None

    def _chat(self, system_prompt: str, user_prompt: str) -> str:
        provider = self._resolve_provider()
        if provider is None:
            return "未找到可用AI provider，请配置 AI_PROVIDERS 与对应 API Key。"
        try:
            return provider.chat(system_prompt, user_prompt)
        except Exception as e:
            return f"AI分析失败({provider.name}): {e}"

    def analyze_hot_topics(self, topics: list[str]) -> str:
        if not topics:
            return "暂无可分析热点。"
        user_prompt = (
            "请基于下面热点给出:\n"
            "1) 可能主线\n2) 风险点\n3) 接下来1-3个交易日观察指标。\n"
            "要求简洁，最多220字。\n\n热点:\n"
            + "\n".join(f"- {t}" for t in topics)
        )
        return self._chat("你是专业的A股/基金研究助理。", user_prompt)

    def analyze_asset(self, asset_type: str, symbol: str, context: str) -> str:
        user_prompt = (
            f"请分析{asset_type} {symbol}。\n"
            "给出:\n1) 短线观点\n2) 中线观点\n3) 关键风险\n4) 操作计划(观察/分批/止损位)。\n"
            "控制在300字以内。\n\n"
            f"数据:\n{context}"
        )
        return self._chat("你是谨慎的投研助手，只能基于给定数据进行推断，不得虚构。", user_prompt)
