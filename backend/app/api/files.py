"""
File Upload API Endpoints - Frontend Compatible

Matches the frontend API client expectations:
- POST /api/files/{chat_id}/upload
- GET /api/files/{chat_id}/attachments
- GET /api/files/download/{path}
"""

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
import logging
import uuid
from datetime import datetime

from app.config import settings
from app.ingestion import ExcelParser, get_normalizer
from app.core import get_dataframe_registry, get_sheet_index
from app.memory import get_chat_memory

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory attachment storage (for demo - use database in production)
_attachments: Dict[str, List[Dict[str, Any]]] = {}


# ============================================================================
# Request/Response Models
# ============================================================================

class SheetInfo(BaseModel):
    """Sheet info matching frontend expectations."""
    name: str
    index: int
    row_count: int
    column_count: int
    columns: List[str]


class Attachment(BaseModel):
    """Attachment model matching frontend expectations."""
    id: str
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    status: str
    sheets: List[SheetInfo]


class UploadResponse(BaseModel):
    """Response model for file upload matching frontend expectations."""
    success: bool
    attachments: List[Attachment]
    total_sheets: int
    total_rows: int


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/{chat_id}/upload", response_model=UploadResponse)
async def upload_files(
    chat_id: str,
    files: List[UploadFile] = File(...),
):
    """
    Upload Excel or CSV files for analysis.
    
    Supports:
    - .csv
    - .xls
    - .xlsx
    - .xlsm
    """
    attachments = []
    total_sheets = 0
    total_rows = 0
    
    for file in files:
        # Validate file type
        if not file.filename:
            continue
        
        extension = file.filename.split(".")[-1].lower()
        if f".{extension}" not in settings.SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: .{extension}. Supported: {', '.join(settings.SUPPORTED_EXTENSIONS)}"
            )
        
        # Validate file size
        content = await file.read()
        size_bytes = len(content)
        size_mb = size_bytes / (1024 * 1024)
        
        if size_mb > settings.MAX_FILE_SIZE_MB:
            raise HTTPException(
                status_code=400,
                detail=f"File too large: {size_mb:.1f}MB. Maximum: {settings.MAX_FILE_SIZE_MB}MB"
            )
        
        try:
            # Parse file
            parser = ExcelParser()
            parsed = parser.parse_bytes(content, file.filename)
            
            if not parsed.sheets:
                raise HTTPException(status_code=400, detail="No data found in file")
            
            # Generate IDs
            file_id = str(uuid.uuid4())
            
            # Get registries
            df_registry = get_dataframe_registry()
            sheet_index = get_sheet_index()
            normalizer = get_normalizer()
            
            # Register all sheets
            sheet_info_list = []
            
            for sheet in parsed.sheets:
                # Normalize data
                df_normalized, changes = normalizer.normalize(sheet.dataframe)
                
                # Register DataFrame
                df_registry.register(
                    chat_id=chat_id,
                    file_id=file_id,
                    sheet_name=sheet.name,
                    dataframe=df_normalized,
                    sheet_index=sheet.index,
                    file_name=file.filename,
                )
                
                # Index for metadata
                sheet_index.index_dataframe(
                    chat_id=chat_id,
                    file_id=file_id,
                    file_name=file.filename,
                    sheet_name=sheet.name,
                    sheet_index=sheet.index,
                    df=df_normalized,
                )
                
                sheet_info = SheetInfo(
                    name=sheet.name,
                    index=sheet.index + 1,  # 1-indexed for users
                    row_count=len(df_normalized),
                    column_count=len(df_normalized.columns),
                    columns=list(df_normalized.columns)[:20],  # First 20 columns
                )
                sheet_info_list.append(sheet_info)
                total_rows += len(df_normalized)
                
                logger.info(f"Registered sheet '{sheet.name}': {len(df_normalized)} rows")
            
            # Create attachment
            attachment = Attachment(
                id=file_id,
                filename=file_id + "_" + file.filename,
                original_filename=file.filename,
                file_type=extension,
                file_size=size_bytes,
                status="processed",
                sheets=sheet_info_list,
            )
            attachments.append(attachment)
            total_sheets += len(sheet_info_list)
            
            # Store attachment info
            if chat_id not in _attachments:
                _attachments[chat_id] = []
            _attachments[chat_id].append(attachment.model_dump())
            
            # Update memory with file context
            memory = get_chat_memory(chat_id)
            memory.set_file_context(
                file_id=file_id,
                file_name=file.filename,
                sheets=[
                    {"name": s.name, "row_count": s.row_count}
                    for s in sheet_info_list
                ],
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"File upload error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    return UploadResponse(
        success=True,
        attachments=attachments,
        total_sheets=total_sheets,
        total_rows=total_rows,
    )


@router.get("/{chat_id}/attachments", response_model=List[Attachment])
async def list_attachments(chat_id: str):
    """List all attachments for a chat session."""
    attachments = _attachments.get(chat_id, [])
    return [Attachment(**a) for a in attachments]


@router.get("/download/{path:path}")
async def download_file(path: str):
    """Download an exported file."""
    from fastapi.responses import FileResponse
    from pathlib import Path
    
    export_dir = Path(settings.EXPORT_DIR)
    file_path = export_dir / path
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    
    # Security check - make sure path is within export dir
    if not file_path.resolve().is_relative_to(export_dir.resolve()):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="text/csv",
    )
