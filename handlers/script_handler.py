import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import HTTPException
import logging
from app.db.postgres_client import get_db_connection
from app.models.scripts import (
    Script, ScriptTemplate, ScriptVersion, ScriptFlow, ScriptNode,
    ScriptValidation, ScriptValidationResult, ScriptAnalytics,
    ScriptPublishRequest, ScriptAnalyticsRequest, ScriptStatus, NodeType
)
from uuid import UUID
from datetime import timedelta

logger = logging.getLogger(__name__)

class ScriptHandler:
    def __init__(self):
        pass

    async def get_templates(self, category: Optional[str] = None, 
                           tags: Optional[List[str]] = None) -> List[ScriptTemplate]:
        """Get all available script templates"""
        async with await get_db_connection() as conn:
            query = """
                SELECT * FROM script_templates 
                WHERE is_public = true
            """
            params = []
            param_count = 1
            
            if category:
                query += f" AND category = ${param_count}"
                params.append(category)
                param_count += 1
            
            if tags:
                query += f" AND tags && ${param_count}::text[]"
                params.append(tags)
                param_count += 1
            
            query += " ORDER BY created_at DESC"
            
            templates = await conn.fetch(query, *params)
            
            result = []
            for template in templates:
                template_dict = dict(template)
                # Parse JSON fields
                if template_dict.get('flow') and isinstance(template_dict['flow'], str):
                    template_dict['flow'] = json.loads(template_dict['flow'])
                if template_dict.get('tags') and isinstance(template_dict['tags'], str):
                    template_dict['tags'] = json.loads(template_dict['tags'])
                
                # Convert flow dict to ScriptFlow object
                if template_dict.get('flow'):
                    template_dict['flow'] = ScriptFlow(**template_dict['flow'])
                
                result.append(ScriptTemplate(**template_dict))
            
            return result
    
    async def create_template(self, template: ScriptTemplate, company_id: str) -> ScriptTemplate:
        """Create a new script template"""
        template_id = f"TMPL-{str(uuid.uuid4())[:8].upper()}"
        now = datetime.utcnow()
        
        async with await get_db_connection() as conn:
            await conn.execute(
                """
                INSERT INTO script_templates (
                    id, company_id, name, description, category, tags, 
                    flow, preview_image, is_public, created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11
                )
                """,
                template_id,
                company_id,
                template.name,
                template.description,
                template.category,
                json.dumps(template.tags),
                json.dumps(template.flow.dict()),
                template.preview_image,
                template.is_public,
                now,
                now
            )
        
        template.id = template_id
        template.created_at = now
        template.updated_at = now
        
        return template
    def convert_uuids_to_strings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert any UUID values to strings in a dictionary"""
        if not isinstance(data, dict):
            return data
            
        result = {}
        for key, value in data.items():
            if isinstance(value, UUID):
                result[key] = str(value)
            elif isinstance(value, dict):
                result[key] = self.convert_uuids_to_strings(value)
            elif isinstance(value, list):
                result[key] = [
                    self.convert_uuids_to_strings(item) if isinstance(item, dict)
                    else str(item) if isinstance(item, UUID)
                    else item
                    for item in value
                ]
            else:
                result[key] = value
        return result
    
    async def get_scripts(self, company_id: str, status: Optional[ScriptStatus] = None) -> List[Script]:
        """Get all scripts for a company"""
        async with await get_db_connection() as conn:
            query = "SELECT * FROM scripts WHERE company_id = $1"
            params = [company_id]
            
            if status:
                query += " AND status = $2"
                params.append(status.value)
            
            query += " ORDER BY updated_at DESC"
            
            scripts = await conn.fetch(query, *params)
            
            result = []
            for script in scripts:
                script_dict = dict(script)
                
                # Convert UUIDs to strings FIRST
                script_dict = self.convert_uuids_to_strings(script_dict)
                
                # Parse JSON fields
                if script_dict.get('flow') and isinstance(script_dict['flow'], str):
                    script_dict['flow'] = json.loads(script_dict['flow'])
                if script_dict.get('tags') and isinstance(script_dict['tags'], str):
                    script_dict['tags'] = json.loads(script_dict['tags'])
                if script_dict.get('metadata') and isinstance(script_dict['metadata'], str):
                    script_dict['metadata'] = json.loads(script_dict['metadata'])
                
                # Convert flow dict to ScriptFlow object
                if script_dict.get('flow'):
                    script_dict['flow'] = ScriptFlow(**script_dict['flow'])
                
                result.append(Script(**script_dict))
            
            return result
    
    async def get_script(self, script_id: str, company_id: str) -> Optional[Script]:
        """Get a single script by ID"""
        async with await get_db_connection() as conn:
            script = await conn.fetchrow(
                "SELECT * FROM scripts WHERE id = $1 AND company_id = $2",
                script_id, company_id
            )
            
            if not script:
                return None
            
            script_dict = dict(script)
            
            # Convert UUIDs to strings
            script_dict = self.convert_uuids_to_strings(script_dict)
            
            # Parse JSON fields
            if script_dict.get('flow') and isinstance(script_dict['flow'], str):
                script_dict['flow'] = json.loads(script_dict['flow'])
            if script_dict.get('tags') and isinstance(script_dict['tags'], str):
                script_dict['tags'] = json.loads(script_dict['tags'])
            if script_dict.get('metadata') and isinstance(script_dict['metadata'], str):
                script_dict['metadata'] = json.loads(script_dict['metadata'])
            
            # Convert flow dict to ScriptFlow object
            if script_dict.get('flow'):
                script_dict['flow'] = ScriptFlow(**script_dict['flow'])
            
            return Script(**script_dict)
    
    async def create_script(self, script: Script, company_id: str, user_id: str) -> Script:
        """Create a new script"""
        script_id = f"SCRIPT-{str(uuid.uuid4())[:8].upper()}"
        now = datetime.utcnow()
        
        # Ensure company_id is a string
        if isinstance(company_id, UUID):
            company_id = str(company_id)
        
        async with await get_db_connection() as conn:
            await conn.execute(
                """
                INSERT INTO scripts (
                    id, company_id, name, description, template_id, flow,
                    status, version, is_active, tags, metadata,
                    created_by, created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
                )
                """,
                script_id,
                company_id,
                script.name,
                script.description,
                script.template_id,
                json.dumps(script.flow.dict()),
                script.status.value,
                1,  # Start with version 1
                False,  # Not active by default
                json.dumps(script.tags),
                json.dumps(script.metadata),
                user_id,
                now,
                now
            )
            
            # Create initial version
            await self._create_version(conn, script_id, script.flow, 1, user_id)
        
        script.id = script_id
        script.company_id = company_id
        script.version = 1
        script.created_by = user_id
        script.created_at = now
        script.updated_at = now
        
        return script
    
    async def update_script(self, script_id: str, updates: Dict[str, Any], 
                           company_id: str, user_id: str) -> Script:
        """Update an existing script"""
        # Ensure company_id is a string
        if isinstance(company_id, UUID):
            company_id = str(company_id)
            
        async with await get_db_connection() as conn:
            # Check if script exists
            existing = await conn.fetchrow(
                "SELECT * FROM scripts WHERE id = $1 AND company_id = $2",
                script_id, company_id
            )
            
            if not existing:
                raise HTTPException(status_code=404, detail="Script not found")
            
            # Build update query
            set_clauses = []
            values = []
            param_count = 1
            
            for field, value in updates.items():
                if field in ['id', 'company_id', 'created_at', 'created_by']:
                    continue  # Skip fields that shouldn't be updated
                
                if field in ['flow', 'tags', 'metadata']:
                    set_clauses.append(f"{field} = ${param_count}::jsonb")
                    if field == 'flow' and isinstance(value, ScriptFlow):
                        values.append(json.dumps(value.dict()))
                    else:
                        values.append(json.dumps(value))
                elif field == 'status' and isinstance(value, ScriptStatus):
                    set_clauses.append(f"{field} = ${param_count}")
                    values.append(value.value)
                else:
                    set_clauses.append(f"{field} = ${param_count}")
                    values.append(value)
                param_count += 1
            
            if not set_clauses:
                return await self.get_script(script_id, company_id)
            
            # Add updated_at
            set_clauses.append(f"updated_at = ${param_count}")
            values.append(datetime.utcnow())
            param_count += 1
            
            # Add WHERE clause parameters
            values.extend([script_id, company_id])
            
            query = f"""
                UPDATE scripts 
                SET {', '.join(set_clauses)}
                WHERE id = ${param_count} AND company_id = ${param_count + 1}
                RETURNING *
            """
            
            result = await conn.fetchrow(query, *values)
            
            # If flow was updated, create a new version
            if 'flow' in updates:
                new_version = existing['version'] + 1
                await self._create_version(
                    conn, script_id, 
                    updates['flow'] if isinstance(updates['flow'], ScriptFlow) else ScriptFlow(**updates['flow']),
                    new_version, user_id
                )
                
                # Update version number
                await conn.execute(
                    "UPDATE scripts SET version = $1 WHERE id = $2",
                    new_version, script_id
                )
            
            return await self.get_script(script_id, company_id)
    
    async def publish_script(self, script_id: str, request: ScriptPublishRequest,
                            company_id: str, user_id: str) -> Dict[str, Any]:
        """Publish a script"""
        # Ensure company_id is a string
        if isinstance(company_id, UUID):
            company_id = str(company_id)
            
        async with await get_db_connection() as conn:
            # Get current script
            script = await conn.fetchrow(
                "SELECT * FROM scripts WHERE id = $1 AND company_id = $2",
                script_id, company_id
            )
            
            if not script:
                raise HTTPException(status_code=404, detail="Script not found")
            
            if script['status'] == ScriptStatus.PUBLISHED.value:
                raise HTTPException(status_code=400, detail="Script is already published")
            
            publish_time = request.schedule_publish or datetime.utcnow()
            
            # Update script status
            await conn.execute(
                """
                UPDATE scripts 
                SET status = $1, published_at = $2, is_active = true, updated_at = $3
                WHERE id = $4 AND company_id = $5
                """,
                ScriptStatus.PUBLISHED.value,
                publish_time,
                datetime.utcnow(),
                script_id,
                company_id
            )
            
            # Update version status
            await conn.execute(
                """
                UPDATE script_versions 
                SET status = $1, published_at = $2
                WHERE script_id = $3 AND version = $4
                """,
                ScriptStatus.PUBLISHED.value,
                publish_time,
                script_id,
                script['version']
            )
            
            # Record publish event
            await conn.execute(
                """
                INSERT INTO script_events (
                    id, script_id, event_type, event_data, created_by, created_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6
                )
                """,
                f"EVT-{str(uuid.uuid4())[:8].upper()}",
                script_id,
                'published',
                json.dumps({
                    'version': script['version'],
                    'notes': request.version_notes,
                    'scheduled': request.schedule_publish is not None
                }),
                user_id,
                datetime.utcnow()
            )
            
            return {
                "success": True,
                "script_id": script_id,
                "version": script['version'],
                "published_at": publish_time.isoformat(),
                "message": f"Script successfully {'scheduled for publishing' if request.schedule_publish else 'published'}"
            }
    
    async def get_script_versions(self, script_id: str, company_id: str) -> List[ScriptVersion]:
        """Get all versions of a script"""
        # Ensure company_id is a string
        if isinstance(company_id, UUID):
            company_id = str(company_id)
            
        async with await get_db_connection() as conn:
            # Verify script belongs to company
            script = await conn.fetchrow(
                "SELECT id FROM scripts WHERE id = $1 AND company_id = $2",
                script_id, company_id
            )
            
            if not script:
                raise HTTPException(status_code=404, detail="Script not found")
            
            versions = await conn.fetch(
                """
                SELECT * FROM script_versions 
                WHERE script_id = $1 
                ORDER BY version DESC
                """,
                script_id
            )
            
            result = []
            for version in versions:
                version_dict = dict(version)
                
                # Convert UUIDs to strings
                version_dict = self.convert_uuids_to_strings(version_dict)
                
                # Parse flow JSON
                if version_dict.get('flow') and isinstance(version_dict['flow'], str):
                    version_dict['flow'] = json.loads(version_dict['flow'])
                
                # Convert flow dict to ScriptFlow object
                if version_dict.get('flow'):
                    version_dict['flow'] = ScriptFlow(**version_dict['flow'])
                
                result.append(ScriptVersion(**version_dict))
            
            return result
    
    async def get_script_analytics(self, script_id: str, request: ScriptAnalyticsRequest,
                                  company_id: str) -> ScriptAnalytics:
        """Get analytics for a script"""
        # Ensure company_id is a string
        if isinstance(company_id, UUID):
            company_id = str(company_id)
            
        async with await get_db_connection() as conn:
            # Verify script belongs to company
            script = await conn.fetchrow(
                "SELECT * FROM scripts WHERE id = $1 AND company_id = $2",
                script_id, company_id
            )
            
            if not script:
                raise HTTPException(status_code=404, detail="Script not found")
            
            # Set date range
            end_date = request.end_date or datetime.utcnow()
            start_date = request.start_date or (end_date - timedelta(days=30))
            
            # Get execution metrics
            executions = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) as total_executions,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_completions,
                    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration_seconds
                FROM script_executions
                WHERE script_id = $1 
                    AND started_at >= $2 
                    AND started_at <= $3
                """,
                script_id, start_date, end_date
            )
            
            # Get node-level analytics
            node_analytics = await conn.fetch(
                """
                SELECT 
                    node_id,
                    COUNT(*) as visits,
                    AVG(duration_ms) as avg_duration_ms,
                    COUNT(CASE WHEN error_occurred THEN 1 END) as errors
                FROM script_node_executions
                WHERE script_id = $1 
                    AND executed_at >= $2 
                    AND executed_at <= $3
                GROUP BY node_id
                """,
                script_id, start_date, end_date
            )
            
            # Get drop-off points
            drop_offs = await conn.fetch(
                """
                SELECT 
                    last_node_id,
                    COUNT(*) as count
                FROM script_executions
                WHERE script_id = $1 
                    AND status = 'abandoned'
                    AND started_at >= $2 
                    AND started_at <= $3
                GROUP BY last_node_id
                ORDER BY count DESC
                LIMIT 10
                """,
                script_id, start_date, end_date
            )
            
            # Process node analytics
            node_metrics = {}
            for node in node_analytics:
                node_dict = dict(node)
                node_dict = self.convert_uuids_to_strings(node_dict)
                
                node_metrics[node_dict['node_id']] = {
                    'visits': node_dict['visits'],
                    'avg_duration_ms': float(node_dict['avg_duration_ms']) if node_dict['avg_duration_ms'] else 0,
                    'errors': node_dict['errors'],
                    'error_rate': (node_dict['errors'] / node_dict['visits'] * 100) if node_dict['visits'] > 0 else 0
                }
            
            # Process drop-off points
            drop_off_list = []
            for drop in drop_offs:
                drop_dict = dict(drop)
                drop_dict = self.convert_uuids_to_strings(drop_dict)
                drop_off_list.append({
                    'node_id': drop_dict['last_node_id'],
                    'count': drop_dict['count']
                })
            
            # Convert execution metrics
            exec_dict = dict(executions)
            exec_dict = self.convert_uuids_to_strings(exec_dict)
            
            return ScriptAnalytics(
                script_id=script_id,
                total_executions=exec_dict['total_executions'] or 0,
                successful_completions=exec_dict['successful_completions'] or 0,
                average_duration_seconds=float(exec_dict['avg_duration_seconds']) if exec_dict['avg_duration_seconds'] else 0,
                node_analytics=node_metrics,
                drop_off_points=drop_off_list,
                date_range={'start': start_date, 'end': end_date},
                performance_metrics={
                    'completion_rate': (exec_dict['successful_completions'] / exec_dict['total_executions'] * 100) 
                                     if exec_dict['total_executions'] > 0 else 0,
                    'abandonment_rate': ((exec_dict['total_executions'] - exec_dict['successful_completions']) / 
                                       exec_dict['total_executions'] * 100) 
                                      if exec_dict['total_executions'] > 0 else 0
                }
            )
    
    async def validate_script(self, validation: ScriptValidation) -> ScriptValidationResult:
        """Validate a script flow"""
        # This method doesn't interact with the database, so no UUID conversion needed
        errors = []
        warnings = []
        info = []
        
        flow = validation.flow
        
        # Validate connections
        if validation.validate_connections:
            node_ids = {node.id for node in flow.nodes}
            
            # Check for orphaned nodes
            connected_nodes = set()
            for node in flow.nodes:
                connected_nodes.update(node.connections)
            
            orphaned = node_ids - connected_nodes
            if orphaned and len(flow.nodes) > 1:  # Single node scripts are valid
                for node_id in orphaned:
                    node = next((n for n in flow.nodes if n.id == node_id), None)
                    if node and node.type != NodeType.START:
                        warnings.append({
                            "type": "orphaned_node",
                            "node_id": node_id,
                            "message": f"Node '{node.label}' is not connected to any other node"
                        })
            
            # Check for invalid connections
            for node in flow.nodes:
                for connection in node.connections:
                    if connection not in node_ids:
                        errors.append({
                            "type": "invalid_connection",
                            "node_id": node.id,
                            "target_id": connection,
                            "message": f"Node '{node.label}' references non-existent node '{connection}'"
                        })
            
            # Check for start and end nodes
            start_nodes = [n for n in flow.nodes if n.type == NodeType.START]
            end_nodes = [n for n in flow.nodes if n.type == NodeType.END]
            
            if not start_nodes:
                errors.append({
                    "type": "missing_start",
                    "message": "Script must have at least one START node"
                })
            elif len(start_nodes) > 1:
                warnings.append({
                    "type": "multiple_starts",
                    "message": "Script has multiple START nodes"
                })
            
            if not end_nodes:
                warnings.append({
                    "type": "missing_end",
                    "message": "Script should have at least one END node"
                })
        
        # Validate conditions
        if validation.validate_conditions:
            for node in flow.nodes:
                if node.type == NodeType.CONDITION and node.conditions:
                    if not node.conditions.get('expression'):
                        errors.append({
                            "type": "missing_condition",
                            "node_id": node.id,
                            "message": f"Condition node '{node.label}' missing expression"
                        })
                    
                    # Check for at least two branches
                    if len(node.connections) < 2:
                        warnings.append({
                            "type": "insufficient_branches",
                            "node_id": node.id,
                            "message": f"Condition node '{node.label}' should have at least 2 branches"
                        })
        
        # Validate variables
        if validation.validate_variables and flow.variables:
            used_vars = set()
            defined_vars = set(flow.variables.keys())
            
            # Check variable usage in nodes
            for node in flow.nodes:
                if node.content:
                    content_str = json.dumps(node.content)
                    # Simple variable detection (looking for {{variable}} pattern)
                    import re
                    vars_in_content = re.findall(r'\{\{(\w+)\}\}', content_str)
                    used_vars.update(vars_in_content)
            
            # Check for undefined variables
            undefined = used_vars - defined_vars
            for var in undefined:
                warnings.append({
                    "type": "undefined_variable",
                    "variable": var,
                    "message": f"Variable '{var}' is used but not defined"
                })
            
            # Check for unused variables
            unused = defined_vars - used_vars
            for var in unused:
                info.append({
                    "type": "unused_variable",
                    "variable": var,
                    "message": f"Variable '{var}' is defined but never used"
                })
        
        is_valid = len(errors) == 0
        
        return ScriptValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            info=info
        )
    
    async def _create_version(self, conn, script_id: str, flow: ScriptFlow, 
                            version: int, user_id: str):
        """Create a new script version"""
        version_id = f"VER-{str(uuid.uuid4())[:8].upper()}"
        
        # Ensure user_id is a string
        if isinstance(user_id, UUID):
            user_id = str(user_id)
        
        await conn.execute(
            """
            INSERT INTO script_versions (
                id, script_id, version, flow, status, created_by, created_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7
            )
            """,
            version_id,
            script_id,
            version,
            json.dumps(flow.dict()),
            ScriptStatus.DRAFT.value,
            user_id,
            datetime.utcnow()
        )