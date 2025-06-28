"""
Security module for webhook signature verification.

This module provides functionality to verify webhook signatures using HMAC-SHA256
to ensure the authenticity and integrity of incoming webhook requests.
"""
import base64
import hashlib
import hmac
from typing import Optional

from .. import config

logger = config.logger


class SignatureVerificationError(Exception):
    """Raised when signature verification fails."""
    pass


class WebhookSecurity:
    """Handles webhook security operations."""
    
    def __init__(self, secret: Optional[str] = None):
        """
        Initialize webhook security with optional secret.
        
        Args:
            secret: Secret key for signature verification. If None, uses config.WEBHOOK_SECRET
        """
        self.secret = secret or config.WEBHOOK_SECRET
    
    def _generate_signature(self, payload: bytes) -> str:
        """
        Generate HMAC-SHA256 signature for the given payload.
        
        Args:
            payload: Raw payload bytes
            
        Returns:
            Base64-encoded signature string
            
        Raises:
            SignatureVerificationError: If secret is not configured
        """
        if not self.secret:
            raise SignatureVerificationError("Webhook secret not configured")
        
        hash_object = hmac.new(
            self.secret.encode('utf-8'),
            msg=payload,
            digestmod=hashlib.sha256
        )
        return base64.b64encode(hash_object.digest()).decode('utf-8')
    
    def verify_signature(self, payload: bytes, received_signature: Optional[str]) -> bool:
        """
        Verify webhook signature against the payload.
        
        Args:
            payload: Raw payload bytes
            received_signature: Signature from the webhook header
            
        Returns:
            True if signature is valid or no secret is configured, False otherwise
        """
        # Skip verification if no secret is configured
        if not self.secret:
            logger.warning("Webhook secret not configured. Skipping signature verification.")
            return True
        
        # Check if signature header is present
        if not received_signature:
            logger.warning("Missing X-Webhook-Signature header.")
            return False
        
        try:
            expected_signature = self._generate_signature(payload)
            
            logger.debug(f"Received Signature: {received_signature}")
            logger.debug(f"Expected Signature: {expected_signature}")
            
            # Use constant-time comparison to prevent timing attacks
            if hmac.compare_digest(received_signature, expected_signature):
                logger.info("Signature verified successfully.")
                return True
            else:
                logger.warning("Signature verification failed.")
                return False
                
        except Exception as e:
            logger.error(f"Error during signature verification: {e}")
            return False


# Default instance for backward compatibility
_default_security = WebhookSecurity()


def verify_signature(payload_body: bytes, signature_header: Optional[str]) -> bool:
    """
    Verify webhook signature (backward compatibility function).
    
    Args:
        payload_body: Raw payload bytes
        signature_header: Signature from the webhook header
        
    Returns:
        True if signature is valid, False otherwise
    """
    return _default_security.verify_signature(payload_body, signature_header)
