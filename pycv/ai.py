import os
import json
import yaml
import logging
import instructor
from anthropic import Anthropic
from dotenv import load_dotenv
from typing import Iterable, Type, Dict, Any, Optional
from pydantic import BaseModel, Field
from abc import ABC, abstractmethod
from .baseclasses import CarStory, Cvitem, JobDescription, Summary, Letterinfo

load_dotenv()  # Load environment variables from .env file

class LLMProvider(ABC):
    """Base class for LLM providers"""
    
    @abstractmethod
    def get_client(self):
        """Return the client for this provider"""
        pass
    
    @abstractmethod
    def create_completion(self, client, model: str, max_tokens: int, response_model: Type[BaseModel], messages: list) -> Any:
        """Create a completion using the provider's API"""
        pass

class AnthropicProvider(LLMProvider):
    """Provider for Anthropic Claude API"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    def get_client(self):
        return instructor.from_anthropic(Anthropic(api_key=self.api_key), mode=instructor.Mode.ANTHROPIC_JSON)
    
    def create_completion(self, client, model: str, max_tokens: int, response_model: Type[BaseModel], messages: list) -> Any:
        return client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            response_model=response_model,
            messages=messages
        )

class OpenAIProvider(LLMProvider):
    """Provider for OpenAI and compatible APIs"""
    
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url
    
    def get_client(self):
        import openai
        client = openai.OpenAI(api_key=self.api_key)
        if self.base_url:
            client.base_url = self.base_url
        return instructor.from_openai(client)
    
    def create_completion(self, client, model: str, max_tokens: int, response_model: Type[BaseModel], messages: list) -> Any:
        return client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            response_model=response_model,
            messages=messages
        )

class Ai:
    def __init__(self):
        self.provider_type = os.getenv('LLM_PROVIDER', 'anthropic').lower()
        self.model = os.getenv('LLM_MODEL', 'claude-3-5-sonnet-20240620')
        self.max_tokens = int(os.getenv('LLM_MAX_TOKENS', '4096'))
        self.base_url = os.getenv('LLM_BASE_URL')  # For local LLMs
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Initialize the appropriate provider
        if self.provider_type == 'anthropic':
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
            self.provider = AnthropicProvider(api_key)
        elif self.provider_type == 'openai':
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is not set")
            self.provider = OpenAIProvider(api_key, self.base_url)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider_type}")

    def ask(self, prompt: str, respmodel):
        client = self.provider.get_client()
        self.logger.info(f"Asking {self.provider_type} LLM for help...")
        res = self.provider.create_completion(
            client=client,
            model=self.model,
            max_tokens=self.max_tokens,
            response_model=respmodel,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )
        self.logger.info("... answer received.")
        return res
    
    def get_json_for(self, arr: list) -> str:
        res = [item.model_dump() for item in arr]
        return json.dumps(res)

    def get_experience(self, jobs:list, carstories:list, descriptions:list, joblink:str) -> Iterable[Cvitem]:
        self.logger.info("Getting job experience information...")
        promptpath = os.path.join(os.path.dirname(__file__), 'cars-prompt.txt')
        with open(promptpath, 'r') as f:
            prompt = f.read()
        prompt = prompt.format(
                    jobs=self.get_json_for(jobs),
                    cars=self.get_json_for(carstories),
                    job=joblink
        )
        selectedStories = self.ask(prompt, Iterable[CarStory])
        promptpath = os.path.join(os.path.dirname(__file__), 'refine-cars-prompt.txt')
        with open(promptpath, 'r') as f:
            prompt = f.read()
        prompt = prompt.format(
                    cars=self.get_json_for(selectedStories),
                    descriptions=self.get_json_for(descriptions),
                    job=joblink
        )
        return self.ask(prompt, Iterable[Cvitem])

    def get_job_summaries(self, skills:list, statements:list, joblink:str) -> Iterable[JobDescription]:
        self.logger.info("Getting job summaries...")
        promptpath = os.path.join(os.path.dirname(__file__), 'jobdescription-prompt.txt')
        with open(promptpath, 'r') as f:
            prompt = f.read()
        prompt = prompt.format(
                    jobs=self.get_json_for(skills),
                    statements=self.get_json_for(statements),
                    job=joblink
        )
        job_descriptions = self.ask(prompt, Iterable[JobDescription])
        
        # Escape special LaTeX characters in descriptions
        for job_desc in job_descriptions:
            job_desc.description = job_desc.description.replace('_', '\\_').replace('%', '\\%').replace('&', '\\&').replace('#', '\\#').replace('$', '\\$').replace('{', '\\{').replace('}', '\\}')
        
        return job_descriptions

    def get_summary(self, skills:list, statements:list, joblink:str) -> Summary:
        self.logger.info("Getting resume summary...")
        promptpath = os.path.join(os.path.dirname(__file__), 'summary-prompt.txt')
        with open(promptpath, 'r') as f:
            prompt = f.read()
        prompt = prompt.format(
                    skills=self.get_json_for(skills),
                    statements=self.get_json_for(statements),
                    job=joblink
        )
        return self.ask(prompt, Summary)

    def get_letterinfo(self, statements:list, carstories:list, joblink:str) -> Letterinfo:
        self.logger.info("Getting coverletter...")
        promptpath = os.path.join(os.path.dirname(__file__), 'letterinfo-prompt.txt')
        with open(promptpath, 'r') as f:
            prompt = f.read()
        prompt = prompt.format(
                    job=joblink,
                    statements=self.get_json_for(statements),
                    cars=self.get_json_for(carstories),
        )
        return self.ask(prompt, Letterinfo)


class StubAi:
    def get_experience(self, jobs:list, carstories:list, descriptions:list, joblink:str) -> Iterable[CarStory]:
        return [
            Cvitem(job=1, item="foo"),
            Cvitem(job=1, item="bar"),
            Cvitem(job=1, item="baz"),
            Cvitem(job=2, item="foo"),
            Cvitem(job=2, item="bar"),
            Cvitem(job=2, item="baz"),
        ]

    def get_summary(self, skills:list, statements:list, joblink:str) -> Iterable[JobDescription]:
        return Summary(summary="This is some example text.")

    def get_job_summaries(self, skills:list, statements:list, joblink:str) -> Iterable[JobDescription]:
        return [
                JobDescription(job=1, description="Something I've done"),
                JobDescription(job=2, description="Something else I've done"),
        ]

    def get_letterinfo(self, statements:list, carstories:list, joblink:str) -> Letterinfo:
        return Letterinfo(
                recipient=["ABC Company","Somestreet 42 Happytown"],
                subject="Application for the position of Head Of Everything",
                opening="Friends, romans, countrymen, lend me your ear",
                content="I really really want to get this thing",
        )
