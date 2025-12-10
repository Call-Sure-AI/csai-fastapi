import asyncio
import sys
import os

# Add parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.postgres_client import get_db_connection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_analytics_table():
    """Create Analytics table for company-level aggregated metrics"""
    async with await get_db_connection() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS public."Analytics" (
                id VARCHAR(255) PRIMARY KEY DEFAULT ('ANA-' || UPPER(SUBSTRING(gen_random_uuid()::text, 1, 8))),
                company_id TEXT NOT NULL,
                
                -- Call Metrics
                total_calls INTEGER DEFAULT 0,
                completed_calls INTEGER DEFAULT 0,
                failed_calls INTEGER DEFAULT 0,
                in_progress_calls INTEGER DEFAULT 0,
                avg_call_duration DOUBLE PRECISION DEFAULT 0.0,
                total_call_cost DOUBLE PRECISION DEFAULT 0.0,
                
                -- Resolution Metrics
                total_tickets_created INTEGER DEFAULT 0,
                resolution_rate DOUBLE PRECISION DEFAULT 0.0,  -- % of calls without tickets
                
                -- Booking Metrics
                total_bookings INTEGER DEFAULT 0,
                pending_bookings INTEGER DEFAULT 0,
                confirmed_bookings INTEGER DEFAULT 0,
                cancelled_bookings INTEGER DEFAULT 0,
                
                -- Quality Metrics
                avg_quality_score DOUBLE PRECISION DEFAULT 0.0,
                
                -- Time tracking
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                -- Foreign key to Company table
                CONSTRAINT Analytics_company_id_fkey 
                    FOREIGN KEY(company_id) 
                    REFERENCES public."Company"(id)
                    ON UPDATE CASCADE
                    ON DELETE CASCADE,
                
                -- One analytics record per company
                CONSTRAINT Analytics_company_unique UNIQUE(company_id)
            );
            
            -- Create indexes for performance
            CREATE INDEX IF NOT EXISTS idx_analytics_company_id ON public."Analytics"(company_id);
            CREATE INDEX IF NOT EXISTS idx_analytics_updated_at ON public."Analytics"(updated_at);
        """)
    
    logger.info("✓ Analytics table created successfully!")


async def calculate_and_store_analytics():
    """Calculate analytics for each company and store in Analytics table"""
    async with await get_db_connection() as conn:
        # Get all companies that have calls
        companies = await conn.fetch("""
            SELECT DISTINCT company_id 
            FROM public."Call" 
            WHERE company_id IS NOT NULL
        """)
        
        if not companies:
            logger.warning("No companies found with call data")
            return
        
        logger.info(f"Found {len(companies)} companies to process")
        
        processed = 0
        for company_row in companies:
            company_id = company_row['company_id']
            
            try:
                # 1. Calculate Call Metrics
                call_metrics = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total_calls,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_calls,
                        COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_calls,
                        COUNT(CASE WHEN status = 'in-progress' THEN 1 END) as in_progress_calls,
                        COALESCE(AVG(duration), 0) as avg_call_duration,
                        COALESCE(SUM(cost), 0) as total_call_cost,
                        COALESCE(AVG(quality_score), 0) as avg_quality_score
                    FROM public."Call"
                    WHERE company_id = $1
                """, company_id)
                
                # 2. Calculate Ticket Metrics (for Resolution Rate)
                ticket_metrics = await conn.fetchrow("""
                    SELECT COUNT(*) as total_tickets
                    FROM public."Ticket"
                    WHERE company_id = $1
                """, company_id)
                
                total_calls = call_metrics['total_calls'] or 0
                total_tickets = ticket_metrics['total_tickets'] or 0
                
                # Resolution Rate = % of calls that did NOT create a ticket
                # If total_calls = 100 and total_tickets = 20, resolution_rate = 80%
                resolution_rate = ((total_calls - total_tickets) / total_calls * 100) if total_calls > 0 else 0.0
                
                # 3. Calculate Booking Metrics (FIXED: using lowercase "campaign")
                # Join booking -> campaign to get company_id
                booking_metrics = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total_bookings,
                        COUNT(CASE WHEN b.status = 'pending' THEN 1 END) as pending_bookings,
                        COUNT(CASE WHEN b.status = 'confirmed' THEN 1 END) as confirmed_bookings,
                        COUNT(CASE WHEN b.status = 'cancelled' THEN 1 END) as cancelled_bookings
                    FROM public.booking b
                    INNER JOIN public.campaign c ON b.campaign_id = c.id
                    WHERE c.company_id = $1
                """, company_id)
                
                # 4. Insert or Update Analytics record
                await conn.execute("""
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
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
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
                        last_calculated_at = CURRENT_TIMESTAMP
                """,
                    company_id,
                    call_metrics['total_calls'],
                    call_metrics['completed_calls'],
                    call_metrics['failed_calls'],
                    call_metrics['in_progress_calls'],
                    call_metrics['avg_call_duration'],
                    call_metrics['total_call_cost'],
                    total_tickets,
                    resolution_rate,
                    booking_metrics['total_bookings'],
                    booking_metrics['pending_bookings'],
                    booking_metrics['confirmed_bookings'],
                    booking_metrics['cancelled_bookings'],
                    call_metrics['avg_quality_score']
                )
                
                processed += 1
                logger.info(f"✓ Processed company {company_id}: {call_metrics['total_calls']} calls, "
                           f"{booking_metrics['total_bookings']} bookings, "
                           f"{resolution_rate:.1f}% resolution rate")
                
            except Exception as e:
                logger.error(f"✗ Error processing company {company_id}: {e}")
                continue
        
        logger.info(f"\n✓ Successfully processed {processed}/{len(companies)} companies")


async def display_analytics_summary():
    """Display summary of analytics data"""
    async with await get_db_connection() as conn:
        analytics = await conn.fetch("""
            SELECT 
                company_id,
                total_calls,
                completed_calls,
                resolution_rate,
                total_bookings,
                total_call_cost,
                avg_quality_score
            FROM public."Analytics"
            ORDER BY total_calls DESC
        """)
        
        if not analytics:
            logger.warning("No analytics data found")
            return
        
        logger.info("\n" + "="*80)
        logger.info("Analytics Summary:")
        logger.info("="*80)
        logger.info(f"{'Company ID':<40} {'Calls':<8} {'Completed':<10} {'Resolution':<12} {'Bookings':<10}")
        logger.info("-"*80)
        
        for row in analytics:
            logger.info(
                f"{row['company_id']:<40} "
                f"{row['total_calls']:<8} "
                f"{row['completed_calls']:<10} "
                f"{row['resolution_rate']:.1f}%{' ':<7} "
                f"{row['total_bookings']:<10}"
            )
        
        # Overall totals
        totals = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_companies,
                SUM(total_calls) as total_calls,
                SUM(completed_calls) as total_completed,
                SUM(total_bookings) as total_bookings,
                AVG(resolution_rate) as avg_resolution_rate
            FROM public."Analytics"
        """)
        
        logger.info("-"*80)
        logger.info(f"Total Companies: {totals['total_companies']}")
        logger.info(f"Total Calls: {totals['total_calls']}")
        logger.info(f"Total Completed: {totals['total_completed']}")
        logger.info(f"Total Bookings: {totals['total_bookings']}")
        logger.info(f"Average Resolution Rate: {totals['avg_resolution_rate']:.1f}%")
        logger.info("="*80 + "\n")


async def main():
    """Main execution"""
    try:
        logger.info("Starting Analytics table creation and data aggregation...\n")
        
        logger.info("STEP 1: Creating Analytics table")
        logger.info("-" * 60)
        await create_analytics_table()
        logger.info("")
        
        logger.info("STEP 2: Calculating and storing analytics")
        logger.info("-" * 60)
        await calculate_and_store_analytics()
        logger.info("")
        
        logger.info("STEP 3: Displaying analytics summary")
        logger.info("-" * 60)
        await display_analytics_summary()
        
        logger.info("✓ Analytics generation completed successfully!")
        
    except Exception as e:
        logger.error(f"Analytics generation failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
