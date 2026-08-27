INSERT INTO customers(customer_id, customer_name, region, signup_date) VALUES
  (1, '晨曦商贸', '华东', CURRENT_DATE - 180),
  (2, '远山零售', '华南', CURRENT_DATE - 150),
  (3, '北辰生活', '华北', CURRENT_DATE - 120),
  (4, '西岭优选', '西南', CURRENT_DATE - 90)
ON CONFLICT DO NOTHING;

INSERT INTO products(product_id, product_name, category, unit_price) VALUES
  (1, '智能水杯', '家居', 199.00),
  (2, '降噪耳机', '数码', 599.00),
  (3, '轻量背包', '服饰', 299.00),
  (4, '咖啡礼盒', '食品', 159.00)
ON CONFLICT DO NOTHING;

INSERT INTO orders(order_id, customer_id, order_date, status, channel, region, gross_amount, discount_amount, refund_amount)
SELECT
  1000 + n,
  1 + (n % 4),
  CURRENT_DATE - (n % 60),
  CASE WHEN n % 17 = 0 THEN 'refunded' WHEN n % 23 = 0 THEN 'cancelled' ELSE 'paid' END,
  CASE WHEN n % 3 = 0 THEN '抖音' WHEN n % 3 = 1 THEN '天猫' ELSE '小程序' END,
  CASE WHEN n % 4 = 0 THEN '华东' WHEN n % 4 = 1 THEN '华南' WHEN n % 4 = 2 THEN '华北' ELSE '西南' END,
  100 + (n % 9) * 75,
  (n % 4) * 10,
  CASE WHEN n % 17 = 0 THEN 50 ELSE 0 END
FROM generate_series(1, 120) AS n
ON CONFLICT DO NOTHING;

INSERT INTO order_items(order_item_id, order_id, product_id, quantity, item_gross_amount)
SELECT 5000 + n, 1000 + n, 1 + (n % 4), 1 + (n % 3), 100 + (n % 9) * 75
FROM generate_series(1, 120) AS n
ON CONFLICT DO NOTHING;

