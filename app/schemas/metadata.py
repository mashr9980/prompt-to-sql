from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class MetadataUploadRequest(BaseModel):
    metadata: Dict[str, Any] = Field(..., description="Complete metadata JSON with tables and analysis")
    
    class Config:
        json_schema_extra = {
            "example": {
                "metadata": {
                    "database_type": "Microsoft SQL Server",
                    "analysis_timestamp": "2025-06-17T09:11:30.013073",
                    "total_tables": 200,
                    "processed_tables": 200
                },
                "tables": [
                    {
                        "schema": {
                            "table_name": "users",
                            "columns": [
                                {
                                    "name": "id",
                                    "type": "INTEGER",
                                    "nullable": False,
                                    "default": None,
                                    "autoincrement": True
                                }
                            ],
                            "primary_keys": ["id"],
                            "foreign_keys": [],
                            "sample_data": []
                        },
                        "llm_analysis": {
                            "purpose": "Stores user information",
                            "data_patterns": [],
                            "relationships": [],
                            "observations": []
                        }
                    }
                ]
            }
        }


class MetadataUploadResponse(BaseModel):
    success: bool = Field(..., description="Whether the upload was successful")
    processed_tables: Optional[int] = Field(None, description="Number of tables processed")
    total_tables: Optional[int] = Field(None, description="Total tables in metadata")
    upload_time: Optional[str] = Field(None, description="Upload timestamp")
    message: str = Field(..., description="Status message")
    error: Optional[str] = Field(None, description="Error message if failed")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "processed_tables": 200,
                "total_tables": 200,
                "upload_time": "2025-06-17T09:11:30.013073",
                "message": "Metadata processed successfully. 200 tables indexed.",
                "error": None
            }
        }


class BusinessLogicUploadResponse(BaseModel):
    success: bool = Field(..., description="Whether the upload was successful")
    processed_chunks: Optional[int] = Field(None, description="Number of chunks processed")
    total_chunks: Optional[int] = Field(None, description="Total chunks created")
    upload_time: Optional[str] = Field(None, description="Upload timestamp")
    message: str = Field(..., description="Status message")
    error: Optional[str] = Field(None, description="Error message if failed")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "processed_chunks": 15,
                "total_chunks": 15,
                "upload_time": "2025-06-17T09:11:30.013073",
                "message": "Business logic processed successfully. 15 chunks indexed.",
                "error": None
            }
        }


class KnowledgeBaseStatus(BaseModel):
    metadata_loaded: bool = Field(..., description="Whether metadata is loaded")
    upload_time: Optional[str] = Field(None, description="Last upload time")
    total_tables: int = Field(..., description="Number of tables in knowledge base")
    index_built: bool = Field(..., description="Whether vector index is built")
    
    class Config:
        json_schema_extra = {
            "example": {
                "metadata_loaded": True,
                "upload_time": "2025-06-17T09:11:30.013073",
                "total_tables": 200,
                "index_built": True
            }
        }


class BusinessLogicStatus(BaseModel):
    business_logic_loaded: bool = Field(..., description="Whether business logic is loaded")
    upload_time: Optional[str] = Field(None, description="Last upload time")
    total_chunks: int = Field(..., description="Number of business logic chunks")
    combined_with_schema: bool = Field(..., description="Whether combined with schema data")
    
    class Config:
        json_schema_extra = {
            "example": {
                "business_logic_loaded": True,
                "upload_time": "2025-06-17T09:11:30.013073",
                "total_chunks": 15,
                "combined_with_schema": True
            }
        }