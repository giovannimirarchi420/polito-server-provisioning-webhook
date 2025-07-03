"""
Server Provisioning Webhook API endpoints.

This module provides FastAPI router with endpoints for processing webhook events
related to server resource provisioning and deprovisioning only.
"""
from typing import Optional, Union

from fastapi import APIRouter, Request, Header, HTTPException, status
from fastapi.responses import JSONResponse

from . import config, models, utils
from .services import security, kubernetes, notification

logger = config.logger

# Constants for event types
EVENT_START = 'EVENT_START'
EVENT_END = 'EVENT_END'
EVENT_DELETED = 'EVENT_DELETED'

router = APIRouter()


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
    
    raw_payload = await utils.verify_webhook_signature(request, x_webhook_signature)
    
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
            if utils.handle_provision_event(
                payload,
                raw_payload
            ):
                return utils.create_success_response("provision", payload.resource_name, payload.user_id)
            else:
                logger.error(f"Failed to provision server '{payload.resource_name}' for event {payload.event_id}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to provision server '{payload.resource_name}'"
                )

        elif payload.event_type == EVENT_END:
            if utils.handle_deprovision_event(
                payload,
                raw_payload
            ):
                return utils.create_success_response("deprovision", payload.resource_name, payload.user_id)
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
            now = utils.parse_timestamp(payload.timestamp) # Parse timestamp from string to datetime
            
            # Parse start and end times from string to datetime
            reservation_start = utils.parse_timestamp(payload.data.start)
            reservation_end = utils.parse_timestamp(payload.data.end)

            logger.debug(f"Current time (UTC): {now}, Reservation Start: {reservation_start}, Reservation End: {reservation_end}")

            if reservation_start <= now < reservation_end:
                logger.info(f"Reservation for server '{payload.data.resource.name}' is currently active. Initiating deprovision.")
                if utils.handle_deprovision_event(
                    payload,
                    raw_payload
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
