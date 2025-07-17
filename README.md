Search files...
Here's a comprehensive understanding of your project and the likely cause of the PDF highlighting issue:

---

## **Project Overview**

### **Purpose**
- The project extracts structured data from documents (Purchase Orders, Contracts) using Azure Document Intelligence and OpenAI, and displays the results in a web interface.
- It also highlights the extracted data directly on the PDF preview in the browser.

### **Main Components**
1. **Backend (Flask)**
   - `app.py`: Handles file uploads, extraction requests, and serves the web app.
   - `extraction.py`: Contains logic for extracting raw text from documents (via Azure Document Intelligence) and extracting specific fields (via OpenAI).
   - `extracted.json`: Stores the latest extraction results and raw text.
   - `saved_data.csv`: Stores exported results.

2. **Frontend**
   - `templates/index.html`: Main web interface for uploading, querying, and viewing PDFs/results.
   - `static/js/main.js`: Handles PDF rendering (using PDF.js), user interactions, and highlighting logic.
   - `static/css/styles.css`: Styles for the web app.

---

## **How Extraction & Highlighting Work**

### **Extraction Flow**
1. **User uploads a document** (`/upload_po` or `/upload_contract`).
2. **Backend**:
   - Saves the file.
   - Extracts raw text using Azure Document Intelligence.
   - Extracts mandatory fields using OpenAI (with a strict prompt to avoid hallucination).
   - Stores results in `extracted.json`.
   - Returns the PDF URL and extracted fields to the frontend.
3. **Frontend**:
   - Renders the PDF using PDF.js.
   - Displays extracted fields.
   - When a user clicks a field, it attempts to highlight the corresponding text in the PDF.

### **Highlighting Logic**
- The frontend uses the `matched_text` value for each field (the exact string as found in the document).
- When a result is clicked, it calls `highlightAllMatches(text, ...)` in `main.js`, which:
  - Searches the PDF's text layer for spans matching the extracted value.
  - Highlights all matches.


## **Summary Diagram**


<img width="1812" height="884" alt="Screenshot 2025-07-17 122830" src="https://github.com/user-attachments/assets/7da5de85-ca9c-43a6-8f19-d754a136f607" />
