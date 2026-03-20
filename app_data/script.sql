/******************************************************
    Havano POS - SAFE Database Creation Script
******************************************************/

-- =============================================
-- CREATE DATABASE IF NOT EXISTS
-- =============================================
DECLARE @DB_NAME NVARCHAR(128) = '{{DB_NAME}}';

-- Create database in master
USE master;

IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = @DB_NAME)
BEGIN
    DECLARE @CreateDB NVARCHAR(MAX) = 'CREATE DATABASE [' + @DB_NAME + ']';
    EXEC sp_executesql @CreateDB;
END

-- =============================================
-- CREATE ALL TABLES IN TARGET DATABASE
-- =============================================
DECLARE @CreateTablesSQL NVARCHAR(MAX) = '
IF OBJECT_ID(''dbo.companies'', ''U'') IS NULL
BEGIN
CREATE TABLE dbo.companies(
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(120) NOT NULL UNIQUE,
    abbreviation NVARCHAR(40) NOT NULL,
    default_currency NVARCHAR(10) NOT NULL DEFAULT ''USD'',
    country NVARCHAR(80) NOT NULL
);
PRINT ''Table [companies] created.'';
END

IF OBJECT_ID(''dbo.company_defaults'', ''U'') IS NULL
BEGIN
CREATE TABLE dbo.company_defaults(
    id INT IDENTITY(1,1) PRIMARY KEY,
    company_name NVARCHAR(255) DEFAULT '''',
    address_1 NVARCHAR(255) DEFAULT '''',
    address_2 NVARCHAR(255) DEFAULT '''',
    email NVARCHAR(100) DEFAULT '''',
    phone NVARCHAR(50) DEFAULT '''',
    vat_number NVARCHAR(50) DEFAULT '''',
    tin_number NVARCHAR(50) DEFAULT '''',
    footer_text NVARCHAR(MAX) DEFAULT '''',
    updated_at DATETIME DEFAULT GETDATE()
);
PRINT ''Table [company_defaults] created.'';
END

IF OBJECT_ID(''dbo.cost_centers'', ''U'') IS NULL
BEGIN
CREATE TABLE dbo.cost_centers(
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(120) NOT NULL,
    company_id INT NOT NULL
);
PRINT ''Table [cost_centers] created.'';
END

IF OBJECT_ID(''dbo.customer_groups'', ''U'') IS NULL
BEGIN
CREATE TABLE dbo.customer_groups(
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(120) NOT NULL UNIQUE,
    parent_group_id INT NULL
);
PRINT ''Table [customer_groups] created.'';
END

IF OBJECT_ID(''dbo.price_lists'', ''U'') IS NULL
BEGIN
CREATE TABLE dbo.price_lists(
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(120) NOT NULL UNIQUE,
    selling BIT DEFAULT 1
);
PRINT ''Table [price_lists] created.'';
END

IF OBJECT_ID(''dbo.warehouses'', ''U'') IS NULL
BEGIN
CREATE TABLE dbo.warehouses(
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(120) NOT NULL,
    company_id INT NOT NULL
);
PRINT ''Table [warehouses] created.'';
END

IF OBJECT_ID(''dbo.customers'', ''U'') IS NULL
BEGIN
CREATE TABLE dbo.customers(
    id INT IDENTITY(1,1) PRIMARY KEY,
    customer_name NVARCHAR(120) NOT NULL,
    customer_group_id INT NOT NULL,
    custom_warehouse_id INT NOT NULL,
    custom_cost_center_id INT NOT NULL,
    default_price_list_id INT NOT NULL
);
PRINT ''Table [customers] created.'';
END

IF OBJECT_ID(''dbo.products'', ''U'') IS NULL
BEGIN
CREATE TABLE dbo.products(
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(120) NOT NULL,
    price DECIMAL(12,2) DEFAULT 0,
    stock INT DEFAULT 0
);
PRINT ''Table [products] created.'';
END

IF OBJECT_ID(''dbo.sales'', ''U'') IS NULL
BEGIN
CREATE TABLE dbo.sales(
    id INT IDENTITY(1,1) PRIMARY KEY,
    total DECIMAL(12,2) DEFAULT 0,
    created_at DATETIME2 DEFAULT SYSDATETIME()
);
PRINT ''Table [sales] created.'';
END

IF OBJECT_ID(''dbo.sale_items'', ''U'') IS NULL
BEGIN
CREATE TABLE dbo.sale_items(
    id INT IDENTITY(1,1) PRIMARY KEY,
    sale_id INT NOT NULL,
    product_name NVARCHAR(120),
    qty DECIMAL(12,4),
    total DECIMAL(12,2)
);
PRINT ''Table [sale_items] created.'';
END

IF OBJECT_ID(''dbo.shifts'', ''U'') IS NULL
BEGIN
CREATE TABLE dbo.shifts(
    id INT IDENTITY(1,1) PRIMARY KEY,
    shift_number INT DEFAULT 1,
    created_at DATETIME2 DEFAULT SYSDATETIME()
);
PRINT ''Table [shifts] created.'';
END

IF OBJECT_ID(''dbo.shift_rows'', ''U'') IS NULL
BEGIN
CREATE TABLE dbo.shift_rows(
    id INT IDENTITY(1,1) PRIMARY KEY,
    shift_id INT NOT NULL,
    income DECIMAL(12,2) DEFAULT 0
);
PRINT ''Table [shift_rows] created.'';
END

IF OBJECT_ID(''dbo.users'', ''U'') IS NULL
BEGIN
CREATE TABLE dbo.users(
    id INT IDENTITY(1,1) PRIMARY KEY,
    username NVARCHAR(80) UNIQUE,
    password NVARCHAR(255),
    role NVARCHAR(20) DEFAULT ''cashier''
);
PRINT ''Table [users] created.'';
END

IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = ''FK_cost_centers_companies'')
ALTER TABLE dbo.cost_centers
ADD CONSTRAINT FK_cost_centers_companies
FOREIGN KEY (company_id) REFERENCES dbo.companies(id);

IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = ''FK_customers_customer_groups'')
ALTER TABLE dbo.customers
ADD CONSTRAINT FK_customers_customer_groups
FOREIGN KEY (customer_group_id) REFERENCES dbo.customer_groups(id);

IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = ''FK_customers_warehouses'')
ALTER TABLE dbo.customers
ADD CONSTRAINT FK_customers_warehouses
FOREIGN KEY (custom_warehouse_id) REFERENCES dbo.warehouses(id);

IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = ''FK_customers_cost_centers'')
ALTER TABLE dbo.customers
ADD CONSTRAINT FK_customers_cost_centers
FOREIGN KEY (custom_cost_center_id) REFERENCES dbo.cost_centers(id);

IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = ''FK_customers_price_lists'')
ALTER TABLE dbo.customers
ADD CONSTRAINT FK_customers_price_lists
FOREIGN KEY (default_price_list_id) REFERENCES dbo.price_lists(id);

IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = ''FK_sale_items_sales'')
ALTER TABLE dbo.sale_items
ADD CONSTRAINT FK_sale_items_sales
FOREIGN KEY (sale_id) REFERENCES dbo.sales(id)
ON DELETE CASCADE;

IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = ''FK_shift_rows_shifts'')
ALTER TABLE dbo.shift_rows
ADD CONSTRAINT FK_shift_rows_shifts
FOREIGN KEY (shift_id) REFERENCES dbo.shifts(id)
ON DELETE CASCADE;

IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = ''FK_warehouses_companies'')
ALTER TABLE dbo.warehouses
ADD CONSTRAINT FK_warehouses_companies
FOREIGN KEY (company_id) REFERENCES dbo.companies(id);

PRINT ''✅ ALL TABLES & CONSTRAINTS CREATED SUCCESSFULLY'';
';

-- Execute with database context parameter
EXEC sp_executesql @CreateTablesSQL, N'@DBName NVARCHAR(128)', @DB_NAME;