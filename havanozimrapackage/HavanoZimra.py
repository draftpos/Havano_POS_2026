import os
import json
from enum import Enum
import time
from xml.etree import ElementTree as ET
from havanozimrapackage.InvoiceData import( receiptWrapper, ReceiptLine, ReceiptTax, CreditDebitNote,
    BuyerData, BuyerContacts, BuyerAddress ) 
from typing import List
from havanozimrapackage.ReceiptQRCodes import ReceiptQRCodes
from havanozimrapackage.Signature import Signature
from dataclasses import asdict
from collections import defaultdict
from datetime import datetime
from io import BytesIO
import random
from decimal import Decimal, getcontext
from decimal import Decimal, ROUND_HALF_UP
from decimal import Decimal, ROUND_DOWN


class ZimraDevice:

    def __init__(self):
        self.config_file_path = None
        self._config_values = {}

    #=========LOAD CONFIG FILE=========
    def load_config_file(self, config_file_path):
        if not config_file_path:
            raise ValueError("Config file path cannot be empty.")
        if not os.path.exists(config_file_path):
            raise FileNotFoundError(f"Config file not found: {config_file_path}")

        config_values = {}
        with open(config_file_path, "r") as config_file:
            for line in config_file:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith(";"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    continue
                if ":" in line:
                    key, value = line.split(":", 1)
                elif "=" in line:
                    key, value = line.split("=", 1)
                else:
                    continue
                config_values[key.strip()] = value.strip()

        self.config_file_path = config_file_path
        self._config_values = config_values
        return self._config_values

    #=========GET CONFIG VALUE=========
    def get_config_value(self, key):
        if not self._config_values:
            raise RuntimeError(
                "Config file has not been loaded. Call load_config_file() first."
            )

        if key in self._config_values:
            return self._config_values[key]

        aliases = {
            "receipt_global_no": "ReceiptGlobalNo",
            "receipt_counter": "ReceiptCounter",
            "previous_receipt_hash": "PreviousReceiptHash",
            "device_id": "DeviceID",
            "device_edf_no": "DeviceEDFNo",
            "fiscal_day": "FiscalDayNo",
            "tax_percent": "TaxPercent",
            "tax_5": "Tax5",
            "tax_15": "Tax15",
            "tax_0": "Tax0",
            "tax_e": "TaxE",
            "verification_server": "VerificationServer",
            "zimra_server": "ZimraServer",
        }

        lookup_key = aliases.get(key, key)
        normalized_lookup = lookup_key.replace("_", "").lower()

        for config_key, config_value in self._config_values.items():
            if config_key.replace("_", "").lower() == normalized_lookup:
                return config_value

        return None

    #=========GET PRIVATE KEY PATH=========
    def get_private_key_path(self):
        if not self.config_file_path:
            raise RuntimeError(
                "Config file has not been loaded. Call load_config_file() first."
            )
        return os.path.join(
            os.path.dirname(os.path.abspath(self.config_file_path)),
            "havano_cert",
            "key.key"
        )

    def add_or_update_tax_item(self,invoice_flag, taxes_item_list, tax_code, tax_percent, tax_id, sales_amount_with_tax, tax_amount, vat_type):
        existing_item = next((item for item in taxes_item_list if item.taxCode == tax_code), None)

        if existing_item:
            if invoice_flag == 1:
                existing_item.salesAmountWithTax = -(abs(existing_item.salesAmountWithTax) + sales_amount_with_tax)
                existing_item.taxAmount = -(abs(existing_item.taxAmount) + tax_amount)
            else:
                existing_item.salesAmountWithTax += sales_amount_with_tax
                existing_item.taxAmount += tax_amount
        else:
            if invoice_flag == 1:
                if vat_type == "EXEMPT":
                    new_item = ReceiptTax(
                        taxCode=tax_code,
                        taxID=tax_id,
                        taxPercent=None,
                        salesAmountWithTax=-sales_amount_with_tax,
                        taxAmount=-tax_amount
                    )
                else:
                    new_item = ReceiptTax(
                        taxCode=tax_code,
                        taxPercent=tax_percent,
                        taxID=tax_id,
                        salesAmountWithTax=-sales_amount_with_tax,
                        taxAmount=-tax_amount
                    )
            else:
                if vat_type == "EXEMPT":
                    new_item =  ReceiptTax(
                        taxCode=tax_code,
                        taxID=tax_id,
                        taxPercent=None,
                        salesAmountWithTax=sales_amount_with_tax,
                        taxAmount=tax_amount
                    )
                else:
                    new_item = ReceiptTax(
                        taxCode=tax_code,
                        taxPercent=tax_percent,
                        taxID=tax_id,
                        salesAmountWithTax=sales_amount_with_tax,
                        taxAmount=tax_amount
                    )
            taxes_item_list.append(new_item)
            
    def create_fiscal_day_json(self, fiscal_day_no, fiscal_day_opened):
        if fiscal_day_no == "0":
            fiscal_day_no = "1"
        else:
            fiscal_day_no = str(int(fiscal_day_no) + 1)
        data = {
            "fiscalDayNo": fiscal_day_no,
            "fiscalDayOpened": fiscal_day_opened
        }
        return json.dumps(data)

    #=======VALIDATE XML STRING==========
    def validate_xml_structure(self, xml_root: ET.Element) -> str:
        # Validate the root element
        if xml_root.tag != "ITEMS":
            return "Root element must be <ITEMS>."
        # Validate the presence of ITEM elements
        item_nodes = xml_root.findall("ITEM")
        if not item_nodes:
            return "At least one <ITEM> element is required."

        # Validate the presence of necessary child elements in each ITEM
        required_fields = ["ITEMCODE", "ITEMNAME", "HH", "QTY", "PRICE", "VATR", "VAT", "TOTAL"]
        for item in item_nodes:
            missing_fields = [field for field in required_fields if item.find(field) is None]
            if missing_fields:
                return "Each <ITEM> element must contain elements: ITEMCODE, ITEMNAME, QTY, PRICE, VATR, VAT, TOTAL."

        return ""  # Return empty string if no validation issues
    #=========CALCULATE TAX AMOUNT ============
    def calculate_tax_amount(self, price_including_tax: float, tax_percent: float) -> float:
        tax_rate = tax_percent / 100
        tax_amount = price_including_tax * tax_rate / (1 + tax_rate)
        return tax_amount

    
    def calculate_exclusive_tax_amount(self, price_without_tax: Decimal, tax_percent: Decimal) -> float:
        price = Decimal(str(price_without_tax))
        tax_rate = Decimal(str(tax_percent)) / Decimal('100')
        tax_amount = price * tax_rate
        rounded_amount = tax_amount.quantize(Decimal('0.0000'), rounding=ROUND_DOWN)
        return rounded_amount   

    def format_to_two_decimals(self, value):
        if value is None:
            return ""
        return f"{value:.2f}"

    def get_tax_percent_formatted(self, rt):
        if rt.taxPercent is None:
            return ""
        return f"{rt.taxPercent:.2f}"
    
    #======SEND OFFLINE INVOICE =========
    def send_offline_invoice(self, config_file_path, device_sn, AddCustomer, InvoiceFlag, Currency, InvoiceNumber,
                        CustomerName, TradeName, CustomerVATNumber, CustomerAddress,
                        CustomerTelephoneNumber, CustomerTIN, CustomerProvince,
                        CustomerStreet, CustomerHouseNo, CustomerCity, CustomerEmail,
                            InvoiceComment,OriginalInvoiceNo, GlobalInvoiceNo, ItemsXML,invoice_tax_type=None):
        self.load_config_file(config_file_path)
        start = time.time()
       
        valid_currencies = ["ZWG", "USD", "EUR", "GBP"]
        receipt_type = ""
        receipt_notes = None
        t1 = time.time()
        #is_connected = await is_internet_available()
        #print(f"Flag {InvoiceFlag}")
        
        if AddCustomer == "0":
            CustomerProvince = None
            CustomerStreet = None
            CustomerHouseNo = None
            CustomerCity = None
            CustomerEmail = ""
            CustomerTelephoneNumber = ""

        if Currency.upper() == "ZIG":
            Currency = "ZWG"

        try:
            ItemsXML = ItemsXML.replace("&", "and")
            xml_root = ET.fromstring(ItemsXML)
        except Exception as ex:
            return json.dumps({
                "Message": f"Invalid ItemXml format Reason: {str(ex)}",
                "Date": datetime.now().isoformat()
            }, indent=4)

        if Currency not in valid_currencies:
            return json.dumps({
                "Message": "Invalid Currency, Only ZWG, USD, EUR and GBP are allowed",
                "Date": datetime.now().isoformat()
            }, indent=4)

        validation_result = self.validate_xml_structure(xml_root)
        if validation_result:
            return validation_result

        zerononvatable = 0
        exemptnonvatable = 0

        #receipt_date = datetime.now().isoformat()
        fdate = datetime.now()
        receipt_date = fdate.strftime("%Y-%m-%dT%H:%M:%S")
        qr_date = datetime.now().strftime("%d%m%Y")

        item_list = []
        taxes_item_list = []
        
        lcount = 0
        sales_plus_tax = 0
        tax_amount = 0
        sales_tax = 0
        
        invo_tax_type = True
        if invoice_tax_type in (None, 1):
            invo_tax_type = True
        else:
            invo_tax_type = False
        global_receipt_no = int(self.get_config_value("receipt_global_no")) + 1
        receipt_counter = int(self.get_config_value("receipt_counter")) + 1
        t2 = time.time()
        buyer_data = None
        if AddCustomer != "0":
            buyer_data = BuyerData(
                buyerRegisterName=CustomerName,
                buyerTradeName=TradeName,
                vatNumber=CustomerVATNumber,
                buyerTIN=CustomerTIN,
                buyerContacts=BuyerContacts(phoneNo=CustomerTelephoneNumber, email=CustomerEmail),
                buyerAddress=BuyerAddress(
                    province=CustomerProvince,
                    street=CustomerStreet,
                    houseNo=CustomerHouseNo,
                    city=CustomerCity
                )
            )
            buyer_data = asdict(buyer_data)

        for item_node in xml_root.findall("ITEM"):
            item_code = item_node.find("ITEMCODE").text
            item_name = item_node.find("ITEMNAME").text
            qty = Decimal(str(item_node.find("QTY").text))
            price = Decimal(str(item_node.find("PRICE").text))
            #tax_per: float = float(item_node.find("VATR").text)
            tax_per: Decimal = Decimal(item_node.find("VATR").text)
            if tax_per == Decimal("0.16"):
                 tax_per = Decimal("0.155")
           
            vat_rate = (tax_per * 100).quantize(Decimal("0.00"))
            #vat_rate = round(tax_per * 100, 2)
            
            total = Decimal(str(item_node.find("TOTAL").text))
            
            vat=0
            vtype = item_node.find("VNAME").text.strip()
            if invoice_tax_type is None or invoice_tax_type == 1:
                vat = self.calculate_tax_amount(total, vat_rate) 
            else:
                vat = self.calculate_exclusive_tax_amount(total, vat_rate)
                decimal_vat = Decimal(str(vat)) 
                total=total + vat  
                #print(vat)
                #print(total)
                
            lcount += 1
            sales_plus_tax += total
            if vat != 0:
                tax_amount += vat
                sales_tax += total

            tcode = "A"
            tax_percent = 0.0
            if vtype == "VAT":
                tid = int(self.get_config_value("tax_15"))
                tcode = "C"
                tax_percent = round(float(self.get_config_value("tax_percent") or 0),2)
                #tax_percent = "{:.2f}".format(float(self.get_config_value("tax_percent")))
            elif vtype == "EXEMPT":
                tid = int(self.get_config_value("tax_e"))
                exemptnonvatable +=total
            elif vtype == "ZERO RATED":
                tid = int(self.get_config_value("tax_0"))
                tcode = "B"
                zerononvatable += total

            self.add_or_update_tax_item(InvoiceFlag, taxes_item_list, tcode, tax_percent, tid, total, vat, vtype)
            if invoice_tax_type is None or invoice_tax_type == 1:
                total=total
            else:
                total=total-vat
                total = round(total,2)

            receipt_item = ReceiptLine(
                receiptLineType="Sale",
                receiptLineNo=lcount,
                receiptLineHSCode=item_code,
                receiptLineName=item_name,
                receiptLineQuantity=qty,
                receiptLinePrice=-price if InvoiceFlag == 1 else price,
                taxID=tid,
                taxCode=tcode,
                taxPercent=vat_rate if vtype != "EXEMPT" else None,
                receiptLineTotal=-total if InvoiceFlag == 1 else total
            )
            item_list.append(receipt_item)
        t3 = time.time()
        ROUND_2 = Decimal("0.00")
        for tax in taxes_item_list:
            #tax.taxAmount = round(tax.taxAmount, 2)    
            decimal_taxmnt = Decimal(str(tax.taxAmount))
            tax.taxAmount = float(decimal_taxmnt.quantize(ROUND_2, rounding=ROUND_HALF_UP))
            
            decimal_sawtax = Decimal(str(tax.salesAmountWithTax))
            tax.salesAmountWithTax = float(decimal_sawtax.quantize(ROUND_2, rounding=ROUND_HALF_UP))
               
            #tax.salesAmountWithTax = round(tax.salesAmountWithTax, 2)
            #print(tax.taxAmount)
        t4 = time.time()
       
        #sales_plus_tax = round(sales_plus_tax, 2)
        decimal_spt = Decimal(str(sales_plus_tax))
        sales_plus_tax = float(decimal_spt.quantize(ROUND_2, rounding=ROUND_HALF_UP))
             
        print(sales_plus_tax)
        credit_note = None

        if InvoiceFlag == 1:
            receipt_notes = OriginalInvoiceNo
            receipt_type = "CREDITNOTE"
            credit_note = asdict(CreditDebitNote(
                receiptID=None,
                deviceID=self.get_config_value("device_id"),
                receiptGlobalNo=int(GlobalInvoiceNo),
                fiscalDayNo=int(self.get_config_value("fiscal_day"))
            ))
            sales_plus_tax = -sales_plus_tax
        else:
            receipt_type = "FISCALINVOICE"
        v_tid = int(self.get_config_value("tax_15"))
        zero_tid = int(self.get_config_value("tax_0"))
        
        prev_receipt_hash = self.get_config_value("previous_receipt_hash")
        filtered_taxes = sorted(
            [item for item in taxes_item_list if str(item.taxID) in ["1", "2", "3",str(zero_tid),str(v_tid)]],
            key=lambda x: str(x.taxID)
        )
        
        receipt_taxes_str= ""
        
        for rt in filtered_taxes:
            tax_code = rt.taxCode
            tax_percent = self.get_tax_percent_formatted(rt)
            stax_amount = float(rt.taxAmount) * 100
            stax_amount = round(stax_amount)
            #stax_amount = round(stax_amount)
            #sales_with_tax = int(rt.salesAmountWithTax * 100)
            sales_with_tax = int(round(rt.salesAmountWithTax * 100))
            receipt_taxes_str += f"{tax_code}{tax_percent}{stax_amount}{sales_with_tax}"
        
        #print(receipt_taxes_str)
        # return ""
        concat_receipt_data = Signature.concatenate_data(
            str(int(self.get_config_value("device_id"))),
            receipt_type,
            Currency,
            str(global_receipt_no),
            receipt_date,
            int(round(sales_plus_tax * 100)),
            receipt_taxes_str,
            prev_receipt_hash
        )
        #print(concat_receipt_data)
       
        receipt_hash = Signature.compute_hash(concat_receipt_data)
        receipt_signature = Signature.sign_data(concat_receipt_data, self.get_private_key_path())
        qr_code = ReceiptQRCodes.generate_qr_code(
            self.get_config_value("verification_server"),
            self.get_config_value("device_id"),
            qr_date,
            str(global_receipt_no),
            receipt_signature
        )
        verification_code = ReceiptQRCodes.generate_verification_code(receipt_signature)
        t5 = time.time()
        receipt_obj = receiptWrapper(receipt={
            "receiptType": receipt_type,
            "receiptCurrency": Currency,
            "receiptCounter": receipt_counter,
            "receiptGlobalNo": global_receipt_no,
            "invoiceNo": InvoiceNumber,
            "buyerData": buyer_data,
            "receiptNotes": receipt_notes,
            "receiptDate": receipt_date,
            "creditDebitNote": credit_note,
            "receiptLinesTaxInclusive":invo_tax_type,
            "receiptLines": [asdict(item) for item in item_list],
            "receiptTaxes": [asdict(tax) for tax in taxes_item_list],
            "receiptPayments": [{"moneyTypeCode": "Cash", "paymentAmount": sales_plus_tax}],
            "receiptTotal": sales_plus_tax,
            "receiptPrintForm": "InvoiceA4",
            "receiptDeviceSignature": {
                "hash": receipt_hash,
                "signature": receipt_signature
            }
        })

        json_string = json.dumps(receipt_obj.__dict__, indent=4, default=str)
        t6 = time.time()
        
        edf_serial = self.get_config_value("device_edf_no")

        response_data = {
            "Message": "Invoice Successfully Sent to Zimra",
            "QRcode": qr_code,
            "VerificationCode": verification_code,
            "DeviceID": self.get_config_value("device_id"),
            "FiscalDay": self.get_config_value("fiscal_day"),
            "receiptType": receipt_type,
            "receiptCurrency": Currency,
            "receiptCounter": receipt_counter,
            "receiptGlobalNo": global_receipt_no,
            "EFDSERIAL": edf_serial
        }
        t6 = time.time() 
        return response_data
    