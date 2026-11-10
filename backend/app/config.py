from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """所有配置都从环境变量读取，见 deploy/.env.example。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"  # dev / prod
    database_url: str = "sqlite:///./dev.db"
    redis_url: str = ""  # 留空时用进程内存计数（仅开发用）

    jwt_secret: str = "dev-secret-change-me"
    jwt_expire_days: int = 30

    # 微信小程序
    wx_appid: str = "wxbe81a96f3114c5f3"
    wx_secret: str = ""
    # 订阅消息模板 ID（在小程序后台申请后填写）
    wx_tmpl_routine: str = ""
    wx_tmpl_medication: str = ""
    wx_miniprogram_state: str = "formal"  # developer / trial / formal

    # 管理后台
    admin_token: str = ""

    # 图片存在本机磁盘
    local_storage_dir: str = "./uploads"
    public_base_url: str = "http://localhost:8000"

    # 大模型：看图主模型 ChatGPT，备用通义千问 VL；文字用 DeepSeek
    openai_api_key: str = ""
    # 不直连 OpenAI，必须填自己服务器上的中转地址（OpenAI 兼容接口，如 https://relay.example.com/v1）；留空则不调用 ChatGPT
    openai_base_url: str = ""
    openai_vision_model: str = "gpt-4.1"
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_vision_model: str = "qwen-vl-max"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    ai_timeout_seconds: float = 40.0

    # 新用户赠送 Pro 试用天数
    trial_days: int = 7


@lru_cache
def get_settings() -> Settings:
    return Settings()
