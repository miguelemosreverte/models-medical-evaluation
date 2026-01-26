"""
Azure OpenAI client via VivioMed backend
Reusable utility for fast LLM calls across all chapters
"""

import requests
import time
from typing import Dict, Optional


class AzureOpenAIClient:
    """Client for Azure OpenAI via VivioMed transcription backend."""

    def __init__(self, endpoint: str = "https://viviomed-transcription-backend.azurewebsites.net/api/openai"):
        self.endpoint = endpoint

    def complete(
        self,
        user_prompt: str,
        system_prompt: str = "You are a helpful assistant",
        temperature: float = 0.7,
        max_tokens: int = 4000,
        timeout: int = 60
    ) -> Dict[str, any]:
        """
        Call Azure OpenAI for text completion.

        Args:
            user_prompt: The user message/prompt
            system_prompt: The system message
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds

        Returns:
            Dict with:
                - success: bool
                - completion: str (if successful)
                - response_time: float (seconds)
                - usage: dict (token counts)
                - error: str (if failed)
        """
        start_time = time.time()

        try:
            response = requests.post(
                self.endpoint,
                json={
                    "system": system_prompt,
                    "user": user_prompt,
                    "temperature": temperature,
                    "maxTokens": max_tokens
                },
                timeout=timeout
            )

            response_time = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'completion': data['completion'],
                    'response_time': response_time,
                    'usage': data.get('usage', {}),
                    'model': data.get('model', 'gpt-4o-mini')
                }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}: {response.text}",
                    'response_time': response_time
                }

        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Request timeout',
                'response_time': timeout
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'response_time': time.time() - start_time
            }

    def generate_json(
        self,
        user_prompt: str,
        system_prompt: str = "You are a helpful assistant",
        temperature: float = 0.7,
        max_tokens: int = 4000
    ) -> Dict[str, any]:
        """
        Generate JSON output from the model.

        Automatically handles markdown code blocks and parses JSON.

        Returns:
            Dict with:
                - success: bool
                - data: parsed JSON (if successful)
                - response_time: float
                - error: str (if failed)
        """
        result = self.complete(user_prompt, system_prompt, temperature, max_tokens)

        if not result['success']:
            return result

        try:
            # Parse JSON from response
            text = result['completion'].strip()

            # Remove markdown code blocks if present
            if text.startswith('```'):
                lines = text.split('\n')
                text = '\n'.join([l for l in lines if not l.startswith('```')])

            import json
            data = json.loads(text)

            return {
                'success': True,
                'data': data,
                'response_time': result['response_time'],
                'usage': result['usage']
            }

        except json.JSONDecodeError as e:
            return {
                'success': False,
                'error': f"JSON parse error: {e}",
                'raw_response': result['completion'],
                'response_time': result['response_time']
            }
