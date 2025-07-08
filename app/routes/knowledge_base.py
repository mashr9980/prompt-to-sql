import json
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse

from app.schemas.metadata import MetadataUploadResponse, KnowledgeBaseStatus
from app.services.text_to_sql import TextToSQLService
from app.core.dependencies import get_text_to_sql_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-base", tags=["Knowledge Base"])


@router.post("/upload-file", response_model=MetadataUploadResponse, summary="Upload metadata JSON file")
async def upload_metadata_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="JSON file containing database metadata"),
    service: TextToSQLService = Depends(get_text_to_sql_service)
) -> MetadataUploadResponse:
    try:
        if not file.filename.endswith('.json'):
            raise HTTPException(
                status_code=400,
                detail="Only JSON files are allowed"
            )
        
        if not hasattr(service, 'enhanced_schema_store'):
            raise HTTPException(
                status_code=500,
                detail="Enhanced schema store not available"
            )
        
        contents = await file.read()
        
        try:
            metadata_json = json.loads(contents.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid JSON format: {str(e)}"
            )
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail="File encoding not supported. Please use UTF-8 encoded JSON file."
            )
        
        if "metadata" not in metadata_json or "tables" not in metadata_json:
            raise HTTPException(
                status_code=400,
                detail="Invalid file structure. Expected 'metadata' and 'tables' keys in JSON."
            )
        
        total_tables = len(metadata_json.get("tables", []))
        
        background_tasks.add_task(
            process_metadata_file_background,
            service.enhanced_schema_store,
            metadata_json,
            file.filename
        )
        
        logger.info(f"Started processing metadata file: {file.filename} with {total_tables} tables")
        
        return MetadataUploadResponse(
            success=True,
            message=f"Metadata file '{file.filename}' upload started. Processing {total_tables} tables in background...",
            processed_tables=None,
            total_tables=total_tables,
            upload_time=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process uploaded file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process uploaded file: {str(e)}"
        )


@router.post("/upload-business-logic", summary="Upload business logic text file")
async def upload_business_logic_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Text file containing business logic rules"),
    service: TextToSQLService = Depends(get_text_to_sql_service)
):
    try:
        if not file.filename.endswith('.txt'):
            raise HTTPException(
                status_code=400,
                detail="Only TXT files are allowed"
            )
        
        if not hasattr(service, 'enhanced_schema_store'):
            raise HTTPException(
                status_code=500,
                detail="Enhanced schema store not available"
            )
        
        contents = await file.read()
        
        try:
            file_content = contents.decode('utf-8')
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail="File encoding not supported. Please use UTF-8 encoded text file."
            )
        
        if not file_content.strip():
            raise HTTPException(
                status_code=400,
                detail="File is empty. Please provide a file with business logic content."
            )
        
        background_tasks.add_task(
            process_business_logic_background,
            service.enhanced_schema_store,
            file_content,
            file.filename
        )
        
        logger.info(f"Started processing business logic file: {file.filename}")
        
        return {
            "success": True,
            "message": f"Business logic file '{file.filename}' upload started. Processing in background...",
            "filename": file.filename,
            "content_length": len(file_content)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process uploaded business logic file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process uploaded file: {str(e)}"
        )


@router.get("/status", response_model=KnowledgeBaseStatus, summary="Get knowledge base status")
async def get_knowledge_base_status(
    service: TextToSQLService = Depends(get_text_to_sql_service)
) -> KnowledgeBaseStatus:
    try:
        if not hasattr(service, 'enhanced_schema_store'):
            return KnowledgeBaseStatus(
                metadata_loaded=False,
                upload_time=None,
                total_tables=0,
                index_built=False
            )
        
        status = service.enhanced_schema_store.get_status()
        
        return KnowledgeBaseStatus(
            metadata_loaded=status["metadata_loaded"],
            upload_time=status["upload_time"],
            total_tables=status["total_tables"],
            index_built=status["index_built"]
        )
        
    except Exception as e:
        logger.error(f"Failed to get knowledge base status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get knowledge base status: {str(e)}"
        )


@router.get("/business-logic/status", summary="Get business logic status")
async def get_business_logic_status(
    service: TextToSQLService = Depends(get_text_to_sql_service)
):
    try:
        if not hasattr(service, 'enhanced_schema_store'):
            return {
                "business_logic_loaded": False,
                "upload_time": None,
                "total_chunks": 0,
                "combined_with_schema": False
            }
        
        status = service.enhanced_schema_store.get_status()
        
        return {
            "business_logic_loaded": status["business_logic_loaded"],
            "upload_time": status["business_logic_upload_time"],
            "total_chunks": status["total_business_logic_chunks"],
            "combined_with_schema": status["metadata_loaded"] and status["business_logic_loaded"]
        }
        
    except Exception as e:
        logger.error(f"Failed to get business logic status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get business logic status: {str(e)}"
        )


@router.get("/tables/{table_name}", summary="Get detailed table information")
async def get_table_details(
    table_name: str,
    service: TextToSQLService = Depends(get_text_to_sql_service)
):
    try:
        if not hasattr(service, 'enhanced_schema_store'):
            raise HTTPException(
                status_code=404,
                detail="Enhanced schema store not available"
            )
        
        if not service.enhanced_schema_store.is_metadata_loaded:
            raise HTTPException(
                status_code=404,
                detail="No metadata loaded. Please upload metadata file first."
            )
        
        table_details = service.enhanced_schema_store.get_table_details(table_name)
        
        if not table_details:
            raise HTTPException(
                status_code=404,
                detail=f"Table '{table_name}' not found in knowledge base"
            )
        
        return {
            "table_name": table_name,
            "details": table_details,
            "found": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get table details for {table_name}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get table details: {str(e)}"
        )


@router.post("/search", summary="Search tables using vector similarity")
async def search_tables(
    query: str,
    limit: int = 5,
    service: TextToSQLService = Depends(get_text_to_sql_service)
):
    try:
        if not hasattr(service, 'enhanced_schema_store'):
            raise HTTPException(
                status_code=404,
                detail="Enhanced schema store not available"
            )
        
        if not service.enhanced_schema_store.is_metadata_loaded:
            raise HTTPException(
                status_code=404,
                detail="No metadata loaded. Please upload metadata file first."
            )
        
        results = service.enhanced_schema_store.search(query, k=limit)
        
        formatted_results = []
        for table_name, schema_text, metadata in results:
            formatted_results.append({
                "table_name": table_name,
                "schema_summary": schema_text[:500] + "..." if len(schema_text) > 500 else schema_text,
                "purpose": metadata.get("llm_analysis", {}).get("purpose", ""),
                "data_patterns": metadata.get("llm_analysis", {}).get("data_patterns", []),
                "relationships": metadata.get("llm_analysis", {}).get("relationships", [])
            })
        
        return {
            "query": query,
            "results": formatted_results,
            "total_found": len(formatted_results),
            "search_method": "vector_similarity"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search tables: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to search tables: {str(e)}"
        )


@router.delete("/clear", summary="Clear knowledge base")
async def clear_knowledge_base(
    service: TextToSQLService = Depends(get_text_to_sql_service)
):
    try:
        if hasattr(service, 'enhanced_schema_store'):
            service.enhanced_schema_store.clear_all()
        
        return {
            "success": True,
            "message": "Knowledge base cleared successfully. System will use basic schema exploration."
        }
        
    except Exception as e:
        logger.error(f"Failed to clear knowledge base: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear knowledge base: {str(e)}"
        )


@router.get("/rebuild", summary="Rebuild vector index")
async def rebuild_vector_index(
    background_tasks: BackgroundTasks,
    service: TextToSQLService = Depends(get_text_to_sql_service)
):
    try:
        if not hasattr(service, 'enhanced_schema_store'):
            raise HTTPException(
                status_code=404,
                detail="Enhanced schema store not available"
            )
        
        if not service.enhanced_schema_store.is_metadata_loaded and not service.enhanced_schema_store.is_business_logic_loaded:
            raise HTTPException(
                status_code=404,
                detail="No metadata or business logic loaded. Please upload files first."
            )
        
        background_tasks.add_task(
            rebuild_index_background,
            service.enhanced_schema_store
        )
        
        return {
            "success": True,
            "message": "Vector index rebuild started in background"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start index rebuild: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start index rebuild: {str(e)}"
        )


def process_metadata_file_background(enhanced_schema_store, metadata_json, filename):
    try:
        logger.info(f"Starting background processing of file: {filename}")
        result = enhanced_schema_store.process_metadata(metadata_json)
        
        if result["success"]:
            logger.info(f"File processing completed: {result['message']}")
        else:
            logger.error(f"File processing failed: {result['error']}")
            
    except Exception as e:
        logger.error(f"Background file processing failed: {str(e)}")


def process_business_logic_background(enhanced_schema_store, file_content, filename):
    try:
        logger.info(f"Starting background processing of business logic file: {filename}")
        result = enhanced_schema_store.process_business_logic_file(file_content, filename)
        
        if result["success"]:
            logger.info(f"Business logic processing completed: {result['message']}")
        else:
            logger.error(f"Business logic processing failed: {result['error']}")
            
    except Exception as e:
        logger.error(f"Background business logic processing failed: {str(e)}")


def rebuild_index_background(enhanced_schema_store):
    try:
        logger.info("Starting vector index rebuild")
        enhanced_schema_store.rebuild_index()
        logger.info("Vector index rebuild completed")
    except Exception as e:
        logger.error(f"Vector index rebuild failed: {str(e)}")