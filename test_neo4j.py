from neo4j import GraphDatabase

uri = "bolt://localhost:7687"
user = "neo4j"
password = "12345678"

try:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    print("✓ Neo4j 连接成功!")
    driver.close()
except Exception as e:
    print(f"✗ Neo4j 连接失败：{e}")
    print("\n可能的解决方案：")
    print("1. 检查 Neo4j 是否已启动")
    print("2. 确认密码是否正确（Neo4j 首次启动会要求修改默认密码）")
    print("3. 在 Neo4j Desktop 中重置密码")
