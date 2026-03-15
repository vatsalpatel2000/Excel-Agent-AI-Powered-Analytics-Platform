"""
Enrichment Tool - Company Classification

Adds sector, industry group, and other classifications to company data.
Uses LLM-based classification with optional external API integration.
"""

import asyncio
from typing import Dict, Any, Optional, List
import logging
import pandas as pd
from openai import AsyncOpenAI

from app.config import settings
from app.core import get_dataframe_registry, get_sheet_index

logger = logging.getLogger(__name__)

# Batch configuration
BATCH_SIZE = 50  # Companies per LLM call
MAX_CONCURRENT_BATCHES = 5  # Parallel API calls
MAX_RETRIES = 3


# Industry classification lookup (fast path)
KNOWN_COMPANIES = {
    "apple": {"sector": "Technology", "industry_group": "Consumer Electronics"},
    "microsoft": {"sector": "Technology", "industry_group": "Software"},
    "amazon": {"sector": "Consumer Discretionary", "industry_group": "Internet & Direct Marketing Retail"},
    "google": {"sector": "Technology", "industry_group": "Interactive Media & Services"},
    "alphabet": {"sector": "Technology", "industry_group": "Interactive Media & Services"},
    "meta": {"sector": "Technology", "industry_group": "Interactive Media & Services"},
    "facebook": {"sector": "Technology", "industry_group": "Interactive Media & Services"},
    "tesla": {"sector": "Consumer Discretionary", "industry_group": "Automobiles"},
    "nvidia": {"sector": "Technology", "industry_group": "Semiconductors"},
    "jpmorgan": {"sector": "Financials", "industry_group": "Banks"},
    "walmart": {"sector": "Consumer Staples", "industry_group": "Consumer Staples Distribution & Retail"},
    "berkshire": {"sector": "Financials", "industry_group": "Diversified Financials"},
    # Additional major companies
    "intel": {"sector": "Technology", "industry_group": "Semiconductors"},
    "amd": {"sector": "Technology", "industry_group": "Semiconductors"},
    "oracle": {"sector": "Technology", "industry_group": "Software"},
    "ibm": {"sector": "Technology", "industry_group": "IT Services"},
    "salesforce": {"sector": "Technology", "industry_group": "Software"},
    "adobe": {"sector": "Technology", "industry_group": "Software"},
    "netflix": {"sector": "Communication Services", "industry_group": "Entertainment"},
    "disney": {"sector": "Communication Services", "industry_group": "Entertainment"},
    "coca-cola": {"sector": "Consumer Staples", "industry_group": "Beverages"},
    "pepsi": {"sector": "Consumer Staples", "industry_group": "Beverages"},
    "johnson": {"sector": "Health Care", "industry_group": "Pharmaceuticals"},
    "pfizer": {"sector": "Health Care", "industry_group": "Pharmaceuticals"},
    "exxon": {"sector": "Energy", "industry_group": "Oil, Gas & Consumable Fuels"},
    "chevron": {"sector": "Energy", "industry_group": "Oil, Gas & Consumable Fuels"},
    "visa": {"sector": "Financials", "industry_group": "IT Services"},
    "mastercard": {"sector": "Financials", "industry_group": "IT Services"},
    "bank of america": {"sector": "Financials", "industry_group": "Banks"},
    "wells fargo": {"sector": "Financials", "industry_group": "Banks"},
    "goldman": {"sector": "Financials", "industry_group": "Capital Markets"},
    "morgan stanley": {"sector": "Financials", "industry_group": "Capital Markets"},
}

# Valid GICS sectors
GICS_SECTORS = [
    "Energy",
    "Materials",
    "Industrials",
    "Consumer Discretionary",
    "Consumer Staples",
    "Health Care",
    "Financials",
    "Information Technology",
    "Technology",
    "Communication Services",
    "Utilities",
    "Real Estate",
]


class EnrichmentTool:
    """
    Tool for enriching company data with classifications.
    
    Uses a cascade approach:
    1. Local cache lookup
    2. Pattern matching
    3. LLM classification (OpenAI)
    """
    
    def __init__(self, chat_id: str):
        self.chat_id = chat_id
        self.df_registry = get_dataframe_registry()
        self.sheet_index = get_sheet_index()
        # Only pass base_url if it's actually configured
        client_kwargs = {"api_key": settings.OPENAI_API_KEY}
        if settings.OPENAI_BASE_URL:
            client_kwargs["base_url"] = settings.OPENAI_BASE_URL
        self.client = AsyncOpenAI(**client_kwargs)

    
    async def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an enrichment action."""
        if action == "classify_companies":
            return await self._classify_companies(
                params.get("sheet_name"),
                params.get("company_column"),
            )
        elif action == "classify_single":
            return await self._classify_single(params.get("company_name", ""))
        elif action == "preview_enrichment":
            return await self._preview_enrichment(
                params.get("sheet_name"),
                params.get("company_column"),
            )
        else:
            return {"error": f"Unknown action: {action}"}
    
    async def _classify_companies(
        self,
        sheet_name: Optional[str],
        company_column: Optional[str],
    ) -> Dict[str, Any]:
        """Classify all companies in a sheet using BATCH processing."""
        # Get the dataframe
        df = self.df_registry.get(self.chat_id, sheet_name)
        
        if df is None:
            sheets = self.df_registry.get_all_sheets(self.chat_id)
            if sheets:
                sheet_name = sheets[0]
                df = self.df_registry.get(self.chat_id, sheet_name)
        
        if df is None:
            return {"error": "No data found"}
        
        # Find company column
        if not company_column:
            company_column = self._detect_company_column(df)
        
        if not company_column:
            return {
                "error": "Could not detect company column",
                "available_columns": list(df.columns),
                "suggestion": "Please specify the column containing company names",
            }
        
        if company_column not in df.columns:
            return {
                "error": f"Column '{company_column}' not found",
                "available_columns": list(df.columns),
            }
        
        # Get unique companies
        companies = df[company_column].dropna().unique().tolist()
        total_companies = len(companies)
        
        logger.info(f"Classifying {total_companies} companies from column {company_column}")
        
        # Step 1: Separate cached vs need-LLM companies
        classifications = {}
        companies_needing_llm = []
        
        for company in companies:
            cached = self._check_cache(str(company))
            if cached:
                classifications[company] = cached
            else:
                companies_needing_llm.append(str(company))
        
        logger.info(f"Cache hits: {len(classifications)}, Need LLM: {len(companies_needing_llm)}")
        
        # Step 2: Batch process companies needing LLM
        if companies_needing_llm:
            batches = [
                companies_needing_llm[i:i + BATCH_SIZE]
                for i in range(0, len(companies_needing_llm), BATCH_SIZE)
            ]
            
            logger.info(f"Processing {len(batches)} batches of up to {BATCH_SIZE} companies each")
            
            # Process batches with limited concurrency
            for i in range(0, len(batches), MAX_CONCURRENT_BATCHES):
                batch_group = batches[i:i + MAX_CONCURRENT_BATCHES]
                results = await asyncio.gather(
                    *[self._classify_batch(batch) for batch in batch_group],
                    return_exceptions=True
                )
                
                for result in results:
                    if isinstance(result, dict):
                        classifications.update(result)
                    elif isinstance(result, Exception):
                        logger.error(f"Batch failed: {result}")
        
        # Step 3: Add new columns to dataframe
        df_enriched = df.copy()
        df_enriched["Sector"] = df_enriched[company_column].apply(
            lambda x: classifications.get(x, {}).get("sector", "Unknown")
        )
        df_enriched["Industry_Group"] = df_enriched[company_column].apply(
            lambda x: classifications.get(x, {}).get("industry_group", "Unknown")
        )
        
        # Register the enriched dataframe
        enriched_sheet_name = f"{sheet_name}_enriched"
        self.df_registry.register(
            chat_id=self.chat_id,
            file_id="enriched",
            sheet_name=enriched_sheet_name,
            dataframe=df_enriched,
            sheet_index=999,
        )
        
        self.sheet_index.index_dataframe(
            chat_id=self.chat_id,
            file_id="enriched",
            file_name="enriched_data",
            sheet_name=enriched_sheet_name,
            sheet_index=999,
            df=df_enriched,
        )
        
        # Generate sample
        sample = df_enriched[[company_column, "Sector", "Industry_Group"]].head(5)
        sample_records = sample.to_dict(orient="records")
        
        return {
            "success": True,
            "total_companies": total_companies,
            "classified": len(classifications),
            "cache_hits": total_companies - len(companies_needing_llm),
            "llm_calls": len(companies_needing_llm) // BATCH_SIZE + (1 if len(companies_needing_llm) % BATCH_SIZE else 0),
            "columns_added": ["Sector", "Industry_Group"],
            "enriched_sheet": enriched_sheet_name,
            "sample": sample_records,
        }
    
    def _check_cache(self, company_name: str) -> Optional[Dict[str, Any]]:
        """Check if company is in local cache."""
        name_lower = company_name.lower().strip()
        
        for known, data in KNOWN_COMPANIES.items():
            if known in name_lower:
                return {
                    "sector": data["sector"],
                    "industry_group": data["industry_group"],
                    "source": "cache",
                    "confidence": 0.95,
                }
        return None

    async def _classify_batch(self, companies: List[str]) -> Dict[str, Dict[str, Any]]:
        """Classify a batch of companies in a SINGLE API call."""
        if not companies:
            return {}
        
        companies_list = "\n".join([f"{i+1}. {c}" for i, c in enumerate(companies)])
        
        prompt = f"""Classify these {len(companies)} companies into sector and industry group.

Valid sectors: {', '.join(GICS_SECTORS)}

Companies to classify:
{companies_list}

Respond with a JSON array (one object per company, in exact same order):
[
  {{"company": "exact company name", "sector": "...", "industry_group": "...", "confidence": 0.0-1.0}},
  ...
]

If you cannot classify a company, use "Unknown" for sector and industry_group with confidence 0.0.
IMPORTANT: Return exactly {len(companies)} objects in the same order as input."""

        for attempt in range(MAX_RETRIES):
            try:
                response = await self.client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a financial analyst. Classify companies into GICS sectors and industry groups. Always respond with valid JSON array."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=4000,  # Increased for batch response
                )
                
                import json
                content = response.choices[0].message.content.strip()
                
                # Extract JSON array from response
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                # Parse JSON response
                if content.startswith("["):
                    results = json.loads(content)
                    
                    # Build classifications dict
                    classifications = {}
                    for i, result in enumerate(results):
                        if i < len(companies):
                            # Use original company name as key
                            company = companies[i]
                            classifications[company] = {
                                "sector": result.get("sector", "Unknown"),
                                "industry_group": result.get("industry_group", "Unknown"),
                                "source": "llm_batch",
                                "confidence": result.get("confidence", 0.5),
                            }
                    
                    logger.info(f"Batch classified {len(classifications)} companies")
                    return classifications
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error on attempt {attempt + 1}: {e}")
            except Exception as e:
                logger.warning(f"Batch classification failed on attempt {attempt + 1}: {e}")
            
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
        
        # Fallback: return unknown for all
        logger.error(f"All retries failed for batch of {len(companies)} companies")
        return {
            company: {
                "sector": "Unknown",
                "industry_group": "Unknown",
                "source": "fallback",
                "confidence": 0.0,
            }
            for company in companies
        }

    
    async def _classify_single(self, company_name: str) -> Dict[str, Any]:
        """Classify a single company."""
        if not company_name:
            return {"error": "No company name provided"}
        
        name_lower = company_name.lower().strip()
        
        # Check local cache first
        for known, data in KNOWN_COMPANIES.items():
            if known in name_lower:
                return {
                    "success": True,
                    "company": company_name,
                    "sector": data["sector"],
                    "industry_group": data["industry_group"],
                    "source": "cache",
                    "confidence": 0.95,
                }
        
        # Use LLM for unknown companies
        try:
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are a financial analyst. Classify the company into sector and industry group.
                        
Valid sectors: {', '.join(GICS_SECTORS)}

Respond in JSON format:
{{"sector": "...", "industry_group": "...", "confidence": 0.0-1.0}}

If you cannot classify, use "Unknown" for both with confidence 0.0."""
                    },
                    {
                        "role": "user",
                        "content": f"Classify: {company_name}"
                    }
                ],
                temperature=0.1,
                max_tokens=100,
            )
            
            import json
            content = response.choices[0].message.content.strip()
            
            # Parse JSON response
            if content.startswith("{"):
                result = json.loads(content)
                return {
                    "success": True,
                    "company": company_name,
                    "sector": result.get("sector", "Unknown"),
                    "industry_group": result.get("industry_group", "Unknown"),
                    "source": "llm",
                    "confidence": result.get("confidence", 0.5),
                }
            
        except Exception as e:
            logger.warning(f"LLM classification failed for {company_name}: {e}")
        
        # Fallback
        return {
            "success": True,
            "company": company_name,
            "sector": "Unknown",
            "industry_group": "Unknown",
            "source": "fallback",
            "confidence": 0.0,
        }
    
    async def _preview_enrichment(
        self,
        sheet_name: Optional[str],
        company_column: Optional[str],
    ) -> Dict[str, Any]:
        """Preview enrichment for a few companies."""
        df = self.df_registry.get(self.chat_id, sheet_name)
        
        if df is None:
            sheets = self.df_registry.get_all_sheets(self.chat_id)
            if sheets:
                df = self.df_registry.get(self.chat_id, sheets[0])
        
        if df is None:
            return {"error": "No data found"}
        
        if not company_column:
            company_column = self._detect_company_column(df)
        
        if not company_column:
            return {"error": "Could not detect company column"}
        
        # Get first 3 companies
        companies = df[company_column].dropna().head(3).tolist()
        
        preview = []
        for company in companies:
            result = await self._classify_single(str(company))
            if result.get("success"):
                preview.append({
                    "company": str(company),
                    "sector": result.get("sector"),
                    "industry_group": result.get("industry_group"),
                })
        
        return {
            "success": True,
            "company_column": company_column,
            "preview": preview,
            "total_companies": len(df[company_column].dropna()),
        }
    
    def _detect_company_column(self, df: pd.DataFrame) -> Optional[str]:
        """Detect which column contains company names."""
        company_keywords = [
            "company", "name", "organization", "firm", "corp", "corporation",
            "business", "entity", "issuer", "ticker", "symbol"
        ]
        
        for col in df.columns:
            col_lower = col.lower()
            for keyword in company_keywords:
                if keyword in col_lower:
                    return col
        
        # Check first column if no match
        if len(df.columns) > 0:
            first_col = df.columns[0]
            # If it's object type with mostly unique values, likely company names
            if df[first_col].dtype == 'object':
                unique_ratio = df[first_col].nunique() / len(df)
                if unique_ratio > 0.5:
                    return first_col
        
        return None


def create_enrichment_tool(chat_id: str) -> EnrichmentTool:
    """Factory function to create an EnrichmentTool."""
    return EnrichmentTool(chat_id)
