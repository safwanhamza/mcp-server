# uk-epc-data-retrieval

## How It Works

1. **Upload CSV**: User uploads a CSV file (with at least address and postcode columns) via a Custom GPT or direct request.
2. **API Receives File Reference**: The API receives an OpenAI file reference, downloads the file, and processes it exactly as uploaded (no reformatting).
3. **Address Matching**: Each property address is cleaned and matched to EPC certificates using advanced fuzzy logic.
4. **EPC Data Retrieval**: For each postcode, the API fetches all relevant EPC certificates (domestic and non-domestic) with pagination.
5. **Result Generation**: The API generates a processed CSV with EPC data appended, and a summary of the results.
6. **Download**: The user receives a summary and a secure download link for the processed file.

---

## API Endpoints

### `POST /process-epc`

**Description**: Process a property data file and append EPC data.

**Request** (OpenAI file reference, recommended):
```
{
  "openaiFileIdRefs": [
    {
      "download_link": "https://files.oaiusercontent.com/file-...csv"
    }
  ]
}
```

**Response**:
```
{
  "status": "success",
  "summary": {
    "processed_records": 50,
    "valid_records": 45,
    "success_rate": "90.0%",
    "domestic_matches": 40,
    "non_domestic_matches": 5,
    "unmatched_addresses": 5,
    "average_match_score": "92.3"
  },
  "file_id": "uuid",
  "filename": "epc_results_uuid.csv"
}
```

---

### `GET /download/`

**Description**: Download the processed CSV file by its unique ID.

**Response**: Returns the processed CSV as a file attachment.

Output files will be downloaded via  ```https://your-server-url/download/{file_id}) ```
Note: replace your-server-url with exact address in system prompt.

---

### `GET /health`

**Description**: Health check endpoint.

**Response**:
```
{
  "status": "API is running",
  "version": "1.0.0",
  "endpoints": {
    "POST /process-epc": "Process CSV file",
    "GET /download/": "Download processed file"
  }
}
```

---

## Input CSV Requirements

- Must include at least **address** or **property** and **postcode** columns (case-insensitive, flexible naming).
- Additional columns (e.g., city, property type) are supported but not required.
- Handles inconsistent formatting, extra columns, and missing fields robustly.

---

## Example Usage

**With OpenAI Custom GPT:**
- Upload your CSV file via the GPT interface.
- The GPT sends a file reference to this API.
- Receive a summary and download link for your EPC-processed file.

**Direct API Call (for testing):**
```
curl -X POST http://localhost:5000/process-epc \
  -H "Content-Type: application/json" \
  -d '{"openaiFileIdRefs": [{"download_link": "https://files.oaiusercontent.com/file-...csv"}]}'
```

---

## Custom GPT Integration

- User uploads CSV file via GPT
- GPT sends file reference to /process-epc endpoint using the OpenAI Actions protocol
- API processes file and returns summary + file ID
- GPT provides download link to user: /download/<file_id>

 ### Example GPT Output
Processing Complete!

| Metric             | Value |
|--------------------|-------|
| Processed Records  | 50    |
| Valid EPCs         | 45    |
| Match Rate         | 90%   |

Download EPC Results - a button linking to https://your-api.com/download/<file_id>


## Deployment (API)

1. **Install dependencies:**
   ```
   pip install flask pandas requests fuzzywuzzy numpy
   ```

3. **Environment Variables:**
   Set your EPC API credentials in the as environment variables in  ```.env ```.

2. **Run the API:**
   ```
   python main.py
   ```

## Custom GPT
1. Create new custom GPT
2. In system Instructions place system prompt (available in config file, with updated file download url development pattern).
3. Create actions using provided action schema (update the server url with exact url of deployed API)
4. Add authentication of API server (if applicable)

---
