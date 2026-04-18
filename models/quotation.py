# models/quotation.py
# Quotation model matching the JSON structure from Frappe with Product linking
# =============================================================================

from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from database.db import get_connection, fetchall_dicts, fetchone_dict


@dataclass
class QuotationItem:
    """Individual item within a quotation - linked to product"""
    item_code: str
    item_name: str
    description: str
    qty: float
    rate: float
    amount: float
    uom: str = "Nos"
    # Link to local product
    product_id: Optional[int] = None
    part_no: Optional[str] = None
    # ── Pharmacy-specific fields ──────────────────────────────────────────
    is_pharmacy: bool = False
    dosage: Optional[str] = None
    batch_no: Optional[str] = None
    expiry_date: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuotationItem':
        return cls(
            item_code=str(data.get("item_code", "")),
            item_name=str(data.get("item_name", "")),
            description=str(data.get("description", "")),
            qty=float(data.get("qty", 0)),
            rate=float(data.get("rate", 0)),
            amount=float(data.get("amount", 0)),
            uom=str(data.get("uom", "Nos")),
            part_no=str(data.get("item_code", "")),
            is_pharmacy=bool(data.get("is_pharmacy", False)),
            dosage=data.get("dosage"),
            batch_no=data.get("batch_no"),
            expiry_date=data.get("expiry_date"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_code": self.item_code,
            "item_name": self.item_name,
            "description": self.description,
            "qty": self.qty,
            "rate": self.rate,
            "amount": self.amount,
            "uom": self.uom,
            "product_id": self.product_id,
            "part_no": self.part_no,
            "is_pharmacy": self.is_pharmacy,
            "dosage": self.dosage,
            "batch_no": self.batch_no,
            "expiry_date": self.expiry_date,
        }
    
    def link_to_product(self, product: dict) -> None:
        """Link this quotation item to a local product"""
        if product:
            self.product_id = product.get("id")
            self.part_no = product.get("part_no")
            self.item_name = product.get("name")
            self.uom = product.get("uom", self.uom)


@dataclass
class Quotation:
    """Main Quotation model matching the JSON structure"""
    name: str
    transaction_date: str
    grand_total: float
    docstatus: int  # 0=Draft, 1=Submitted, 2=Cancelled
    company: str
    status: str  # Submitted, Cancelled, etc.
    customer: str
    items: List[QuotationItem] = field(default_factory=list)
    valid_till: Optional[str] = None
    reference_number: Optional[str] = None
    synced: bool = False  # Local sync field - True if synced to local DB
    local_id: Optional[int] = None  # Local database ID
    sync_date: Optional[str] = None  # When it was synced
    frappe_ref: Optional[str] = None  # Reference to Frappe document
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Quotation':
        items = []
        for item_data in data.get("items", []):
            items.append(QuotationItem.from_dict(item_data))
        
        return cls(
            name=str(data.get("name", "")),
            transaction_date=str(data.get("transaction_date", "")),
            grand_total=float(data.get("grand_total", 0)),
            docstatus=int(data.get("docstatus", 0)),
            company=str(data.get("company", "")),
            status=str(data.get("status", "")),
            customer=str(data.get("customer", "")),
            items=items,
            valid_till=data.get("valid_till"),
            reference_number=data.get("reference_number"),
            synced=data.get("synced", False),
            local_id=data.get("local_id"),
            sync_date=data.get("sync_date"),
            frappe_ref=data.get("frappe_ref")
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "transaction_date": self.transaction_date,
            "valid_till": self.valid_till,
            "grand_total": self.grand_total,
            "docstatus": self.docstatus,
            "company": self.company,
            "reference_number": self.reference_number,
            "status": self.status,
            "customer": self.customer,
            "items": [item.to_dict() for item in self.items],
            "synced": self.synced,
            "local_id": self.local_id,
            "sync_date": self.sync_date,
            "frappe_ref": self.frappe_ref
        }
    
    def link_items_to_products(self) -> int:
        """Link quotation items to local products by part_no"""
        from models.product import get_product_by_part_no
        
        linked_count = 0
        for item in self.items:
            if item.part_no:
                product = get_product_by_part_no(item.part_no)
                if product:
                    item.link_to_product(product)
                    linked_count += 1
        return linked_count
    
    @property
    def is_submitted(self) -> bool:
        return self.docstatus == 1
    
    @property
    def is_cancelled(self) -> bool:
        return self.docstatus == 2
    
    @property
    def is_draft(self) -> bool:
        return self.docstatus == 0
    
    @property
    def total_items_count(self) -> int:
        # Count of distinct line items, not sum of all quantities
        return len(self.items)
    
    def can_convert_to_sale(self) -> bool:
        """Check if quotation can be converted to a sale"""
        return self.is_submitted and not self.is_cancelled


@dataclass
class QuotationsResponse:
    """Wrapper for the API response"""
    status: str  # "success" or "error"
    quotations: List[Quotation] = field(default_factory=list)
    message: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuotationsResponse':
        quotations = []
        message_data = data.get("message", {})
        
        status = message_data.get("status", "error")
        
        for qtn_data in message_data.get("quotations", []):
            quotations.append(Quotation.from_dict(qtn_data))
        
        return cls(
            status=status,
            quotations=quotations,
            message=message_data.get("message")
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "message": {
                "status": self.status,
                "quotations": [q.to_dict() for q in self.quotations],
                "message": self.message
            }
        }


# =============================================================================
# Database operations for quotations
# =============================================================================

def create_quotations_table():
    """Create the quotations table if it doesn't exist"""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME = 'quotations'
        )
        CREATE TABLE quotations (
            id                 INT IDENTITY(1,1) PRIMARY KEY,
            name               NVARCHAR(100) NOT NULL,
            transaction_date   NVARCHAR(20) NOT NULL,
            valid_till         NVARCHAR(20) NULL,
            grand_total        DECIMAL(12,2) NOT NULL DEFAULT 0,
            docstatus          INT NOT NULL DEFAULT 0,
            company            NVARCHAR(120) NOT NULL DEFAULT '',
            reference_number   NVARCHAR(80) NULL,
            status             NVARCHAR(50) NOT NULL DEFAULT '',
            customer           NVARCHAR(120) NOT NULL DEFAULT '',
            synced             BIT NOT NULL DEFAULT 0,
            frappe_ref         NVARCHAR(80) NULL,
            sync_date          DATETIME2 NULL,
            raw_data           NVARCHAR(MAX) NULL,
            created_at         DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
            updated_at         DATETIME2 NOT NULL DEFAULT SYSDATETIME()
        )
    """)
    
    # Create quotation items table with product linking
    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME = 'quotation_items'
        )
        CREATE TABLE quotation_items (
            id             INT IDENTITY(1,1) PRIMARY KEY,
            quotation_id   INT NOT NULL,
            item_code      NVARCHAR(50) NOT NULL,
            item_name      NVARCHAR(200) NOT NULL,
            description    NVARCHAR(MAX) NULL,
            qty            DECIMAL(12,4) NOT NULL DEFAULT 1,
            rate           DECIMAL(12,2) NOT NULL DEFAULT 0,
            amount         DECIMAL(12,2) NOT NULL DEFAULT 0,
            uom            NVARCHAR(20) NOT NULL DEFAULT 'Nos',
            product_id     INT NULL,
            part_no        NVARCHAR(50) NULL,
            FOREIGN KEY (quotation_id) REFERENCES quotations(id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()
    print("[Quotation] ✅ Tables created/verified.")


def save_quotation(quotation: Quotation) -> int:
    """Save a quotation to local database with product linking"""
    conn = get_connection()
    cur = conn.cursor()
    
    # First, try to link items to local products
    quotation.link_items_to_products()
    
    # Check if already exists
    cur.execute("SELECT id FROM quotations WHERE name = ?", (quotation.name,))
    existing = cur.fetchone()
    
    if existing:
        # Update existing
        quotation_id = existing[0]
        cur.execute("""
            UPDATE quotations 
            SET transaction_date = ?,
                valid_till = ?,
                grand_total = ?,
                docstatus = ?,
                company = ?,
                reference_number = ?,
                status = ?,
                customer = ?,
                synced = ?,
                frappe_ref = ?,
                updated_at = SYSDATETIME()
            WHERE id = ?
        """, (
            quotation.transaction_date,
            quotation.valid_till,
            quotation.grand_total,
            quotation.docstatus,
            quotation.company,
            quotation.reference_number,
            quotation.status,
            quotation.customer,
            1 if quotation.synced else 0,
            quotation.frappe_ref,
            quotation_id
        ))
        
        # Delete old items
        cur.execute("DELETE FROM quotation_items WHERE quotation_id = ?", (quotation_id,))
    else:
        # Insert new - use OUTPUT INSERTED.id
        cur.execute("""
            INSERT INTO quotations (
                name, transaction_date, valid_till, grand_total, docstatus,
                company, reference_number, status, customer, synced, frappe_ref
            )
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            quotation.name,
            quotation.transaction_date,
            quotation.valid_till,
            quotation.grand_total,
            quotation.docstatus,
            quotation.company,
            quotation.reference_number,
            quotation.status,
            quotation.customer,
            1 if quotation.synced else 0,
            quotation.frappe_ref
        ))
        
        row = cur.fetchone()
        if row and row[0]:
            quotation_id = int(row[0])
        else:
            conn.rollback()
            conn.close()
            raise Exception("Failed to get inserted quotation ID")
    
    # Insert items with product links (plus pharmacy fields)
    for item in quotation.items:
        cur.execute("""
            INSERT INTO quotation_items (
                quotation_id, item_code, item_name, description,
                qty, rate, amount, uom, product_id, part_no,
                is_pharmacy, dosage, batch_no, expiry_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            quotation_id,
            item.item_code,
            item.item_name,
            item.description,
            item.qty,
            item.rate,
            item.amount,
            item.uom,
            item.product_id,
            item.part_no,
            1 if item.is_pharmacy else 0,
            item.dosage,
            item.batch_no,
            item.expiry_date,
        ))
    
    conn.commit()
    conn.close()
    return quotation_id


def save_quotations_batch(quotations: List[Quotation]) -> int:
    """Save multiple quotations to database"""
    count = 0
    for quotation in quotations:
        try:
            save_quotation(quotation)
            count += 1
        except Exception as e:
            print(f"[ERROR] Failed to save quotation {quotation.name}: {e}")
    return count


def get_all_quotations() -> List[Quotation]:
    """Get all quotations from local database with linked products"""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM quotations 
        ORDER BY transaction_date DESC, name DESC
    """)
    rows = fetchall_dicts(cur)
    
    quotations = []
    for row in rows:
        # Get items for this quotation
        cur.execute("""
            SELECT qi.*, p.name as local_product_name, p.price as local_price
            FROM quotation_items qi
            LEFT JOIN products p ON qi.product_id = p.id
            WHERE qi.quotation_id = ?
        """, (row["id"],))
        items_rows = fetchall_dicts(cur)
        
        items = []
        for item_row in items_rows:
            items.append(QuotationItem(
                item_code=item_row["item_code"],
                item_name=item_row.get("local_product_name") or item_row["item_name"],
                description=item_row.get("description", ""),
                qty=float(item_row["qty"]),
                rate=float(item_row["rate"]),
                amount=float(item_row["amount"]),
                uom=item_row.get("uom", "Nos"),
                product_id=item_row.get("product_id"),
                part_no=item_row.get("part_no")
            ))
        
        quotations.append(Quotation(
            name=row["name"],
            transaction_date=row["transaction_date"],
            valid_till=row.get("valid_till"),
            grand_total=float(row["grand_total"]),
            docstatus=row["docstatus"],
            company=row["company"],
            reference_number=row.get("reference_number"),
            status=row["status"],
            customer=row["customer"],
            items=items,
            synced=bool(row.get("synced", False)),
            local_id=row["id"],
            frappe_ref=row.get("frappe_ref"),
            sync_date=row.get("sync_date")
        ))
    
    conn.close()
    return quotations


def get_unsynced_quotations() -> List[Quotation]:
    """Get quotations that haven't been synced to local DB yet"""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM quotations 
        WHERE synced = 0
        ORDER BY transaction_date DESC
    """)
    rows = fetchall_dicts(cur)
    
    quotations = []
    for row in rows:
        cur.execute("""
            SELECT qi.*, p.name as local_product_name
            FROM quotation_items qi
            LEFT JOIN products p ON qi.product_id = p.id
            WHERE qi.quotation_id = ?
        """, (row["id"],))
        items_rows = fetchall_dicts(cur)
        
        items = [QuotationItem(
            item_code=r["item_code"],
            item_name=r.get("local_product_name") or r["item_name"],
            description=r.get("description", ""),
            qty=float(r["qty"]),
            rate=float(r["rate"]),
            amount=float(r["amount"]),
            uom=r.get("uom", "Nos"),
            product_id=r.get("product_id"),
            part_no=r.get("part_no")
        ) for r in items_rows]
        
        quotations.append(Quotation(
            name=row["name"],
            transaction_date=row["transaction_date"],
            valid_till=row.get("valid_till"),
            grand_total=float(row["grand_total"]),
            docstatus=row["docstatus"],
            company=row["company"],
            reference_number=row.get("reference_number"),
            status=row["status"],
            customer=row["customer"],
            items=items,
            synced=bool(row.get("synced", False)),
            local_id=row["id"],
            frappe_ref=row.get("frappe_ref")
        ))
    
    conn.close()
    return quotations


def mark_quotation_synced(quotation_id: int, frappe_ref: str = None) -> bool:
    """Mark a quotation as synced"""
    conn = get_connection()
    cur = conn.cursor()
    
    if frappe_ref:
        cur.execute("""
            UPDATE quotations 
            SET synced = 1, frappe_ref = ?, sync_date = SYSDATETIME()
            WHERE id = ?
        """, (frappe_ref, quotation_id))
    else:
        cur.execute("""
            UPDATE quotations 
            SET synced = 1, sync_date = SYSDATETIME()
            WHERE id = ?
        """, (quotation_id,))
    
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def get_quotation_by_name(name: str) -> Optional[Quotation]:
    """Get a specific quotation by its name"""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM quotations WHERE name = ?", (name,))
    row = fetchone_dict(cur)
    
    if not row:
        conn.close()
        return None
    
    cur.execute("""
        SELECT qi.*, p.name as local_product_name, p.price as local_price, p.stock
        FROM quotation_items qi
        LEFT JOIN products p ON qi.product_id = p.id
        WHERE qi.quotation_id = ?
    """, (row["id"],))
    items_rows = fetchall_dicts(cur)
    
    print(f"\n[DEBUG] get_quotation_by_name: '{name}' | {len(items_rows)} items found in DB")

    items = []
    for r in items_rows:
        print(f"[DEBUG]   DB row → item_code={r.get('item_code')!r} | part_no={r.get('part_no')!r} | "
              f"product_id={r.get('product_id')!r} | local_product_name={r.get('local_product_name')!r} | "
              f"qty={r.get('qty')!r} | rate={r.get('rate')!r}")
        items.append(QuotationItem(
            item_code=r["item_code"],
            item_name=r.get("local_product_name") or r["item_name"],
            description=r.get("description", ""),
            qty=float(r["qty"]),
            rate=float(r["rate"]),
            amount=float(r["amount"]),
            uom=r.get("uom", "Nos"),
            product_id=r.get("product_id"),
            part_no=r.get("part_no")
        ))
    
    conn.close()
    
    return Quotation(
        name=row["name"],
        transaction_date=row["transaction_date"],
        valid_till=row.get("valid_till"),
        grand_total=float(row["grand_total"]),
        docstatus=row["docstatus"],
        company=row["company"],
        reference_number=row.get("reference_number"),
        status=row["status"],
        customer=row["customer"],
        items=items,
        synced=bool(row.get("synced", False)),
        local_id=row["id"],
        frappe_ref=row.get("frappe_ref")
    )


def convert_quotation_to_cart(quotation: Quotation) -> list[dict]:
    """
    Convert a quotation to cart items for POS sale.
    Returns list of cart items ready for create_sale().

    Qty fix: the quotation stores qty as float (e.g. 5.0). The cart
    expects a clean number — we pass int when it's a whole number so
    the POS doesn't split or misinterpret the quantity.
    """
    cart_items = []

    print(f"\n[DEBUG] convert_quotation_to_cart: '{quotation.name}' | {len(quotation.items)} items")

    for item in quotation.items:
        print(f"[DEBUG]   item_code={item.item_code!r} | part_no={item.part_no!r} | "
              f"product_id={item.product_id!r} | qty={item.qty!r} (type={type(item.qty).__name__}) | "
              f"rate={item.rate!r} | item_name={item.item_name!r}")

        # Use integer qty when it is a whole number (5.0 → 5),
        # otherwise keep the decimal (1.5 stays 1.5)
        qty = int(item.qty) if item.qty == int(item.qty) else item.qty

        # Recalculate amount from rate * qty to be safe in case
        # the stored amount has rounding drift
        amount = round(item.rate * qty, 2)

        part_no = item.part_no or item.item_code
        print(f"[DEBUG]   → resolved part_no={part_no!r} | qty={qty!r} | amount={amount!r}")

        cart_items.append({
            "part_no":      part_no,
            "product_name": item.item_name,
            "qty":          qty,
            "price":        item.rate,
            "total":        amount,
            "discount":     0,
            "tax":          "",
            "tax_type":     "",
            "tax_rate":     0.0,
            "tax_amount":   0.0,
            "remarks":      f"From quotation: {quotation.name}",
            # ── Pharmacy round-trip fields ────────────────────────────
            "is_pharmacy":  bool(item.is_pharmacy),
            "dosage":       item.dosage,
            "batch_no":     item.batch_no,
            "expiry_date":  item.expiry_date,
        })

    print(f"[DEBUG] cart_items built: {len(cart_items)} entries")
    return cart_items


def delete_quotation(quotation_id: int) -> bool:
    """Delete a quotation from local database"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM quotations WHERE id = ?", (quotation_id,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def get_quotations_count() -> int:
    """Get total number of quotations"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM quotations")
    count = cur.fetchone()[0]
    conn.close()
    return count


def get_synced_count() -> int:
    """Get number of synced quotations"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM quotations WHERE synced = 1")
    count = cur.fetchone()[0]
    conn.close()
    return count


def get_quotations_by_customer(customer_name: str) -> List[Quotation]:
    """Get quotations for a specific customer"""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM quotations 
        WHERE customer = ?
        ORDER BY transaction_date DESC
    """, (customer_name,))
    rows = fetchall_dicts(cur)
    
    quotations = []
    for row in rows:
        cur.execute("SELECT * FROM quotation_items WHERE quotation_id = ?", (row["id"],))
        items_rows = fetchall_dicts(cur)
        
        items = [QuotationItem(
            item_code=r["item_code"],
            item_name=r["item_name"],
            description=r.get("description", ""),
            qty=float(r["qty"]),
            rate=float(r["rate"]),
            amount=float(r["amount"]),
            uom=r.get("uom", "Nos")
        ) for r in items_rows]
        
        quotations.append(Quotation(
            name=row["name"],
            transaction_date=row["transaction_date"],
            valid_till=row.get("valid_till"),
            grand_total=float(row["grand_total"]),
            docstatus=row["docstatus"],
            company=row["company"],
            reference_number=row.get("reference_number"),
            status=row["status"],
            customer=row["customer"],
            items=items,
            synced=bool(row.get("synced", False)),
            local_id=row["id"],
            frappe_ref=row.get("frappe_ref")
        ))
    
    conn.close()
    return quotations


def get_company_defaults_for_quotation() -> dict:
    """Get company defaults for quotation printing"""
    from models.company_defaults import get_defaults
    defaults = get_defaults()
    return {
        "company_name": defaults.get("company_name", ""),
        "address_1": defaults.get("address_1", ""),
        "address_2": defaults.get("address_2", ""),
        "phone": defaults.get("phone", ""),
        "email": defaults.get("email", ""),
        "vat_number": defaults.get("vat_number", ""),
        "tin_number": defaults.get("tin_number", ""),
        "footer_text": defaults.get("footer_text", "Thank you for your business!"),
        "zimra_serial_no": defaults.get("zimra_serial_no", ""),
        "zimra_device_id": defaults.get("zimra_device_id", "")
    }


# =============================================================================
# API Integration
# =============================================================================

def fetch_quotations_from_frappe(
    frappe_url: str = None,
    api_key: str = None,
    api_secret: str = None
) -> QuotationsResponse:
    """
    Fetch quotations from Frappe API
    
    Expected response format:
    {
        "message": {
            "status": "success",
            "quotations": [...]
        }
    }
    """
    from models.company_defaults import get_defaults
    
    defaults = get_defaults()
    
    url = frappe_url or defaults.get("frappe_url", "")
    key = api_key or defaults.get("frappe_api_key", "")
    secret = api_secret or defaults.get("frappe_api_secret", "")
    
    if not url or not key or not secret:
        return QuotationsResponse(
            status="error",
            message="Frappe credentials not configured"
        )
    
    # Ensure URL ends with /api/method/
    if not url.endswith("/"):
        url += "/"
    if "api/method" not in url:
        url += "api/method/"
    
    endpoint = f"{url}pos_api.get_quotations"
    
    try:
        import requests
        response = requests.get(
            endpoint,
            auth=(key, secret),
            timeout=30,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            return QuotationsResponse.from_dict(data)
        else:
            return QuotationsResponse(
                status="error",
                message=f"HTTP {response.status_code}: {response.text}"
            )
            
    except requests.exceptions.Timeout:
        return QuotationsResponse(status="error", message="Request timeout")
    except requests.exceptions.ConnectionError:
        return QuotationsResponse(status="error", message="Connection failed")
    except Exception as e:
        return QuotationsResponse(status="error", message=str(e))


def sync_quotations_from_frappe() -> dict:
    """
    Fetch quotations from Frappe and save to local database.
    Returns sync result stats.
    """
    response = fetch_quotations_from_frappe()
    
    if response.status == "error":
        return {
            "success": False,
            "message": response.message,
            "synced": 0,
            "total": 0
        }
    
    # Save all quotations to database
    saved_count = 0
    for quotation in response.quotations:
        try:
            # Mark as synced since we just fetched it
            quotation.synced = True
            save_quotation(quotation)
            saved_count += 1
        except Exception as e:
            print(f"[ERROR] Failed to save {quotation.name}: {e}")
    
    return {
        "success": True,
        "message": f"Synced {saved_count} quotations",
        "synced": saved_count,
        "total": len(response.quotations)
    }


# Initialize table on import
try:
    create_quotations_table()
except Exception as e:
    print(f"[Quotation] Table init warning: {e}")