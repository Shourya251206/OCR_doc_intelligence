import os
import base64
import json
import logging
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

ENDPOINT = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
KEY = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")

# ✅ NEW: Separate model IDs for each doc type
MODEL_ID_INVOICE = os.getenv("MODEL_ID_INVOICE")
MODEL_ID_CONTRACT = os.getenv("MODEL_ID_CONTRACT")

OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
OPENAI_KEY = os.getenv("AZURE_OPENAI_API_KEY")
OPENAI_VERSION = os.getenv("AZURE_OPENAI_VERSION")
OPENAI_MODEL = os.getenv("AZURE_OPENAI_MODEL")

# Initialize clients
client = DocumentIntelligenceClient(
    endpoint=ENDPOINT,
    credential=AzureKeyCredential(KEY)
)

openai_client = AzureOpenAI(
    azure_endpoint=OPENAI_ENDPOINT,
    api_key=OPENAI_KEY,
    api_version=OPENAI_VERSION
)

EXTRACTED_JSON = "extracted.json"


def extract_po_content(file_path):
    logging.info(f"Starting Purchase Order extraction for: {file_path}")

    with open(file_path, "rb") as f:
        base64_content = base64.b64encode(f.read()).decode('utf-8')

    logging.info("Sending document to Azure Document Intelligence...")

    # ✅ Use INVOICE model
    poller = client.begin_analyze_document(
        model_id=MODEL_ID_INVOICE,
        body={"base64Source": base64_content}
    )

    result = poller.result()
    raw_content = result.content if hasattr(result, "content") else ""

    logging.info("Document analyzed successfully.")

    mandatory_fields = [
        "Purchase Order Number",
        "Purchase Order Date",
        "Customer Name",
        "Customer Address",
        "Grand Total",
        "Tax",
        "Subtotal",
        "Supplier Name",
        "Currency"  # Added Currency
    ]

    with open(EXTRACTED_JSON, "w") as f:
        json.dump({"raw": raw_content, "mandatory_fields": mandatory_fields}, f, indent=2)

    logging.info(f"Raw content and mandatory fields saved to {EXTRACTED_JSON}")

    return raw_content


def extract_contract_content(file_path):
    logging.info(f"Starting Contract extraction for: {file_path}")

    with open(file_path, "rb") as f:
        base64_content = base64.b64encode(f.read()).decode('utf-8')

    logging.info("Sending document to Azure Document Intelligence...")

    # ✅ Use CONTRACT model
    poller = client.begin_analyze_document(
        model_id=MODEL_ID_CONTRACT,
        body={"base64Source": base64_content}
    )

    result = poller.result()
    raw_content = result.content if hasattr(result, "content") else ""

    logging.info("Document analyzed successfully.")

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

    logging.info(f"Raw content and mandatory fields saved to {EXTRACTED_JSON}")

    return raw_content


def extract_specific_fields_with_openai(raw_text, fields):
    with open(EXTRACTED_JSON) as f:
        data = json.load(f)
    # Only use the fields requested by the user
    logging.info(f"Fields requested: {fields}")

    prompt = f"""
You are a hyper-vigilant data extraction AI. Your single most important rule is: **DO NOT INVENT, GUESS, OR HALLUCINATE INFORMATION.** If you are not 100% certain, do not include the field.

**Your Task:**
You will be given a list of "Target Concepts" and raw text. For each concept, you must perform the following steps:
1.  **Literal Search:** Search the text for a label that is a very close semantic match to the Target Concept. For example, for "Termination Date", a label like "End Date" is acceptable, but "Governing Law" is not.
2.  **Rejection Rule:** If you find a label that is conceptually similar but not a direct match (e.g., finding "Jurisdiction" when searching for "Distribution"), you **MUST REJECT IT** and not include it in your output.
3.  **Confidence Check:** Before including any field, ask yourself: "Am I absolutely certain this is the correct field?" If there is any doubt, omit it.
4.  **Matched Text Rule:** For each field, the `matched_text` array should ONLY include the exact value(s) found in the document for that field, as they appear in the document. Do NOT include the field name, label, or any surrounding text—only the value itself.

**Raw Document Text:**
---
{raw_text}
---

**Target Concepts to Extract:**
{fields}

**Required JSON Format:**
Your output MUST be a valid JSON object. Only include keys for the concepts you find with high confidence.
{{
  "Concept Name From List": {{
    "value": "The normalized value found",
    "matched_text": ["The exact value string(s) as they appear in the document"]
  }}
}}
"""

    logging.info("Sending ultra-strict extraction prompt to Azure OpenAI...")

    response = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You are a skeptical and precise data extraction engine. Your primary directive is to avoid making assumptions or inferring data that is not explicitly present."},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        response_format={"type": "json_object"}
    )

    logging.info("Received response from OpenAI.")
    result = response.choices[0].message.content.strip()
    logging.info(f"OpenAI raw output: {result[:200]}...")

    return result
