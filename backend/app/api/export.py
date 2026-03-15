"""
Export API Endpoints

Handles:
- CSV/Excel file download
- Export status
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
import logging

from app.config import settings
from app.tools import create_export_tool

logger = logging.getLogger(__name__)

router = APIRouter()


class ExportRequest(BaseModel):
    """Request model for export."""
    chat_id: str
    sheet_name: Optional[str] = None
    filename: Optional[str] = None


class ExportResponse(BaseModel):
    """Response model for export."""
    success: bool
    filename: str
    rows_exported: int
    download_url: str


@router.post("/csv", response_model=ExportResponse)
async def export_csv(request: ExportRequest):
    """Export a sheet to CSV."""
    try:
        export_tool = create_export_tool(request.chat_id)
        
        result = export_tool.execute(
            action="export_csv",
            params={
                "sheet_name": request.sheet_name,
                "filename": request.filename,
            }
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Export failed"))
        
        return ExportResponse(
            success=True,
            filename=result["filename"],
            rows_exported=result["rows_exported"],
            download_url=result["download_url"],
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Export error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{filename}")
async def download_file(filename: str):
    """Download an exported file."""
    try:
        export_dir = Path(settings.EXPORT_DIR)
        file_path = export_dir / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {filename}")
        
        # Security check - make sure path is within export dir
        if not file_path.resolve().is_relative_to(export_dir.resolve()):
            raise HTTPException(status_code=403, detail="Access denied")
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="text/csv",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Download error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
