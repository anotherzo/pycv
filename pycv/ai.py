import os
import json
import yaml
import logging
import instructor
from anthropic import Anthropic
from dotenv import load_dotenv
from typing import Iterable, Type, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
from abc import ABC, abstractmethod
from .baseclasses import CarStory, Cvitem, JobDescription, Summary, Letterinfo
from .cost_tracker import CostTracker

load_dotenv()  # Load environment variables from .env file

class LLMProvider(ABC):
    """Base class for LLM providers"""
    
    @abstractmethod
    def get_client(self):
        """Return the client for this provider"""
        pass

class AnthropicProvider(LLMProvider):
    """Provider for Anthropic Claude API"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    def get_client(self):
        return instructor.from_anthropic(Anthropic(api_key=self.api_key), mode=instructor.Mode.ANTHROPIC_JSON)

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

class CustomProvider(LLMProvider):
    """Provider for custom LLM servers"""
    
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
    
    def get_client(self):
        import openai
        client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
        return instructor.from_openai(client)

class Ai:
    def __init__(self, cost_tracker: Optional[CostTracker] = None):
        self.provider_type = os.getenv('LLM_PROVIDER', 'anthropic').lower()
        self.model = os.getenv('LLM_MODEL', 'claude-3-5-sonnet-20241022')
        self.max_tokens = int(os.getenv('LLM_MAX_TOKENS', '4096'))
        self.base_url = os.getenv('LLM_BASE_URL')  # For local LLMs
        self.logger = logging.getLogger(self.__class__.__name__)
        self.cost_tracker = cost_tracker or CostTracker()
        
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
        elif self.provider_type == 'custom':
            api_key = os.getenv('OPENAI_API_KEY', 'dummy-key')  # Some servers don't need a real key
            if not self.base_url:
                raise ValueError("LLM_BASE_URL environment variable is not set for custom provider")
            self.provider = CustomProvider(api_key, self.base_url)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider_type}")

    def ask(self, prompt: str, respmodel, operation: str = "generic_query"):
        client = self.provider.get_client()
        self.logger.info(f"Asking {self.provider_type} LLM for help with {operation}...")
        
        try:
            # Create messages for the API call
            messages = [
                {
                    "role": "user",
                    "content": prompt,
                }
            ]
            
            # For OpenAI provider or custom provider
            if self.provider_type in ['openai', 'custom']:
                try:
                    response = client.chat.completions.create(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        response_model=respmodel,
                        messages=messages
                    )
                    
                    # Debug logging for custom providers
                    if self.provider_type == 'custom':
                        self.logger.debug(f"Raw response from custom provider: {response}")
                        if hasattr(response, '_raw_response'):
                            self.logger.debug(f"_raw_response attribute: {response._raw_response}")
                    
                    # Extract token usage from OpenAI response
                    input_tokens = 0
                    output_tokens = 0
                    
                    # Try to get token usage if available
                    try:
                        if hasattr(response, '_raw_response') and response._raw_response is not None:
                            if hasattr(response._raw_response, 'usage'):
                                usage = response._raw_response.usage
                                input_tokens = getattr(usage, 'prompt_tokens', 0)
                                output_tokens = getattr(usage, 'completion_tokens', 0)
                            # For custom servers that might return different structures
                            elif isinstance(response._raw_response, dict):
                                usage = response._raw_response.get('usage', {})
                                if usage is not None:
                                    input_tokens = usage.get('prompt_tokens', 0)
                                    output_tokens = usage.get('completion_tokens', 0)
                    except (AttributeError, TypeError) as e:
                        self.logger.warning(f"Could not extract token usage: {e}")
                        # Estimate token count
                        input_tokens = len(prompt) // 4
                        response_str = str(response)
                        output_tokens = len(response_str) // 4
                    
                    # Track the cost
                    if self.cost_tracker:
                        self.cost_tracker.track_call(
                            provider=self.provider_type,
                            model=self.model,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            operation=operation
                        )
                    
                    self.logger.info(f"... answer received. Used {input_tokens} input and {output_tokens} output tokens.")
                        
                    return response
                except Exception as e:
                    self.logger.error(f"Error with OpenAI/custom provider: {e}")
                    # If we're using a custom provider, try a more direct approach as fallback
                    if self.provider_type == 'custom':
                        self.logger.info("Attempting fallback for custom provider...")
                        try:
                            import openai
                            client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
                            
                            # Try a simpler request without instructor
                            response = client.chat.completions.create(
                                model=self.model,
                                max_tokens=self.max_tokens,
                                messages=messages
                            )
                            
                            # Extract the content from the response
                            content = response.choices[0].message.content
                            
                            # Try to parse the content as JSON
                            try:
                                parsed_content = json.loads(content)
                                # Create an instance of the response model
                                if issubclass(respmodel, BaseModel):
                                    result = respmodel.model_validate(parsed_content)
                                    return result
                                elif hasattr(respmodel, '__origin__') and respmodel.__origin__ is Iterable:
                                    # Handle Iterable[SomeModel]
                                    item_type = respmodel.__args__[0]
                                    if isinstance(parsed_content, list):
                                        return [item_type.model_validate(item) for item in parsed_content]
                                    else:
                                        return [item_type.model_validate(parsed_content)]
                            except (json.JSONDecodeError, ValueError) as json_err:
                                self.logger.error(f"Failed to parse response as JSON: {json_err}")
                                raise
                        except Exception as fallback_err:
                            self.logger.error(f"Fallback approach failed: {fallback_err}")
                            raise
                    else:
                        raise
                
            # For Anthropic provider
            elif self.provider_type == 'anthropic':
                response = client.chat.completions.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    response_model=respmodel,
                    messages=messages
                )
                
                # Extract token usage from Anthropic response
                # Check different possible locations for token usage information
                usage_found = False
                
                # Check if usage is in _raw_response
                if hasattr(response, '_raw_response') and response._raw_response is not None:
                    raw_resp = response._raw_response
                    if hasattr(raw_resp, 'usage'):
                        usage = raw_resp.usage
                        if hasattr(usage, 'input_tokens') and hasattr(usage, 'output_tokens'):
                            input_tokens = usage.input_tokens
                            output_tokens = usage.output_tokens
                            usage_found = True
                    # Try dictionary access if it's a dict-like object
                    elif isinstance(raw_resp, dict) and 'usage' in raw_resp:
                        usage = raw_resp['usage']
                        if usage is not None and 'input_tokens' in usage and 'output_tokens' in usage:
                            input_tokens = usage['input_tokens']
                            output_tokens = usage['output_tokens']
                            usage_found = True
                
                # If we still don't have usage, estimate based on prompt and response length
                if not usage_found:
                    # Estimate token count (rough approximation: 1 token ≈ 4 characters)
                    input_tokens = len(prompt) // 4
                    # For output tokens, we need to estimate from the response
                    # Convert response to string representation and estimate
                    response_str = str(response)
                    output_tokens = len(response_str) // 4
                    
                    self.logger.info(f"Token usage not found in response, using estimated counts")
                
                # Track the cost
                if self.cost_tracker:
                    self.cost_tracker.track_call(
                        provider=self.provider_type,
                        model=self.model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        operation=operation
                    )
                
                self.logger.info(f"... answer received. Used {input_tokens} input and {output_tokens} output tokens.")
                    
                return response
                
        except Exception as e:
            self.logger.error(f"Error getting response from LLM: {e}")
            raise
    
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
        selectedStories = self.ask(prompt, Iterable[CarStory], operation="get_experience_stories")
        promptpath = os.path.join(os.path.dirname(__file__), 'refine-cars-prompt.txt')
        with open(promptpath, 'r') as f:
            prompt = f.read()
        prompt = prompt.format(
                    cars=self.get_json_for(selectedStories),
                    descriptions=self.get_json_for(descriptions),
                    job=joblink
        )
        return self.ask(prompt, Iterable[Cvitem], operation="refine_experience_items")

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
        job_descriptions = self.ask(prompt, Iterable[JobDescription], operation="get_job_summaries")
        
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
        return self.ask(prompt, Summary, operation="get_summary")

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
        return self.ask(prompt, Letterinfo, operation="get_letterinfo")


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
