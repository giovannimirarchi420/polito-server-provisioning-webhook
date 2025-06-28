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
    
    def _create_payload(
        self,
        webhook_id: str,
        user_id: str,
        resource_name: str,
        success: bool,
        error_message: Optional[str] = None,
        event_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create notification payload.
        
        Args:
            webhook_id: Webhook identifier
            user_id: User identifier
            resource_name: Name of the resource
            success: Whether the operation was successful
            error_message: Error message if operation failed
            event_id: Event identifier
            
        Returns:
            Notification payload dictionary
        """
        payload = {
            "webhookId": webhook_id,
            "userId": user_id,
            "resourceName": resource_name,
            "success": success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "notificationId": str(uuid.uuid4())
        }
        
        if event_id:
            payload["eventId"] = event_id
            
        if not success and error_message:
            payload["errorMessage"] = error_message
            
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
            headers = {"Content-Type": "application/json"}
            
            # Add signature if webhook secret is configured
            if config.WEBHOOK_SECRET:
                payload_json = json.dumps(payload, separators=(',', ':')).encode('utf-8')
                signature = self.security._generate_signature(payload_json)
                headers["X-Webhook-Signature"] = signature
            
            response = self.session.post(
                endpoint,
                json=payload,
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
        webhook_id: str,
        user_id: str,
        resource_name: str,
        success: bool,
        error_message: Optional[str] = None,
        event_id: Optional[str] = None
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
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        if not config.NOTIFICATION_ENDPOINT:
            logger.debug("No notification endpoint configured, skipping notification")
            return True
        
        payload = self._create_payload(
            webhook_id, user_id, resource_name, success, error_message, event_id
        )
        
        logger.info(f"Sending provisioning notification for resource '{resource_name}' (success: {success})")
        return self._send_request(config.NOTIFICATION_ENDPOINT, payload, config.NOTIFICATION_TIMEOUT)
    
    def send_webhook_log(
        self,
        webhook_id: str,
        event_type: str,
        success: bool,
        status_code: int = 200,
        response_message: str = "OK",
        retry_count: int = 0,
        resource_name: Optional[str] = None,
        user_id: Optional[str] = None,
        error_message: Optional[str] = None,
        event_id: Optional[str] = None
    ) -> bool:
        """
        Send webhook event log.
        
        Args:
            webhook_id: Webhook identifier
            event_type: Type of the webhook event
            success: Whether the webhook processing was successful
            status_code: HTTP status code for the response
            response_message: Response message
            retry_count: Number of retries attempted
            resource_name: Name of the resource (optional)
            user_id: User identifier (optional)
            error_message: Error message if processing failed (optional)
            event_id: Event identifier (optional)
            
        Returns:
            True if log was sent successfully, False otherwise
        """
        if not config.WEBHOOK_LOG_ENDPOINT:
            logger.debug("No webhook log endpoint configured, skipping webhook log")
            return True
        
        payload = {
            "webhookId": webhook_id,
            "eventType": event_type,
            "success": success,
            "statusCode": status_code,
            "responseMessage": response_message,
            "retryCount": retry_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "logId": str(uuid.uuid4())
        }
        
        if resource_name:
            payload["resourceName"] = resource_name
        if user_id:
            payload["userId"] = user_id
        if error_message:
            payload["errorMessage"] = error_message
        if event_id:
            payload["eventId"] = event_id
        
        logger.info(f"Sending webhook log for event '{event_type}' (success: {success})")
        return self._send_request(config.WEBHOOK_LOG_ENDPOINT, payload, config.WEBHOOK_LOG_TIMEOUT)


# Singleton instance
_notification_service = NotificationService()


def send_provisioning_notification(
    webhook_id: str,
    user_id: str,
    resource_name: str,
    success: bool,
    error_message: Optional[str] = None,
    event_id: Optional[str] = None
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
        
    Returns:
        True if notification was sent successfully, False otherwise
    """
    return _notification_service.send_provisioning_notification(
        webhook_id, user_id, resource_name, success, error_message, event_id
    )


def send_webhook_log(
    webhook_id: str,
    event_type: str,
    success: bool,
    status_code: int = 200,
    response_message: str = "OK",
    retry_count: int = 0,
    resource_name: Optional[str] = None,
    user_id: Optional[str] = None,
    error_message: Optional[str] = None,
    event_id: Optional[str] = None
) -> bool:
    """
    Send webhook log (convenience function).
    
    Args:
        webhook_id: Webhook identifier
        event_type: Type of the webhook event
        success: Whether the webhook processing was successful
        status_code: HTTP status code for the response
        response_message: Response message
        retry_count: Number of retries attempted
        resource_name: Name of the resource (optional)
        user_id: User identifier (optional)
        error_message: Error message if processing failed (optional)
        event_id: Event identifier (optional)
        
    Returns:
        True if log was sent successfully, False otherwise
    """
    return _notification_service.send_webhook_log(
        webhook_id, event_type, success, status_code, response_message,
        retry_count, resource_name, user_id, error_message, event_id
    )
