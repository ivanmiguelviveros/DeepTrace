from flask import Flask, request, jsonify, render_template
import pandas as pd
import chardet
import os
import json
import datetime
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from dotenv import load_dotenv
from mcp_server import init_mcp_server, add_error_to_mcp, analyze_log_with_mcp, get_mcp_stats

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize MCP server
mcp_server = init_mcp_server()

# Database of known errors and solutions (would be stored in a real DB/Elasticsearch)
ERROR_DB = []

# Expected schema for validation
EXPECTED_COLUMNS = {
    'sales_data': ['id', 'date', 'product', 'amount', 'customer'],
    'user_data': ['user_id', 'name', 'email', 'created_at'],
    'inventory': ['product_id', 'name', 'stock', 'price']
}

# Get Zendesk credentials from environment variables
ZENDESK_SUBDOMAIN = os.getenv('ZENDESK_SUBDOMAIN', '')
ZENDESK_API_TOKEN = os.getenv('ZENDESK_API_TOKEN', '')
ZENDESK_USER = os.getenv('ZENDESK_USER', '')
ZENDESK_BASE = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2" if ZENDESK_SUBDOMAIN else ""

# Initialize TF-IDF vectorizer for log similarity
vectorizer = TfidfVectorizer(stop_words='english')

# Helper: detect encoding
def detect_encoding(file_path, n_bytes=10000):
    with open(file_path, 'rb') as f:
        raw = f.read(n_bytes)
    result = chardet.detect(raw)
    return result['encoding']

# Helper: add comment to Zendesk ticket
def add_comment(ticket_id, text, public=False):
    if not all([ZENDESK_SUBDOMAIN, ZENDESK_API_TOKEN, ZENDESK_USER]):
        return {"status": "error", "message": "Zendesk credentials not configured"}
    
    url = f"{ZENDESK_BASE}/tickets/{ticket_id}.json"
    data = {"ticket": {"comment": {"body": text, "public": public}}}
    try:
        resp = requests.put(url, json=data,
                            auth=(ZENDESK_USER, ZENDESK_API_TOKEN))
        resp.raise_for_status()
        return {"status": "success", "data": resp.json()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Helper: find similar logs in our database
def find_similar_logs(log_text, threshold=0.7):
    if not ERROR_DB:
        return None
    
    # Extract log texts from DB
    db_logs = [entry['log'] for entry in ERROR_DB]
    
    # Add the new log to create a combined corpus
    all_logs = db_logs + [log_text]
    
    # Create TF-IDF matrix
    try:
        tfidf_matrix = vectorizer.fit_transform(all_logs)
        
        # Get the last row (our query log)
        query_vector = tfidf_matrix[-1]
        
        # Calculate similarities with all other logs
        similarities = cosine_similarity(query_vector, tfidf_matrix[:-1])[0]
        
        # Find the most similar log
        best_match_idx = np.argmax(similarities)
        best_match_score = similarities[best_match_idx]
        
        if best_match_score >= threshold:
            return ERROR_DB[best_match_idx]
        
    except Exception as e:
        print(f"Error in similarity calculation: {e}")
    
    return None

@app.route('/')
def index():
    # For headless operation, just return API status
    return jsonify({
        'status': 'running',
        'version': '1.0.0',
        'description': 'DeepTrace Error Analysis and Re-execution System',
        'endpoints': [
            '/api/validate - Validate a file',
            '/api/rerun - Re-execute a job',
            '/api/analyze-log - Analyze a log for error patterns',
            '/api/zendesk-hook - Webhook for Zendesk tickets',
            '/api/stats - Get system statistics',
            '/api/mcp-stats - Get MCP server statistics'
        ]
    })

@app.route('/api/validate', methods=['POST'])
def validate_file():
    file = request.files.get('file')
    if not file:
        return jsonify({'status': 'error', 'message': 'No file provided'}), 400
    
    file_type = request.form.get('file_type', 'sales_data')
    expected_cols = EXPECTED_COLUMNS.get(file_type, [])
    
    # Save temporarily
    filepath = os.path.join('/tmp', file.filename)
    file.save(filepath)

    # Check encoding
    enc = detect_encoding(filepath)
    if enc.lower() not in ['utf-8', 'ascii']:
        # Log the error
        error_entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'type': 'encoding_error',
            'file': file.filename,
            'detected_encoding': enc,
            'message': f"Expected UTF-8 encoding, detected {enc}"
        }
        ERROR_DB.append(error_entry)
        
        # Add to MCP server
        add_error_to_mcp(error_entry)
        
        return jsonify({
            'status': 'fail', 
            'error': 'encoding', 
            'detected': enc,
            'recommendation': "Convert file to UTF-8 encoding before uploading"
        }), 200

    # Load with pandas
    try:
        df = pd.read_csv(filepath)
        cols = list(df.columns)
        
        if expected_cols and cols != expected_cols:
            # Find missing and extra columns
            missing = [col for col in expected_cols if col not in cols]
            extra = [col for col in cols if col not in expected_cols]
            
            # Log the error
            error_entry = {
                'timestamp': datetime.datetime.now().isoformat(),
                'type': 'column_mismatch',
                'file': file.filename,
                'expected_columns': expected_cols,
                'actual_columns': cols,
                'missing': missing,
                'extra': extra,
                'message': f"Column mismatch: missing {missing}, extra {extra}"
            }
            ERROR_DB.append(error_entry)
            
            # Add to MCP server
            add_error_to_mcp(error_entry)
            
            return jsonify({
                'status': 'fail',
                'error': 'column_mismatch',
                'expected_columns': expected_cols,
                'actual_columns': cols,
                'missing': missing,
                'extra': extra,
                'recommendation': "Ensure file contains all required columns with exact naming"
            }), 200
            
        # Success case
        return jsonify({
            'status': 'success',
            'message': 'File validation passed',
            'rows': len(df),
            'columns': cols
        })
        
    except Exception as e:
        # Log the error
        error_entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'type': 'parse_error',
            'file': file.filename,
            'message': str(e)
        }
        ERROR_DB.append(error_entry)
        
        # Add to MCP server
        add_error_to_mcp(error_entry)
        
        return jsonify({
            'status': 'error',
            'message': f'Error parsing file: {str(e)}',
            'recommendation': "Check if file is valid CSV format"
        }), 400
    
@app.route('/api/rerun', methods=['POST'])
def rerun_job():
    data = request.json
    job_name = data.get('job')
    
    if not job_name:
        return jsonify({'status': 'error', 'message': 'No job specified'}), 400
    
    # Simulate job run - in a real scenario, this would trigger MCP/Airflow
    log_outcome = f"Triggered re-execution of job: {job_name}\n"
    log_outcome += f"Timestamp: {datetime.datetime.now().isoformat()}\n"
    log_outcome += "Status: RUNNING\n"
    
    # Log the rerun
    rerun_entry = {
        'timestamp': datetime.datetime.now().isoformat(),
        'type': 'job_rerun',
        'job': job_name,
        'status': 'initiated',
        'log': log_outcome
    }
    ERROR_DB.append(rerun_entry)
    
    return jsonify({
        'status': 'success',
        'message': f'Job {job_name} re-execution triggered',
        'log': log_outcome,
        'estimated_completion': (datetime.datetime.now() + datetime.timedelta(minutes=5)).isoformat()
    })

@app.route('/api/analyze-log', methods=['POST'])
def analyze_log():
    data = request.json
    log_text = data.get('log')
    job_name = data.get('job', 'unknown')
    
    if not log_text:
        return jsonify({'status': 'error', 'message': 'No log provided'}), 400
    
    # Use MCP server for analysis
    mcp_analysis = analyze_log_with_mcp(log_text, job_name)
    
    if mcp_analysis['status'] == 'success' and mcp_analysis.get('confidence') in ['high', 'medium']:
        # MCP provided high or medium confidence analysis
        return jsonify(mcp_analysis)
    
    # Fall back to legacy analysis for low confidence or error
    similar_entry = find_similar_logs(log_text)
    
    if similar_entry:
        # We found a similar log entry with a solution
        return jsonify({
            'status': 'success',
            'analysis': 'Known error pattern detected',
            'engineer_message': similar_entry.get('solution_engineer', 'Similar error seen before, investigating...'),
            'client_message': similar_entry.get('solution_client', 'We are working on resolving this issue.'),
            'confidence': 'high',
            'similar_job': similar_entry.get('job', 'unknown')
        })
    
    # Simple log analysis for common patterns
    analysis = {
        'status': 'success',
        'analysis': 'Log analyzed',
        'patterns': [],
        'engineer_message': '',
        'client_message': 'We are analyzing the error and will provide an update soon.',
        'confidence': 'low'
    }
    
    # Check for common error patterns
    if "FileNotFoundError" in log_text:
        analysis['patterns'].append('missing_file')
        analysis['engineer_message'] = "File not found error detected. Check if input files exist in the expected location."
    elif "Permission" in log_text and ("denied" in log_text or "Error" in log_text):
        analysis['patterns'].append('permission_error')
        analysis['engineer_message'] = "Permission error detected. Verify file/directory permissions."
    elif "Timeout" in log_text or "timed out" in log_text:
        analysis['patterns'].append('timeout')
        analysis['engineer_message'] = "Operation timeout detected. Check for resource constraints or hung processes."
    elif "MemoryError" in log_text or "OutOfMemoryError" in log_text:
        analysis['patterns'].append('memory_error')
        analysis['engineer_message'] = "Memory error detected. Job may need more resources or optimization."
    elif "encoding" in log_text.lower():
        analysis['patterns'].append('encoding_issue')
        analysis['engineer_message'] = "File encoding issue detected. Convert input files to UTF-8."
    
    # Save this analysis for future reference
    if analysis['patterns']:
        analysis['confidence'] = 'medium'
        error_entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'type': 'log_analysis',
            'job': job_name,
            'log': log_text,
            'patterns': analysis['patterns'],
            'solution_engineer': analysis['engineer_message'],
            'solution_client': analysis['client_message']
        }
        ERROR_DB.append(error_entry)
        
        # Add to MCP server for future pattern matching
        add_error_to_mcp(error_entry)
    
    return jsonify(analysis)

@app.route('/api/zendesk-hook', methods=['POST'])
def zendesk_hook():
    payload = request.json
    
    # Basic validation
    if not payload or 'ticket' not in payload:
        return jsonify({'status': 'error', 'message': 'Invalid payload'}), 400
    
    ticket = payload['ticket']
    tid = ticket.get('id')
    subject = ticket.get('subject', '')
    description = ticket.get('description', '')
    
    # Extract job name and log (if available)
    job_line = next((l for l in description.splitlines() if l.lower().startswith('job:')), None)
    log_line = next((l for l in description.splitlines() if l.lower().startswith('log:')), None)
    
    job = job_line.split(':', 1)[1].strip() if job_line else None
    log_url = log_line.split(':', 1)[1].strip() if log_line else None
    
    # Extract log content if URL is provided (simplified for demo)
    log_content = None
    if log_url:
        try:
            log_content = "Example log content from URL - in production, we would download the actual log file."
        except Exception as e:
            log_content = f"Error fetching log: {str(e)}"
    
    # Analyze the ticket and determine action
    if job:
        # Try to re-execute the job
        rerun_resp = requests.post('http://localhost:5000/api/rerun', json={'job': job})
        rerun_result = rerun_resp.json()
        
        # Analyze log if available
        analysis_result = None
        if log_content:
            analysis_resp = requests.post('http://localhost:5000/api/analyze-log', 
                                         json={'job': job, 'log': log_content})
            analysis_result = analysis_resp.json()
        
        # Formulate response based on analysis and rerun
        if rerun_result.get('status') == 'success':
            engineer_comment = f"✅ Re-execution of job **{job}** has been triggered.\n"
            if analysis_result and analysis_result.get('engineer_message'):
                engineer_comment += f"\nAnalysis: {analysis_result.get('engineer_message')}"
            
            client_comment = f"We've initiated the re-execution of the process. "
            if analysis_result and analysis_result.get('client_message'):
                client_comment += analysis_result.get('client_message')
            
            # Add comments to ticket
            add_comment(tid, engineer_comment, public=False)
            add_comment(tid, client_comment, public=True)
            
            return jsonify({
                'status': 'success', 
                'message': 'Job rerun triggered and ticket updated',
                'ticket_id': tid,
                'job': job
            })
        else:
            comment = f"❌ Unable to re-execute job **{job}**: {rerun_result.get('message', 'Unknown error')}"
            add_comment(tid, comment, public=False)
    else:
        comment = "❌ No job identified in the ticket description. Please specify by adding a line starting with 'Job:'"
        add_comment(tid, comment, public=False)
    
    return jsonify({'status': 'error', 'message': 'Process incomplete'})

@app.route('/api/stats', methods=['GET'])
def get_stats():
    if not ERROR_DB:
        return jsonify({'status': 'success', 'data': {'total_errors': 0}})
    
    # Count errors by type
    error_types = {}
    for entry in ERROR_DB:
        error_type = entry.get('type', 'unknown')
        error_types[error_type] = error_types.get(error_type, 0) + 1
    
    # Get recent errors (last 10)
    recent = sorted(ERROR_DB, key=lambda x: x.get('timestamp', ''), reverse=True)[:10]
    
    return jsonify({
        'status': 'success',
        'data': {
            'total_errors': len(ERROR_DB),
            'by_type': error_types,
            'recent': recent
        }
    })

@app.route('/api/mcp-stats', methods=['GET'])
def mcp_statistics():
    """Get statistics from the MCP server"""
    stats = get_mcp_stats()
    return jsonify({'status': 'success', 'data': stats})

if __name__ == '__main__':
    # Add some sample error patterns to start with
    ERROR_DB.append({
        'timestamp': datetime.datetime.now().isoformat(),
        'type': 'connection_error',
        'job': 'nightly_import',
        'log': 'Error: Could not connect to database at 10.0.1.5:3306. Connection timed out.',
        'patterns': ['connection_error', 'timeout'],
        'solution_engineer': 'Check if the database is running and network connectivity is established.',
        'solution_client': 'We are experiencing connectivity issues with our database. Our engineers are working to resolve this.'
    })
    
    ERROR_DB.append({
        'timestamp': datetime.datetime.now().isoformat(),
        'type': 'column_mismatch',
        'job': 'customer_import',
        'log': 'Error: Expected column "customer_id" but found "id" instead. Schema validation failed.',
        'patterns': ['column_mismatch'],
        'solution_engineer': 'File schema has changed. Update column names to match expected schema or adjust validation rules.',
        'solution_client': 'There appears to be a format issue with the uploaded file. Please ensure it follows our template format.'
    })
    
    # Add sample errors to MCP server as well
    for error in ERROR_DB:
        add_error_to_mcp(error)
    
    print("DeepTrace server started with MCP integration")
    app.run(debug=True, port=5000) 