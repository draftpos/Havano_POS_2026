#!/usr/bin/env python
"""
Standalone script to create/update the default walk-in customer.
Run this separately to test and verify default customer creation.

Usage:
    python setup_default_customer.py
    python setup_default_customer.py --force  (force recreate even if exists)
    python setup_default_customer.py --sync   (sync with Frappe after creation)
"""

import sys
import os
import argparse
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def print_header():
    """Print formatted header"""
    print("\n" + "="*60)
    print("  DEFAULT CUSTOMER SETUP")
    print("="*60)
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")

def print_section(title):
    """Print section header"""
    print(f"\n  ┌─ {title}")
    print(f"  │")

def print_info(msg, indent=2):
    """Print info message"""
    print(f"{' ' * indent}ℹ️  {msg}")

def print_success(msg, indent=2):
    """Print success message"""
    print(f"{' ' * indent}✅ {msg}")

def print_error(msg, indent=2):
    """Print error message"""
    print(f"{' ' * indent}❌ {msg}")

def print_warning(msg, indent=2):
    """Print warning message"""
    print(f"{' ' * indent}⚠️  {msg}")

def print_data(key, value, indent=2):
    """Print key-value pair"""
    print(f"{' ' * indent}📌 {key}: {value}")

def main():
    parser = argparse.ArgumentParser(description='Setup default walk-in customer')
    parser.add_argument('--force', action='store_true', 
                       help='Force recreate default customer even if exists')
    parser.add_argument('--sync', action='store_true',
                       help='Sync with Frappe after creation')
    args = parser.parse_args()
    
    print_header()
    
    try:
        from database.db import get_connection
        print_section("1. Database Connection")
        conn = get_connection()
        print_success("Database connected successfully")
    except Exception as e:
        print_error(f"Failed to connect to database: {e}")
        return 1
    
    try:
        cursor = conn.cursor()
        
        # ============================================================
        # Step 1: Check Company Defaults
        # ============================================================
        print_section("2. Checking Company Defaults")
        
        cursor.execute("""
            SELECT TOP 1 
                [server_warehouse], 
                [server_cost_center],
                [server_walk_in_customer],
                [server_company],
                [server_company_currency],
                [company_name],
                [email],
                [phone]
            FROM [dbo].[company_defaults]
        """)
        
        company_default = cursor.fetchone()
        
        if not company_default:
            print_error("No company defaults found in database!")
            print_info("Please run setup_database.py first", indent=4)
            return 1
        
        print_success("Company defaults retrieved")
        print_data("Company Name", company_default[5] or "(not set)")
        print_data("Server Company", company_default[3] or "(not set)")
        print_data("Currency", company_default[4] or "USD")
        print_data("Email", company_default[6] or "(not set)")
        print_data("Phone", company_default[7] or "(not set)")
        print_data("Configured Warehouse", company_default[0] or "(not set)")
        print_data("Configured Cost Center", company_default[1] or "(not set)")
        print_data("Custom Customer Name", company_default[2] or "(not set)")
        
        # ============================================================
        # Step 2: Determine Default Customer Settings
        # ============================================================
        print_section("3. Determining Default Customer Settings")
        
        # Customer name from company defaults or default
        default_customer_name = "Walk-in Customer"
        if company_default[2] and company_default[2] != 'default':
            default_customer_name = company_default[2]
            print_info(f"Using custom customer name from company defaults: '{default_customer_name}'")
        else:
            print_info(f"Using default customer name: '{default_customer_name}'")
        
        # Find warehouse ID
        warehouse_id = None
        warehouse_name = None
        if company_default[0]:
            warehouse_name = company_default[0]
            print_info(f"Looking for warehouse: '{warehouse_name}'")
            
            # Try to find by name first
            cursor.execute("""
                SELECT TOP 1 id, name FROM [dbo].[warehouses] 
                WHERE name = ? OR CAST(id AS NVARCHAR) = ?
            """, (warehouse_name, warehouse_name))
            
            wh = cursor.fetchone()
            if wh:
                warehouse_id = wh[0]
                warehouse_name = wh[1]
                print_success(f"Found warehouse: {warehouse_name} (ID: {warehouse_id})")
            else:
                print_warning(f"Warehouse '{warehouse_name}' not found in warehouses table")
                print_info("Default customer will be created without warehouse link", indent=4)
        else:
            print_info("No warehouse configured in company defaults")
        
        # Find cost center ID
        cost_center_id = None
        cost_center_name = None
        if company_default[1]:
            cost_center_name = company_default[1]
            print_info(f"Looking for cost center: '{cost_center_name}'")
            
            cursor.execute("""
                SELECT TOP 1 id, name FROM [dbo].[cost_centers] 
                WHERE name = ? OR CAST(id AS NVARCHAR) = ?
            """, (cost_center_name, cost_center_name))
            
            cc = cursor.fetchone()
            if cc:
                cost_center_id = cc[0]
                cost_center_name = cc[1]
                print_success(f"Found cost center: {cost_center_name} (ID: {cost_center_id})")
            else:
                print_warning(f"Cost center '{cost_center_name}' not found in cost_centers table")
                print_info("Default customer will be created without cost center link", indent=4)
        else:
            print_info("No cost center configured in company defaults")
        
        # ============================================================
        # Step 3: Check Existing Default Customer
        # ============================================================
        print_section("4. Checking Existing Customers")
        
        # Count total customers
        cursor.execute("SELECT COUNT(*) FROM [dbo].[customers]")
        total_customers = cursor.fetchone()[0]
        print_data("Total customers in database", total_customers)
        
        # Find walk-in/individual customers
        cursor.execute("""
            SELECT 
                id, customer_name, customer_type,
                custom_warehouse_id, custom_cost_center_id,
                balance, outstanding_amount, laybye_balance,
                frappe_synced
            FROM [dbo].[customers] 
            WHERE customer_type = 'individual' 
               OR customer_name LIKE '%Walk-in%'
               OR customer_name = ?
            ORDER BY id ASC
        """, (default_customer_name,))
        
        existing_customers = cursor.fetchall()
        
        if existing_customers:
            print_info(f"Found {len(existing_customers)} potential default customer(s):")
            for cust in existing_customers:
                print(f"      • ID: {cust[0]}, Name: '{cust[1]}', Type: {cust[2]}")
                if cust[3]:
                    print(f"        Warehouse ID: {cust[3]}")
                if cust[4]:
                    print(f"        Cost Center ID: {cust[4]}")
        else:
            print_info("No existing walk-in/individual customers found")
        
        # ============================================================
        # Step 4: Create or Update Default Customer
        # ============================================================
        print_section("5. Creating/Updating Default Customer")
        
        if args.force:
            print_warning("Force mode enabled - will recreate default customer")
            # Delete existing individual customers
            cursor.execute("""
                DELETE FROM [dbo].[customers] 
                WHERE customer_type = 'individual' 
                   OR customer_name LIKE '%Walk-in%'
            """)
            print_info(f"Deleted {cursor.rowcount} existing individual customers")
            existing_customers = []  # Clear the list
        
        if not existing_customers or args.force:
            # Create new default customer
            print_info("Creating new default customer...")
            
            cursor.execute("""
                INSERT INTO [dbo].[customers] 
                    (customer_name, customer_type, 
                     custom_warehouse_id, custom_cost_center_id,
                     balance, outstanding_amount, laybye_balance, 
                     loyalty_points, frappe_synced)
                OUTPUT INSERTED.id, INSERTED.customer_name
                VALUES (?, 'individual', ?, ?, 0, 0, 0, 0, 0)
            """, (default_customer_name, warehouse_id, cost_center_id))
            
            result = cursor.fetchone()
            customer_id = result[0]
            customer_name = result[1]
            conn.commit()
            
            print_success(f"Default customer created successfully!")
            print_data("Customer ID", customer_id)
            print_data("Customer Name", customer_name)
            print_data("Customer Type", "individual")
            print_data("Warehouse ID", warehouse_id or "(not set)")
            print_data("Cost Center ID", cost_center_id or "(not set)")
            print_data("Balance", "0.00")
            print_data("Outstanding Amount", "0.00")
            print_data("Laybye Balance", "0.00")
            
            default_customer = {
                'id': customer_id,
                'name': customer_name,
                'warehouse_id': warehouse_id,
                'cost_center_id': cost_center_id
            }
        else:
            # Update existing default customer
            existing = existing_customers[0]
            customer_id = existing[0]
            needs_update = False
            
            print_info(f"Found existing default customer (ID: {customer_id})")
            
            # Check if needs update
            if existing[3] != warehouse_id:
                print_info(f"Warehouse needs update: {existing[3]} → {warehouse_id}")
                needs_update = True
            
            if existing[4] != cost_center_id:
                print_info(f"Cost center needs update: {existing[4]} → {cost_center_id}")
                needs_update = True
            
            if existing[1] != default_customer_name:
                print_info(f"Name needs update: '{existing[1]}' → '{default_customer_name}'")
                needs_update = True
            
            if needs_update:
                print_info("Updating default customer with current company defaults...")
                cursor.execute("""
                    UPDATE [dbo].[customers] 
                    SET customer_name = ?,
                        custom_warehouse_id = ?,
                        custom_cost_center_id = ?
                    WHERE id = ?
                """, (default_customer_name, warehouse_id, cost_center_id, customer_id))
                conn.commit()
                print_success(f"Default customer updated successfully!")
            else:
                print_success("Default customer is already up to date!")
            
            print_data("Customer ID", customer_id)
            print_data("Customer Name", existing[1] if not needs_update else default_customer_name)
            print_data("Customer Type", existing[2])
            print_data("Warehouse ID", existing[3] if not needs_update else warehouse_id)
            print_data("Cost Center ID", existing[4] if not needs_update else cost_center_id)
            print_data("Balance", f"{float(existing[5] or 0):.2f}")
            print_data("Outstanding", f"{float(existing[6] or 0):.2f}")
            print_data("Frappe Synced", "Yes" if existing[8] else "No")
            
            default_customer = {
                'id': customer_id,
                'name': existing[1] if not needs_update else default_customer_name,
                'warehouse_id': existing[3] if not needs_update else warehouse_id,
                'cost_center_id': existing[4] if not needs_update else cost_center_id
            }
        
        # ============================================================
        # Step 5: Verify Creation
        # ============================================================
        print_section("6. Verification")
        
        # Verify the customer exists and has correct data
        cursor.execute("""
            SELECT 
                id, customer_name, customer_type,
                custom_warehouse_id, custom_cost_center_id,
                balance, outstanding_amount, laybye_balance,
                frappe_synced
            FROM [dbo].[customers] 
            WHERE id = ?
        """, (default_customer['id'],))
        
        verify = cursor.fetchone()
        
        if verify:
            print_success("Customer verified in database")
            print_data("ID", verify[0])
            print_data("Name", verify[1])
            print_data("Type", verify[2])
            print_data("Warehouse ID", verify[3] or "NULL")
            print_data("Cost Center ID", verify[4] or "NULL")
            print_data("Balance", f"{float(verify[5] or 0):.2f}")
            print_data("Outstanding", f"{float(verify[6] or 0):.2f}")
            print_data("Laybye Balance", f"{float(verify[7] or 0):.2f}")
        else:
            print_error("Failed to verify customer creation!")
        
        # ============================================================
        # Step 6: Frappe Sync (Optional)
        # ============================================================
        if args.sync:
            print_section("7. Syncing with Frappe")
            try:
                from sync.frappe_sync import sync_customer_to_frappe
                print_info("Attempting to sync with Frappe...")
                result = sync_customer_to_frappe(default_customer)
                if result:
                    print_success("Customer synced with Frappe successfully!")
                    
                    # Update sync status
                    cursor.execute("""
                        UPDATE [dbo].[customers] 
                        SET frappe_synced = 1 
                        WHERE id = ?
                    """, (default_customer['id'],))
                    conn.commit()
                else:
                    print_warning("Frappe sync failed or not configured")
            except ImportError:
                print_warning("Frappe sync module not available")
            except Exception as e:
                print_error(f"Error during Frappe sync: {e}")
        
        # ============================================================
        # Summary
        # ============================================================
        print_section("SUMMARY")
        print_success("Default customer setup completed successfully!")
        print(f"\n  📋 Customer Details:")
        print(f"     • Name: {default_customer['name']}")
        print(f"     • ID: {default_customer['id']}")
        print(f"     • Type: individual")
        if default_customer['warehouse_id']:
            print(f"     • Warehouse ID: {default_customer['warehouse_id']}")
        if default_customer['cost_center_id']:
            print(f"     • Cost Center ID: {default_customer['cost_center_id']}")
        
        print("\n" + "="*60)
        print("  Setup Complete!")
        print("="*60 + "\n")
        
        conn.close()
        return 0
        
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return 1

if __name__ == "__main__":
    sys.exit(main())