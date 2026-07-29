from pathlib import Path
import os
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


class ModelConfig(BaseModel):
    name: str = "openai/gpt-oss-20b:free"
    temperature: float = Field(default=0.7, ge=0, le=2.0)
    context_window: int = 256_000


class Config(BaseModel):
    model: ModelConfig = Field(default_factoy=ModelConfig)
    cwd: Path = Field(default_factory=Path.cwd())

    max_turns: int = 100

    developer_instructions: str | None = None
    user_instructions: str | None = None

    debug: bool = False

    @property
    def api_key(self):
        return os.environ.get("API_KEY")

    @property
    def base_url(self):
        return os.environ.get("BASE_URL")

    @property
    def model_name(self):
        return self.model.name

    @model_name.setter
    def model_name(self, value: str) -> None:
        self.model.name = value

    @property
    def temperature(self):
        return self.model.temperature

    @temperature.setter
    def temperature(self, value: float) -> None:
        self.model.temperature = value

    def validate(self) -> list[str]:
        errors: list[str] = []

        if not self.api_key:
            errors.append(f"No API Key found. Set API_KEY environment variable")

        if not self.base_url:
            errors.append(f"No base url found. Set BASE_URL environment variable")

        if not self.cwd.exists():
            errors.append(f"Working directory does not exist: {self.cwd}")

        return errors
