import asyncio
import sys
import os

# Add parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.postgres_client import get_db_connection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_trigger_function():
    """Create the trigger function that updates Analytics table"""
    async with await get_db_connection() as conn:
        await conn.execute("""
            -- Drop existing function if it exists
            DROP FUNCTION IF EXISTS update_analytics_on_call_change() CASCADE;
            
            -- Create the trigger function
            CREATE OR REPLACE FUNCTION update_analytics_on_call_change()
            RETURNS TRIGGER AS $$
            DECLARE
                target_company_id TEXT;
                v_total_calls INTEGER;
                v_completed_calls INTEGER;
                v_failed_calls INTEGER;
                v_in_progress_calls INTEGER;
                v_avg_call_duration DOUBLE PRECISION;
                v_total_call_cost DOUBLE PRECISION;
                v_avg_quality_score DOUBLE PRECISION;
                v_total_tickets INTEGER;
                v_resolution_rate DOUBLE PRECISION;
                v_total_bookings INTEGER;
                v_pending_bookings INTEGER;
                v_confirmed_bookings INTEGER;
                v_cancelled_bookings INTEGER;
            BEGIN
                -- Determine which company_id to update
                IF TG_OP = 'DELETE' THEN
                    target_company_id := OLD.company_id;
                ELSE
                    target_company_id := NEW.company_id;
                END IF;
                
                -- Skip if company_id is NULL
                IF target_company_id IS NULL THEN
                    RETURN NEW;
                END IF;
                
                -- Calculate Call Metrics
                SELECT 
                    COUNT(*),
                    COUNT(CASE WHEN status = 'completed' THEN 1 END),
                    COUNT(CASE WHEN status = 'failed' THEN 1 END),
                    COUNT(CASE WHEN status = 'in-progress' THEN 1 END),
                    COALESCE(AVG(duration), 0),
                    COALESCE(SUM(cost), 0),
                    COALESCE(AVG(quality_score), 0)
                INTO 
                    v_total_calls,
                    v_completed_calls,
                    v_failed_calls,
                    v_in_progress_calls,
                    v_avg_call_duration,
                    v_total_call_cost,
                    v_avg_quality_score
                FROM public."Call"
                WHERE company_id = target_company_id;
                
                -- Calculate Ticket Metrics
                SELECT COUNT(*)
                INTO v_total_tickets
                FROM public."Ticket"
                WHERE company_id = target_company_id;
                
                -- Calculate Resolution Rate
                IF v_total_calls > 0 THEN
                    v_resolution_rate := ((v_total_calls - v_total_tickets)::DOUBLE PRECISION / v_total_calls) * 100;
                ELSE
                    v_resolution_rate := 0.0;
                END IF;
                
                -- Calculate Booking Metrics
                SELECT 
                    COUNT(*),
                    COUNT(CASE WHEN b.status = 'pending' THEN 1 END),
                    COUNT(CASE WHEN b.status = 'confirmed' THEN 1 END),
                    COUNT(CASE WHEN b.status = 'cancelled' THEN 1 END)
                INTO
                    v_total_bookings,
                    v_pending_bookings,
                    v_confirmed_bookings,
                    v_cancelled_bookings
                FROM public.booking b
                INNER JOIN public.campaign c ON b.campaign_id = c.id
                WHERE c.company_id = target_company_id;
                
                -- Upsert Analytics record (UPDATE if exists, INSERT if not)
                INSERT INTO public."Analytics" (
                    company_id,
                    total_calls,
                    completed_calls,
                    failed_calls,
                    in_progress_calls,
                    avg_call_duration,
                    total_call_cost,
                    total_tickets_created,
                    resolution_rate,
                    total_bookings,
                    pending_bookings,
                    confirmed_bookings,
                    cancelled_bookings,
                    avg_quality_score,
                    updated_at,
                    last_calculated_at
                ) VALUES (
                    target_company_id,
                    v_total_calls,
                    v_completed_calls,
                    v_failed_calls,
                    v_in_progress_calls,
                    v_avg_call_duration,
                    v_total_call_cost,
                    v_total_tickets,
                    v_resolution_rate,
                    v_total_bookings,
                    v_pending_bookings,
                    v_confirmed_bookings,
                    v_cancelled_bookings,
                    v_avg_quality_score,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (company_id) DO UPDATE SET
                    total_calls = EXCLUDED.total_calls,
                    completed_calls = EXCLUDED.completed_calls,
                    failed_calls = EXCLUDED.failed_calls,
                    in_progress_calls = EXCLUDED.in_progress_calls,
                    avg_call_duration = EXCLUDED.avg_call_duration,
                    total_call_cost = EXCLUDED.total_call_cost,
                    total_tickets_created = EXCLUDED.total_tickets_created,
                    resolution_rate = EXCLUDED.resolution_rate,
                    total_bookings = EXCLUDED.total_bookings,
                    pending_bookings = EXCLUDED.pending_bookings,
                    confirmed_bookings = EXCLUDED.confirmed_bookings,
                    cancelled_bookings = EXCLUDED.cancelled_bookings,
                    avg_quality_score = EXCLUDED.avg_quality_score,
                    updated_at = CURRENT_TIMESTAMP,
                    last_calculated_at = CURRENT_TIMESTAMP;
                
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)
        
        logger.info("✓ Trigger function created successfully!")


async def create_triggers():
    """Create triggers on Call table"""
    async with await get_db_connection() as conn:
        # Drop existing triggers if they exist
        await conn.execute("""
            DROP TRIGGER IF EXISTS trigger_update_analytics_on_insert ON public."Call";
            DROP TRIGGER IF EXISTS trigger_update_analytics_on_update ON public."Call";
            DROP TRIGGER IF EXISTS trigger_update_analytics_on_delete ON public."Call";
        """)
        
        # Create trigger for INSERT
        await conn.execute("""
            CREATE TRIGGER trigger_update_analytics_on_insert
            AFTER INSERT ON public."Call"
            FOR EACH ROW
            EXECUTE FUNCTION update_analytics_on_call_change();
        """)
        logger.info("✓ INSERT trigger created")
        
        # Create trigger for UPDATE
        await conn.execute("""
            CREATE TRIGGER trigger_update_analytics_on_update
            AFTER UPDATE ON public."Call"
            FOR EACH ROW
            EXECUTE FUNCTION update_analytics_on_call_change();
        """)
        logger.info("✓ UPDATE trigger created")
        
        # Create trigger for DELETE
        await conn.execute("""
            CREATE TRIGGER trigger_update_analytics_on_delete
            AFTER DELETE ON public."Call"
            FOR EACH ROW
            EXECUTE FUNCTION update_analytics_on_call_change();
        """)
        logger.info("✓ DELETE trigger created")


async def test_trigger():
    """Test the trigger by checking current analytics"""
    async with await get_db_connection() as conn:
        analytics = await conn.fetch("""
            SELECT 
                company_id,
                total_calls,
                completed_calls,
                resolution_rate,
                total_bookings,
                last_calculated_at
            FROM public."Analytics"
            ORDER BY updated_at DESC
            LIMIT 5
        """)
        
        if analytics:
            logger.info("\n" + "="*80)
            logger.info("Current Analytics (Most Recent):")
            logger.info("="*80)
            for row in analytics:
                logger.info(f"Company: {row['company_id']}")
                logger.info(f"  Calls: {row['total_calls']}, Completed: {row['completed_calls']}")
                logger.info(f"  Resolution Rate: {row['resolution_rate']:.1f}%")
                logger.info(f"  Bookings: {row['total_bookings']}")
                logger.info(f"  Last Updated: {row['last_calculated_at']}")
                logger.info("-" * 80)
            logger.info("="*80 + "\n")
        else:
            logger.info("No analytics data found yet")


async def main():
    """Main execution"""
    try:
        logger.info("Setting up automatic analytics updates...\n")
        
        logger.info("STEP 1: Creating trigger function")
        logger.info("-" * 60)
        await create_trigger_function()
        logger.info("")
        
        logger.info("STEP 2: Creating triggers on Call table")
        logger.info("-" * 60)
        await create_triggers()
        logger.info("")
        
        logger.info("STEP 3: Testing current analytics state")
        logger.info("-" * 60)
        await test_trigger()
        
        logger.info("✓ Triggers setup completed successfully!")
        logger.info("\nℹ️  Analytics will now auto-update on every Call table change")
        logger.info("   - New call inserted → Analytics updated")
        logger.info("   - Call status updated → Analytics recalculated")
        logger.info("   - Call deleted → Analytics adjusted")
        
    except Exception as e:
        logger.error(f"Trigger setup failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
