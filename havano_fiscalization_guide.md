# Havano ZIMRA Cloud Fiscalization API Documentation

Complete technical specification and integration guide for the **Havano ZIMRA Cloud Fiscalization API**, including sales invoice submission, device connection testing (Ping), credit notes, line-item XML generation, and offline fallback mode.

---

## Table of Contents
1. [Overview & Architecture](#1-overview--architecture)
2. [Authentication & Security](#2-authentication--security)
3. [Device Connection Test (Ping Device)](#3-device-connection-test-ping-device)
4. [Sales Invoice Fiscalization](#4-sales-invoice-fiscalization)
   - [API Endpoint & Headers](#api-endpoint--headers)
   - [Form Payload Parameters](#form-payload-parameters)
   - [Line Item XML Schema (`items_xml`)](#line-item-xml-schema-items_xml)
   - [Inclusive VAT Calculation Formula](#inclusive-vat-calculation-formula)
   - [API Response Structure](#api-response-structure)
5. [Credit Note / Refund Fiscalization](#5-credit-note--refund-fiscalization)
6. [Offline Dynamic Fallback Mode](#6-offline-dynamic-fallback-mode)
7. [Complete Python Implementation Reference](#7-complete-python-implementation-reference)

---

## 1. Overview & Architecture

The **Havano ZIMRA Cloud Service** connects POS systems with ZIMRA Electronic Fiscal Devices (EFD).

```
+------------------+         (HTTP POST)        +--------------------------+         +---------------+
| POS Application  |  ----------------------->  | Havano ZIMRA Cloud API   |  -----> | ZIMRA / EFD   |
| (Local / Client) |  <-----------------------  | (Frappe / REST Gateway)  |  <----- | Server        |
+------------------+     (JSON Response)        +--------------------------+         +---------------+
```

### Supported Currencies:
- `USD` (US Dollar)
- `ZIG` (Zimbabwe Gold - automatically mapped from `ZWD`, `ZWL`, `ZWG`)
- `EUR` (Euro)
- `GBP` (British Pound)
- `ZAR` (South African Rand)

---

## 2. Authentication & Security

Every request to Havano ZIMRA Cloud requires **Two-Tier Authentication**:

1. **CSRF Token**: Obtained dynamically per transaction from the token endpoint.
2. **API Credentials**: Passed via standard Frappe API Token Header.

### Required Headers for All Payload Requests:
```http
X-Frappe-CSRF-Token: <CSRF_TOKEN>
Authorization: token <API_KEY>:<API_SECRET>
Content-Type: application/x-www-form-urlencoded
```

---

## 3. Device Connection Test (Ping Device)

Used in **Company Defaults -> Fiscalization Settings** to verify API keys, device serial status, and server connectivity.

### Step 3.1: Fetch CSRF Token
- **HTTP Method**: `POST`
- **URL**: `{base_url}/api/method/havanozimracloud.api.token`
- **Headers**: None required
- **Response**:
  ```json
  {
    "message": "99a8b7c6d5e4f3a2b1..."
  }
  ```

### Step 3.2: Ping Device
- **HTTP Method**: `POST`
- **URL**: `{base_url}/api/method/havanozimracloud.api.pingzimra`
- **Headers**:
  ```http
  X-Frappe-CSRF-Token: 99a8b7c6d5e4f3a2b1...
  Authorization: token <API_KEY>:<API_SECRET>
  Content-Type: application/x-www-form-urlencoded
  ```
- **Form Body Data**:
  ```ini
  device_sn=EFD-908123
  ```
- **Success Response**:
  ```json
  {
    "message": {
      "device_sn": "EFD-908123",
      "reporting_frequency": 5,
      "operation_id": "PING-OK"
    }
  }
  ```

---

## 4. Sales Invoice Fiscalization

### API Endpoint & Headers
- **HTTP Method**: `POST`
- **URL**: `{base_url}/api/method/havanozimracloud.api.sendinvoice`
- **Headers**:
  ```http
  X-Frappe-CSRF-Token: <CSRF_TOKEN>
  Authorization: token <API_KEY>:<API_SECRET>
  Content-Type: application/x-www-form-urlencoded
  ```

### Form Payload Parameters (`x-www-form-urlencoded`)

| Parameter | Type | Required | Description / Example |
| :--- | :--- | :--- | :--- |
| `device_sn` | String | **Yes** | ZIMRA EFD Serial Number (e.g. `EFD-908123`) |
| `invoice_flag` | String | **Yes** | `"0"` for Sales Invoice, `"1"` for Credit Note |
| `add_customer` | String | **Yes** | Set to `"0"` |
| `currency` | String | **Yes** | ISO Currency Code (`"USD"`, `"ZIG"`, `"ZAR"`, etc.) |
| `invoice_number` | String | **Yes** | Unique Store Invoice Number (e.g. `INV-10089`) |
| `customer_name` | String | **Yes** | Buyer Name (e.g. `"Cash Customer"` or company name) |
| `trade_name` | String | Optional | Customer trade name (e.g. `"Acme Trading"`) |
| `customer_tin` | String | Optional | 10-digit Customer TIN (e.g. `"111111111"` if default) |
| `customer_vat_number` | String | Optional | 9-digit Customer VAT No (e.g. `"000000000"` if default) |
| `customer_address` | String | Optional | Combined street & city address |
| `customer_telephone_number`| String| Optional | Customer Phone Number |
| `customer_email` | String | Optional | Customer Email Address |
| `customer_street` | String | Optional | Street Address |
| `customer_houseNo` | String | Optional | House / Building Number |
| `customer_city` | String | Optional | City Name |
| `customer_province` | String | Optional | Province Name |
| `original_invoice_no` | String | Optional | Empty string `""` for sales |
| `global_invoice_no` | String | Optional | Empty string `""` for sales |
| `tendered` | String | **Yes** | Total tendered amount formatted to 2 decimals (e.g. `45.00`) |
| `items_xml` | String | **Yes** | Line items XML string (see below) |

---

### Line Item XML Schema (`items_xml`)

Line items must be compiled into a valid XML string and passed inside the `items_xml` form parameter:

```xml
<ITEMS>
    <ITEM>
        <HH>1</HH>
        <ITEMCODE>99999999</ITEMCODE>
        <ITEMNAME>Sugar 2kg</ITEMNAME>
        <ITEMNAME2>Sugar 2kg</ITEMNAME2>
        <QTY>2.00</QTY>
        <PRICE>3.50</PRICE>
        <TOTAL>7.00</TOTAL>
        <VAT>0.91</VAT>
        <VATR>0.150</VATR>
        <VNAME>VAT</VNAME>
    </ITEM>
    <ITEM>
        <HH>2</HH>
        <ITEMCODE>99999999</ITEMCODE>
        <ITEMNAME>Bread 700g</ITEMNAME>
        <ITEMNAME2>Bread 700g</ITEMNAME2>
        <QTY>1.00</QTY>
        <PRICE>1.00</PRICE>
        <TOTAL>1.00</TOTAL>
        <VAT>0.00</VAT>
        <VATR>0.000</VATR>
        <VNAME>ZERO RATED</VNAME>
    </ITEM>
</ITEMS>
```

#### Line Item Element Reference:
- `<HH>`: Line item number (`1`, `2`, `3`...).
- `<ITEMCODE>`: HS Code (defaults to `"99999999"` if not set).
- `<ITEMNAME>`: Item name (Max 100 characters).
- `<ITEMNAME2>`: Secondary item name (Max 100 characters).
- `<QTY>`: Quantity (`2 decimal places`).
- `<PRICE>`: Unit price inclusive of tax (`2 decimal places`).
- `<TOTAL>`: Line total inclusive of tax (`2 decimal places`).
- `<VAT>`: Inclusive VAT amount (`2 decimal places`).
- `<VATR>`: VAT Rate as a decimal fraction (`0.150` for 15% VAT, `0.000` for exempt/zero-rated).
- `<VNAME>`: Category name (`"VAT"`, `"ZERO RATED"`, or `"EXEMPT"`).

---

### Inclusive VAT Calculation Formula

To pass ZIMRA strict tax audit checks, inclusive tax amounts must be calculated as follows:

$$\text{VAT Amount} = \text{Round}\left( \text{Total} - \left( \frac{\text{Total}}{1 + \frac{\text{VAT Rate}}{100}} \right), 2 \right)$$

#### Example (Total = $20.00, VAT Rate = 15%):
$$\text{VAT Amount} = 20.00 - \left( \frac{20.00}{1.15} \right) = 20.00 - 17.3913 = \$2.61$$

---

### API Response Structure

#### Success Response:
```json
{
  "message": {
    "Message": "Invoice fiscalized successfully",
    "QRcode": "https://zimra.gov.zw/verify?sn=EFD-908123&no=8921&hash=A1B2C3",
    "VerificationCode": "A1B2C3D4E5F67890",
    "DeviceID": "DEV-55421",
    "FiscalDay": "2026-08-18",
    "receiptType": "Fiscal Invoice",
    "receiptCurrency": "USD",
    "receiptCounter": 142,
    "receiptGlobalNo": 8921,
    "EFDSERIAL": "EFD-908123"
  }
}
```

---

## 5. Credit Note / Refund Fiscalization

For returns or credit notes, the invoice flag is set to `"1"` and must reference the original sale's invoice and global sequence number.

### Payload Adjustments for Credit Notes:
- `invoice_flag`: Set to `"1"`.
- `invoice_number`: Credit Note Number (e.g. `CN-00104`).
- `original_invoice_no`: Store Invoice Number of original sale (e.g. `INV-10089`).
- `global_invoice_no`: ZIMRA `receiptGlobalNo` returned during original sale (e.g. `8921`).
- `tendered`: Refund total amount.

---

## 6. Offline Dynamic Fallback Mode

When internet connectivity is unavailable:
1. Generate local 16-character SHA-256 signature hash of `(DeviceSN + Date + GlobalNo + Total)`.
2. Construct local ZIMRA verification URL.
3. Save record in database with `fiscal_status = 'PENDING_SYNC'`.
4. Background worker syncs the pending invoice automatically when online.

---

## 7. Complete Python Implementation Reference

```python
import requests
import xml.etree.ElementTree as ET

class HavanoZimraFiscalizer:
    def __init__(self, base_url: str, api_key: str, api_secret: str, device_sn: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.api_secret = api_secret
        self.device_sn = device_sn

    def fetch_csrf_token(self) -> str:
        url = f"{self.base_url}/api/method/havanozimracloud.api.token"
        resp = requests.post(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        token = data.get("message") or data.get("token")
        if not token:
            raise ValueError("Failed to obtain CSRF token")
        return token

    def ping_device((self) -> dict:
        csrf_token = self.fetch_csrf_token()
        url = f"{self.base_url}/api/method/havanozimracloud.api.pingzimra"
        headers = {
            "X-Frappe-CSRF-Token": csrf_token,
            "Authorization": f"token {self.api_key}:{self.api_secret}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        resp = requests.post(url, data={"device_sn": self.device_sn}, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def build_items_xml(self, items: list) -> str:
        root = ET.Element("ITEMS")
        for idx, item in enumerate(items, 1):
            elem = ET.SubElement(root, "ITEM")
            total = float(item["total"])
            rate = float(item.get("vat_rate", 15.0))
            vat_amount = round(total - (total / (1 + (rate / 100))), 2) if rate > 0 else 0.0

            ET.SubElement(elem, "HH").text = str(idx)
            ET.SubElement(elem, "ITEMCODE").text = str(item.get("hs_code") or "99999999")
            ET.SubElement(elem, "ITEMNAME").text = str(item["name"])[:100]
            ET.SubElement(elem, "ITEMNAME2").text = str(item["name"])[:100]
            ET.SubElement(elem, "QTY").text = f"{float(item['qty']):.2f}"
            ET.SubElement(elem, "PRICE").text = f"{float(item['price']):.2f}"
            ET.SubElement(elem, "TOTAL").text = f"{total:.2f}"
            ET.SubElement(elem, "VAT").text = f"{vat_amount:.2f}"
            ET.SubElement(elem, "VATR").text = f"{(rate / 100):.3f}"
            ET.SubElement(elem, "VNAME").text = "VAT" if rate > 0 else "EXEMPT"
        return ET.tostring(root, encoding="unicode")

    def send_invoice(self, invoice_number: str, currency: str, customer_name: str, items: list, tendered: float) -> dict:
        csrf_token = self.fetch_csrf_token()
        url = f"{self.base_url}/api/method/havanozimracloud.api.sendinvoice"
        headers = {
            "X-Frappe-CSRF-Token": csrf_token,
            "Authorization": f"token {self.api_key}:{self.api_secret}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        payload = {
            "device_sn": self.device_sn,
            "add_customer": "0",
            "invoice_flag": "0",
            "currency": currency.upper(),
            "invoice_number": invoice_number,
            "customer_name": customer_name,
            "trade_name": customer_name,
            "customer_vat_number": "000000000",
            "customer_tin": "111111111",
            "tendered": f"{tendered:.2f}",
            "items_xml": self.build_items_xml(items)
        }

        resp = requests.post(url, data=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        return resp.json()
