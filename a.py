import psycopg2

try:
    conn = psycopg2.connect(
        host="dpg-d08s5b2dbo4c73e8hii0-a.oregon-postgres.render.com",
        database="travel_system",
        user="travel_system_user",
        password="XNqBilUUZo9lA0K93WzXa2uIljJyMqc4",
        port=5432
    )
    print("✅ 成功連線到 PostgreSQL！")
    conn.close()
except Exception as e:
    print("❌ 無法連線：", e)