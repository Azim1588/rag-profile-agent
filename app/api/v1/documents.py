"""Document management endpoints."""
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_database
from app.schemas.document import DocumentResponse, DocumentListResponse

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    db: AsyncSession = Depends(get_database),
):
    """List all documents."""
    # TODO: Implement document listing
    pass


@router.post("/", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_database),
):
    """Upload a new document."""
    # TODO: Implement document upload
    pass


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_database),
):
    """Get a specific document."""
    # TODO: Implement document retrieval
    pass


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_database),
):
    """Delete a document."""
    # TODO: Implement document deletion
    pass

