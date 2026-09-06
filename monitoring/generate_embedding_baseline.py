"""
Generate the embedding baseline for LLM query drift detection.

Embeds ~50 representative AQI questions and saves vectors + questions to
monitoring/embedding_baseline.npz. Mirrors monitoring/generate_baseline.py,
which does the same job for tabular features.

Usage:
    python monitoring/generate_embedding_baseline.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# llm/ is a sibling directory, not an installed package -> add it to the import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "llm"))

from embeddings import embed_batch, MODEL_NAME  # noqa: E402

REFERENCE_QUESTIONS = [
    # -- general safety --
    "Is the air quality safe today?",
    "How bad is the pollution right now?",
    "What is the current AQI level?",
    "Is it safe to go outside right now?",
    "Should I be worried about today's air quality?",
    # -- exercise / activities --
    "Is it safe to go for a run right now?",
    "Can I do my morning jog today?",
    "Should I cancel my outdoor workout?",
    "Is cycling to work a bad idea today?",
    "Can my kids play outside this afternoon?",
    "Is it okay to walk my dog in this air?",
    "Can we have a picnic outside today?",
    # -- sensitive groups --
    "Is the air safe for my asthmatic child?",
    "My grandmother has COPD, should she stay indoors?",
    "Is this air quality dangerous for pregnant women?",
    "How does PM2.5 affect elderly people?",
    "Should people with heart conditions avoid going out?",
    "Is the air safe for infants and toddlers?",
    # -- health symptoms --
    "Why do my eyes burn when I go outside?",
    "Can this pollution cause headaches?",
    "I have a sore throat, is it because of the air?",
    "What are the symptoms of PM2.5 exposure?",
    "Can air pollution make my allergies worse?",
    # -- protection measures --
    "Should I wear a mask outside today?",
    "What kind of mask protects against PM2.5?",
    "Do air purifiers help with this pollution?",
    "Should I keep my windows closed today?",
    "How can I protect myself from air pollution?",
    "What should I do when AQI is unhealthy?",
    # -- understanding the data --
    "What does PM2.5 mean?",
    "What is the difference between PM2.5 and PM10?",
    "What does an AQI of 150 mean?",
    "Why is PM2.5 more dangerous than PM10?",
    "What level of PM2.5 is considered unhealthy?",
    "How is the AQI calculated?",
    "What are safe levels of air pollution?",
    # -- trends / forecasts --
    "Will the air quality improve tomorrow?",
    "When is the best time of day to go outside?",
    "Is the air quality better in the morning or evening?",
    "What will the AQI be this weekend?",
    "Why is pollution worse in winter?",
    "How long will this bad air last?",
    # -- location specific --
    "How is the air quality in Kathmandu today?",
    "Which area of the city has the cleanest air?",
    "Is the air better outside the city center?",
    "Why is Kathmandu so polluted?",
    # -- comparisons / context --
    "Is today's air worse than yesterday?",
    "How does our air compare to WHO guidelines?",
    "Is indoor air safer than outdoor air right now?",
    "How much does traffic contribute to the pollution here?",
]

OUTPUT_FILE = Path(__file__).resolve().parent / "embedding_baseline.npz"


def main():
    print(f"Embedding {len(REFERENCE_QUESTIONS)} reference questions with {MODEL_NAME}...")
    embeddings = embed_batch(REFERENCE_QUESTIONS)

    print(f"Embeddings shape: {embeddings.shape}")  # expect (~50, 384)

    np.savez_compressed(
        OUTPUT_FILE,
        embeddings=embeddings.astype(np.float32),
        questions=np.array(REFERENCE_QUESTIONS),
        centroid=embeddings.mean(axis=0).astype(np.float32),
        model_name=np.array(MODEL_NAME),
        created_at=np.array(datetime.now(timezone.utc).isoformat()),
    )
    print(f"✅ Baseline saved to {OUTPUT_FILE} ({OUTPUT_FILE.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()