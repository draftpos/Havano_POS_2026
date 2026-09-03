-- Create Lookup Tables for Foreign Key dependencies
CREATE TABLE IF NOT EXISTS customer_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name NVARCHAR(255) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS warehouses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name NVARCHAR(255) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS cost_centers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name NVARCHAR(255) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS price_lists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name NVARCHAR(255) UNIQUE NOT NULL
);

-- Create/Update the Customers Table
-- Using NVARCHAR for SQL Server compatibility as seen in your db.py
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='customers' AND xtype='U')
CREATE TABLE customers (
    id INT IDENTITY(1,1) PRIMARY KEY,
    customer_name NVARCHAR(255) UNIQUE NOT NULL,
    customer_type NVARCHAR(50) DEFAULT 'Individual',
    customer_group_id INT,
    
    custom_trade_name NVARCHAR(255),
    custom_telephone_number NVARCHAR(50),
    custom_email_address NVARCHAR(255),
    custom_city NVARCHAR(100),
    custom_house_no NVARCHAR(50),
    
    custom_warehouse_id INT,
    custom_cost_center_id INT,
    default_price_list_id INT,
    
    custom_customer_tin NVARCHAR(100),
    custom_customer_vat NVARCHAR(100),
    
    balance DECIMAL(18, 4) DEFAULT 0.0,
    outstanding_amount DECIMAL(18, 4) DEFAULT 0.0,
    loyalty_points INT DEFAULT 0,

    FOREIGN KEY (customer_group_id) REFERENCES customer_groups(id),
    FOREIGN KEY (custom_warehouse_id) REFERENCES warehouses(id),
    FOREIGN KEY (custom_cost_center_id) REFERENCES cost_centers(id),
    FOREIGN KEY (default_price_list_id) REFERENCES price_lists(id)
);

-- Ensure products table has cost_price and track_stock
IF EXISTS (SELECT * FROM sysobjects WHERE name='products' AND xtype='U')
BEGIN
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE Name = N'cost_price' AND Object_ID = Object_ID(N'products'))
    BEGIN
        ALTER TABLE products ADD cost_price DECIMAL(18,2) DEFAULT 0.0;
    END

    IF NOT EXISTS (SELECT * FROM sys.columns WHERE Name = N'track_stock' AND Object_ID = Object_ID(N'products'))
    BEGIN
        ALTER TABLE products ADD track_stock BIT NOT NULL DEFAULT 1;
    END
END

-- Ensure sale_items table has cost_price
IF EXISTS (SELECT * FROM sysobjects WHERE name='sale_items' AND xtype='U')
BEGIN
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE Name = N'cost_price' AND Object_ID = Object_ID(N'sale_items'))
    BEGIN
        ALTER TABLE sale_items ADD cost_price DECIMAL(18,2) DEFAULT 0.0;
    END
END

-- Ensure company_defaults table has support_number and agent_number
IF EXISTS (SELECT * FROM sysobjects WHERE name='company_defaults' AND xtype='U')
BEGIN
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE Name = N'support_number' AND Object_ID = Object_ID(N'company_defaults'))
    BEGIN
        ALTER TABLE company_defaults ADD support_number NVARCHAR(255) DEFAULT '+263 773 351 6588';
    END

    IF NOT EXISTS (SELECT * FROM sys.columns WHERE Name = N'agent_number' AND Object_ID = Object_ID(N'company_defaults'))
    BEGIN
        ALTER TABLE company_defaults ADD agent_number NVARCHAR(255) DEFAULT 'Agent';
    END
END

-- Seed lookup data so names match the API exactly
INSERT INTO warehouses (name) SELECT 'Stores - AT' WHERE NOT EXISTS (SELECT 1 FROM warehouses WHERE name = 'Stores - AT');
INSERT INTO cost_centers (name) SELECT 'Main - AT' WHERE NOT EXISTS (SELECT 1 FROM cost_centers WHERE name = 'Main - AT');