"""
AI Search adapter (Mock implementation).

Provides knowledge base search functionality.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class AISearchClient:
    """Mock AI Search client."""

    def __init__(self):
        """Initialize client with mock knowledge base."""
        self._interview_kb = [
            {
                "id": "kb001",
                "title": "インターネット接続トラブル診断手順",
                "content": "1. ランプ状態の確認 2. 機器の再起動 3. 回線試験",
                "category": "troubleshooting",
            },
            {
                "id": "kb002",
                "title": "ルーターランプ状態の見方",
                "content": "POWERランプ: 電源状態, WANランプ: 回線接続状態, LANランプ: LAN接続状態",
                "category": "device_info",
            },
        ]

        self._dispatch_kb = [
            {
                "id": "kb101",
                "title": "訪問修理の所要時間",
                "content": "通常の故障修理は1-2時間程度です",
                "category": "dispatch",
            },
            {
                "id": "kb102",
                "title": "訪問時の立ち会い",
                "content": "訪問時はお客様またはご家族の立ち会いが必要です",
                "category": "dispatch",
            },
        ]

    async def search_interview_kb(
        self, query: str, top_k: int = 3
    ) -> List[Dict]:
        """
        Search interview knowledge base.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of relevant KB articles
        """
        logger.info(f"AI Search: Searching interview KB for '{query}'")

        # Simple keyword matching for demo
        results = []
        for article in self._interview_kb:
            score = 0
            query_lower = query.lower()

            if any(
                keyword in article["title"].lower()
                or keyword in article["content"].lower()
                for keyword in query_lower.split()
            ):
                score += 1

            if score > 0:
                results.append({**article, "score": score})

        # Sort by score and return top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    async def search_dispatch_kb(
        self, query: str, top_k: int = 3
    ) -> List[Dict]:
        """
        Search dispatch knowledge base.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of relevant KB articles
        """
        logger.info(f"AI Search: Searching dispatch KB for '{query}'")

        # Simple keyword matching for demo
        results = []
        for article in self._dispatch_kb:
            score = 0
            query_lower = query.lower()

            if any(
                keyword in article["title"].lower()
                or keyword in article["content"].lower()
                for keyword in query_lower.split()
            ):
                score += 1

            if score > 0:
                results.append({**article, "score": score})

        # Sort by score and return top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]


# Global instance
_ai_search_client: Optional[AISearchClient] = None


def get_ai_search_client() -> AISearchClient:
    """Get or create AI Search client instance."""
    global _ai_search_client
    if _ai_search_client is None:
        _ai_search_client = AISearchClient()
    return _ai_search_client
