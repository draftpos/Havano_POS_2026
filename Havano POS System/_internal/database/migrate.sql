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
    
    balance DECIMAL(18, 4) DEFAULT 0.0,
    outstanding_amount DECIMAL(18, 4) DEFAULT 0.0,
    loyalty_points INT DEFAULT 0,

    FOREIGN KEY (customer_group_id) REFERENCES customer_groups(id),
    FOREIGN KEY (custom_warehouse_id) REFERENCES warehouses(id),
    FOREIGN KEY (custom_cost_center_id) REFERENCES cost_centers(id),
    FOREIGN KEY (default_price_list_id) REFERENCES price_lists(id)
);

-- Seed lookup data so names match the API exactly
INSERT INTO warehouses (name) SELECT 'Stores - AT' WHERE NOT EXISTS (SELECT 1 FROM warehouses WHERE name = 'Stores - AT');
INSERT INTO cost_centers (name) SELECT 'Main - AT' WHERE NOT EXISTS (SELECT 1 FROM cost_centers WHERE name = 'Main - AT');