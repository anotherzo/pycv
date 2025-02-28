import os
import json
import logging
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
    
    def _load_custom_pricing(self) -> Optional[Dict[str, Any]]:
        """Load custom pricing from a JSON file if available."""
        pricing_file = Path('pricing.json')
        if pricing_file.exists():
            try:
                with open(pricing_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load custom pricing: {e}")
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
        try:
            input_cost = (input_tokens / 1_000_000) * self.pricing[provider][model]['input']
            output_cost = (output_tokens / 1_000_000) * self.pricing[provider][model]['output']
            total_cost = input_cost + output_cost
        except KeyError:
            self.logger.warning(f"Pricing not found for {provider}/{model}, using estimate")
            # Use a reasonable default if specific pricing not available
            input_cost = (input_tokens / 1_000_000) * 5.0  # $5 per million tokens as fallback
            output_cost = (output_tokens / 1_000_000) * 15.0  # $15 per million tokens as fallback
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
