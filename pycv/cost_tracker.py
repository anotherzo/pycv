import os
import json
import csv
import logging
import httpx
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

class CostTracker:
    """
    Tracks the cost of API calls to LLM providers.
    
    This class maintains a record of API calls, their token usage,
    and estimated costs based on provider-specific pricing.
    """
    
    # Default pricing per 1M tokens (in USD)
    DEFAULT_PRICING = {
        'anthropic': {
            'claude-3-5-sonnet-20240620': {'input': 3.00, 'output': 15.00},
            'claude-3-opus-20240229': {'input': 15.00, 'output': 75.00},
            'claude-3-sonnet-20240229': {'input': 3.00, 'output': 15.00},
            'claude-3-haiku-20240307': {'input': 0.25, 'output': 1.25},
            'claude-2.1': {'input': 8.00, 'output': 24.00},
            'claude-2.0': {'input': 8.00, 'output': 24.00},
            'claude-instant-1.2': {'input': 1.63, 'output': 5.51}
        },
        'openai': {
            'gpt-4o': {'input': 5.00, 'output': 15.00},
            'gpt-4-turbo': {'input': 10.00, 'output': 30.00},
            'gpt-4': {'input': 30.00, 'output': 60.00},
            'gpt-3.5-turbo': {'input': 0.50, 'output': 1.50}
        }
    }
    
    def __init__(self, log_dir: str = 'logs'):
        """
        Initialize the cost tracker.
        
        Args:
            log_dir: Directory to store cost logs
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True, parents=True)
        
        # Load custom pricing if available
        self.pricing = self._load_custom_pricing() or self.DEFAULT_PRICING
        
        # Initialize tracking data
        self.reset()
    
    def reset(self):
        """Reset the tracking data."""
        self.calls = []
        self.total_tokens = {'input': 0, 'output': 0}
        self.total_cost = 0.0
    
    def _fetch_external_pricing(self) -> Optional[Dict[str, Any]]:
        """
        Fetch pricing data from the gramener/llmpricing repository.
        
        Returns:
            Dictionary with pricing data organized by provider and model
        """
        url = "https://raw.githubusercontent.com/gramener/llmpricing/master/elo.csv"
        
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url)
                response.raise_for_status()
                
                # Save to a temporary file and parse as CSV
                with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
                    temp_file.write(response.text)
                    temp_file.flush()
                    temp_path = Path(temp_file.name)
                
                # Parse the CSV
                pricing_data = {
                    'anthropic': {},
                    'openai': {},
                    'google': {},
                    'mistral': {},
                    'meta': {},
                    'other': {}
                }
                
                with open(temp_path, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Skip rows without pricing info
                        if not row.get('cpmi') or row['cpmi'] == '':
                            continue
                            
                        try:
                            model_name = row['model'].strip()
                            price_per_million = float(row['cpmi'])
                            
                            # Determine provider based on model name
                            if 'claude' in model_name:
                                provider = 'anthropic'
                            elif any(prefix in model_name for prefix in ['gpt', 'chatgpt', 'o1']):
                                provider = 'openai'
                            elif any(prefix in model_name for prefix in ['gemini', 'gemma']):
                                provider = 'google'
                            elif 'mistral' in model_name:
                                provider = 'mistral'
                            elif 'llama' in model_name:
                                provider = 'meta'
                            else:
                                provider = 'other'
                            
                            # Store pricing with input/output rates
                            pricing_data[provider][model_name] = {
                                'input': price_per_million,
                                'output': price_per_million
                            }
                        except (ValueError, KeyError) as e:
                            self.logger.warning(f"Error parsing pricing row: {e}")
                            continue
                
                # Clean up temp file
                temp_path.unlink(missing_ok=True)
                
                return pricing_data
        except Exception as e:
            self.logger.warning(f"Failed to fetch external pricing: {e}")
            return None
    
    def _load_custom_pricing(self) -> Optional[Dict[str, Any]]:
        """Load custom pricing from a JSON file if available or from external source."""
        # First try local pricing file
        pricing_file = Path('pricing.json')
        if pricing_file.exists():
            try:
                with open(pricing_file, 'r') as f:
                    self.logger.info("Using custom pricing from pricing.json")
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load custom pricing from file: {e}")
        
        # Then try external pricing source
        external_pricing = self._fetch_external_pricing()
        if external_pricing:
            self.logger.info("Using pricing data from gramener/llmpricing")
            return external_pricing
        
        return None
    
    def track_call(self, 
                  provider: str, 
                  model: str, 
                  input_tokens: int, 
                  output_tokens: int, 
                  operation: str):
        """
        Track a single API call.
        
        Args:
            provider: The LLM provider (e.g., 'anthropic', 'openai')
            model: The model used (e.g., 'claude-3-sonnet', 'gpt-4')
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            operation: The operation being performed (e.g., 'get_summary')
        """
        # Calculate cost
        input_cost = 0.0
        output_cost = 0.0
        
        try:
            # First try exact match in provider's pricing
            if provider in self.pricing and model in self.pricing[provider]:
                input_cost = (input_tokens / 1_000_000) * self.pricing[provider][model]['input']
                output_cost = (output_tokens / 1_000_000) * self.pricing[provider][model]['output']
            else:
                # Try to find a similar model name in the pricing data
                found_match = False
                
                if provider in self.pricing:
                    for priced_model in self.pricing[provider]:
                        # Check if the model name contains the priced model or vice versa
                        if priced_model in model or model in priced_model:
                            input_cost = (input_tokens / 1_000_000) * self.pricing[provider][priced_model]['input']
                            output_cost = (output_tokens / 1_000_000) * self.pricing[provider][priced_model]['output']
                            found_match = True
                            self.logger.debug(f"Using pricing for {priced_model} as a match for {model}")
                            break
                
                # If still no match, check 'other' provider category
                if not found_match and 'other' in self.pricing:
                    for priced_model in self.pricing['other']:
                        if priced_model in model or model in priced_model:
                            input_cost = (input_tokens / 1_000_000) * self.pricing['other'][priced_model]['input']
                            output_cost = (output_tokens / 1_000_000) * self.pricing['other'][priced_model]['output']
                            found_match = True
                            self.logger.debug(f"Using pricing from 'other' category for {model}")
                            break
                
                # If still no match, use default pricing
                if not found_match:
                    self.logger.warning(f"Pricing not found for {provider}/{model}, using estimate")
                    # Use a reasonable default if specific pricing not available
                    input_cost = (input_tokens / 1_000_000) * 5.0  # $5 per million tokens as fallback
                    output_cost = (output_tokens / 1_000_000) * 15.0  # $15 per million tokens as fallback
        except Exception as e:
            self.logger.warning(f"Error calculating cost for {provider}/{model}: {e}")
            # Use a reasonable default if there was an error
            input_cost = (input_tokens / 1_000_000) * 5.0
            output_cost = (output_tokens / 1_000_000) * 15.0
        
        total_cost = input_cost + output_cost
        
        # Record the call
        call_data = {
            'timestamp': datetime.now().isoformat(),
            'provider': provider,
            'model': model,
            'operation': operation,
            'tokens': {
                'input': input_tokens,
                'output': output_tokens,
                'total': input_tokens + output_tokens
            },
            'cost': {
                'input': input_cost,
                'output': output_cost,
                'total': total_cost
            }
        }
        
        self.calls.append(call_data)
        self.total_tokens['input'] += input_tokens
        self.total_tokens['output'] += output_tokens
        self.total_cost += total_cost
        
        self.logger.debug(f"Tracked API call: {operation} - {input_tokens+output_tokens} tokens, ${total_cost:.6f}")
    
    def save_log(self, project_name: str):
        """
        Save the current tracking data to a log file.
        
        Args:
            project_name: Name of the project to include in the log filename
        """
        if not self.calls:
            self.logger.info("No API calls to log")
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.log_dir / f"cost_log_{project_name}_{timestamp}.json"
        
        log_data = {
            'project': project_name,
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_calls': len(self.calls),
                'total_tokens': self.total_tokens,
                'total_cost_usd': self.total_cost
            },
            'calls': self.calls
        }
        
        with open(log_file, 'w') as f:
            json.dump(log_data, f, indent=2)
            
        self.logger.info(f"Cost log saved to {log_file}")
        
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current tracking data.
        
        Returns:
            Dictionary with summary information
        """
        return {
            'total_calls': len(self.calls),
            'total_tokens': self.total_tokens,
            'total_cost_usd': self.total_cost
        }
    
    def print_summary(self):
        """Print a summary of the current tracking data to the console."""
        if not self.calls:
            print("No API calls recorded")
            return
            
        summary = self.get_summary()
        print("\n=== Cost Summary ===")
        print(f"Total API calls: {summary['total_calls']}")
        print(f"Total tokens: {summary['total_tokens']['input'] + summary['total_tokens']['output']:,}")
        print(f"  - Input tokens: {summary['total_tokens']['input']:,}")
        print(f"  - Output tokens: {summary['total_tokens']['output']:,}")
        print(f"Estimated cost: ${summary['total_cost_usd']:.4f}")
        print("===================\n")
