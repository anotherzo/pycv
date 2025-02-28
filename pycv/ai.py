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
        # Make sure the endpoint starts with /v1 as shown in the server logs
        self.endpoint = os.getenv('LLM_ENDPOINT', '/v1/chat/completions')
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"using {self.endpoint}")
        
    def get_client(self):
        import openai
        # The OpenAI client will automatically append the endpoint to the base_url
        client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
        return client  # Return raw client, we'll handle the instructor part manually

class Ai:
    def __init__(self, cost_tracker: Optional[CostTracker] = None):
        self.provider_type = os.getenv('LLM_PROVIDER', 'anthropic').lower()
        self.model = os.getenv('LLM_MODEL', 'claude-3-5-sonnet-20241022')
        
        # Get max_tokens with better error handling
        max_tokens_str = os.getenv('LLM_MAX_TOKENS', '4096')
        try:
            self.max_tokens = int(max_tokens_str) if max_tokens_str else 4096
        except ValueError:
            self.logger = logging.getLogger(self.__class__.__name__)
            self.logger.warning(f"Invalid value for LLM_MAX_TOKENS: '{max_tokens_str}'. Using default of 4096.")
            self.max_tokens = 4096
            
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
            
            # For OpenAI provider
            if self.provider_type == 'openai':
                try:
                    response = client.chat.completions.create(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        response_model=respmodel,
                        messages=messages
                    )
                    
                    # Extract token usage from OpenAI response
                    input_tokens = 0
                    output_tokens = 0
                    
                    # Try to get token usage if available
                    try:
                        # First check if response has a usage attribute directly
                        if hasattr(response, 'usage'):
                            usage = response.usage
                            input_tokens = getattr(usage, 'prompt_tokens', 0)
                            output_tokens = getattr(usage, 'completion_tokens', 0)
                        # Then check if it's in _raw_response
                        elif hasattr(response, '_raw_response') and response._raw_response is not None:
                            raw_resp = response._raw_response
                            if hasattr(raw_resp, 'usage'):
                                usage = raw_resp.usage
                                input_tokens = getattr(usage, 'prompt_tokens', 0)
                                output_tokens = getattr(usage, 'completion_tokens', 0)
                            # For custom servers that might return different structures
                            elif isinstance(raw_resp, dict) and 'usage' in raw_resp:
                                usage = raw_resp['usage']
                                if usage is not None:
                                    input_tokens = usage.get('prompt_tokens', 0)
                                    output_tokens = usage.get('completion_tokens', 0)
                        
                        # If we still don't have token counts, check if it's in the response dict
                        if input_tokens == 0 and output_tokens == 0 and hasattr(response, '__dict__'):
                            resp_dict = response.__dict__
                            if 'usage' in resp_dict and resp_dict['usage'] is not None:
                                usage = resp_dict['usage']
                                if isinstance(usage, dict):
                                    input_tokens = usage.get('prompt_tokens', 0)
                                    output_tokens = usage.get('completion_tokens', 0)
                        
                        # If we still don't have token counts, try to access the response as a dictionary
                        if input_tokens == 0 and output_tokens == 0:
                            try:
                                if isinstance(response, dict) and 'usage' in response:
                                    usage = response['usage']
                                    input_tokens = usage.get('prompt_tokens', 0)
                                    output_tokens = usage.get('completion_tokens', 0)
                            except (TypeError, AttributeError):
                                pass
                                
                        # If we still don't have token counts, estimate them
                        if input_tokens == 0 and output_tokens == 0:
                            # Log the response structure to help debug
                            self.logger.debug(f"Response type: {type(response)}")
                            self.logger.debug(f"Response attributes: {dir(response) if hasattr(response, '__dir__') else 'No dir available'}")
                            
                            # Estimate token count (rough approximation: 1 token ≈ 4 characters)
                            input_tokens = len(prompt) // 4
                            # For output tokens, we need to estimate from the response
                            response_str = str(response)
                            output_tokens = len(response_str) // 4
                            self.logger.debug("Using estimated token counts")
                            
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
                    self.logger.error(f"Error with OpenAI provider: {e}")
                    # Create a fallback response based on the model type
                    if issubclass(respmodel, Summary):
                        return Summary(summary="Failed to generate summary due to API error.")
                    elif issubclass(respmodel, Letterinfo):
                        return Letterinfo(
                            recipient=["Company"],
                            subject="Application",
                            opening="Dear Hiring Manager,",
                            content="Failed to generate content due to API error."
                        )
                    elif hasattr(respmodel, '__origin__') and respmodel.__origin__ is Iterable:
                        # For Iterable[JobDescription] or similar
                        item_type = respmodel.__args__[0]
                        if issubclass(item_type, JobDescription):
                            return [JobDescription(job=1, description="Failed to generate description due to API error.")]
                        elif issubclass(item_type, Cvitem):
                            return [Cvitem(job=1, item="Failed to generate item due to API error.")]
                        else:
                            # Create a stub response for other iterable types
                            return [item_type()]
                    else:
                        # Last resort: return a stub instance
                        return respmodel()
            # For custom provider
            elif self.provider_type == 'custom':
                try:
                    # For custom provider, don't use response_model directly with OpenAI client
                    response = client.chat.completions.create(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        messages=messages
                    )
                        
                    # Check if response is None or doesn't have the expected structure
                    if not response or not hasattr(response, 'choices') or not response.choices:
                        self.logger.error("Received invalid response from custom provider")
                        # Create a fallback response based on the model type
                        if issubclass(respmodel, Summary):
                            return Summary(summary="Failed to generate summary due to API error.")
                        elif issubclass(respmodel, Letterinfo):
                            return Letterinfo(
                                recipient=["Company"],
                                subject="Application",
                                opening="Dear Hiring Manager,",
                                content="Failed to generate content due to API error."
                            )
                        elif hasattr(respmodel, '__origin__') and respmodel.__origin__ is Iterable:
                            # For Iterable[JobDescription] or similar
                            item_type = respmodel.__args__[0]
                            if issubclass(item_type, JobDescription):
                                return [JobDescription(job=1, description="Failed to generate description due to API error.")]
                            elif issubclass(item_type, Cvitem):
                                return [Cvitem(job=1, item="Failed to generate item due to API error.")]
                            else:
                                # Create a stub response for other iterable types
                                return [item_type()]
                        else:
                            # Last resort: return a stub instance
                            return respmodel()
                        
                    # Extract the content from the response
                    content = response.choices[0].message.content
                    
                    # Strip out any thinking section enclosed in ``` tags
                    think_start = content.find("```thinking")
                    if think_start != -1:
                        think_end = content.find("```", think_start + 10)
                        if think_end != -1:
                            think_end += 3  # Include the closing ```
                            content = content[:think_start] + content[think_end:]
                            content = content.strip()
                            self.logger.debug(f"Removed thinking section from response")
                    
                    self.logger.debug(f"Raw response content: {content}")
                    
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
                    except json.JSONDecodeError as json_err:
                        self.logger.error(f"Failed to parse response as JSON: {json_err}")
                        self.logger.debug(f"Non-JSON response: {content}")
                        
                        # If we can't parse as JSON, try to create a simple instance with the text
                        if issubclass(respmodel, Summary):
                            return Summary(summary=content)
                        elif issubclass(respmodel, Letterinfo):
                            return Letterinfo(
                                recipient=["Company"],
                                subject="Application",
                                opening="Dear Hiring Manager,",
                                content=content
                            )
                        elif hasattr(respmodel, '__origin__') and respmodel.__origin__ is Iterable:
                            # For Iterable[JobDescription] or similar
                            item_type = respmodel.__args__[0]
                            if issubclass(item_type, JobDescription):
                                return [JobDescription(job=1, description=content)]
                            elif issubclass(item_type, Cvitem):
                                return [Cvitem(job=1, item=content)]
                            else:
                                # Create a stub response for other iterable types
                                return [item_type()]
                        else:
                            # Last resort: return a stub instance
                            return respmodel()
                    
                    # Make sure result is defined before we try to use it
                    if 'result' not in locals():
                        # If result wasn't set in the try block, create a fallback
                        if issubclass(respmodel, Summary):
                            result = Summary(summary=content)
                        elif issubclass(respmodel, Letterinfo):
                            result = Letterinfo(
                                recipient=["Company"],
                                subject="Application",
                                opening="Dear Hiring Manager,",
                                content=content
                            )
                        elif hasattr(respmodel, '__origin__') and respmodel.__origin__ is Iterable:
                            # For Iterable[JobDescription] or similar
                            item_type = respmodel.__args__[0]
                            if issubclass(item_type, JobDescription):
                                result = [JobDescription(job=1, description=content)]
                            elif issubclass(item_type, Cvitem):
                                result = [Cvitem(job=1, item=content)]
                            else:
                                # Create a stub response for other iterable types
                                result = [item_type()]
                        else:
                            # Last resort: return a stub instance
                            result = respmodel()
                        
                    # Extract token usage from OpenAI response
                    input_tokens = 0
                    output_tokens = 0
                        
                    # Try to get token usage if available
                    try:
                        # First check if response has a usage attribute directly
                        if hasattr(response, 'usage'):
                            usage = response.usage
                            input_tokens = getattr(usage, 'prompt_tokens', 0)
                            output_tokens = getattr(usage, 'completion_tokens', 0)
                        # Then check if it's in _raw_response
                        elif hasattr(response, '_raw_response') and response._raw_response is not None:
                            raw_resp = response._raw_response
                            if hasattr(raw_resp, 'usage'):
                                usage = raw_resp.usage
                                input_tokens = getattr(usage, 'prompt_tokens', 0)
                                output_tokens = getattr(usage, 'completion_tokens', 0)
                            # For custom servers that might return different structures
                            elif isinstance(raw_resp, dict) and 'usage' in raw_resp:
                                usage = raw_resp['usage']
                                if usage is not None:
                                    input_tokens = usage.get('prompt_tokens', 0)
                                    output_tokens = usage.get('completion_tokens', 0)
                        
                        # If we still don't have token counts, check if it's in the response dict
                        if input_tokens == 0 and output_tokens == 0 and hasattr(response, '__dict__'):
                            resp_dict = response.__dict__
                            if 'usage' in resp_dict and resp_dict['usage'] is not None:
                                usage = resp_dict['usage']
                                if isinstance(usage, dict):
                                    input_tokens = usage.get('prompt_tokens', 0)
                                    output_tokens = usage.get('completion_tokens', 0)
                        
                        # If we still don't have token counts, try to access the response as a dictionary
                        if input_tokens == 0 and output_tokens == 0:
                            try:
                                if isinstance(response, dict) and 'usage' in response:
                                    usage = response['usage']
                                    input_tokens = usage.get('prompt_tokens', 0)
                                    output_tokens = usage.get('completion_tokens', 0)
                            except (TypeError, AttributeError):
                                pass
                                
                        # If we still don't have token counts, estimate them
                        if input_tokens == 0 and output_tokens == 0:
                            # Log the response structure to help debug
                            self.logger.debug(f"Response type: {type(response)}")
                            self.logger.debug(f"Response attributes: {dir(response) if hasattr(response, '__dir__') else 'No dir available'}")
                            
                            # Estimate token count (rough approximation: 1 token ≈ 4 characters)
                            input_tokens = len(prompt) // 4
                            # For output tokens, we need to estimate from the response
                            response_str = str(response)
                            output_tokens = len(response_str) // 4
                            self.logger.debug("Using estimated token counts")
                            
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
                            
                    return result
                except Exception as e:
                    self.logger.error(f"Error with custom provider: {e}")
                    raise
                    
            # For Anthropic provider
            elif self.provider_type == 'anthropic':
                try:
                    response = client.chat.completions.create(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        response_model=respmodel,
                        messages=messages
                    )
                    
                    # Extract token usage from Anthropic response
                    # Check different possible locations for token usage information
                    input_tokens = 0
                    output_tokens = 0
                    
                    # Try to get token usage if available
                    try:
                        # First check if response has a usage attribute directly
                        if hasattr(response, 'usage'):
                            usage = response.usage
                            if hasattr(usage, 'input_tokens') and hasattr(usage, 'output_tokens'):
                                input_tokens = usage.input_tokens
                                output_tokens = usage.output_tokens
                            elif isinstance(usage, dict) and 'input_tokens' in usage and 'output_tokens' in usage:
                                input_tokens = usage['input_tokens']
                                output_tokens = usage['output_tokens']
                        
                        # Then check if it's in _raw_response
                        elif hasattr(response, '_raw_response') and response._raw_response is not None:
                            raw_resp = response._raw_response
                            if hasattr(raw_resp, 'usage'):
                                usage = raw_resp.usage
                                if hasattr(usage, 'input_tokens') and hasattr(usage, 'output_tokens'):
                                    input_tokens = usage.input_tokens
                                    output_tokens = usage.output_tokens
                            # Try dictionary access if it's a dict-like object
                            elif isinstance(raw_resp, dict) and 'usage' in raw_resp:
                                usage = raw_resp['usage']
                                if usage is not None and 'input_tokens' in usage and 'output_tokens' in usage:
                                    input_tokens = usage['input_tokens']
                                    output_tokens = usage['output_tokens']
                        
                        # If we still don't have token counts, check if it's in the response dict
                        if input_tokens == 0 and output_tokens == 0 and hasattr(response, '__dict__'):
                            resp_dict = response.__dict__
                            if 'usage' in resp_dict and resp_dict['usage'] is not None:
                                usage = resp_dict['usage']
                                if isinstance(usage, dict):
                                    input_tokens = usage.get('input_tokens', 0)
                                    output_tokens = usage.get('output_tokens', 0)
                        
                        # If we still don't have token counts, try to access the response as a dictionary
                        if input_tokens == 0 and output_tokens == 0:
                            try:
                                if isinstance(response, dict) and 'usage' in response:
                                    usage = response['usage']
                                    input_tokens = usage.get('input_tokens', 0)
                                    output_tokens = usage.get('output_tokens', 0)
                            except (TypeError, AttributeError):
                                pass
                        
                        # If we still don't have token counts, estimate them
                        if input_tokens == 0 and output_tokens == 0:
                            # Log the response structure to help debug
                            self.logger.debug(f"Response type: {type(response)}")
                            self.logger.debug(f"Response attributes: {dir(response) if hasattr(response, '__dir__') else 'No dir available'}")
                            
                            # Estimate token count (rough approximation: 1 token ≈ 4 characters)
                            input_tokens = len(prompt) // 4
                            # For output tokens, we need to estimate from the response
                            response_str = str(response)
                            output_tokens = len(response_str) // 4
                            self.logger.debug("Using estimated token counts")
                    
                    except (AttributeError, TypeError) as e:
                        self.logger.warning(f"Could not extract token usage: {e}")
                        # Estimate token count
                        input_tokens = len(prompt) // 4
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
                    self.logger.error(f"Error with Anthropic provider: {e}")
                    # Create a fallback response based on the model type
                    if issubclass(respmodel, Summary):
                        return Summary(summary="Failed to generate summary due to API error.")
                    elif issubclass(respmodel, Letterinfo):
                        return Letterinfo(
                            recipient=["Company"],
                            subject="Application",
                            opening="Dear Hiring Manager,",
                            content="Failed to generate content due to API error."
                        )
                    elif hasattr(respmodel, '__origin__') and respmodel.__origin__ is Iterable:
                        # For Iterable[JobDescription] or similar
                        item_type = respmodel.__args__[0]
                        if issubclass(item_type, JobDescription):
                            return [JobDescription(job=1, description="Failed to generate description due to API error.")]
                        elif issubclass(item_type, Cvitem):
                            return [Cvitem(job=1, item="Failed to generate item due to API error.")]
                        else:
                            # Create a stub response for other iterable types
                            return [item_type()]
                    else:
                        # Last resort: return a stub instance
                        return respmodel()
                
                # This section is now handled in the Anthropic provider block above
                
                # This section is now handled in the Anthropic provider block above
                
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
        
        try:
            selectedStories = self.ask(prompt, Iterable[CarStory], operation="get_experience_stories")
            
            # Check if selectedStories is None or not iterable
            if selectedStories is None:
                self.logger.warning("Received None for selected stories, using empty list")
                selectedStories = []
                
            # Try to convert to list to ensure it's iterable
            try:
                selectedStories_list = list(selectedStories)
            except (TypeError, ValueError) as e:
                self.logger.warning(f"Could not convert selected stories to list: {e}")
                selectedStories_list = []
                
            # If we have no stories, return an empty list early
            if not selectedStories_list:
                self.logger.warning("No stories selected, returning empty list")
                return []
                
            promptpath = os.path.join(os.path.dirname(__file__), 'refine-cars-prompt.txt')
            with open(promptpath, 'r') as f:
                prompt = f.read()
            prompt = prompt.format(
                        cars=self.get_json_for(selectedStories_list),
                        descriptions=self.get_json_for(descriptions) if descriptions else "[]",
                        job=joblink
            )
            
            job_items = self.ask(prompt, Iterable[Cvitem], operation="refine_experience_items")
            
            # Check if job_items is None or not iterable
            if job_items is None:
                self.logger.warning("Received None for job items, using empty list")
                return []
                
            # Try to convert to list to ensure it's iterable
            try:
                job_items_list = list(job_items)
            except (TypeError, ValueError) as e:
                self.logger.warning(f"Could not convert job items to list: {e}")
                return []
                
            return job_items_list
        except Exception as e:
            self.logger.warning(f"Error in get_experience: {e}")
            return []

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
        
        try:
            job_descriptions = self.ask(prompt, Iterable[JobDescription], operation="get_job_summaries")
            
            # Check if job_descriptions is None or not iterable
            if job_descriptions is None:
                self.logger.warning("Received None for job descriptions, using empty list")
                return []
                
            # Try to convert to list to ensure it's iterable
            try:
                job_descriptions_list = list(job_descriptions)
            except (TypeError, ValueError) as e:
                self.logger.warning(f"Could not convert job descriptions to list: {e}")
                return []
            
            # Escape special LaTeX characters in descriptions
            for job_desc in job_descriptions_list:
                if hasattr(job_desc, 'description') and job_desc.description:
                    job_desc.description = job_desc.description.replace('_', '\\_').replace('%', '\\%').replace('&', '\\&').replace('#', '\\#').replace('$', '\\$').replace('{', '\\{').replace('}', '\\}')
            
            return job_descriptions_list
        except Exception as e:
            self.logger.warning(f"Error in get_job_summaries: {e}")
            return []

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
                recipient=["ABC Company", "Somestreet 42 Happytown"],
                subject="Application for the position of Software Engineer",
                opening="Dear Hiring Manager,",
                content="I am writing to express my interest in the Software Engineer position at your company. With my experience in software development and problem-solving skills, I believe I would be a valuable addition to your team. I look forward to discussing how my background aligns with your needs.",
        )
