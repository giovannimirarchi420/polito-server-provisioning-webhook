"""
Utility functions for webhook payload processing.

This module provides helper functions for safely parsing and handling
custom parameters from webhook payloads.
"""
import json
import logging
from typing import Dict, Any, Optional

from .config import logger


def parse_custom_parameters(custom_params_str: Optional[str]) -> Dict[str, Any]:
    """
    Safe parsing of custom parameters from webhook payload.
    
    Args:
        custom_params_str: JSON serialized string of custom parameters
        
    Returns:
        Dictionary with custom parameters or empty dict if not present/invalid
    """
    if not custom_params_str:
        return {}
    
    try:
        return json.loads(custom_params_str)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Error parsing customParameters: {e}")
        return {}


def get_custom_parameter(custom_params: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    Get a specific custom parameter with default value.
    
    Args:
        custom_params: Dictionary of custom parameters
        key: Key of the parameter to get
        default: Default value if parameter doesn't exist
        
    Returns:
        Parameter value or default value
    """
    return custom_params.get(key, default)


def has_custom_parameters(custom_params_str: Optional[str]) -> bool:
    """
    Check if valid custom parameters are present.
    
    Args:
        custom_params_str: JSON serialized string of custom parameters
        
    Returns:
        True if valid custom parameters are present, False otherwise
    """
    if not custom_params_str:
        return False
    
    custom_params = parse_custom_parameters(custom_params_str)
    return bool(custom_params)
