"""
Server Provisioning Webhook API endpoints.

This module provides FastAPI router with endpoints for processing webhook events
related to server resource provisioning and deprovisioning only.
"""
from typing import Optional, List, Union
from datetime import datetime
import uuid

from fastapi import APIRouter, Request, Header, HTTPException, status
from fastapi.responses import JSONResponse

from . import config, models
from .services import security, kubernetes, notification

logger = config.logger

# Constants for event types
EVENT_START = 'EVENT_START'
EVENT_END = 'EVENT_END'
EVENT_DELETED = 'EVENT_DELETED'

router = APIRouter()


async def _verify_webhook_signature(request: Request, signature: Optional[str]) -> bytes:
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


def _create_success_response(action: str, resource_name: str, user_id: Optional[str]) -> JSONResponse:
    """Create a standardized success response for single event operations."""
    return JSONResponse({
        "status": "success",
        "message": f"Successfully {action}ed server '{resource_name}'",
        "userId": user_id,
        "timestamp": datetime.now().isoformat()
    })


def _handle_provision_event(
    resource_name: str, 
    ssh_public_key: Optional[str], 
    event_id: str,
    user_id: str,
    webhook_id: int
) -> bool:
    """
    Handle provisioning event for a single server resource. Returns True on success.
    """
    try:
        success = kubernetes.patch_baremetalhost(
            bmh_name=resource_name,
            image_url=config.PROVISION_IMAGE,
            ssh_key=ssh_public_key,
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
                payload_data=f"Provisioning initiated for server '{resource_name}'",
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


def _handle_deprovision_event(
    resource_name: str, 
    event_id: str,
    webhook_id: int,
    user_id: Optional[str] = None
) -> bool:
    """
    Handle deprovisioning event for a single server resource. Returns True on success.
    """
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
                payload_data=f"Deprovisioning completed for server '{resource_name}'",
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


@router.post("/webhook")
async def handle_webhook(
    payload: Union[models.WebhookPayload, models.EventWebhookPayload],
    request: Request, 
    x_webhook_signature: Optional[str] = Header(None)
) -> JSONResponse:
    """
    Handle incoming webhook events for server provisioning/deprovisioning.
    Only processes events for Server resource types.
    """
    logger.info(f"Received webhook request. Attempting to parse payload.")
    
    raw_payload = await _verify_webhook_signature(request, x_webhook_signature)
    
    # Handle single event payload format
    if isinstance(payload, models.WebhookPayload):
        logger.info(
            f"Processing single server webhook event. Event Type: '{payload.event_type}', "
            f"User: '{payload.username}', Resource: '{payload.resource_name}', "
            f"Resource Type: '{payload.resource_type}'."
        )

        # Check if this is a Server resource type
        if payload.resource_type != "Server":
            logger.info(f"Skipping non-Server resource '{payload.resource_name}' of type '{payload.resource_type}'. No action taken.")
            return JSONResponse({
                "status": "success",
                "message": f"No action needed for resource type '{payload.resource_type}'."
            })

        # Process the single server event
        if payload.event_type == EVENT_START:
            if _handle_provision_event(
                payload.resource_name, 
                payload.ssh_public_key, 
                payload.event_id,
                payload.user_id or "unknown",
                payload.webhook_id
            ):
                return _create_success_response("provision", payload.resource_name, payload.user_id)
            else:
                logger.error(f"Failed to provision server '{payload.resource_name}' for event {payload.event_id}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to provision server '{payload.resource_name}'"
                )

        elif payload.event_type == EVENT_END:
            if _handle_deprovision_event(
                payload.resource_name, 
                payload.event_id,
                payload.webhook_id,
                payload.user_id
            ):
                return _create_success_response("deprovision", payload.resource_name, payload.user_id)
            else:
                logger.error(f"Failed to deprovision server '{payload.resource_name}' for event {payload.event_id}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to deprovision server '{payload.resource_name}'"
                )
        else:
            logger.info(f"No action configured for event type '{payload.event_type}'.")
            return JSONResponse({
                "status": "success",
                "message": f"No action needed for event type '{payload.event_type}'."
            })

    elif isinstance(payload, models.EventWebhookPayload):
        logger.info(
            f"Processing server {payload.event_type} webhook. "
            f"Resource Name: '{payload.data.resource.name}'."
        )
        
        if payload.event_type == EVENT_DELETED:
            now = payload.timestamp # Use timestamp from the payload
            
            # Ensure start and end times are offset-aware for comparison with offset-aware 'now'
            reservation_start = payload.data.start
            reservation_end = payload.data.end

            logger.debug(f"Current time (UTC): {now}, Reservation Start: {reservation_start}, Reservation End: {reservation_end}")

            if reservation_start <= now < reservation_end:
                logger.info(f"Reservation for server '{payload.data.resource.name}' is currently active. Initiating deprovision.")
                if _handle_deprovision_event(
                    payload.data.resource.name, 
                    str(payload.data.id),
                    payload.webhook_id,
                    payload.data.keycloak_id if payload.data else None
                ):
                    logger.info(f"Successfully initiated deprovisioning for server '{payload.data.resource.name}' due to EVENT_DELETED.")
                    return JSONResponse({
                        "status": "success", 
                        "message": f"Deprovisioning initiated for server '{payload.data.resource.name}' due to active reservation deletion."
                    })
                else:
                    logger.error(f"Failed to initiate deprovisioning for server '{payload.data.resource.name}' for EVENT_DELETED.")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to deprovision server '{payload.data.resource.name}' after EVENT_DELETED."
                    )
            else:
                logger.info(f"Reservation for server '{payload.data.resource.name}' is not currently active. No deprovision action taken for EVENT_DELETED.")
                return JSONResponse({
                    "status": "success",
                    "message": f"No deprovision action taken for server '{payload.data.resource.name}' as reservation is not currently active."
                })
        else:
            return JSONResponse({
                "status": "success",
                "message": f"No action needed for event type '{payload.event_type}'."
            })
    else:
        # If event type is not recognized, return success with no action needed
        event_type_to_log = payload.event_type if hasattr(payload, 'event_type') else "unknown"
        username_to_log = payload.username if isinstance(payload, models.WebhookPayload) and hasattr(payload, 'username') else "N/A"
        
        logger.info(f"Received event type '{event_type_to_log}' for user {username_to_log}. No action configured for this event type.")
        return JSONResponse({
            "status": "success",
            "message": f"No action needed for event type '{event_type_to_log}'."
        })


@router.get("/healthz")
def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "service": "server-provisioning-webhook"}
