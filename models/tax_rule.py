# models/tax_rule.py

from dataclasses import dataclass
from typing import List, Optional
from database.db import get_connection

@dataclass
class TaxRule:
    id: Optional[int] = None
    tax_name: str = ""        # e.g., "VAT"
    tax_rate: float = 0.0     # e.g., 15.0
    is_default: bool = False
    
    @classmethod
    def from_dict(cls, data: dict) -> "TaxRule":
        return cls(
            id=data.get("id"),
            tax_name=data.get("tax_name", ""),
            tax_rate=float(data.get("tax_rate", 0.0)),
            is_default=bool(data.get("is_default", False))
        )

class TaxRuleRepository:
    @staticmethod
    def _ensure_table():
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'tax_rules')
                BEGIN
                    CREATE TABLE tax_rules (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        tax_name NVARCHAR(100) NOT NULL UNIQUE,
                        tax_rate DECIMAL(8,4) NOT NULL DEFAULT 0.0,
                        is_default BIT NOT NULL DEFAULT 0,
                        created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
                        updated_at DATETIME2 NOT NULL DEFAULT SYSDATETIME()
                    )
                END
            """)
            conn.commit()
        except Exception as e:
            print(f"[TaxRule] Error creating table: {e}")
        finally:
            conn.close()

    @staticmethod
    def get_all() -> List[TaxRule]:
        TaxRuleRepository._ensure_table()
        conn = get_connection()
        cursor = conn.cursor()
        rules = []
        try:
            cursor.execute("SELECT id, tax_name, tax_rate, is_default FROM tax_rules ORDER BY tax_name")
            columns = [column[0] for column in cursor.description]
            for row in cursor.fetchall():
                row_dict = dict(zip(columns, row))
                rules.append(TaxRule.from_dict(row_dict))
        except Exception as e:
            print(f"[TaxRule] Error getting rules: {e}")
        finally:
            conn.close()
        return rules

    @staticmethod
    def save(rule: TaxRule) -> TaxRule:
        TaxRuleRepository._ensure_table()
        conn = get_connection()
        cursor = conn.cursor()
        try:
            if rule.is_default:
                # Set all others to false
                cursor.execute("UPDATE tax_rules SET is_default = 0")
                
            if rule.id is None:
                cursor.execute("""
                    INSERT INTO tax_rules (tax_name, tax_rate, is_default, created_at, updated_at)
                    OUTPUT INSERTED.id
                    VALUES (?, ?, ?, SYSDATETIME(), SYSDATETIME())
                """, (rule.tax_name, rule.tax_rate, 1 if rule.is_default else 0))
                row = cursor.fetchone()
                if row:
                    rule.id = row[0]
            else:
                cursor.execute("""
                    UPDATE tax_rules SET
                        tax_name = ?,
                        tax_rate = ?,
                        is_default = ?,
                        updated_at = SYSDATETIME()
                    WHERE id = ?
                """, (rule.tax_name, rule.tax_rate, 1 if rule.is_default else 0, rule.id))
            conn.commit()
        except Exception as e:
            print(f"[TaxRule] Error saving rule: {e}")
            conn.rollback()
        finally:
            conn.close()
        return rule

    @staticmethod
    def delete(rule_id: int) -> bool:
        TaxRuleRepository._ensure_table()
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM tax_rules WHERE id = ?", (rule_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"[TaxRule] Error deleting rule: {e}")
            return False
        finally:
            conn.close()
