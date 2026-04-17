# services/fiscal_device_monitor.py

import threading
import time
from typing import Optional
from datetime import datetime
from dataclasses import dataclass


@dataclass
class DeviceStatus:
    """Device status model"""
    status: str  # online, offline, error, disabled, unknown
    last_ping_time: Optional[datetime] = None
    reporting_frequency: Optional[int] = None
    operation_id: Optional[str] = None
    
    @property
    def is_online(self) -> bool:
        return self.status == "online"
    
    @property
    def is_offline(self) -> bool:
        return self.status in ("offline", "error")
    
    @property
    def is_disabled(self) -> bool:
        return self.status == "disabled"
    
    @property
    def status_text(self) -> str:
        status_map = {
            "online": "Device Online",
            "offline": "Device Offline",
            "error": "Connection Error",
            "disabled": "Fiscalization Disabled",
            "unknown": "Status Unknown",
        }
        return status_map.get(self.status, "Status Unknown")
    
    @property
    def time_since_last_ping(self) -> Optional[str]:
        if self.last_ping_time is None:
            return None
        
        now = datetime.now()
        diff = now - self.last_ping_time
        
        if diff.total_seconds() < 60:
            return "Just now"
        elif diff.total_seconds() < 3600:
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes}m ago"
        elif diff.total_seconds() < 86400:
            hours = int(diff.total_seconds() / 3600)
            return f"{hours}h ago"
        else:
            days = int(diff.total_seconds() / 86400)
            return f"{days}d ago"


class FiscalDeviceMonitorService:
    """Service for monitoring fiscal device status"""
    
    def __init__(self):
        self._settings_repo = None
        self._zimra_service = None
        self._ping_timer: Optional[threading.Timer] = None
        self._running = False
    
    def _get_settings_repo(self):
        """Lazy import to avoid circular imports"""
        if self._settings_repo is None:
            from models.fiscal_settings import FiscalSettingsRepository
            self._settings_repo = FiscalSettingsRepository()
        return self._settings_repo
    
    def _get_zimra_service(self):
        """Lazy import to avoid circular imports"""
        if self._zimra_service is None:
            from services.zimra_api_service import get_zimra_service
            self._zimra_service = get_zimra_service()
        return self._zimra_service
    
    def start_monitoring(self):
        """Start monitoring device status"""
        self.stop_monitoring()
        
        repo = self._get_settings_repo()
        settings = repo.get_settings()
        
        if not settings or not settings.enabled:
            return
        
        self._running = True
        
        # Initial ping
        self._ping_device(settings)
        
        # Schedule periodic pings
        interval_minutes = settings.ping_interval_minutes
        self._schedule_ping(settings, interval_minutes)
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self._running = False
        if self._ping_timer:
            self._ping_timer.cancel()
            self._ping_timer = None
    
    def restart_monitoring(self):
        """Restart monitoring (useful after settings change)"""
        self.stop_monitoring()
        self.start_monitoring()
    
    def ping_device_now(self):
        """Manually ping device"""
        repo = self._get_settings_repo()
        settings = repo.get_settings()
        if not settings or not settings.enabled:
            return None
        
        result = self._ping_device(settings)
        return result
    
    def _schedule_ping(self, settings, minutes: int):
        """Schedule a ping after specified minutes"""
        if not self._running:
            return
        
        self._ping_timer = threading.Timer(
            minutes * 60,
            self._timed_ping,
            args=[settings]
        )
        self._ping_timer.daemon = True
        self._ping_timer.start()
    
    def _timed_ping(self, settings):
        """Called by timer to perform ping and reschedule"""
        if not self._running:
            return
        
        self._ping_device(settings)
        
        # Reschedule
        self._schedule_ping(settings, settings.ping_interval_minutes)
    
    def _ping_device(self, settings):
        """Internal ping method"""
        try:
            service = self._get_zimra_service()
            repo = self._get_settings_repo()
            
            # Get token
            token_result = service.get_token(settings)
            if not token_result.is_success or token_result.data is None:
                repo.update_device_status("offline")
                return None
            
            # Ping ZIMRA
            response_result = service.ping_zimra(settings)
            
            if response_result.is_success and response_result.data:
                response = response_result.data
                repo.update_device_status(
                    status="online",
                    reporting_frequency=response.reporting_frequency,
                    operation_id=response.operation_id,
                )
                return response
            else:
                repo.update_device_status("offline")
                return None
                
        except Exception as e:
            print(f"[Device Monitor] Ping error: {e}")
            repo = self._get_settings_repo()
            repo.update_device_status("error")
            return None
    
    def get_device_status(self) -> DeviceStatus:
        """Get current device status"""
        repo = self._get_settings_repo()
        settings = repo.get_settings()
        
        if not settings or not settings.enabled:
            return DeviceStatus(status="disabled")
        
        return DeviceStatus(
            status=settings.device_status,
            last_ping_time=settings.last_ping_time,
            reporting_frequency=settings.reporting_frequency,
            operation_id=settings.operation_id,
        )
    
    def is_device_ready(self) -> bool:
        """Check if device is ready for fiscalization"""
        status = self.get_device_status()
        return status.is_online
    
    def dispose(self):
        """Dispose resources"""
        self.stop_monitoring()


# Singleton instance
_device_monitor = None


def get_device_monitor_service() -> FiscalDeviceMonitorService:
    """Get the singleton device monitor service"""
    global _device_monitor
    if _device_monitor is None:
        _device_monitor = FiscalDeviceMonitorService()
    return _device_monitor