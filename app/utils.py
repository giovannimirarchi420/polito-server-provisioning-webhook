"""
Utility functions for webhook payload processing.

This module provides helper functions for safely parsing and handling
custom parameters from webhook payloads.
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Union

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse

from .config import logger
from . import config, models
from .services import security, kubernetes, notification

# Constants for event types
EVENT_START = 'EVENT_START'
EVENT_END = 'EVENT_END'
EVENT_DELETED = 'EVENT_DELETED'


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


def parse_timestamp(timestamp_str: str) -> datetime:
    """
    Parse timestamp string to datetime object.
    
    Args:
        timestamp_str: ISO format timestamp string
        
    Returns:
        datetime object
        
    Raises:
        ValueError: If timestamp format is invalid
    """
    try:
        # Handle ISO format with or without microseconds
        if '.' in timestamp_str:
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    except ValueError as e:
        logger.error(f"Failed to parse timestamp '{timestamp_str}': {e}")
        raise ValueError(f"Invalid timestamp format: {timestamp_str}")


async def verify_webhook_signature(request: Request, signature: Optional[str]) -> bytes:
    """
    Verify webhook signature and return raw payload.
    
    Args:
        request: FastAPI request object
        signature: Signature from webhook header
        
    Returns:
        Raw payload bytes
        
    Raises:
        HTTPException: If signature verification fails
    """
    raw_payload = await request.body()
    
    if config.WEBHOOK_SECRET:
        if not security.verify_signature(raw_payload, signature):
            logger.warning("Webhook signature verification failed")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
    
    return raw_payload


def create_success_response(action: str, resource_name: str, user_id: Optional[str]) -> JSONResponse:
    """Create a standardized success response for single event operations."""
    return JSONResponse({
        "status": "success",
        "message": f"Successfully {action}ed server '{resource_name}'",
        "userId": user_id
    })


def handle_provision_event(
    payload: models.WebhookPayload,
    raw_payload: bytes
) -> bool:
    """
    Handle provisioning event for a single server resource. Returns True on success.
    """
    resource_name = payload.resource_name
    event_id = payload.event_id
    webhook_id = payload.webhook_id
    user_id = payload.user_id or "unknown"

    try:
        success = kubernetes.patch_baremetalhost(
            bmh_name=resource_name,
            image_url=config.PROVISION_IMAGE,
            ssh_key=payload.ssh_public_key,
            checksum=config.PROVISION_CHECKSUM,
            checksum_type=config.PROVISION_CHECKSUM_TYPE,
            wait_for_completion=False,
            webhook_id=webhook_id,
            user_id=user_id,
            event_id=event_id,
            timeout=config.PROVISIONING_TIMEOUT
        )
        
        if success:
            # Send webhook log for successful initiation
            if not notification.send_webhook_log(
                webhook_id=webhook_id,
                event_type=EVENT_START,
                success=True,
                payload_data=payload.model_dump(),
                status_code=200,
                response=f"Provisioning initiated for server '{resource_name}'",
                retry_count=0,
                metadata={"resourceName": resource_name, "userId": user_id, "eventId": event_id}
            ):
                logger.warning(f"Failed to send webhook log for server '{resource_name}'")
        
            logger.info(f"[{EVENT_START}] Successfully initiated provisioning for server '{resource_name}' (Event ID: {event_id}). Monitoring in background.")
            return True
        else:
            logger.error(f"[{EVENT_START}] Failed to start provisioning for server '{resource_name}' (Event ID: {event_id}).")
            return False
            
    except Exception as e:
        logger.error(f"Error provisioning server '{resource_name}': {str(e)}")
        return False


def handle_deprovision_event(
    payload: Union[models.WebhookPayload, models.EventWebhookPayload],
    raw_payload: bytes
) -> bool:
    """
    Handle deprovisioning event for a single server resource. Returns True on success.
    """
    if isinstance(payload, models.WebhookPayload):
        resource_name = payload.resource_name
        event_id = payload.event_id
        webhook_id = payload.webhook_id
        user_id = payload.user_id
    elif isinstance(payload, models.EventWebhookPayload):
        resource_name = payload.data.resource.name
        event_id = str(payload.data.id)
        webhook_id = payload.webhook_id
        user_id = payload.data.keycloak_id if payload.data else None
    else:
        logger.error("Invalid payload type for deprovisioning.")
        return False

    try:
        success = kubernetes.patch_baremetalhost(
            bmh_name=resource_name,
            image_url=None  # None triggers deprovisioning
        )
        
        if success:
            logger.info(f"[{EVENT_END}] Successfully initiated deprovisioning for server '{resource_name}' (Event ID: {event_id}).")
            
            # Send webhook log for successful deprovisioning
            if event_id and notification.send_webhook_log(
                webhook_id=webhook_id,
                event_type=EVENT_END,
                success=True,
                payload_data=payload.model_dump(),
                status_code=200,
                response=f"Deprovisioning completed for server '{resource_name}'",
                retry_count=0,
                metadata={"resourceName": resource_name, "userId": user_id, "eventId": event_id}
            ):
                logger.debug(f"Successfully sent webhook log for server '{resource_name}' deprovisioning")
            else:
                logger.warning(f"Failed to send webhook log for server '{resource_name}' deprovisioning")
                
        else:
            logger.error(f"[{EVENT_END}] Failed to deprovision server '{resource_name}' (Event ID: {event_id}).")
        
        return success
        
    except Exception as e:
        logger.error(f"Error deprovisioning server '{resource_name}': {str(e)}")
        return False
