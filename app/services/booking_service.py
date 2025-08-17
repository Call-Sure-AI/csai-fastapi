import uuid
import csv
import io
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from app.db.postgres_client import get_db_connection
from app.models.schemas import (
    BookingCreate, BookingUpdate, BookingResponse, 
    BookingBulkUpdate, BookingFilter
)
import logging

logger = logging.getLogger(__name__)

BOOKING_STATUSES = ["pending", "confirmed", "cancelled", "rescheduled", "completed"]

def to_naive_utc(dt: datetime) -> datetime:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        return dt

class BookingService:    
    async def list_bookings(
        self, 
        company_id: str,
        filters: BookingFilter,
        offset: int = 0,
        limit: int = 100
    ) -> List[Dict[str, Any]]:

        conditions = ["c.company_id = $1"]
        params = [company_id]
        param_count = 2

        if filters.campaign_id:
            conditions.append(f"b.campaign_id = ${param_count}")
            params.append(filters.campaign_id)
            param_count += 1
            
        if filters.customer:
            conditions.append(f"b.customer ILIKE ${param_count}")
            params.append(f"%{filters.customer}%")
            param_count += 1
            
        if filters.status:
            if filters.status not in BOOKING_STATUSES:
                raise ValueError(f"Invalid status: {filters.status}")
            conditions.append(f"b.status = ${param_count}")
            params.append(filters.status)
            param_count += 1
            
        if filters.start_date:
            conditions.append(f"b.slot_start >= ${param_count}")
            params.append(to_naive_utc(filters.start_date))
            param_count += 1
            
        if filters.end_date:
            conditions.append(f"b.slot_end <= ${param_count}")
            params.append(to_naive_utc(filters.end_date))
            param_count += 1
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
            SELECT b.*, c.campaign_name 
            FROM booking b
            JOIN Campaign c ON b.campaign_id = c.id
            WHERE {where_clause}
            ORDER BY b.slot_start DESC
            OFFSET ${param_count} LIMIT ${param_count + 1}
        """
        
        params.extend([offset, limit])
        
        async with await get_db_connection() as conn:
            rows = await conn.fetch(query, *params)
        
        return [dict(row) for row in rows]
    
    async def create_booking(
        self, 
        company_id: str, 
        booking_data: BookingCreate,
        user_id: str
    ) -> BookingResponse:

        slot_start = to_naive_utc(booking_data.slot_start)
        slot_end = to_naive_utc(booking_data.slot_end)

        async with await get_db_connection() as conn:
            campaign = await conn.fetchrow("""
                SELECT id FROM Campaign 
                WHERE id = $1 AND company_id = $2
            """, booking_data.campaign_id, company_id)
            
            if not campaign:
                raise ValueError("Campaign not found or doesn't belong to your company")

            conflicts = await conn.fetchrow("""
                SELECT id FROM booking 
                WHERE campaign_id = $1 
                AND status IN ('pending', 'confirmed')
                AND (
                    (slot_start <= $2 AND slot_end > $2) OR
                    (slot_start < $3 AND slot_end >= $3) OR
                    (slot_start >= $2 AND slot_end <= $3)
                )
            """, booking_data.campaign_id, slot_start, slot_end)
            
            if conflicts:
                raise ValueError("Time slot conflicts with existing booking")

            booking_id = f"BOOK-{uuid.uuid4().hex[:8].upper()}"
            now = datetime.utcnow()
            
            row = await conn.fetchrow("""
                INSERT INTO booking (
                    id, campaign_id, customer, slot_start, slot_end, status,
                    customer_email, customer_phone, notes, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING *
            """, booking_id, booking_data.campaign_id, booking_data.customer,
                 slot_start, slot_end, booking_data.status,
                 booking_data.customer_email, booking_data.customer_phone, 
                 booking_data.notes, now, now)
            
            logger.info(f"Booking created: {booking_id} for company {company_id}")
            return BookingResponse(**dict(row))
    
    async def get_booking(
        self, 
        booking_id: str, 
        company_id: str
    ) -> Optional[BookingResponse]:
        
        async with await get_db_connection() as conn:
            row = await conn.fetchrow("""
                SELECT b.*, c.campaign_name 
                FROM booking b
                JOIN Campaign c ON b.campaign_id = c.id
                WHERE b.id = $1 AND c.company_id = $2
            """, booking_id, company_id)
            
        return BookingResponse(**dict(row)) if row else None
    
    async def update_booking(
        self, 
        booking_id: str, 
        company_id: str,
        updates: BookingUpdate
    ) -> Optional[BookingResponse]:
        
        update_fields = []
        values = []
        param_count = 1
        
        update_data = updates.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            if field == "status" and value not in BOOKING_STATUSES:
                raise ValueError(f"Invalid status: {value}")

            if field in ["slot_start", "slot_end"] and isinstance(value, datetime):
                value = to_naive_utc(value)
                
            update_fields.append(f"{field} = ${param_count}")
            values.append(value)
            param_count += 1
            
        if not update_fields:
            return await self.get_booking(booking_id, company_id)

        update_fields.append("updated_at = CURRENT_TIMESTAMP")

        values.append(booking_id)
        values.append(company_id)
        
        query = f"""
            UPDATE booking 
            SET {', '.join(update_fields)}
            WHERE id = ${param_count} 
            AND campaign_id IN (
                SELECT id FROM Campaign WHERE company_id = ${param_count + 1}
            )
            RETURNING *
        """
        
        async with await get_db_connection() as conn:
            row = await conn.fetchrow(query, *values)
            
        return BookingResponse(**dict(row)) if row else None
        
    async def delete_booking(self, booking_id: str, company_id: str) -> bool:
        async with await get_db_connection() as conn:
            result = await conn.execute("""
                UPDATE booking 
                SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
                WHERE id = $1 
                AND campaign_id IN (
                    SELECT id FROM Campaign WHERE company_id = $2
                )
            """, booking_id, company_id)
            
        return result.startswith("UPDATE 1")
    
    async def update_booking_status(self, booking_id: str, company_id: str, status: str):
        if status not in BOOKING_STATUSES:
            raise ValueError(f"Invalid status: {status}")
            
        async with await get_db_connection() as conn:
            row = await conn.fetchrow("""
                UPDATE booking 
                SET status = $1, updated_at = CURRENT_TIMESTAMP
                WHERE id = $2 
                AND campaign_id IN (
                    SELECT id FROM Campaign WHERE company_id = $3
                )
                RETURNING *
            """, status, booking_id, company_id)
            
        return BookingResponse(**dict(row)) if row else None

    async def bulk_update_bookings(
        self, 
        company_id: str,
        bulk_update: BookingBulkUpdate
    ) -> int:

        update_data = bulk_update.updates.dict(exclude_unset=True)
        if not update_data:
            return 0
            
        update_fields = []
        values = []
        param_count = 1
        
        for field, value in update_data.items():
            if field == "status" and value not in BOOKING_STATUSES:
                raise ValueError(f"Invalid status: {value}")
            update_fields.append(f"{field} = ${param_count}")
            values.append(value)
            param_count += 1
            
        update_fields.append(f"updated_at = ${param_count}")
        values.append(datetime.utcnow())
        param_count += 1

        placeholders = ', '.join(f'${i}' for i in range(param_count, param_count + len(bulk_update.booking_ids)))
        values.extend(bulk_update.booking_ids)
        values.append(company_id)
        
        query = f"""
            UPDATE booking 
            SET {', '.join(update_fields)}
            WHERE id IN ({placeholders})
            AND campaign_id IN (
                SELECT id FROM Campaign WHERE company_id = ${len(values)}
            )
        """
        
        async with await get_db_connection() as conn:
            result = await conn.execute(query, *values)

        updated_count = int(result.split()[-1]) if result.startswith("UPDATE") else 0
        return updated_count
    
    async def export_bookings(
        self, 
        company_id: str,
        filters: BookingFilter
    ) -> str:

        bookings = await self.list_bookings(company_id, filters, 0, 10000)
        
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            'id', 'campaign_id', 'campaign_name', 'customer', 
            'customer_email', 'customer_phone', 'slot_start', 'slot_end', 
            'status', 'notes', 'created_at', 'updated_at'
        ])

        for booking in bookings:
            writer.writerow([
                booking.get('id'), booking.get('campaign_id'),
                booking.get('campaign_name'), booking.get('customer'),
                booking.get('customer_email'), booking.get('customer_phone'),
                booking.get('slot_start'), booking.get('slot_end'),
                booking.get('status'), booking.get('notes'),
                booking.get('created_at'), booking.get('updated_at')
            ])
            
        output.seek(0)
        return output.getvalue()
