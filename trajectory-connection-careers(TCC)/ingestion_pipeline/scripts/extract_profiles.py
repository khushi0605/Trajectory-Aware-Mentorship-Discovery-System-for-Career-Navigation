import os
import json
import asyncio
import fitz  # PyMuPDF
from pdf2image import convert_from_path
import pytesseract
from pydantic import BaseModel, Field

import sys
# Ensure src is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.llm import LLMClient, load_llm_config

SYSTEM_PROMPT = """You are a profile extractor. Read the resume and extract:
1. A 1-sentence summary of the user's background and core skills.
2. A 1-sentence aspirational career goal inferred from their experience.
Return ONLY valid JSON matching this schema:
{
  "background_and_skills": "string",
  "goal": "string"
}"""

class ProfileExtraction(BaseModel):
    background_and_skills: str = Field(description="A 1-sentence summary of the user's background and core skills.")
    goal: str = Field(description="A 1-sentence aspirational career goal inferred from their experience.")

async def extract_profiles():
    llm_config = load_llm_config()
    llm_client = LLMClient(llm_config)
    
    resume_dir = "test_data/resumes"
    batch_inputs_path = "test_data/batch_inputs.json"
    if os.path.exists(batch_inputs_path):
        with open(batch_inputs_path, "r") as f:
            results = json.load(f)
        processed_ids = {item["profile_id"] for item in results}
        print(f"Loaded {len(results)} existing profiles.")
    else:
        results = []
        processed_ids = set()
    
    if not os.path.exists(resume_dir):
        print(f"Directory {resume_dir} not found.")
        return

    print(f"Reading resumes from {resume_dir}...")
    
    for filename in sorted(os.listdir(resume_dir)):
        if filename.endswith(".pdf"):
            profile_id = filename.replace(".pdf", "")
            if profile_id in processed_ids:
                print(f"Skipping {filename}, already processed.")
                continue

            filepath = os.path.join(resume_dir, filename)
            # 1. Attempt standard PyMuPDF Extraction
            try:
                doc = fitz.open(filepath)
                text_pages = [page.get_text() for page in doc]
                text = " ".join(text_pages).strip()
                doc.close()
                
                # 2. OCR Fallback for Image-Based PDFs
                if not text:
                    print(f"No text found in {filename}. Attempting OCR fallback...")
                    try:
                        images = convert_from_path(filepath)
                        ocr_text = []
                        for img in images:
                            ocr_text.append(pytesseract.image_to_string(img))
                        text = " ".join(ocr_text).strip()
                    except Exception as ocr_e:
                        print(f"OCR failed for {filename}: {ocr_e}")
                        text = ""
                        
            except Exception as e:
                print(f"ERROR reading {filename}: {e}")
                text = ""
            
            # 3. Call LLM to extract structured data
            if text:
                print(f"Successfully extracted text for {filename}. Generating profile...")
                try:
                    extracted_json = await llm_client.generate_structured(
                        system_prompt=SYSTEM_PROMPT,
                        user_prompt=f"Resume Text:\n{text}",
                        response_schema=ProfileExtraction,
                        temperature=0.1
                    ) 
                    
                    # Handling if extracted_json is a Pydantic model vs a dict
                    if hasattr(extracted_json, 'model_dump'):
                        data = extracted_json.model_dump()
                    elif hasattr(extracted_json, 'dict'):
                        data = extracted_json.dict()
                    else:
                        data = extracted_json if isinstance(extracted_json, dict) else {}
                    
                    results.append({
                        "profile_id": filename.replace(".pdf", ""),
                        "resume_path": filepath,
                        "resume_text": text,
                        "background_and_skills": data.get("background_and_skills", ""),
                        "goal": data.get("goal", "")
                    })
                except Exception as e:
                    print(f"Error processing LLM extraction for {filename}: {e}")
                    results.append({
                        "profile_id": filename.replace(".pdf", ""),
                        "resume_path": filepath,
                        "resume_text": text,
                        "background_and_skills": "LLM EXTRACTION FAILED",
                        "goal": "LLM EXTRACTION FAILED"
                    })
            else:
                results.append({
                    "profile_id": filename.replace(".pdf", ""),
                    "resume_path": filepath,
                    "resume_text": "",
                    "background_and_skills": "EXTRACTION FAILED",
                    "goal": "EXTRACTION FAILED"
                })
            
    with open("test_data/batch_inputs.json", "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"Finished extracting {len(results)} profiles. Saved to test_data/batch_inputs.json")

if __name__ == "__main__":
    asyncio.run(extract_profiles())
