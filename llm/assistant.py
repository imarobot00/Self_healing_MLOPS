"""
AQI Assistant - asks a Groq LLM air-quality questions using the
production prompt from the PromptRegistry.
"""

import logging
import time
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv
from groq import Groq

from prompt_registry import PromptRegistry
from trace_logger import TraceLogger
from embeddings import embed_text

# Load GROQ_API_KEY from the project-root .env (this file is in llm/, so go up one level).
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AQIAssistant:
    def __init__(self, prompt_id: str = "aqi_advisor"):
        self.prompt_id = prompt_id
        self.registry = PromptRegistry()
        self.client = Groq()  # automatically reads GROQ_API_KEY from the environment
        self.trace_logger = TraceLogger()  # one instance for the app's lifetime

    def ask(self, question: str, aqi_context: str) -> Dict:
        # 1. Always load whichever prompt version is currently 'production'.
        prompt = self.registry.get_production(self.prompt_id)

        # 2. Fill the template blanks with the real data + question.
        user_message = self.registry.render(
            prompt, aqi_context=aqi_context, question=question
        )

        # 3. Call the LLM. model + temperature come FROM the prompt version.
        start = time.perf_counter()
        response = self.client.chat.completions.create(
            model=prompt["model"],
            temperature=prompt["temperature"],
            messages=[
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": user_message},
            ],
        )
        latency_ms = (time.perf_counter() - start) * 1000

        # 4. Return the answer TAGGED with the prompt version + hash (audit trail).
        result = {
            "answer": response.choices[0].message.content,
            "prompt_version": prompt["version"],
            "prompt_hash": prompt["hash"],
            "model": prompt["model"],
        }

        # 5. Trace the interaction. Logging must never break the user's request.
        try:
            self.trace_logger.log(
                query=question,
                response=result["answer"],
                retrieved_context=aqi_context,
                prompt_version=result["prompt_version"],
                prompt_hash=result["prompt_hash"],
                model=result["model"],
                embedding=embed_text(question),
                latency_ms=round(latency_ms, 1),
            )
        except Exception as e:
            logger.warning(f"Trace logging failed (request unaffected): {e}")

        return result


if __name__ == "__main__":
    assistant = AQIAssistant()
    demo_context = "Location: Baneshwor. PM2.5: 82 µg/m³ (unhealthy). Temperature: 24°C. Humidity: 61%."
    result = assistant.ask("Is it safe to go for a run right now?", demo_context)
    print("\n--- ANSWER ---")
    print(result["answer"])
    print(f"\n(prompt v{result['prompt_version']} hash={result['prompt_hash']}, model={result['model']})")