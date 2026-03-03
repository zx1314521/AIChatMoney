from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    feishu_app_id: str = os.getenv("FEISHU_APP_ID", "").strip()
    feishu_app_secret: str = os.getenv("FEISHU_APP_SECRET", "").strip()
    feishu_verification_token: str = os.getenv("FEISHU_VERIFICATION_TOKEN", "").strip()

    # AI provider registry
    ai_provider: str = os.getenv("AI_PROVIDER", "deepseek").strip().lower()
    ai_providers: str = os.getenv("AI_PROVIDERS", "deepseek").strip()

    # Backward-compatible DeepSeek keys
    ai_api_key: str = os.getenv("AI_API_KEY", "").strip()
    ai_api_base_url: str = os.getenv("AI_API_BASE_URL", "https://api.deepseek.com").strip()
    ai_model: str = os.getenv("AI_MODEL", "deepseek-chat").strip()

    # Provider-specific configs
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "").strip()
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "").strip()
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "").strip()

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "").strip()
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    qwen_api_key: str = os.getenv("QWEN_API_KEY", "").strip()
    qwen_base_url: str = os.getenv(
        "QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ).strip()
    qwen_model: str = os.getenv("QWEN_MODEL", "qwen-plus").strip()

    port: int = int(os.getenv("PORT", "8000"))
    tz: str = os.getenv("TZ", "Asia/Shanghai").strip()
    report_cron: str = os.getenv("REPORT_CRON", "").strip()
    hot_push_times: str = os.getenv("HOT_PUSH_TIMES", "09:30,14:30").strip()
    price_alert_cron: str = os.getenv("PRICE_ALERT_CRON", "*/5 * * * 1-5").strip()
    price_alert_threshold_pct: float = float(os.getenv("PRICE_ALERT_THRESHOLD_PCT", "2"))

    default_open_id: str = os.getenv("FEISHU_DEFAULT_OPEN_ID", "").strip()
    default_chat_id: str = os.getenv("FEISHU_DEFAULT_CHAT_ID", "").strip()

    @property
    def has_feishu_auth(self) -> bool:
        return bool(self.feishu_app_id and self.feishu_app_secret)

    @property
    def enabled_ai_providers(self) -> List[str]:
        return [x.strip().lower() for x in self.ai_providers.split(",") if x.strip()]

    @property
    def provider_configs(self) -> Dict[str, dict]:
        deepseek_key = self.deepseek_api_key or self.ai_api_key
        deepseek_url = self.deepseek_base_url or self.ai_api_base_url
        deepseek_model = self.deepseek_model or self.ai_model
        return {
            "deepseek": {"api_key": deepseek_key, "base_url": deepseek_url, "model": deepseek_model},
            "openai": {"api_key": self.openai_api_key, "base_url": self.openai_base_url, "model": self.openai_model},
            "qwen": {"api_key": self.qwen_api_key, "base_url": self.qwen_base_url, "model": self.qwen_model},
        }


settings = Settings()
