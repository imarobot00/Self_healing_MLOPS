"""
Prompt Registry - Git-backed Version Tracking for LLM Prompts

Mirrors training/model_registry.py: each prompt is a versioned YAML file on
disk (Git tracks its history), and a registry.json per-prompt-id file holds
the "production" pointer, similar to how ModelRegistry tracks production
model IDs.

Usage:
    from prompt_registry import PromptRegistry

    registry = PromptRegistry()

    # Load the version currently live in production
    prompt = registry.get_production("aqi_advisor")

    # Load a specific version (e.g. to test a challenger before promoting it)
    prompt = registry.get_version("aqi_advisor", "2.0.0")
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional, Dict
import yaml #To read the prompt

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PromptRegistry:
    def __init__(self, prompt_dir: str = None):
        #This is for the prompt registry, which is a directory of prompts, each with a versioned YAML file and a registry.json file that holds the production pointer.
        if prompt_dir is None:
            prompt_dir = Path(__file__).parent / "prompts" # TThis will be the default prompts directory, which is a subdirectory of the current file's parent directory.
        self.prompts_dir = Path(prompt_dir)

    def _registry_path(self, prompt_id: str) -> Path:
        """Get the path to the registry.json for a given prompt ID"""
        return self.prompts_dir / prompt_id / "registry.json"

    def _version_path(self, prompt_id, version):
        return self.prompts_dir / prompt_id / f"v{version.split('.')[0]}.yaml"

    def _load_pointer_file(self, prompt_id):
        registry_path = self._registry_path(prompt_id)
        with open(registry_path, 'r') as f:
            return json.load(f)

    def get_production_version(self, prompt_id):
        pointer = self._load_pointer_file(prompt_id)
        version = pointer.get('production')
        if version is None:
            raise ValueError(f"No production version set for prompt ID '{prompt_id}'")
        return version

    def get_version(self, prompt_id, version):
        version_path = self._version_path(prompt_id, version)
        raw_text = version_path.read_text()
        prompt = yaml.safe_load(raw_text)
        prompt['hash'] = hashlib.sha256(raw_text.encode('utf-8')).hexdigest()[:12]
        return prompt

    def get_production(self, prompt_id):        # combo: "give me whatever's live"
        version = self.get_production_version(prompt_id)
        return self.get_version(prompt_id, version)

    def render(self, prompt, **kwargs):         # fill {question}, {aqi_context}
        return prompt['template'].format(**kwargs)


if __name__ == "__main__":
    registry = PromptRegistry()
    active = registry.get_production("aqi_advisor")
    print(f"Active prompt version: {active['version']}, hash: {active['hash']}") 