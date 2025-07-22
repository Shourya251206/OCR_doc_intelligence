import os
import base64
import json
import logging
from dotenv import load_dotenv

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential

from openai import AzureOpenAI
import numpy as np
import faiss

# Load env
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# Document Intelligence
ENDPOINT = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
KEY = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")

MODEL_ID_INVOICE = os.getenv("MODEL_ID_INVOICE")
MODEL_ID_CONTRACT = os.getenv("MODEL_ID_CONTRACT")

# OpenAI Chat Completion
OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
OPENAI_KEY = os.getenv("AZURE_OPENAI_API_KEY")
OPENAI_VERSION = os.getenv("AZURE_OPENAI_VERSION")
OPENAI_MODEL = os.getenv("AZURE_OPENAI_MODEL")

# OpenAI Embedding
EMBEDDING_ENDPOINT = os.getenv("AZURE_OPENAI_EMBEDDING_ENDPOINT")
EMBEDDING_KEY = os.getenv("AZURE_OPENAI_EMBEDDING_KEY")
EMBEDDING_MODEL = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
EMBEDDING_VERSION = os.getenv("AZURE_OPENAI_EMBEDDING_API_VERSION")

# Clients
client = DocumentIntelligenceClient(
    endpoint=ENDPOINT,
    credential=AzureKeyCredential(KEY)
)

openai_client = AzureOpenAI(
    azure_endpoint=OPENAI_ENDPOINT,
    api_key=OPENAI_KEY,
    api_version=OPENAI_VERSION
)

embedding_client = AzureOpenAI(
    azure_endpoint=EMBEDDING_ENDPOINT,
    api_key=EMBEDDING_KEY,
    api_version=EMBEDDING_VERSION
)

EXTRACTED_JSON = "extracted.json"

def embed_text(text: str):
    logging.info(f"Embedding text: {text[:30]}...")
    response = embedding_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text
    )
    return np.array(response.data[0].embedding, dtype=np.float32)

def extract_po_content(file_path):
    logging.info(f"Extracting PO: {file_path}")
    with open(file_path, "rb") as f:
        base64_content = base64.b64encode(f.read()).decode("utf-8")

    poller = client.begin_analyze_document(
        model_id=MODEL_ID_INVOICE,
        body={"base64Source": base64_content}
    )

    result = poller.result()
    raw_content = result.content if hasattr(result, "content") else ""

    mandatory_fields = [
        "Purchase Order Number",
        "Purchase Order Date",
        "Customer Name",
        "Customer Address",
        "Grand Total",
        "Tax",
        "Subtotal",
        "Supplier Name",
        "Currency"
    ]

    with open(EXTRACTED_JSON, "w") as f:
        json.dump({"raw": raw_content, "mandatory_fields": mandatory_fields}, f, indent=2)

    return raw_content

def extract_contract_content(file_path):
    logging.info(f"Extracting Contract: {file_path}")
    with open(file_path, "rb") as f:
        base64_content = base64.b64encode(f.read()).decode("utf-8")

    poller = client.begin_analyze_document(
        model_id=MODEL_ID_CONTRACT,
        body={"base64Source": base64_content}
    )

    result = poller.result()

    raw_lines = []
    embeddings = []

    for page in result.pages:
        for line in page.lines:
            content = line.content.strip()
            raw_lines.append(content)
            emb = embed_text(content)
            embeddings.append(emb)

    raw_content = "\n".join(raw_lines)

    index = faiss.IndexFlatL2(len(embeddings[0]))
    index.add(np.vstack(embeddings))

    faiss.write_index(index, "contract_faiss.index")

    mandatory_fields = [
        "Licensor",
        "Licensee",
        "Registration Number",
        "Effective Date",
        "Termination Date",
        "Governing Law",
        "Jurisdiction"
    ]

    with open(EXTRACTED_JSON, "w") as f:
        json.dump({"raw": raw_content, "mandatory_fields": mandatory_fields}, f, indent=2)

    logging.info(f"Layout + FAISS index saved. Lines: {len(raw_lines)}")
    return raw_content

def extract_specific_fields_with_openai(raw_text, fields):
    logging.info(f"Extracting fields: {fields}")
    if not fields:
        return json.dumps({})

    prompt = f"""
You are a hyper-vigilant data extraction AI.
**DO NOT GUESS.**

For each target field, extract the **entire section** of the document that corresponds to that field, including all subpoints (such as (a), (b), (c), etc.) and any related text. 
If the section contains multiple subpoints, return all of them as an array of values.

**Raw:**
---
{raw_text}
---

**Fields to find:**
{fields}

**Output JSON:**
{{
  "FieldName": {{
    "values": ["...all relevant text blocks for this field, including subpoints..."],
    "matched_label": "...the section header or label as found in the text...",
    "matched_text": ["...the exact matched text(s) for each value..."]
  }}
}}
"""

    response = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You are a precise extraction AI. Only return if you are sure."},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        response_format={"type": "json_object"}
    )

    result = response.choices[0].message.content.strip()
    try:
        result_json = json.loads(result)

        # ✅ If LLM only gave a single value, auto-wrap in array for 'values'
        for field_name, data in result_json.items():
            if isinstance(data, dict):
                if "values" in data and not isinstance(data["values"], list):
                    data["values"] = [data["values"]]
                if not data.get("matched_label"):
                    data["matched_label"] = field_name
                if data.get("values") and not data.get("matched_text"):
                    data["matched_text"] = data["values"]

        return json.dumps(result_json)

    except Exception as e:
        logging.warning(f"Post-process error: {e}")
        return "{}"

