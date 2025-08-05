from fastapi import APIRouter, HTTPException, Depends, Path, Body
from typing import List, Dict, Any
from app.models.schemas import CompanyCreate, CompanyUpdate, Company, UserResponse
from handlers.company_handler import CompanyHandler
from middleware.auth_middleware import get_current_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/company", tags=["companies"])
company_handler = CompanyHandler()

@router.get("/user/{user_id}", response_model=List[Company])
async def get_all_companies_for_user(
    user_id: str = Path(..., description="User ID to get companies for"),
    current_user: dict = Depends(get_current_user)
):
    try:
        companies = await company_handler.get_all_companies_for_user(user_id)
        return companies
    except Exception as e:
        logger.error(f"Error in get_all_companies_for_user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/me", response_model=Company)
async def get_company_by_current_user(
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler)
):
    try:
        user_id = current_user.id
        company = await company_handler.get_company_by_user(user_id)
        return company
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error in get_company_by_current_user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/by-user/{user_id}", response_model=List[Company])
async def get_companies_by_user_id(
    user_id: str = Path(..., description="User ID"),
    current_user: dict = Depends(get_current_user)
):
    try:
        companies = await company_handler.get_companies_by_user_id(user_id)
        return companies
    except Exception as e:
        logger.error(f"Error in get_companies_by_user_id: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/create", response_model=Company, status_code=201)
async def create_company(
    company_data: CompanyCreate,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler)
):
    try:
        logger.info(f"Creating company for user: {current_user.id}")
        logger.info(f"Company data received: {company_data.dict()}")
        
        user_id = current_user.id
        company = await company_handler.create_company(company_data, user_id)
        
        logger.info(f"Company created successfully: {company.get('id')}")
        return company
        
    except ValueError as e:
        logger.error(f"ValueError in create_company: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in create_company: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/create-or-update", response_model=Company)
async def create_or_update_company(
    company_data: CompanyCreate = Body(...),
    current_user: UserResponse = Depends(get_current_user)
):
    try:
        logger.info(f"Received create-or-update request for user: {current_user.id}")
        logger.info(f"Company data: {company_data.dict()}")
        
        user_id = current_user.id
        company = await company_handler.create_or_update_company(company_data, user_id)
        
        logger.info(f"Successfully created/updated company: {company.get('id')}")
        return company
    except ValueError as e:
        logger.error(f"ValueError in create_or_update_company: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in create_or_update_company: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{company_id}", response_model=Company)
async def update_company(
    company_id: str = Path(..., description="Company ID"),
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
    company_data: CompanyUpdate = Body(...)
):
    try:
        user_id = current_user.id
        company = await company_handler.update_company(company_id, company_data, user_id)
        return company
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error in update_company: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{company_id}", status_code=204)
async def delete_company(
    company_id: str = Path(..., description="Company ID"),
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = current_user.id
        await company_handler.delete_company(company_id, user_id)
        return None
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error in delete_company: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{company_id}/regenerate-api-key")
async def regenerate_api_key(
    company_id: str = Path(..., description="Company ID"),
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = current_user.id
        result = await company_handler.regenerate_api_key(company_id, user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error in regenerate_api_key: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
