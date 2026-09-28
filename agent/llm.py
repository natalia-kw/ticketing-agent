"""Azure OpenAI client setup, shared by the agent and the PR review bot."""

import os

from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

REQUIRED_SETTINGS = (
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_API_VERSION",
    "AZURE_OPENAI_DEPLOYMENT",
)


class ConfigError(RuntimeError):
    """Raised when required Azure OpenAI settings are missing."""


def create_client() -> tuple[AzureOpenAI, str]:
    """Return an Azure OpenAI client and the deployment (model) name to use."""
    missing = [name for name in REQUIRED_SETTINGS if not os.getenv(name)]
    if missing:
        raise ConfigError(
            f"Missing settings: {', '.join(missing)}. "
            "Copy .env.example to .env and fill in the Azure OpenAI values."
        )

    client = AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
    )
    return client, os.environ["AZURE_OPENAI_DEPLOYMENT"]
