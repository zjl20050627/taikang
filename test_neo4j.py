"""测试 Neo4j Aura / 本地连接"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage.neo4j_settings import get_neo4j_settings
from neo4j import GraphDatabase

settings = get_neo4j_settings()
print("连接配置:")
print(f"  URI:      {settings['uri']}")
print(f"  USER:     {settings['user']}")
print(f"  DATABASE: {settings['database']}")
print(f"  PASSWORD: {'*' * 8} (已配置)" if settings['password'] else "  PASSWORD: (未配置)")

try:
    driver = GraphDatabase.driver(
        settings["uri"],
        auth=(settings["user"], settings["password"]),
    )
    driver.verify_connectivity()
    with driver.session(database=settings["database"]) as session:
        result = session.run("MATCH (n) RETURN count(n) AS cnt")
        cnt = result.single()["cnt"]
    print(f"\n✓ Neo4j 连接成功! 节点数: {cnt}")
    driver.close()
except Exception as e:
    print(f"\n✗ Neo4j 连接失败: {e}")
    print("\n排查建议:")
    print("1. 登录 https://console.neo4j.io/ 确认实例状态为 Running")
    print("2. 新实例需等待约 60 秒后再连接")
    print("3. 检查 .env 中 NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD / NEO4J_DATABASE")
    print("4. 若 DNS 解析失败，尝试切换网络（如手机热点）或配置代理")
