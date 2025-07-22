import os
import csv
import json
from flask import Flask, request, jsonify, render_template, send_from_directory
from dotenv import load_dotenv
from extraction import extract_po_content, extract_contract_content, extract_specific_fields_with_openai

load_dotenv()

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "docx"}

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/po")
def po():
    return render_template("purchase_order.html")


@app.route("/contract")
def contract():
    return render_template("contract.html")


@app.route("/upload_po", methods=["POST"])
def upload_po():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = file.filename
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        # Extract raw content (this also saves to extracted.json with mandatory fields)
        raw_content = extract_po_content(file_path)

        # Read the mandatory fields that were saved to extracted.json
        try:
            with open("extracted.json") as f:
                data = json.load(f)
            mandatory_fields = data.get("mandatory_fields", [])
        except Exception as e:
            print(f"Error reading extracted.json: {e}")
            mandatory_fields = []

        # Extract the mandatory fields using OpenAI
        if mandatory_fields:
            mandatory_result = extract_specific_fields_with_openai(raw_content, mandatory_fields)
            try:
                mandatory_result_json = json.loads(mandatory_result)
            except Exception as e:
                print(f"Error parsing OpenAI result: {e}")
                mandatory_result_json = {}
        else:
            mandatory_result_json = {}

        return jsonify({
            "message": "PO uploaded!",
            "pdf_url": f"/uploads/{filename}",
            "mandatory_fields": mandatory_result_json
        })

    return jsonify({"error": "Invalid file type"}), 400


@app.route("/upload_contract", methods=["POST"])
def upload_contract():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
 
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400
 
    if file and allowed_file(file.filename):
        filename = file.filename
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)
 
        # Extract raw content (this also saves to extracted.json with mandatory fields)
        raw_content = extract_contract_content(file_path)
 
        # Read the mandatory fields that were saved to extracted.json
        try:
            with open("extracted.json") as f:
                data = json.load(f)
            mandatory_fields = data.get("mandatory_fields", [])
        except Exception as e:
            print(f"Error reading extracted.json: {e}")
            mandatory_fields = []

        # Extract the mandatory fields using OpenAI
        if mandatory_fields:
            mandatory_result = extract_specific_fields_with_openai(raw_content, mandatory_fields)
            try:
                mandatory_result_json = json.loads(mandatory_result)
            except Exception as e:
                print(f"Error parsing OpenAI result: {e}")
                mandatory_result_json = {}
        else:
            mandatory_result_json = {}
 
        return jsonify({
            "message": "Contract uploaded!",
            "pdf_url": f"/uploads/{filename}",
            "mandatory_fields": mandatory_result_json
        })
 
    return jsonify({"error": "Invalid file type"}), 400

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/get_fields", methods=["POST"])
def get_fields():
    requested_fields = request.json.get("fields", [])

    try:
        with open("extracted.json") as f:
            data = json.load(f)
    except Exception:
        return jsonify({"error": "No extracted data found"}), 400

    raw_text = data.get("raw", "")

    if not raw_text:
        return jsonify({"fields_output": {}})

    if not requested_fields:
        return jsonify({"fields_output": {}})

    extracted = extract_specific_fields_with_openai(raw_text, requested_fields)

    try:
        extracted_dict = json.loads(extracted)
    except Exception as e:
        print(f"Error parsing extracted fields: {e}")
        return jsonify({"fields_output": {}})

    # Update the extracted.json with the new fields
    data["fields"] = extracted_dict
    with open("extracted.json", "w") as f:
        json.dump(data, f, indent=2)

    return jsonify({"fields_output": extracted_dict})

@app.route("/save", methods=["POST"])
def save():
    # Load extracted data
    try:
        with open("extracted.json") as f:
            data = json.load(f)
    except Exception:
        return jsonify({"error": "No extracted data found"}), 400

    fields_data = data.get("fields", {})
    if not fields_data:
        return jsonify({"error": "No fields to save"}), 400

    # Prepare CSV rows
    rows = []
    for key, field_data in fields_data.items():
        if isinstance(field_data, dict):
            # Handle both 'values' (new) and 'value' (old) for compatibility
            values = field_data.get("values", [])
            if not values and "value" in field_data:
                values = [field_data["value"]]

            row = {
                "Field Name": key,
                "Value": "\\n".join(map(str, values)) if values else "N/A",
                "Matched Text": ", ".join(field_data.get("matched_text", []))
            }
        else:
            row = {
                "Field Name": key,
                "Value": "N/A",
                "Matched Text": ""
            }
        rows.append(row)

    # Define CSV header
    fieldnames = ["Field Name", "Value", "Matched Text"]

    # Write to CSV (append mode)
    csv_file = "saved_data.csv"
    file_exists = os.path.isfile(csv_file)

    with open(csv_file, mode="a", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        # Write header only if file is new
        if not file_exists:
            writer.writeheader()

        for row in rows:
            writer.writerow(row)

    return jsonify({"message": "Data saved to saved_data.csv!"})

if __name__ == "__main__":
    app.run(debug=True)