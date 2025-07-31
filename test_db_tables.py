import asyncio
import asyncpg
import os

async def explore_database():
    # Replace with your actual Neon database URL
    DATABASE_URL = "Your_db_url"
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        print("=== ALL TABLES ===")
        tables = await conn.fetch("""
            SELECT table_name, table_schema 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        
        for table in tables:
            print(f"- {table['table_name']}")
        
        print("\n=== TABLE DETAILS ===")
        for table in tables:
            table_name = table['table_name']
            print(f"\n{table_name}:")
            
            columns = await conn.fetch("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                  AND table_name = $1
                ORDER BY ordinal_position
            """, table_name)
            
            for col in columns:
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                print(f"  • {col['column_name']}: {col['data_type']} ({nullable})")
        
        await conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

# Run the exploration
asyncio.run(explore_database())
