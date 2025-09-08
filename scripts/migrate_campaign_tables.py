# scripts/migrate_campaign_leads.py
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.postgres_client import get_db_connection
import logging
import uuid
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate_existing_campaign_leads():
    """Migrate existing Campaign_Lead data to new lead management structure"""
    
    async with await get_db_connection() as conn:
        try:
            # Start transaction
            async with conn.transaction():
                logger.info("Starting migration of Campaign_Lead data...")
                
                # Get all campaigns with their company IDs
                campaigns = await conn.fetch("""
                    SELECT id, company_id 
                    FROM Campaign
                """)
                
                total_migrated = 0
                total_associations = 0
                
                for campaign in campaigns:
                    campaign_id = campaign['id']
                    company_id = campaign['company_id']
                    
                    logger.info(f"Processing campaign {campaign_id}...")
                    
                    # Get all leads for this campaign
                    campaign_leads = await conn.fetch("""
                        SELECT 
                            id as old_lead_id,
                            first_name,
                            last_name,
                            email,
                            phone,
                            company as lead_company,
                            custom_fields,
                            call_attempts,
                            last_call_at,
                            status,
                            created_at,
                            updated_at
                        FROM Campaign_Lead
                        WHERE campaign_id = $1
                    """, campaign_id)
                    
                    for lead in campaign_leads:
                        if not lead['email']:
                            logger.warning(f"Skipping lead without email: {lead['old_lead_id']}")
                            continue
                        
                        # Check if lead already exists for this company
                        existing_lead = await conn.fetchrow("""
                            SELECT id 
                            FROM leads 
                            WHERE company_id = $1 AND LOWER(email) = LOWER($2)
                        """, uuid.UUID(company_id), lead['email'])
                        
                        if existing_lead:
                            lead_id = existing_lead['id']
                            logger.info(f"Found existing lead: {lead['email']}")
                        else:
                            # Create new lead in master table
                            lead_id = await conn.fetchval("""
                                INSERT INTO leads (
                                    company_id,
                                    email,
                                    first_name,
                                    last_name,
                                    phone,
                                    lead_company,
                                    custom_fields,
                                    source,
                                    status,
                                    created_at,
                                    updated_at
                                ) VALUES (
                                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11
                                ) RETURNING id
                            """, 
                                uuid.UUID(company_id),
                                lead['email'].lower(),
                                lead['first_name'],
                                lead['last_name'],
                                lead['phone'],
                                lead['lead_company'],
                                lead['custom_fields'],
                                'campaign_import',
                                'new',  # Reset to new in master table
                                lead['created_at'],
                                lead['updated_at']
                            )
                            total_migrated += 1
                            logger.info(f"Created new lead: {lead['email']}")
                        
                        # Create campaign-lead association
                        existing_association = await conn.fetchrow("""
                            SELECT id 
                            FROM campaign_leads 
                            WHERE campaign_id = $1 AND lead_id = $2
                        """, campaign_id, lead_id)
                        
                        if not existing_association:
                            await conn.execute("""
                                INSERT INTO campaign_leads (
                                    campaign_id,
                                    lead_id,
                                    campaign_status,
                                    call_attempts,
                                    last_call_at,
                                    campaign_custom_fields,
                                    added_to_campaign_at
                                ) VALUES (
                                    $1, $2, $3, $4, $5, $6, $7
                                )
                            """,
                                campaign_id,
                                lead_id,
                                lead['status'] or 'pending',
                                lead['call_attempts'] or 0,
                                lead['last_call_at'],
                                lead['custom_fields'],
                                lead['created_at']
                            )
                            total_associations += 1
                        
                        # Migrate Campaign_Activity data if exists
                        activities = await conn.fetch("""
                            SELECT 
                                activity_type,
                                status,
                                details,
                                created_at
                            FROM Campaign_Activity
                            WHERE campaign_id = $1 AND lead_id = $2
                        """, campaign_id, lead['old_lead_id'])
                        
                        for activity in activities:
                            await conn.execute("""
                                INSERT INTO lead_events (
                                    lead_id,
                                    campaign_id,
                                    event_type,
                                    event_data,
                                    created_at
                                ) VALUES (
                                    $1, $2, $3, $4, $5
                                )
                            """,
                                lead_id,
                                campaign_id,
                                activity['activity_type'],
                                {
                                    'status': activity['status'],
                                    'details': activity['details']
                                },
                                activity['created_at']
                            )
                
                logger.info(f"✅ Migration completed successfully!")
                logger.info(f"   - New leads created: {total_migrated}")
                logger.info(f"   - Campaign associations created: {total_associations}")
                
                return {
                    'success': True,
                    'new_leads': total_migrated,
                    'associations': total_associations
                }
                
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise

async def verify_migration():
    """Verify the migration was successful"""
    
    async with await get_db_connection() as conn:
        try:
            # Count original Campaign_Lead records
            original_count = await conn.fetchval("""
                SELECT COUNT(DISTINCT email) 
                FROM Campaign_Lead 
                WHERE email IS NOT NULL
            """)
            
            # Count migrated leads
            migrated_count = await conn.fetchval("""
                SELECT COUNT(*) 
                FROM leads 
                WHERE source = 'campaign_import'
            """)
            
            # Count campaign associations
            association_count = await conn.fetchval("""
                SELECT COUNT(*) 
                FROM campaign_leads
            """)
            
            # Get sample of migrated data
            sample_leads = await conn.fetch("""
                SELECT 
                    l.email,
                    l.first_name,
                    l.last_name,
                    COUNT(cl.campaign_id) as campaign_count
                FROM leads l
                LEFT JOIN campaign_leads cl ON cl.lead_id = l.id
                WHERE l.source = 'campaign_import'
                GROUP BY l.id, l.email, l.first_name, l.last_name
                LIMIT 10
            """)
            
            logger.info("📊 Migration Verification Report:")
            logger.info(f"   Original unique emails: {original_count}")
            logger.info(f"   Migrated leads: {migrated_count}")
            logger.info(f"   Campaign associations: {association_count}")
            logger.info("\n   Sample migrated leads:")
            for lead in sample_leads:
                logger.info(f"   - {lead['email']}: {lead['campaign_count']} campaigns")
            
            return {
                'original_count': original_count,
                'migrated_count': migrated_count,
                'association_count': association_count,
                'verification_passed': migrated_count <= original_count
            }
            
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            raise

async def rollback_migration():
    """Rollback the migration if needed"""
    
    async with await get_db_connection() as conn:
        try:
            async with conn.transaction():
                logger.info("Rolling back migration...")
                
                # Delete campaign associations
                deleted_associations = await conn.fetchval("""
                    DELETE FROM campaign_leads
                    WHERE lead_id IN (
                        SELECT id FROM leads WHERE source = 'campaign_import'
                    )
                    RETURNING COUNT(*)
                """)
                
                # Delete migrated leads
                deleted_leads = await conn.fetchval("""
                    DELETE FROM leads 
                    WHERE source = 'campaign_import'
                    RETURNING COUNT(*)
                """)
                
                logger.info(f"✅ Rollback completed:")
                logger.info(f"   - Deleted leads: {deleted_leads}")
                logger.info(f"   - Deleted associations: {deleted_associations}")
                
                return {
                    'success': True,
                    'deleted_leads': deleted_leads,
                    'deleted_associations': deleted_associations
                }
                
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            raise

async def main():
    """Main migration function with options"""
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "migrate":
            logger.info("Starting Campaign_Lead migration...")
            result = await migrate_existing_campaign_leads()
            logger.info(f"Migration result: {result}")
            
        elif command == "verify":
            logger.info("Verifying migration...")
            result = await verify_migration()
            logger.info(f"Verification result: {result}")
            
        elif command == "rollback":
            response = input("⚠️  Are you sure you want to rollback the migration? (yes/no): ")
            if response.lower() == "yes":
                result = await rollback_migration()
                logger.info(f"Rollback result: {result}")
            else:
                logger.info("Rollback cancelled")
                
        else:
            logger.error(f"Unknown command: {command}")
            logger.info("Usage: python migrate_campaign_leads.py [migrate|verify|rollback]")
            
    else:
        # Default: Run migration and verification
        logger.info("Running full migration process...")
        
        # Run migration
        migration_result = await migrate_existing_campaign_leads()
        
        # Verify migration
        verification_result = await verify_migration()
        
        if verification_result['verification_passed']:
            logger.info("✅ Migration completed and verified successfully!")
        else:
            logger.warning("⚠️  Migration completed but verification shows discrepancies")
            logger.info("Please review the results and run 'python migrate_campaign_leads.py verify' for details")

if __name__ == "__main__":
    asyncio.run(main())