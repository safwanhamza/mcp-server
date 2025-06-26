from flask import Flask, request, send_file, jsonify
import pandas as pd
import requests
import re
import os
import tempfile
from fuzzywuzzy import fuzz, process
import numpy as np
import uuid

app = Flask(__name__)

# Configuration
FIELD_MAPPING = {
    'CURRENT_ENERGY_RATING': 'current-energy-rating',
    'TOTAL_FLOOR_AREA': 'total-floor-area',
    'POTENTIAL_RATING': 'potential-energy-rating',
    'CO2_EMISSIONS': 'co2-emissions-current',
    'PROPERTY_TYPE': 'property-type',
    'BUILT_FORM': 'built-form',
    'CONSTRUCTION_AGE': 'construction-age-band',
    'MAIN_FUEL': 'main-fuel',
    'TENURE': 'tenure',
    'MAINS_GAS': 'mains-gas-flag',
    'SOLAR_WATER': 'solar-water-heating-flag',
    'MECH_VENTILATION': 'mechanical-ventilation'
}

NON_DOMESTIC_FIELD_MAP = {
    'BUILDING_REFERENCE': 'building-reference-number',
    'ENERGY_CONSUMPTION': 'energy-consumption-current',
    'RENEWABLES': 'renewables-percentage'
}

EPC_API_URL = "https://epc.opendatacommunities.org/api/v1"
API_EMAIL = "zachafron@proton.me"
API_KEY = "emFjaGFmcm9uQHByb3Rvbi5tZToxMjNhNzNmMzZlNzExZTU2ZDJjZTQxZDQ3NGM4NzA2MzQ5MTU3ZDMz"
HEADERS = {
    "Accept": "application/json",
    "Authorization": f"Basic {API_KEY}"
}

# Global storage for processed files (in-memory for demo)
file_store = {}

# Helper functions
def standardize_synonyms(address):
    synonym_map = {
        r'\bapartment\b': 'flat',
        r'\bapt\b': 'flat',
        r'\bunit\b': 'flat',
        r'\bflt\b': 'flat',
        r'\bfl\b': 'flat',
    }
    address = address.lower()
    for pattern, replacement in synonym_map.items():
        address = re.sub(pattern, replacement, address)
    return address.upper()

def preprocess_address(address):
    address = re.sub(r'\b(flat|apartment|apt|unit)\b', 'FL', address, flags=re.IGNORECASE)
    address = re.sub(r'(\d+)([A-Z])', r'\1 \2', address)
    address = re.sub(r'\b[A-Z]{2}\d{1,2}[A-Z]?\b', '', address)
    return address.upper().strip()

def build_full_address(cert):
    return ', '.join(
        filter(None, [
            cert.get('address1', ''),
            cert.get('address2', ''),
            cert.get('address3', '')
        ])
    ).upper()

def extract_flat_number(address):
    match = re.search(r'\b(FLAT|APARTMENT|APT|UNIT|FL)\s*(\w+)\b', address, re.IGNORECASE)
    return match.group(2).upper() if match else None

def fuzzy_match_address(input_address, certificates, input_postcode=None):
    input_std = standardize_synonyms(input_address)
    input_flat = extract_flat_number(input_std)

    candidates = []
    for cert in certificates:
        candidate_raw = build_full_address(cert)
        candidate_std = standardize_synonyms(candidate_raw)
        candidates.append((candidate_std, candidate_raw, cert))

    # 1. Full fuzzy matching
    best_match, score = process.extractOne(
        input_std,
        [c[0] for c in candidates],
        scorer=fuzz.token_sort_ratio
    )

    if score >= 85:
        match_candidate = next(c for c in candidates if c[0] == best_match)
        matched_cert = match_candidate[2]
        return matched_cert, score

    # 2. Flat number matching
    if input_flat:
        for candidate_std, candidate_raw, cert in candidates:
            if input_flat in candidate_std:
                return cert, 90

    # 3. Partial match
    if ',' not in input_std and len(input_std.split()) < 4:
        for candidate_std, candidate_raw, cert in candidates:
            if any(word in candidate_std for word in input_std.split()):
                return cert, 85

    return None, score

def fetch_epc_data(postcode, api_type):
    """Fetch EPC data with pagination and error handling"""
    url = f"{EPC_API_URL}/{api_type}/search"
    params = {"postcode": postcode.replace(" ", ""), "size": 5000}
    all_rows = []
    search_after = None

    while True:
        if search_after:
            params['search-after'] = search_after

        try:
            response = requests.get(
                url,
                headers=HEADERS,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            json_data = response.json()
            rows = json_data.get('rows', [])
            all_rows.extend(rows)

            # Get next page token
            search_after = response.headers.get('X-Next-Search-After')
            if not search_after:
                break

        except Exception as e:
            print(f"Error fetching {api_type} data for {postcode}: {str(e)}")
            break

    return all_rows

def process_epc_data(df):
    """Main processing workflow with chunked processing"""
    # Preprocess data
    df.columns = df.columns.str.strip()
    col_mapping = {}
    for col in df.columns:
        col_lower = col.lower()
        if 'property' in col_lower or 'address' in col_lower:
            col_mapping[col] = 'address'
        elif 'postcode' in col_lower:
            col_mapping[col] = 'postcode'
    df = df.rename(columns=col_mapping)

    if 'address' not in df.columns or 'postcode' not in df.columns:
        raise ValueError("CSV must contain 'address' and 'postcode' columns")

    df['cleaned_address'] = df['address'].apply(preprocess_address)
    df['cleaned_postcode'] = df['postcode'].str.replace(r'\s+', '', regex=True).str.upper()

    results = []
    postcodes = df['cleaned_postcode'].unique()

    for i, postcode in enumerate(postcodes):
        print(f"Processing postcode {i+1}/{len(postcodes)}: {postcode}")

        # Fetch EPC data
        domestic_certs = fetch_epc_data(postcode, "domestic")
        non_domestic_certs = fetch_epc_data(postcode, "non-domestic")
        combined_certs = domestic_certs + non_domestic_certs

        # Process addresses for this postcode
        for _, row in df[df['cleaned_postcode'] == postcode].iterrows():
            result = {
                'INPUT_ADDRESS': row['address'],
                'INPUT_POSTCODE': row['postcode'],
                'MATCHED_ADDRESS': '',
                'MATCH_SCORE': 0,
                'DATA_SOURCE': 'none',
                **{k: '' for k in FIELD_MAPPING}
            }

            if combined_certs:
                matched_cert, score = fuzzy_match_address(
                    row['cleaned_address'],
                    combined_certs,
                    input_postcode=row['cleaned_postcode']
                )
                result['MATCH_SCORE'] = score

                if matched_cert:
                    # Determine data source
                    api_type = 'domestic' if matched_cert in domestic_certs else 'non-domestic'
                    result['DATA_SOURCE'] = api_type

                    # Extract EPC fields
                    for field, source in FIELD_MAPPING.items():
                        result[field] = matched_cert.get(source, '')

                    # Add non-domestic fields if applicable
                    if api_type == 'non-domestic':
                        for field, source in NON_DOMESTIC_FIELD_MAP.items():
                            result[field] = matched_cert.get(source, '')

            results.append(result)

    return pd.DataFrame(results)

def generate_summary(result_df):
    """Generate processing summary report"""
    # Count valid energy ratings
    valid_rating_mask = result_df['CURRENT_ENERGY_RATING'].apply(
        lambda x: bool(re.match(r'^[A-G]$', str(x)))
    )

    # Count matches
    domestic_mask = result_df['DATA_SOURCE'] == 'domestic'
    non_domestic_mask = result_df['DATA_SOURCE'] == 'non-domestic'
    unmatched_mask = result_df['DATA_SOURCE'] == 'none'

    # Calculate average match score (only for matched records)
    matched_mask = ~unmatched_mask
    avg_score = result_df.loc[matched_mask, 'MATCH_SCORE'].mean()

    return {
        "processed_records": len(result_df),
        "valid_records": int(valid_rating_mask.sum()),
        "success_rate": f"{valid_rating_mask.sum()/len(result_df):.1%}",
        "domestic_matches": int(domestic_mask.sum()),
        "non_domestic_matches": int(non_domestic_mask.sum()),
        "unmatched_addresses": int(unmatched_mask.sum()),
        "average_match_score": f"{avg_score:.1f}" if not pd.isna(avg_score) else "N/A"
    }

@app.route('/process-epc', methods=['POST'])
def process_epc():
    """Endpoint for EPC processing"""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        # Generate unique file ID
        file_id = str(uuid.uuid4())
        output_filename = f"epc_results_{file_id}.csv"

        # Create temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as temp_file:
            file.save(temp_file.name)
            input_path = temp_file.name

        # Process data
        df = pd.read_csv(input_path)
        result_df = process_epc_data(df)

        # Save results
        output_path = os.path.join(tempfile.gettempdir(), output_filename)
        result_df.to_csv(output_path, index=False)

        # Store file reference
        file_store[file_id] = output_path

        # Generate summary
        summary = generate_summary(result_df)

        # Return summary and file ID
        return jsonify({
            "status": "success",
            "summary": summary,
            "file_id": file_id,
            "filename": output_filename
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/download/<file_id>', methods=['GET'])
def download_file(file_id):
    """Download processed file by ID"""
    if file_id not in file_store:
        return jsonify({"error": "File not found"}), 404

    file_path = file_store[file_id]
    return send_file(
        file_path,
        as_attachment=True,
        download_name=f"epc_results_{file_id}.csv",
        mimetype='text/csv'
    )

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "API is running",
        "version": "1.0.0",
        "endpoints": {
            "POST /process-epc": "Process CSV file",
            "GET /download/<file_id>": "Download processed file"
        }
    })

@app.route('/test-epc/<postcode>',methods=['GET'])
def test_epc(postcode):
    domestic = fetch_epc_data(postcode, "domestic")
    non_domestic = fetch_epc_data(postcode, "non-domestic")
    return jsonify({
        "postcode": postcode,
        "domestic_records": len(domestic),
        "non_domestic_records": len(non_domestic)
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
