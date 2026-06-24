from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ollama_chat_model: str = "qwen2.5:3b"
    ollama_embed_model: str = "nomic-embed-text"

    model_config = {"env_prefix": ""}


settings = Settings()
