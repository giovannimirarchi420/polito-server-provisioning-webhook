"""
Configuration management for the server provisioning webhook.

This module handles environment variable loading and application configuration.
"""
import os
import logging
from typing import Optional

class AppConfig:
    """Application configuration from environment variables."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        # Server configuration
        self.port = int(os.environ.get("PORT", "5001"))
        self.log_level = os.environ.get("LOG_LEVEL", "INFO")
        
        # Kubernetes configuration
        self.k8s_namespace = os.environ.get("K8S_NAMESPACE", "default")
        self.bmh_api_group = os.environ.get("BMH_API_GROUP", "metal3.io")
        self.bmh_api_version = os.environ.get("BMH_API_VERSION", "v1alpha1")
        self.bmh_plural = os.environ.get("BMH_PLURAL", "baremetalhosts")
        
        # Provisioning configuration
        self.provision_image = os.environ.get("PROVISION_IMAGE")
        self.provision_checksum = os.environ.get("PROVISION_CHECKSUM")
        self.provision_checksum_type = os.environ.get("PROVISION_CHECKSUM_TYPE", "sha256")
        self.deprovision_image = os.environ.get("DEPROVISION_IMAGE")
        self.user_data_secret_prefix = os.environ.get("USER_DATA_SECRET_PREFIX", "user-data")
        
        # Security configuration
        self.webhook_secret = os.environ.get("WEBHOOK_SECRET")
        
        # Timeout configuration
        self.provisioning_timeout = int(os.environ.get("PROVISIONING_TIMEOUT", "600"))
        
        # Notification configuration
        self.notification_endpoint = os.environ.get("NOTIFICATION_ENDPOINT")
        self.notification_timeout = int(os.environ.get("NOTIFICATION_TIMEOUT", "30"))
        self.webhook_log_endpoint = os.environ.get("WEBHOOK_LOG_ENDPOINT")
        self.webhook_log_timeout = int(os.environ.get("WEBHOOK_LOG_TIMEOUT", "30"))
        
        # Validate required configuration
        if not self.provision_image:
            raise ValueError("PROVISION_IMAGE environment variable is required")
    
    @property
    def is_webhook_security_enabled(self) -> bool:
        """Check if webhook signature verification is enabled."""
        return bool(self.webhook_secret)

# Global configuration instance
config = AppConfig()

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Export commonly used values
PORT = config.port
K8S_NAMESPACE = config.k8s_namespace
BMH_API_GROUP = config.bmh_api_group
BMH_API_VERSION = config.bmh_api_version
BMH_PLURAL = config.bmh_plural
PROVISION_IMAGE = config.provision_image
PROVISION_CHECKSUM = config.provision_checksum
PROVISION_CHECKSUM_TYPE = config.provision_checksum_type
DEPROVISION_IMAGE = config.deprovision_image
WEBHOOK_SECRET = config.webhook_secret
PROVISIONING_TIMEOUT = config.provisioning_timeout
NOTIFICATION_ENDPOINT = config.notification_endpoint
NOTIFICATION_TIMEOUT = config.notification_timeout
WEBHOOK_LOG_ENDPOINT = config.webhook_log_endpoint
WEBHOOK_LOG_TIMEOUT = config.webhook_log_timeout
