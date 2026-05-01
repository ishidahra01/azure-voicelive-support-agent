"""
OOB (Out-of-Band) client for Azure OpenAI / Foundry inference.

Provides a thin wrapper around the OpenAI SDK for non-real-time inference tasks
such as summarization, classification, and other text processing operations.
"""

import logging
from typing import Any, Dict, List, Optional

from openai import AsyncAzureOpenAI
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class OOBConfig(BaseModel):
    """Configuration for OOB client."""

    endpoint: str
    api_key: str
    api_version: str = "2024-10-21"
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 1000


class OOBClient:
    """
    Client for out-of-band (non-real-time) LLM inference.

    Used for tasks like summarization, classification, and analysis that don't
    require real-time streaming responses.
    """

    def __init__(self, config: OOBConfig):
        """
        Initialize the OOB client.

        Args:
            config: OOB configuration
        """
        self.config = config
        self.client = AsyncAzureOpenAI(
            azure_endpoint=config.endpoint,
            api_key=config.api_key,
            api_version=config.api_version,
        )

    async def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        """
        Complete a chat conversation.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (overrides config)
            max_tokens: Maximum tokens to generate (overrides config)
            **kwargs: Additional arguments passed to the API

        Returns:
            Generated text response
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=temperature or self.config.temperature,
                max_tokens=max_tokens or self.config.max_tokens,
                **kwargs,
            )

            content = response.choices[0].message.content

            if content is None:
                logger.warning("Empty response from OOB client")
                return ""

            return content

        except Exception as e:
            logger.error(f"Error in OOB completion: {e}", exc_info=True)
            raise

    async def summarize(
        self,
        text: str,
        max_length: int = 200,
        style: str = "concise",
    ) -> str:
        """
        Summarize text.

        Args:
            text: Text to summarize
            max_length: Maximum length of summary in characters
            style: Summary style ("concise", "detailed", "bullet_points")

        Returns:
            Summarized text
        """
        style_prompts = {
            "concise": "要約は簡潔に、最も重要な情報のみを含めてください。",
            "detailed": "要約は詳細に、主要なポイントすべてを含めてください。",
            "bullet_points": "要約を箇条書きで、各ポイントを明確に記載してください。",
        }

        style_instruction = style_prompts.get(style, style_prompts["concise"])

        messages = [
            {
                "role": "system",
                "content": f"以下のテキストを{max_length}文字程度で要約してください。{style_instruction}",
            },
            {"role": "user", "content": text},
        ]

        return await self.complete(messages, temperature=0.3, max_tokens=500)

    async def classify(
        self,
        text: str,
        categories: List[str],
        instructions: Optional[str] = None,
    ) -> str:
        """
        Classify text into one of the given categories.

        Args:
            text: Text to classify
            categories: List of possible categories
            instructions: Additional classification instructions

        Returns:
            Selected category
        """
        categories_str = "\n".join(f"- {cat}" for cat in categories)

        system_content = f"""以下のカテゴリのいずれかにテキストを分類してください:

{categories_str}

カテゴリ名のみを返してください。"""

        if instructions:
            system_content += f"\n\n追加の指示: {instructions}"

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": text},
        ]

        response = await self.complete(messages, temperature=0.1, max_tokens=50)

        # Extract the category from the response
        response_clean = response.strip().lower()

        for category in categories:
            if category.lower() in response_clean:
                return category

        logger.warning(f"Classification unclear, defaulting to first category: {response}")
        return categories[0]

    async def extract_structured(
        self,
        text: str,
        schema: Dict[str, Any],
        instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract structured information from text.

        Args:
            text: Text to extract from
            schema: JSON schema describing the desired structure
            instructions: Additional extraction instructions

        Returns:
            Extracted structured data
        """
        import json

        schema_str = json.dumps(schema, indent=2, ensure_ascii=False)

        system_content = f"""以下のスキーマに従って、テキストから情報を抽出してJSON形式で返してください:

{schema_str}

JSONのみを返し、他のテキストは含めないでください。"""

        if instructions:
            system_content += f"\n\n追加の指示: {instructions}"

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": text},
        ]

        response = await self.complete(messages, temperature=0.1, max_tokens=1000)

        try:
            # Try to parse JSON from the response
            # Remove markdown code blocks if present
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                cleaned = cleaned.strip()

            return json.loads(cleaned)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from response: {response}")
            raise ValueError(f"Invalid JSON in response: {e}")

    async def close(self) -> None:
        """Close the client and clean up resources."""
        await self.client.close()


async def create_oob_client(
    endpoint: str,
    api_key: str,
    **kwargs,
) -> OOBClient:
    """
    Convenience function to create an OOB client.

    Args:
        endpoint: Azure OpenAI endpoint URL
        api_key: API key
        **kwargs: Additional config arguments

    Returns:
        Initialized OOBClient
    """
    config = OOBConfig(endpoint=endpoint, api_key=api_key, **kwargs)
    return OOBClient(config)
