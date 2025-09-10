import asyncio
import logging
from typing import List, Dict, Any, Tuple
import asyncpg

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ComprehensiveSchemaFixer:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.views_to_drop = []
        self.view_definitions = {}
        self.constraints_to_restore = []
        
    async def analyze_all_tables(self, conn: asyncpg.Connection) -> Dict[str, List[str]]:
        """Analyze all tables to find UUID columns that should be VARCHAR"""
        
        # Find all columns with UUID type in your script-related tables
        query = """
        SELECT 
            c.table_name,
            c.column_name,
            c.data_type,
            c.udt_name
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
        AND c.udt_name = 'uuid'
        AND (
            c.table_name LIKE 'script%'
            OR c.table_name IN ('leads', 'users', 'companies')
        )
        ORDER BY c.table_name, c.column_name
        """
        
        results = await conn.fetch(query)
        
        tables_to_fix = {}
        for row in results:
            table = row['table_name']
            column = row['column_name']
            
            if table not in tables_to_fix:
                tables_to_fix[table] = []
            tables_to_fix[table].append(column)
        
        return tables_to_fix
    
    async def get_dependent_views(self, conn: asyncpg.Connection, tables: List[str]) -> None:
        """Get all views that depend on the tables we're modifying"""
        
        if not tables:
            return
            
        table_list = "', '".join(tables)
        query = f"""
        SELECT DISTINCT 
            c.relname as table_name,
            v.relname as view_name,
            pg_get_viewdef(v.oid, true) as view_definition
        FROM pg_class c
        JOIN pg_depend d ON c.oid = d.refobjid
        JOIN pg_rewrite r ON d.objid = r.oid
        JOIN pg_class v ON r.ev_class = v.oid
        WHERE c.relname IN ('{table_list}')
        AND c.relkind = 'r'
        AND v.relkind IN ('v', 'm')  -- Include both views and materialized views
        AND d.deptype = 'n'
        """
        
        results = await conn.fetch(query)
        
        for row in results:
            view = row['view_name']
            definition = row['view_definition']
            
            if view not in self.views_to_drop:
                self.views_to_drop.append(view)
                self.view_definitions[view] = definition
    
    async def get_foreign_key_constraints(self, conn: asyncpg.Connection, tables_to_fix: Dict[str, List[str]]) -> None:
        """Get all foreign key constraints that reference UUID columns"""
        
        for table, columns in tables_to_fix.items():
            for column in columns:
                query = """
                SELECT 
                    tc.constraint_name,
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name,
                    rc.update_rule,
                    rc.delete_rule
                FROM information_schema.table_constraints AS tc 
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                    AND ccu.table_schema = tc.table_schema
                JOIN information_schema.referential_constraints AS rc
                    ON tc.constraint_name = rc.constraint_name
                    AND tc.table_schema = rc.constraint_schema
                WHERE tc.constraint_type = 'FOREIGN KEY' 
                    AND tc.table_schema = 'public'
                    AND (
                        (tc.table_name = $1 AND kcu.column_name = $2)
                        OR (ccu.table_name = $1 AND ccu.column_name = $2)
                    )
                """
                
                constraints = await conn.fetch(query, table, column)
                
                for constraint in constraints:
                    self.constraints_to_restore.append({
                        'name': constraint['constraint_name'],
                        'table': constraint['table_name'],
                        'column': constraint['column_name'],
                        'foreign_table': constraint['foreign_table_name'],
                        'foreign_column': constraint['foreign_column_name'],
                        'update_rule': constraint['update_rule'],
                        'delete_rule': constraint['delete_rule']
                    })
    
    async def drop_constraints(self, conn: asyncpg.Connection):
        """Drop foreign key constraints"""
        dropped_constraints = set()
        
        for constraint in self.constraints_to_restore:
            if constraint['name'] not in dropped_constraints:
                try:
                    await conn.execute(f"""
                        ALTER TABLE {constraint['table']} 
                        DROP CONSTRAINT IF EXISTS {constraint['name']}
                    """)
                    dropped_constraints.add(constraint['name'])
                    logger.info(f"  ✓ Dropped constraint: {constraint['name']}")
                except Exception as e:
                    logger.warning(f"  ⚠ Could not drop constraint {constraint['name']}: {e}")
    
    async def restore_constraints(self, conn: asyncpg.Connection):
        """Restore foreign key constraints"""
        restored_constraints = set()
        
        for constraint in self.constraints_to_restore:
            if constraint['name'] not in restored_constraints:
                try:
                    await conn.execute(f"""
                        ALTER TABLE {constraint['table']} 
                        ADD CONSTRAINT {constraint['name']} 
                        FOREIGN KEY ({constraint['column']}) 
                        REFERENCES {constraint['foreign_table']}({constraint['foreign_column']})
                        ON UPDATE {constraint['update_rule']}
                        ON DELETE {constraint['delete_rule']}
                    """)
                    restored_constraints.add(constraint['name'])
                    logger.info(f"  ✓ Restored constraint: {constraint['name']}")
                except Exception as e:
                    logger.warning(f"  ⚠ Could not restore constraint {constraint['name']}: {e}")
    
    async def drop_views(self, conn: asyncpg.Connection):
        """Drop all dependent views"""
        for view in self.views_to_drop:
            try:
                # Check if it's a materialized view
                is_materialized = await conn.fetchval("""
                    SELECT relkind = 'm' FROM pg_class WHERE relname = $1
                """, view)
                
                if is_materialized:
                    await conn.execute(f"DROP MATERIALIZED VIEW IF EXISTS {view} CASCADE")
                    logger.info(f"  ✓ Dropped materialized view: {view}")
                else:
                    await conn.execute(f"DROP VIEW IF EXISTS {view} CASCADE")
                    logger.info(f"  ✓ Dropped view: {view}")
            except Exception as e:
                logger.error(f"  ❌ Failed to drop view {view}: {e}")
    
    async def recreate_views(self, conn: asyncpg.Connection):
        """Recreate the views after column conversion"""
        for view_name, definition in self.view_definitions.items():
            try:
                # Check if it was a materialized view
                was_materialized = 'MATERIALIZED VIEW' in definition.upper()
                
                if was_materialized:
                    # Clean up the definition for materialized views
                    definition = definition.replace('::uuid', '::varchar')
                    await conn.execute(f"CREATE MATERIALIZED VIEW {view_name} AS {definition}")
                    logger.info(f"  ✓ Recreated materialized view: {view_name}")
                else:
                    # Regular view
                    definition = definition.replace('::uuid', '::varchar')
                    await conn.execute(f"CREATE VIEW {view_name} AS {definition}")
                    logger.info(f"  ✓ Recreated view: {view_name}")
            except Exception as e:
                logger.error(f"  ❌ Failed to recreate view {view_name}: {e}")
    
    async def convert_columns(self, conn: asyncpg.Connection, tables_to_fix: Dict[str, List[str]]):
        """Convert UUID columns to VARCHAR"""
        
        for table, columns in tables_to_fix.items():
            for column in columns:
                try:
                    # Drop any indexes on the column
                    await conn.execute(f"""
                        DROP INDEX IF EXISTS idx_{table}_{column}
                    """)
                    
                    # Convert the column
                    await conn.execute(f"""
                        ALTER TABLE {table} 
                        ALTER COLUMN {column} TYPE VARCHAR(50) 
                        USING {column}::text
                    """)
                    
                    logger.info(f"  ✓ Converted {table}.{column} to VARCHAR(50)")
                    
                    # Recreate the index
                    await conn.execute(f"""
                        CREATE INDEX IF NOT EXISTS idx_{table}_{column} 
                        ON {table}({column})
                    """)
                    
                except Exception as e:
                    logger.error(f"  ❌ Failed to convert {table}.{column}: {e}")
                    raise
    
    async def verify_changes(self, conn: asyncpg.Connection, tables_to_fix: Dict[str, List[str]]) -> bool:
        """Verify all columns are now VARCHAR"""
        
        all_good = True
        logger.info("\n📊 Verification Results:")
        logger.info("-" * 60)
        
        for table, columns in tables_to_fix.items():
            for column in columns:
                result = await conn.fetchrow("""
                    SELECT data_type, udt_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND table_name = $1
                    AND column_name = $2
                """, table, column)
                
                if result:
                    is_varchar = result['data_type'] == 'character varying'
                    status = "✅" if is_varchar else "❌"
                    logger.info(f"{status} {table}.{column}: {result['data_type']}")
                    
                    if not is_varchar:
                        all_good = False
                else:
                    logger.warning(f"⚠️  {table}.{column}: Column not found")
                    all_good = False
        
        return all_good
    
    async def run(self):
        """Execute the complete migration"""
        conn = await asyncpg.connect(self.connection_string)
        
        try:
            logger.info("🚀 Starting Comprehensive Database Schema Fix")
            logger.info("=" * 60)
            
            # 1. Analyze all tables
            logger.info("\n🔍 Analyzing database schema...")
            tables_to_fix = await self.analyze_all_tables(conn)
            
            if not tables_to_fix:
                logger.info("✅ No UUID columns found that need conversion!")
                return
            
            logger.info(f"\nFound {sum(len(cols) for cols in tables_to_fix.values())} columns to convert:")
            for table, columns in tables_to_fix.items():
                for column in columns:
                    logger.info(f"  - {table}.{column}")
            
            # Start transaction
            async with conn.transaction():
                # 2. Get dependent views
                logger.info("\n📝 Finding dependent views...")
                await self.get_dependent_views(conn, list(tables_to_fix.keys()))
                
                if self.views_to_drop:
                    logger.info(f"Found {len(self.views_to_drop)} dependent views")
                
                # 3. Get foreign key constraints
                logger.info("\n📝 Finding foreign key constraints...")
                await self.get_foreign_key_constraints(conn, tables_to_fix)
                
                if self.constraints_to_restore:
                    logger.info(f"Found {len(self.constraints_to_restore)} foreign key constraints")
                
                # 4. Drop constraints
                if self.constraints_to_restore:
                    logger.info("\n📝 Dropping foreign key constraints...")
                    await self.drop_constraints(conn)
                
                # 5. Drop views
                if self.views_to_drop:
                    logger.info("\n📝 Dropping views...")
                    await self.drop_views(conn)
                
                # 6. Convert columns
                logger.info("\n📝 Converting columns to VARCHAR...")
                await self.convert_columns(conn, tables_to_fix)
                
                # 7. Restore constraints
                if self.constraints_to_restore:
                    logger.info("\n📝 Restoring foreign key constraints...")
                    await self.restore_constraints(conn)
                
                # 8. Recreate views
                if self.views_to_drop:
                    logger.info("\n📝 Recreating views...")
                    await self.recreate_views(conn)
            
            # 9. Verify changes (outside transaction)
            success = await self.verify_changes(conn, tables_to_fix)
            
            logger.info("\n" + "=" * 60)
            if success:
                logger.info("✅ SUCCESS: All columns converted successfully!")
            else:
                logger.info("⚠️  WARNING: Some columns may not have been converted")
            
            # 10. Test with sample string IDs
            logger.info("\n🧪 Testing with string IDs...")
            try:
                # Test script_events table
                test_id = f"TEST-{asyncio.get_event_loop().time():.0f}"
                await conn.execute("""
                    INSERT INTO script_events (id, script_id, event_type, event_data, created_by, created_at)
                    VALUES ($1, $2, $3, $4, $5, NOW())
                    ON CONFLICT (id) DO NOTHING
                """, test_id, 'SCRIPT-TEST', 'test', '{}', 'user-test')
                
                # Clean up test data
                await conn.execute("DELETE FROM script_events WHERE id = $1", test_id)
                
                logger.info("  ✅ String ID insertion test passed!")
            except Exception as e:
                logger.error(f"  ❌ String ID test failed: {e}")
            
        except Exception as e:
            logger.error(f"\n❌ ERROR: Migration failed: {e}")
            raise
        finally:
            await conn.close()

async def main():
    # Update with your database connection string
    CONNECTION_STRING = "postgresql://username:password@localhost:5432/database_name"
    
    fixer = ComprehensiveSchemaFixer(CONNECTION_STRING)
    await fixer.run()

if __name__ == "__main__":
    asyncio.run(main())