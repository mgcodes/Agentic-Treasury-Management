import requests
from dotenv import load_dotenv
import os

load_dotenv(override=True)
config = os.environ
from abc import ABC
import os
import json
from typing import Union, AsyncGenerator


class LlmAdapter:
    def __init__(self):
        # Get credentials from environment variables
        self.credentials = self._get_credentials_from_env()
        
        if self.is_available():
            # Initialize with credentials from env
            pass

    def _get_credentials_from_env(self):
        """Create service account credentials from environment variables."""
        try:
            # Get required fields from environment
            info = {
                "endpoint": os.getenv("LLM_ENDPOINT"),
                "model": os.getenv("LLM_MODEL_NAME"),
                "api_key": os.getenv("LLM_API_KEY"),
            }
            # debug step removed
            # Check if all required fields are present
            return info

        except Exception:
            return None

    def is_available(self) -> bool:
        required_fields = [
            self.credentials.get("endpoint"),
            self.credentials.get("model"),
            self.credentials.get("api_key"),
        ]
        return all(required_fields)

    async def generate(
        self, messages: list[dict], stream: bool = False, **kwargs
    ) -> Union[str, AsyncGenerator[str, None]]:
        if not self.is_available():
            raise ValueError("LLM adapter is not properly configured")

        try:
            pass
            headers: dict = {
                "Content-Type": "application/json",
                "X-API-KEY": self.credentials.get("api_key"),
            }

            payload = {
                "model": self.credentials.get("model"),
                "messages": messages,
                "temperature": kwargs.get("temperature", 0.9),
                "top_p": kwargs.get("top_p", 0.95),
                "max_tokens": kwargs.get("max_tokens", 4000),
                "stream": stream,
            }
            if stream:

                async def async_generator():
                    try:
                        # Create the stream

                        response = requests.post(
                            self.credentials.get("endpoint"),
                            headers=headers,
                            json=payload,
                            stream=True,
                            timeout=10,  # Adjust the timeout as needed
                        )

                        # Process each chunk
                        for chunk in response.iter_lines():
                            if chunk:
                                decoded_chunk = chunk.decode("utf-8")
                                if decoded_chunk.startswith("data: "):
                                    try:
                                        json_data = json.loads(decoded_chunk[6:])
                                        if "choices" in json_data and json_data[
                                            "choices"
                                        ][0]["delta"].get("content"):
                                            
                                            yield json_data["choices"][0]["delta"][
                                                    "content"
                                                ]
                                    except json.JSONDecodeError:
                                        # Handle cases where a chunk is not valid JSON
                                        # Or if it's the end of the stream
                                        if "[DONE]" in decoded_chunk:
                                            break
                    except Exception:
                        raise

                return async_generator()
            else:

                response = requests.post(
                    self.credentials.get("endpoint"), headers=headers, json=payload
                )

                
                data = response.json()
                # Process the response
                return data["choices"][0]["message"]["content"]

        except Exception:
            raise


llm_client = LlmAdapter()
 
 
# Pull sweep runner from new module if available
try:
    from agentic_sweeper.sweep_agent import run_sweep_example as run_sweep_example
except Exception:
    def run_sweep_example():
        print("sweep runner not available")


if __name__ == "__main__":
    run_sweep_example()
 