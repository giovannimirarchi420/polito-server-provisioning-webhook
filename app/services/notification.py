"""
Notification service for sending status updates via webhooks.

This module provides functionality to send notifications about
BareMetalHost provisioning status to external endpoints.
"""
import json
from datetime import datetime, timezone
from typing import Dict, Optional, Any
import uuid

import requests

from .. import config
from .security import WebhookSecurity

logger = config.logger


class NotificationError(Exception):
    """Custom exception for notification operations."""
    pass


class NotificationService:
    """Service for sending notifications to external endpoints."""
    
    def __init__(self):
        self.security = WebhookSecurity()
        self.session = requests.Session()
        
        # Set default timeout for all requests
        self.session.timeout = config.NOTIFICATION_TIMEOUT
    
    def _create_notification_payload(
        self,
        webhook_id: str,
        user_id: str,
        message: str,
        message_type: str = "INFO",
        event_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        event_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create notification payload following WebhookNotificationRequestDTO structure.
        
        Args:
            webhook_id: Webhook identifier
            user_id: User identifier
            message: Notification message (max 500 chars)
            message_type: Type of message (max 50 chars)
            event_id: Event identifier
            resource_id: Resource identifier
            event_type: Type of event
            metadata: Additional metadata
            
        Returns:
            Notification payload dictionary
        """
        # Truncate message if too long
        if len(message) > 500:
            message = message[:497] + "..."
            
        # Truncate type if too long
        if len(message_type) > 50:
            message_type = message_type[:50]
            
        payload = {
            "webhookId": webhook_id,
            "userId": user_id,
            "message": message,
            "type": message_type
        }
        
        if event_id:
            payload["eventId"] = event_id
        if resource_id:
            payload["resourceId"] = resource_id
        if event_type:
            payload["eventType"] = event_type
        if metadata:
            payload["metadata"] = metadata
            
        return payload
    
    def _create_webhook_log_payload(
        self,
        webhook_id: int,
        event_type: str,
        payload_data: str,
        success: bool,
        status_code: Optional[int] = None,
        response: Optional[str] = None,
        retry_count: int = 0,
        resource_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create webhook log payload following WebhookLogRequestDTO structure.
        
        Args:
            webhook_id: Webhook identifier
            event_type: Type of the webhook event
            payload_data: Webhook payload (max 4000 chars)
            success: Whether the webhook processing was successful
            status_code: HTTP status code for the response
            response: Response message (max 4000 chars)
            retry_count: Number of retries attempted
            resource_id: Resource identifier
            metadata: Additional metadata
            
        Returns:
            Webhook log payload dictionary
        """
        # Truncate payload if too long
        if len(payload_data) > 4000:
            payload_data = payload_data[:3997] + "..."
            
        # Truncate response if too long
        if response and len(response) > 4000:
            response = response[:3997] + "..."
            
        payload = {
            "webhookId": webhook_id,
            "eventType": event_type,
            "payload": payload_data,
            "success": success,
            "statusCode": status_code,
            "response": response,
            "retryCount": retry_count,
            "resourceId": resource_id,
            "metadata": metadata
        }
            
        return payload
    
    def _send_request(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        timeout: int
    ) -> bool:
        """
        Send HTTP request to endpoint.
        
        Args:
            endpoint: Target endpoint URL
            payload: Request payload
            timeout: Request timeout in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert payload to JSON bytes for signature generation
            payload_json = json.dumps(payload, separators=(',', ':'))  # Compact JSON
            payload_bytes = payload_json.encode('utf-8')
            
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "switch-port-webhook/1.0"
            }
            
            # Add signature if webhook secret is configured
            if config.WEBHOOK_SECRET:
                signature = self.security._generate_signature(payload_bytes)
                headers["X-Webhook-Signature"] = signature
                logger.debug(f"Generated signature for payload: {signature}")
            
            logger.debug(f"Sending request to {endpoint} with payload: {payload}")
            logger.debug(f"Request headers: {headers}")
            
            response = self.session.post(
                endpoint,
                data=payload_bytes,  # Use raw bytes to match signature
                headers=headers,
                timeout=timeout
            )
            
            response.raise_for_status()
            logger.debug(f"Successfully sent request to {endpoint}: {response.status_code}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending request to {endpoint}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending request to {endpoint}: {str(e)}")
            return False
    
    def send_provisioning_notification(
        self,
        webhook_id: int,
        user_id: str,
        resource_name: str,
        success: bool,
        error_message: Optional[str] = None,
        event_id: Optional[str] = None,
        resource_id: Optional[str] = None
    ) -> bool:
        """
        Send provisioning completion notification.
        
        Args:
            webhook_id: Webhook identifier
            user_id: User identifier
            resource_name: Name of the provisioned resource
            success: Whether provisioning was successful
            error_message: Error message if provisioning failed
            event_id: Event identifier
            resource_id: Resource identifier
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        if not config.NOTIFICATION_ENDPOINT:
            logger.debug("No notification endpoint configured, skipping notification")
            return True
        
        # Create message based on success status
        if success:
            message = f"Resource '{resource_name}' provisioned successfully"
            message_type = "SUCCESS"
        else:
            message = f"Failed to provision resource '{resource_name}'"
            if error_message:
                message += f": {error_message}"
            message_type = "ERROR"
        
        payload = self._create_notification_payload(
            webhook_id=webhook_id,
            user_id=user_id,
            message=message,
            message_type=message_type,
            event_id=event_id,
            resource_id=resource_id,
            event_type="PROVISIONING",
            metadata={"resourceName": resource_name}
        )
        
        logger.info(f"Sending provisioning notification for resource '{resource_name}' (success: {success})")
        return self._send_request(config.NOTIFICATION_ENDPOINT, payload, config.NOTIFICATION_TIMEOUT)
    
    def send_webhook_log(
        self,
        webhook_id: int,
        event_type: str,
        success: bool,
        payload_data: str = "",
        status_code: Optional[int] = None,
        response: Optional[str] = None,
        retry_count: int = 0,
        resource_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send webhook event log.
        
        Args:
            webhook_id: Webhook identifier
            event_type: Type of the webhook event
            success: Whether the webhook processing was successful
            payload_data: Webhook payload data
            status_code: HTTP status code for the response
            response: Response message
            retry_count: Number of retries attempted
            resource_id: Resource identifier
            metadata: Additional metadata
            
        Returns:
            True if log was sent successfully, False otherwise
        """
        if not config.WEBHOOK_LOG_ENDPOINT:
            logger.debug("No webhook log endpoint configured, skipping webhook log")
            return True
        
        payload = self._create_webhook_log_payload(
            webhook_id=webhook_id,
            event_type=event_type,
            payload_data=payload_data,
            success=success,
            status_code=status_code,
            response=response,
            retry_count=retry_count,
            resource_id=resource_id,
            metadata=metadata
        )
        
        logger.info(f"Sending webhook log for event '{event_type}' (success: {success})")
        return self._send_request(config.WEBHOOK_LOG_ENDPOINT, payload, config.WEBHOOK_LOG_TIMEOUT)


# Singleton instance
_notification_service = NotificationService()


def send_provisioning_notification(
    webhook_id: int,
    user_id: str,
    resource_name: str,
    success: bool,
    error_message: Optional[str] = None,
    event_id: Optional[str] = None,
    resource_id: Optional[str] = None
) -> bool:
    """
    Send provisioning notification (convenience function).
    
    Args:
        webhook_id: Webhook identifier
        user_id: User identifier
        resource_name: Name of the provisioned resource
        success: Whether provisioning was successful
        error_message: Error message if provisioning failed
        event_id: Event identifier
        resource_id: Resource identifier
        
    Returns:
        True if notification was sent successfully, False otherwise
    """
    return _notification_service.send_provisioning_notification(
        webhook_id, user_id, resource_name, success, error_message, event_id, resource_id
    )


def send_webhook_log(
    webhook_id: int,
    event_type: str,
    success: bool,
    payload_data: str = "",
    status_code: Optional[int] = None,
    response: Optional[str] = None,
    retry_count: int = 0,
    resource_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Send webhook log (convenience function).
    
    Args:
        webhook_id: Webhook identifier
        event_type: Type of the webhook event
        success: Whether the webhook processing was successful
        payload_data: Webhook payload data
        status_code: HTTP status code for the response
        response: Response message
        retry_count: Number of retries attempted
        resource_id: Resource identifier
        metadata: Additional metadata
        
    Returns:
        True if log was sent successfully, False otherwise
    """
    return _notification_service.send_webhook_log(
        webhook_id, event_type, success, payload_data, status_code, response,
        retry_count, resource_id, metadata
    )
