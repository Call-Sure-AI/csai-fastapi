from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json
import uuid

class LeadQueries:
    @staticmethod
    def create_lead() -> str:
        return """
        INSERT INTO leads (
            id, company_id, email, first_name, last_name, phone, lead_company,
            job_title, industry, country, city, state,
            source, status, priority, score, tags,
            custom_fields, assigned_to, created_by, created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
            $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22
        ) ON CONFLICT (company_id, email) DO UPDATE SET
            first_name = COALESCE(EXCLUDED.first_name, leads.first_name),
            last_name = COALESCE(EXCLUDED.last_name, leads.last_name),
            phone = COALESCE(EXCLUDED.phone, leads.phone),
            lead_company = COALESCE(EXCLUDED.lead_company, leads.lead_company),
            updated_at = EXCLUDED.updated_at
        RETURNING id, email
        """
    
    @staticmethod
    def bulk_create_leads() -> str:
        return """
        INSERT INTO leads (
            id, company_id, email, first_name, last_name, phone, lead_company,
            job_title, industry, country, city, state,
            source, status, priority, score, tags,
            custom_fields, assigned_to, created_by, created_at, updated_at
        ) VALUES $1
        ON CONFLICT (company_id, email) DO UPDATE SET
            first_name = COALESCE(EXCLUDED.first_name, leads.first_name),
            last_name = COALESCE(EXCLUDED.last_name, leads.last_name),
            phone = COALESCE(EXCLUDED.phone, leads.phone),
            lead_company = COALESCE(EXCLUDED.lead_company, leads.lead_company),
            updated_at = EXCLUDED.updated_at
        RETURNING id, email
        """
    
    @staticmethod
    def get_lead_by_id() -> str:
        return """
        SELECT 
            id, company_id, email, first_name, last_name, phone, lead_company,
            job_title, industry, country, city, state,
            source, status, priority, score, 
            tags, custom_fields, 
            assigned_to, created_by, created_at, updated_at,
            last_contacted_at, converted_at
        FROM leads 
        WHERE id = $1
        """
    
    @staticmethod
    def get_leads_by_ids() -> str:
        return """
        SELECT 
            id, company_id, email, first_name, last_name, phone, lead_company,
            job_title, industry, country, city, state,
            source, status, priority, score, 
            tags, custom_fields, 
            assigned_to, created_by, created_at, updated_at
        FROM leads 
        WHERE id = ANY($1)
        """
    
    @staticmethod
    def get_leads_filtered() -> str:
        return """
        SELECT 
            id, company_id, email, first_name, last_name, phone, lead_company,
            job_title, industry, country, city, state,
            source, status, priority, score, 
            tags, custom_fields, 
            assigned_to, created_by, created_at, updated_at
        FROM leads 
        WHERE 1=1
        {filters}
        ORDER BY {sort_by} {sort_order}
        LIMIT $1 OFFSET $2
        """
    
    @staticmethod
    def count_leads_filtered() -> str:
        return """
        SELECT COUNT(*) 
        FROM leads 
        WHERE 1=1
        {filters}
        """
    
    @staticmethod
    def update_lead_score() -> str:
        return """
        UPDATE leads 
        SET score = $1, updated_at = $2
        WHERE id = $3
        RETURNING id, score
        """
    
    @staticmethod
    def bulk_update_lead_scores() -> str:
        return """
        UPDATE leads AS l
        SET score = c.score, updated_at = c.updated_at
        FROM (VALUES $1) AS c(id, score, updated_at)
        WHERE c.id = l.id
        RETURNING l.id, l.score
        """
    
    @staticmethod
    def update_lead_status() -> str:
        return """
        UPDATE leads 
        SET status = $1, updated_at = $2
        WHERE id = $3
        RETURNING id, status
        """
    
    @staticmethod
    def bulk_update_leads() -> str:
        return """
        UPDATE leads 
        SET {updates}, updated_at = $1
        WHERE id = ANY($2)
        RETURNING id
        """
    
    @staticmethod
    def assign_leads() -> str:
        return """
        UPDATE leads 
        SET assigned_to = $1, updated_at = $2
        WHERE id = ANY($3)
        RETURNING id, assigned_to
        """
    
    @staticmethod
    def merge_leads() -> str:
        return """
        WITH deleted AS (
            DELETE FROM leads 
            WHERE id = ANY($1)
            RETURNING *
        )
        UPDATE leads 
        SET {merge_fields}, updated_at = $2
        WHERE id = $3
        RETURNING id
        """
    
    @staticmethod
    def create_segment() -> str:
        return """
        INSERT INTO lead_segments (
            id, company_id, name, description, criteria, created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7
        ) RETURNING id
        """
    
    @staticmethod
    def get_segments() -> str:
        return """
        SELECT 
            s.id, s.name, s.description, s.criteria,
            s.created_at, s.updated_at,
            COUNT(DISTINCT lss.lead_id) as lead_count
        FROM lead_segments s
        LEFT JOIN lead_segment_members lss ON s.id = lss.segment_id
        WHERE s.company_id = $1
        GROUP BY s.id
        ORDER BY s.created_at DESC
        """
    
    @staticmethod
    def add_leads_to_segment() -> str:
        return """
        INSERT INTO lead_segment_members (lead_id, segment_id, added_at)
        VALUES $1
        ON CONFLICT (lead_id, segment_id) DO NOTHING
        """
    
    @staticmethod
    def get_segment_leads() -> str:
        return """
        SELECT l.*
        FROM leads l
        JOIN lead_segment_members lss ON l.id = lss.lead_id
        WHERE lss.segment_id = $1
        """
    
    @staticmethod
    def create_nurturing_campaign() -> str:
        return """
        INSERT INTO nurturing_campaigns (
            id, name, description, trigger, schedule, steps, active, created_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8
        ) RETURNING id
        """
    
    @staticmethod
    def enroll_in_nurturing() -> str:
        return """
        INSERT INTO lead_nurturing_enrollment (
            lead_id, campaign_id, enrolled_at, current_step, status
        ) VALUES $1
        ON CONFLICT (lead_id, campaign_id) DO UPDATE SET
            enrolled_at = EXCLUDED.enrolled_at,
            status = 'active'
        """
    
    @staticmethod
    def record_lead_event() -> str:
        return """
        INSERT INTO lead_events (
            id, lead_id, event_type, event_data, created_at
        ) VALUES (
            $1, $2, $3, $4, $5
        )
        """
    
    @staticmethod
    def get_lead_journey() -> str:
        return """
        SELECT 
            le.event_type, le.event_data, le.created_at,
            l.status, l.score, l.assigned_to
        FROM lead_events le
        JOIN leads l ON l.id = le.lead_id
        WHERE le.lead_id = $1
        ORDER BY le.created_at DESC
        """
    
    @staticmethod
    def get_lead_duplicates() -> str:
        return """
        SELECT id, email, first_name, last_name, lead_company, company_id, score
        FROM leads
        WHERE LOWER(email) = LOWER($1)
           OR (LOWER(first_name) = LOWER($2) AND LOWER(last_name) = LOWER($3))
           OR (phone = $4 AND phone IS NOT NULL)
        """
    
    @staticmethod
    def cleanse_lead_data() -> str:
        return """
        UPDATE leads 
        SET email = LOWER(TRIM(email)),
            first_name = INITCAP(TRIM(first_name)),
            last_name = INITCAP(TRIM(last_name)),
            phone = REGEXP_REPLACE(phone, '[^0-9+]', '', 'g'),
            updated_at = $1
        WHERE id = ANY($2)
        RETURNING id
        """
    
    @staticmethod
    def get_lead_stats() -> str:
        return """
        SELECT 
            status, COUNT(*) as count,
            AVG(score) as avg_score,
            COUNT(DISTINCT assigned_to) as assigned_agents
        FROM leads
        WHERE created_at >= $1 AND created_at <= $2
        GROUP BY status
        """