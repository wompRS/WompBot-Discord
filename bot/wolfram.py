"""
Wolfram Alpha API integration for computational knowledge queries.
"""
import os
import requests
from typing import Optional, Dict, Any
import urllib.parse


class WolframAlpha:
    """
    Wrapper for Wolfram Alpha API.

    Uses the Short Answers API for concise text responses perfect for chat.
    Handles calculations, unit conversions, factual queries, and more.
    """

    def __init__(self, app_id: Optional[str] = None):
        """
        Initialize Wolfram Alpha client.

        Args:
            app_id: Wolfram Alpha App ID. If not provided, reads from WOLFRAM_APP_ID env var.
        """
        self.app_id = app_id or os.getenv('WOLFRAM_APP_ID')
        if not self.app_id:
            raise ValueError("Wolfram Alpha App ID not configured. Set WOLFRAM_APP_ID environment variable.")

        self.short_answer_url = "http://api.wolframalpha.com/v1/result"
        self.simple_api_url = "http://api.wolframalpha.com/v1/simple"

        # Reusable HTTP session for connection pooling (avoids redundant TCP+TLS handshakes)
        self.session = requests.Session()

    def query(self, question: str, units: str = "metric") -> Dict[str, Any]:
        """
        Query Wolfram Alpha with a question.

        Args:
            question: Natural language question or calculation
            units: Unit system to use ("metric" or "imperial")

        Returns:
            Dict with success status, answer text, and metadata
        """
        try:
            # Try Short Answers API first (concise text response)
            params = {
                'appid': self.app_id,
                'i': question,
                'units': units,
                'timeout': 5,
            }

            response = self.session.get(self.short_answer_url, params=params, timeout=10)

            if response.status_code == 200:
                answer = response.text.strip()

                # Wolfram returns specific error messages
                if answer.lower() in ['wolfram|alpha did not understand your input',
                                     'no short answer available',
                                     'insufficient data']:
                    return {
                        'success': False,
                        'error': 'Could not find an answer to that query',
                        'query': question
                    }

                return {
                    'success': True,
                    'answer': answer,
                    'query': question,
                    'source': 'Wolfram Alpha'
                }
            else:
                return {
                    'success': False,
                    'error': f'API returned status {response.status_code}',
                    'query': question
                }

        except requests.Timeout:
            return {
                'success': False,
                'error': 'Request timed out',
                'query': question
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Error querying Wolfram Alpha: {str(e)}',
                'query': question
            }

    def calculate(self, expression: str) -> Dict[str, Any]:
        """
        Evaluate a mathematical expression.

        Args:
            expression: Math expression (e.g., "2+2", "sqrt(16)", "sin(pi/2)")

        Returns:
            Dict with calculation result
        """
        return self.query(expression)

    def convert(self, value: str, from_unit: str, to_unit: str) -> Dict[str, Any]:
        """
        Convert between units.

        Args:
            value: Value to convert
            from_unit: Source unit
            to_unit: Target unit

        Returns:
            Dict with conversion result
        """
        query = f"convert {value} {from_unit} to {to_unit}"
        return self.query(query)

    def get_fact(self, topic: str) -> Dict[str, Any]:
        """
        Get a fact about a topic.

        Args:
            topic: Topic to get information about

        Returns:
            Dict with factual answer
        """
        return self.query(topic)
