from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum

class ScriptStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    TESTING = "testing"

class NodeType(str, Enum):
    START = "start"
    END = "end"
    MESSAGE = "message"
    QUESTION = "question"
    CONDITION = "condition"
    ACTION = "action"
    WEBHOOK = "webhook"
    TRANSFER = "transfer"
    WAIT = "wait"
    LOOP = "loop"

class ScriptNode(BaseModel):
    id: str
    type: NodeType
    label: str
    content: Optional[Dict[str, Any]] = {}
    position: Dict[str, float]  # x, y coordinates
    connections: List[str] = []  # IDs of connected nodes
    conditions: Optional[Dict[str, Any]] = None
    actions: Optional[List[Dict[str, Any]]] = []
    metadata: Optional[Dict[str, Any]] = {}

class ScriptFlow(BaseModel):
    nodes: List[ScriptNode]
    edges: List[Dict[str, Any]]  # Connection definitions
    variables: Optional[Dict[str, Any]] = {}
    settings: Optional[Dict[str, Any]] = {}

class ScriptTemplate(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    category: str
    tags: List[str] = []
    flow: ScriptFlow
    preview_image: Optional[str] = None
    is_public: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class Script(BaseModel):
    id: Optional[str] = None
    company_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    template_id: Optional[str] = None
    flow: ScriptFlow
    status: ScriptStatus = ScriptStatus.DRAFT
    version: int = 1
    is_active: bool = False
    tags: List[str] = []
    metadata: Dict[str, Any] = {}
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    published_at: Optional[datetime] = None

class ScriptVersion(BaseModel):
    id: Optional[str] = None
    script_id: str
    version: int
    flow: ScriptFlow
    status: ScriptStatus
    changes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    published_at: Optional[datetime] = None

class ScriptValidation(BaseModel):
    flow: ScriptFlow
    validate_connections: bool = True
    validate_conditions: bool = True
    validate_variables: bool = True

class ScriptValidationResult(BaseModel):
    is_valid: bool
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    info: List[Dict[str, Any]] = []

class ScriptAnalytics(BaseModel):
    script_id: str
    total_executions: int = 0
    successful_completions: int = 0
    average_duration_seconds: float = 0
    node_analytics: Dict[str, Dict[str, Any]] = {}  # node_id -> metrics
    drop_off_points: List[Dict[str, Any]] = []
    user_paths: List[Dict[str, Any]] = []
    date_range: Optional[Dict[str, datetime]] = None
    performance_metrics: Dict[str, Any] = {}

class ScriptPublishRequest(BaseModel):
    version_notes: Optional[str] = None
    notify_users: bool = False
    schedule_publish: Optional[datetime] = None

class ScriptAnalyticsRequest(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    metrics: List[str] = ["executions", "completions", "duration", "drop_offs"]
    group_by: Optional[str] = "day"