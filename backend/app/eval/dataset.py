"""
Evaluation Dataset (Section 6 - Evaluation Plan).
Contains question and gold SQL pairs across e-commerce and SaaS metrics:
- Single-table queries
- Multi-table joins (orders + customers)
- Aggregations and GROUP BY
- Rankings and TOP-K
- Date filters and status filters
"""

EVAL_DATASET = [
    {
        "id": "eval-01",
        "category": "basic_list",
        "question": "Show all products with their price and stock",
        "gold_sql": "SELECT products.id, products.name, products.category, products.price, products.stock_quantity FROM products ORDER BY products.id ASC LIMIT 100",
    },
    {
        "id": "eval-02",
        "category": "aggregation",
        "question": "How many total orders are there?",
        "gold_sql": "SELECT COUNT(*) AS total_orders FROM orders LIMIT 100",
    },
    {
        "id": "eval-03",
        "category": "aggregation_sum",
        "question": "What is the total revenue from all orders?",
        "gold_sql": "SELECT SUM(orders.total_amount) AS total_revenue, COUNT(orders.id) AS total_orders FROM orders LIMIT 100",
    },
    {
        "id": "eval-04",
        "category": "filter",
        "question": "Show all pending orders",
        "gold_sql": "SELECT orders.id, orders.customer_id, orders.status, orders.total_amount, orders.created_at FROM orders WHERE orders.status = 'pending' ORDER BY orders.id ASC LIMIT 100",
    },
    {
        "id": "eval-05",
        "category": "filter",
        "question": "List all paid orders",
        "gold_sql": "SELECT orders.id, orders.customer_id, orders.status, orders.total_amount, orders.created_at FROM orders WHERE orders.status = 'paid' ORDER BY orders.id ASC LIMIT 100",
    },
    {
        "id": "eval-06",
        "category": "group_by",
        "question": "What is the total revenue by order status?",
        "gold_sql": "SELECT orders.status, SUM(orders.total_amount) AS revenue, COUNT(orders.id) AS order_count FROM orders GROUP BY orders.status ORDER BY revenue DESC LIMIT 100",
    },
    {
        "id": "eval-07",
        "category": "top_k",
        "question": "Show the top 5 highest value orders",
        "gold_sql": "SELECT orders.id, orders.customer_id, orders.total_amount, orders.created_at FROM orders ORDER BY orders.total_amount DESC LIMIT 5",
    },
    {
        "id": "eval-08",
        "category": "multi_join",
        "question": "Show total spending per customer with customer names",
        "gold_sql": "SELECT customers.name, COUNT(orders.id) AS order_count, SUM(orders.total_amount) AS total_spent FROM orders JOIN customers ON orders.customer_id = customers.id GROUP BY customers.name ORDER BY total_spent DESC LIMIT 10",
    },
    {
        "id": "eval-09",
        "category": "basic_list",
        "question": "List all customers and their country",
        "gold_sql": "SELECT customers.id, customers.name, customers.email, customers.country, customers.created_at FROM customers ORDER BY customers.id ASC LIMIT 100",
    },
    {
        "id": "eval-10",
        "category": "ranking",
        "question": "What are the most expensive products?",
        "gold_sql": "SELECT products.id, products.name, products.price FROM products ORDER BY products.price DESC LIMIT 10",
    },
    {
        "id": "eval-11",
        "category": "aggregation",
        "question": "How many customers are registered?",
        "gold_sql": "SELECT COUNT(*) AS total_customers FROM customers LIMIT 100",
    },
    {
        "id": "eval-12",
        "category": "aggregation",
        "question": "How many products do we have in total?",
        "gold_sql": "SELECT COUNT(*) AS total_products FROM products LIMIT 100",
    }
]

