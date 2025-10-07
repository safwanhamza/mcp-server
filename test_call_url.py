import requests
resp = requests.post(
    "https://6c874e39-fa4d-48c9-ac74-1371e5189141-00-1m0rv7aeuz964.pike.replit.dev/process-epoc",
    json={
        "openaiFileIdRefs": [{
            "file_name": "test.csv",
            "mime_type": "text/csv",
            "download_link": "https://github.com/safwanhamza/mcp-server/blob/main/input.csv"
        }]
    }
)
print(resp.status_code, resp.text



