# models/fiscal_settings.py

from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from database.db import get_connection


@dataclass
class FiscalSettings:
    enabled: bool = False
    base_url: str = ""
    api_key: str = ""
    api_secret: str = ""
    device_sn: str = ""
    ping_interval_minutes: int = 5
    device_status: str = "unknown"
    last_ping_time: Optional[datetime] = None
    reporting_frequency: Optional[int] = None
    operation_id: Optional[str] = None
    id: Optional[int] = None
    
    @classmethod
    def from_dict(cls, data: dict) -> "FiscalSettings":
        return cls(
            id=data.get("id"),
            enabled=bool(data.get("enabled", False)),
            base_url=str(data.get("base_url", "")),
            api_key=str(data.get("api_key", "")),
            api_secret=str(data.get("api_secret", "")),
            device_sn=str(data.get("device_sn", "")),
            ping_interval_minutes=int(data.get("ping_interval_minutes", 5)),
            device_status=str(data.get("device_status", "unknown")),
            last_ping_time=data.get("last_ping_time"),
            reporting_frequency=data.get("reporting_frequency"),
            operation_id=data.get("operation_id"),
        )


class FiscalSettingsRepository:
    """Repository for fiscal settings CRUD operations"""
    
    @staticmethod
    def get_settings() -> Optional[FiscalSettings]:
        """Get fiscal settings from database"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if table exists first
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = 'fiscal_settings'
            """)
            table_exists = cursor.fetchone()[0]
            
            if not table_exists:
                print("[FiscalSettings] Table fiscal_settings does not exist yet")
                return None
            
            cursor.execute("SELECT TOP 1 * FROM fiscal_settings ORDER BY id")
            row = cursor.fetchone()
            
            if not row:
                return None
            
            # Convert row to dict manually
            columns = [column[0] for column in cursor.description]
            row_dict = dict(zip(columns, row))
            
            return FiscalSettings.from_dict(row_dict)
        except Exception as e:
            print(f"[FiscalSettings] Error getting settings: {e}")
            return None
        finally:
            conn.close()
    
    @staticmethod
    def save_settings(settings: FiscalSettings) -> FiscalSettings:
        """Save fiscal settings to database"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if table exists
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = 'fiscal_settings'
            """)
            table_exists = cursor.fetchone()[0]
            
            if not table_exists:
                print("[FiscalSettings] Creating fiscal_settings table...")
                cursor.execute("""
                    CREATE TABLE fiscal_settings (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        enabled BIT NOT NULL DEFAULT 0,
                        base_url NVARCHAR(500) NOT NULL DEFAULT '',
                        api_key NVARCHAR(200) NOT NULL DEFAULT '',
                        api_secret NVARCHAR(200) NOT NULL DEFAULT '',
                        device_sn NVARCHAR(100) NOT NULL DEFAULT '',
                        ping_interval_minutes INT NOT NULL DEFAULT 5,
                        device_status NVARCHAR(20) NOT NULL DEFAULT 'unknown',
                        last_ping_time DATETIME2 NULL,
                        reporting_frequency INT NULL,
                        operation_id NVARCHAR(100) NULL,
                        created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
                        updated_at DATETIME2 NOT NULL DEFAULT SYSDATETIME()
                    )
                """)
                conn.commit()
                print("[FiscalSettings] Table created successfully")
            
            # Check if any record exists
            cursor.execute("SELECT COUNT(*) FROM fiscal_settings")
            count = cursor.fetchone()[0]
            
            if count == 0:
                # Insert new - use OUTPUT INSERTED.id instead of SCOPE_IDENTITY()
                cursor.execute("""
                    INSERT INTO fiscal_settings (
                        enabled, base_url, api_key, api_secret, device_sn,
                        ping_interval_minutes, device_status, last_ping_time,
                        reporting_frequency, operation_id, created_at, updated_at
                    ) 
                    OUTPUT INSERTED.id
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, SYSDATETIME(), SYSDATETIME())
                """, (
                    1 if settings.enabled else 0,
                    settings.base_url,
                    settings.api_key,
                    settings.api_secret,
                    settings.device_sn,
                    settings.ping_interval_minutes,
                    settings.device_status,
                    settings.last_ping_time,
                    settings.reporting_frequency,
                    settings.operation_id,
                ))
                row = cursor.fetchone()
                if row:
                    settings.id = int(row[0])
                else:
                    # Fallback: get the last inserted ID
                    cursor.execute("SELECT @@IDENTITY as id")
                    row = cursor.fetchone()
                    if row:
                        settings.id = int(row[0])
            else:
                # Update existing - get the first record's ID
                cursor.execute("SELECT TOP 1 id FROM fiscal_settings")
                row = cursor.fetchone()
                if row:
                    existing_id = int(row[0])
                    settings.id = existing_id
                    
                    cursor.execute("""
                        UPDATE fiscal_settings SET
                            enabled = ?,
                            base_url = ?,
                            api_key = ?,
                            api_secret = ?,
                            device_sn = ?,
                            ping_interval_minutes = ?,
                            device_status = ?,
                            last_ping_time = ?,
                            reporting_frequency = ?,
                            operation_id = ?,
                            updated_at = SYSDATETIME()
                        WHERE id = ?
                    """, (
                        1 if settings.enabled else 0,
                        settings.base_url,
                        settings.api_key,
                        settings.api_secret,
                        settings.device_sn,
                        settings.ping_interval_minutes,
                        settings.device_status,
                        settings.last_ping_time,
                        settings.reporting_frequency,
                        settings.operation_id,
                        existing_id
                    ))
            
            conn.commit()
            print(f"[FiscalSettings] Settings saved successfully (id={settings.id})")
            return settings
            
        except Exception as e:
            print(f"[FiscalSettings] Error saving settings: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    @staticmethod
    def update_device_status(status: str, reporting_frequency: Optional[int] = None, 
                            operation_id: Optional[str] = None) -> bool:
        """Update device status without loading full settings"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if table exists and has data
            cursor.execute("SELECT COUNT(*) FROM fiscal_settings")
            count = cursor.fetchone()[0]
            
            if count == 0:
                # Create default settings first
                from models.fiscal_settings import FiscalSettings
                default = FiscalSettings()
                FiscalSettingsRepository.save_settings(default)
            
            # Get the first record's ID
            cursor.execute("SELECT TOP 1 id FROM fiscal_settings")
            row = cursor.fetchone()
            if not row:
                return False
            
            existing_id = int(row[0])
            
            cursor.execute("""
                UPDATE fiscal_settings 
                SET device_status = ?,
                    reporting_frequency = ISNULL(?, reporting_frequency),
                    operation_id = ISNULL(?, operation_id),
                    last_ping_time = SYSDATETIME(),
                    updated_at = SYSDATETIME()
                WHERE id = ?
            """, (status, reporting_frequency, operation_id, existing_id))
            
            affected = cursor.rowcount
            conn.commit()
            return affected > 0
        except Exception as e:
            print(f"[FiscalSettings] Error updating device status: {e}")
            return False
        finally:
            conn.close()