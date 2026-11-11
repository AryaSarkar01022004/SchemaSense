-- =====================================================================
-- SchemaSense Target Customer Database Demo (PostgreSQL)
-- Creates an E-Commerce & SaaS database with full relational schema,
-- mock data, and a locked-down dedicated read-only role.
-- =====================================================================

-- 1. Create Dedicated Read-Only DB Role (Section 5.4 Defense-in-depth)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'schemasense_readonly') THEN
        CREATE ROLE schemasense_readonly WITH LOGIN PASSWORD 'readonly_secret';
    END IF;
END
$$;

-- Restrict permissions: strictly SELECT only
GRANT CONNECT ON DATABASE postgres TO schemasense_readonly;
GRANT USAGE ON SCHEMA public TO schemasense_readonly;

-- 2. Drop existing sample tables if re-initializing
DROP TABLE IF EXISTS product_reviews CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS subscriptions CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

-- 3. Customers Table
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    phone VARCHAR(30),
    country VARCHAR(60) NOT NULL DEFAULT 'USA',
    city VARCHAR(80),
    customer_tier VARCHAR(20) NOT NULL DEFAULT 'standard' CHECK (customer_tier IN ('standard', 'silver', 'gold', 'vip')),
    signup_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Categories Table
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(60) UNIQUE NOT NULL,
    slug VARCHAR(60) UNIQUE NOT NULL,
    description TEXT
);

-- 5. Products Table
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    category_id INT REFERENCES categories(id) ON DELETE SET NULL,
    sku VARCHAR(40) UNIQUE NOT NULL,
    name VARCHAR(150) NOT NULL,
    description TEXT,
    price NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    cost_price NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    stock_quantity INT NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. Orders Table
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_id INT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    order_number VARCHAR(40) UNIQUE NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'paid', 'shipped', 'delivered', 'refunded', 'cancelled')),
    total_amount NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (total_amount >= 0),
    tax_amount NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    shipping_fee NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    shipping_country VARCHAR(60),
    ordered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    shipped_at TIMESTAMPTZ
);

-- 7. Order Items Table
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INT NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0),
    line_total NUMERIC(10, 2) GENERATED ALWAYS AS (quantity * unit_price) STORED
);

-- 8. SaaS Subscriptions Table
CREATE TABLE subscriptions (
    id SERIAL PRIMARY KEY,
    customer_id INT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    plan_name VARCHAR(50) NOT NULL CHECK (plan_name IN ('Starter', 'Growth', 'Scale', 'Enterprise')),
    monthly_mrr NUMERIC(10, 2) NOT NULL,
    billing_interval VARCHAR(20) NOT NULL DEFAULT 'monthly' CHECK (billing_interval IN ('monthly', 'annual')),
    status VARCHAR(20) NOT NULL CHECK (status IN ('active', 'past_due', 'canceled', 'trialing')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cancelled_at TIMESTAMPTZ
);

-- 9. Product Reviews Table
CREATE TABLE product_reviews (
    id SERIAL PRIMARY KEY,
    product_id INT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    customer_id INT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    rating INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review_title VARCHAR(120),
    review_text TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Grant Read-Only Select permissions to our sandbox role
GRANT SELECT ON ALL TABLES IN SCHEMA public TO schemasense_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO schemasense_readonly;

-- =====================================================================
-- Realistic Seed Data
-- =====================================================================

-- Categories
INSERT INTO categories (name, slug, description) VALUES
('Cloud Software', 'cloud-software', 'SaaS subscriptions and API licenses'),
('Developer Hardware', 'hardware', 'High-performance engineering workstations and servers'),
('Network Security', 'security', 'Firewalls, VPN hardware, and security gateways'),
('Storage & Backup', 'storage', 'SAN appliances and encrypted backup drives');

-- Customers
INSERT INTO customers (name, email, phone, country, city, customer_tier, signup_date) VALUES
('Alice Johnson', 'alice.johnson@techcorp.com', '+1-555-0101', 'USA', 'San Francisco', 'vip', '2025-01-15'),
('Bob Smith', 'bob.smith@cloudscale.io', '+1-555-0102', 'USA', 'New York', 'gold', '2025-02-10'),
('Carlos Mendoza', 'carlos.m@globalnet.es', '+34-91-555-0103', 'Spain', 'Madrid', 'silver', '2025-03-01'),
('Diana Prince', 'diana.p@themyscira.org', '+1-555-0104', 'Canada', 'Toronto', 'vip', '2025-03-22'),
('Emma Watson', 'emma.w@oxforddata.co.uk', '+44-20-7946-0105', 'United Kingdom', 'London', 'gold', '2025-04-05'),
('Franz Wagner', 'franz.w@berlinauto.de', '+49-30-555-0106', 'Germany', 'Berlin', 'standard', '2025-05-18'),
('Grace Hopper', 'grace.h@compilers.org', '+1-555-0107', 'USA', 'Boston', 'vip', '2025-06-12'),
('Hidenori Sato', 'hidenori.s@tokyotech.jp', '+81-3-5555-0108', 'Japan', 'Tokyo', 'gold', '2025-07-20'),
('Isabelle Moreau', 'isabelle.m@lyonbio.fr', '+33-4-55-50-109', 'France', 'Lyon', 'silver', '2025-08-14'),
('Jack Miller', 'jack.m@sydneydata.com.au', '+61-2-5550-0110', 'Australia', 'Sydney', 'standard', '2025-09-02');

-- Products
INSERT INTO products (category_id, sku, name, description, price, cost_price, stock_quantity) VALUES
(1, 'SW-ANALYTICS-PRO', 'Cloud Analytics Pro (Seat)', 'Annual AI analytics explorer seat', 599.00, 120.00, 500),
(1, 'SW-GATEWAY-LIC', 'API Gateway Enterprise License', 'Unlimited requests per second gateway license', 1499.00, 300.00, 200),
(2, 'HW-DEV-STATION', 'Titan Dev Workstation 128GB', 'High-end developer machine with liquid cooling', 3499.00, 2100.00, 25),
(3, 'SEC-FIREWALL-X1', 'CyberShield Hardware Firewall X1', '10Gbps line-rate packet filter appliance', 1899.00, 950.00, 40),
(4, 'ST-NVME-ARRAY', '8TB Enterprise NVMe SAN Array', 'Ultra-low latency dual-controller storage', 2499.00, 1400.00, 15),
(1, 'SW-MONITOR-CORE', 'App Performance Monitor (Core)', 'Real-time telemetry and APM monitoring', 249.00, 45.00, 1000);

-- Orders
INSERT INTO orders (customer_id, order_number, status, total_amount, tax_amount, shipping_fee, shipping_country, ordered_at) VALUES
(1, 'ORD-2026-001', 'paid', 4098.00, 320.00, 0.00, 'USA', NOW() - INTERVAL '45 days'),
(2, 'ORD-2026-002', 'paid', 1499.00, 120.00, 0.00, 'USA', NOW() - INTERVAL '38 days'),
(3, 'ORD-2026-003', 'shipped', 2499.00, 210.00, 50.00, 'Spain', NOW() - INTERVAL '30 days'),
(4, 'ORD-2026-004', 'delivered', 5398.00, 450.00, 0.00, 'Canada', NOW() - INTERVAL '25 days'),
(5, 'ORD-2026-005', 'paid', 1899.00, 160.00, 45.00, 'United Kingdom', NOW() - INTERVAL '20 days'),
(6, 'ORD-2026-006', 'pending', 599.00, 50.00, 0.00, 'Germany', NOW() - INTERVAL '14 days'),
(7, 'ORD-2026-007', 'paid', 7497.00, 600.00, 0.00, 'USA', NOW() - INTERVAL '10 days'),
(8, 'ORD-2026-008', 'delivered', 3499.00, 300.00, 100.00, 'Japan', NOW() - INTERVAL '6 days'),
(1, 'ORD-2026-009', 'paid', 1198.00, 95.00, 0.00, 'USA', NOW() - INTERVAL '3 days'),
(9, 'ORD-2026-010', 'refunded', 249.00, 20.00, 0.00, 'France', NOW() - INTERVAL '1 day');

-- Order Items
INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
(1, 1, 1, 599.00),
(1, 3, 1, 3499.00),
(2, 2, 1, 1499.00),
(3, 5, 1, 2499.00),
(4, 3, 1, 3499.00),
(4, 4, 1, 1899.00),
(5, 4, 1, 1899.00),
(6, 1, 1, 599.00),
(7, 2, 5, 1499.00),
(8, 3, 1, 3499.00),
(9, 1, 2, 599.00),
(10, 6, 1, 249.00);

-- SaaS Subscriptions
INSERT INTO subscriptions (customer_id, plan_name, monthly_mrr, billing_interval, status, started_at) VALUES
(1, 'Enterprise', 1499.00, 'annual', 'active', NOW() - INTERVAL '180 days'),
(2, 'Growth', 499.00, 'monthly', 'active', NOW() - INTERVAL '90 days'),
(3, 'Starter', 199.00, 'monthly', 'active', NOW() - INTERVAL '60 days'),
(4, 'Enterprise', 1999.00, 'annual', 'active', NOW() - INTERVAL '120 days'),
(5, 'Scale', 899.00, 'monthly', 'active', NOW() - INTERVAL '45 days'),
(7, 'Enterprise', 2499.00, 'annual', 'active', NOW() - INTERVAL '210 days'),
(8, 'Growth', 499.00, 'monthly', 'active', NOW() - INTERVAL '30 days');

-- Product Reviews
INSERT INTO product_reviews (product_id, customer_id, rating, review_title, review_text) VALUES
(1, 1, 5, 'Indispensable tool', 'Transformed our data exploration and queries.'),
(3, 1, 5, 'Blazing fast workstation', 'Compiles our entire monorepo in seconds.'),
(2, 2, 4, 'Reliable API Gateway', 'Handled 50M requests last month without breaking a sweat.'),
(4, 5, 5, 'Outstanding hardware security', 'Easy to configure and zero packet drops.');

ANALYZE;

