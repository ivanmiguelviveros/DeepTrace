import os
import time
import json
import threading
import requests
import datetime
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import DBSCAN
import numpy as np
import pandas as pd
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("mcp_server.log"), logging.StreamHandler()]
)
logger = logging.getLogger("MCP_Server")

# Load environment variables
load_dotenv()

# Configuration
CHECK_INTERVAL = int(os.getenv('MCP_CHECK_INTERVAL', '60'))  # seconds
ERROR_THRESHOLD = int(os.getenv('MCP_ERROR_THRESHOLD', '3'))  # number of similar errors to trigger alert
SIMILARITY_THRESHOLD = float(os.getenv('MCP_SIMILARITY_THRESHOLD', '0.7'))  # cosine similarity threshold

class MCPServer:
    def __init__(self):
        self.error_db = []
        self.running = False
        self.monitor_thread = None
        self.vectorizer = TfidfVectorizer(stop_words='english')
        self.clusterer = DBSCAN(eps=0.3, min_samples=2, metric='cosine')
        self.error_clusters = {}
        self.error_patterns = self._load_error_patterns()
        logger.info("MCP Server initialized")
        
    def _load_error_patterns(self):
        """Load pretrained error patterns from file or initialize with defaults"""
        try:
            if os.path.exists('error_patterns.json'):
                with open('error_patterns.json', 'r') as f:
                    patterns = json.load(f)
                logger.info(f"Loaded {len(patterns)} error patterns from file")
                return patterns
        except Exception as e:
            logger.error(f"Error loading patterns: {e}")
            
        # Default patterns if file doesn't exist or has issues
        return [
            {
                "pattern_name": "database_connection",
                "keywords": ["connection refused", "could not connect", "database", "timeout"],
                "solution_engineer": "Check database connection, ensure service is running, check network connectivity",
                "solution_client": "We're experiencing database connectivity issues. Our team is working to restore service."
            },
            {
                "pattern_name": "file_encoding",
                "keywords": ["encoding", "utf", "ascii", "decode", "unicode"],
                "solution_engineer": "File encoding issue detected. Convert to UTF-8 before processing.",
                "solution_client": "There was an issue with the file format. Please ensure files are saved as UTF-8."
            },
            {
                "pattern_name": "permission_denied",
                "keywords": ["permission denied", "access", "forbidden", "403"],
                "solution_engineer": "Check file/directory permissions and service account privileges.",
                "solution_client": "Our system encountered a permissions issue. The team is addressing it."
            },
            {
                "pattern_name": "memory_error",
                "keywords": ["memory", "out of memory", "oom", "heap space"],
                "solution_engineer": "Process is running out of memory. Increase resource allocation or optimize processing.",
                "solution_client": "The process requires more resources than available. We're optimizing it."
            },
            {
                "pattern_name": "column_mismatch",
                "keywords": ["column", "schema", "field", "missing column", "expected"],
                "solution_engineer": "File schema does not match expected format. Check mappings and source data.",
                "solution_client": "The uploaded file format doesn't match our requirements. Please check the template."
            }
        ]

    def _save_error_patterns(self):
        """Save the current error patterns to disk"""
        try:
            with open('error_patterns.json', 'w') as f:
                json.dump(self.error_patterns, f, indent=2)
            logger.info(f"Saved {len(self.error_patterns)} error patterns to file")
        except Exception as e:
            logger.error(f"Error saving patterns: {e}")
    
    def add_error(self, error_data):
        """Add a new error to the database"""
        if not isinstance(error_data, dict):
            logger.error("Invalid error data format")
            return False
            
        # Add timestamp if not present
        if 'timestamp' not in error_data:
            error_data['timestamp'] = datetime.datetime.now().isoformat()
            
        self.error_db.append(error_data)
        logger.info(f"Added new error: {error_data.get('type', 'unknown')} for job {error_data.get('job', 'unknown')}")
        
        # Update clusters if we have enough data
        if len(self.error_db) % 5 == 0:
            self._update_clusters()
            
        return True
    
    def _update_clusters(self):
        """Update error clusters using DBSCAN"""
        if len(self.error_db) < 2:
            return
            
        try:
            # Extract log messages
            logs = [entry.get('log', '') or entry.get('message', '') for entry in self.error_db]
            if not any(logs):
                return
                
            # Vectorize the logs
            vectors = self.vectorizer.fit_transform(logs)
            
            # Cluster the vectors
            cluster_labels = self.clusterer.fit_predict(vectors)
            
            # Group errors by cluster
            self.error_clusters = {}
            for i, label in enumerate(cluster_labels):
                if label == -1:  # Noise points
                    continue
                if label not in self.error_clusters:
                    self.error_clusters[label] = []
                self.error_clusters[label].append(self.error_db[i])
                
            # Check for clusters that exceed threshold
            for label, errors in self.error_clusters.items():
                if len(errors) >= ERROR_THRESHOLD:
                    self._handle_error_cluster(label, errors)
                    
            logger.info(f"Updated clusters: found {len(self.error_clusters)} clusters")
        except Exception as e:
            logger.error(f"Error updating clusters: {e}")
    
    def _handle_error_cluster(self, cluster_id, errors):
        """Handle a cluster of similar errors that exceed the threshold"""
        # Get the most recent error in the cluster
        latest = max(errors, key=lambda x: x.get('timestamp', ''))
        job_name = latest.get('job', 'unknown')
        error_type = latest.get('type', 'unknown')
        
        logger.warning(f"Error cluster detected: {len(errors)} similar errors for job type {job_name}/{error_type}")
        
        # Check if we can find a matching pattern
        pattern = self._find_matching_pattern(latest.get('log', '') or latest.get('message', ''))
        
        if pattern:
            logger.info(f"Found matching pattern: {pattern['pattern_name']}")
            
            # Create alert for engineers
            alert = {
                'timestamp': datetime.datetime.now().isoformat(),
                'alert_type': 'error_cluster',
                'job': job_name,
                'error_type': error_type,
                'occurrences': len(errors),
                'pattern_name': pattern['pattern_name'],
                'solution_engineer': pattern['solution_engineer'],
                'solution_client': pattern['solution_client']
            }
            
            # In a real system, we would send this alert via email, Slack, etc.
            logger.warning(f"ALERT: {alert['solution_engineer']}")
            
            # Try to trigger re-execution of the job
            if job_name != 'unknown':
                self._trigger_rerun(job_name, pattern)
    
    def _find_matching_pattern(self, log_text):
        """Find a matching error pattern for the given log text"""
        if not log_text:
            return None
            
        # Calculate match scores based on keyword presence
        matches = []
        for pattern in self.error_patterns:
            score = 0
            for keyword in pattern['keywords']:
                if keyword.lower() in log_text.lower():
                    score += 1
            if score > 0:
                matches.append((pattern, score / len(pattern['keywords'])))
        
        # Sort by score and return the best match
        if matches:
            matches.sort(key=lambda x: x[1], reverse=True)
            if matches[0][1] >= 0.5:  # At least 50% of keywords matched
                return matches[0][0]
                
        return None
    
    def _trigger_rerun(self, job_name, pattern=None):
        """Trigger a re-execution of the failed job"""
        try:
            # In a production system, this would call your job orchestration system
            # For the demo, we'll just call our rerun API
            rerun_data = {'job': job_name}
            response = requests.post('http://localhost:5000/api/rerun', json=rerun_data)
            
            if response.status_code == 200:
                logger.info(f"Successfully triggered rerun of job {job_name}")
                return True
            else:
                logger.error(f"Failed to trigger rerun of job {job_name}: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error triggering rerun: {e}")
            return False
    
    def analyze_log(self, log_text, job_name='unknown'):
        """Analyze a log entry and return insights"""
        if not log_text:
            return {
                'status': 'error',
                'message': 'No log text provided'
            }
            
        # Find matching pattern
        pattern = self._find_matching_pattern(log_text)
        
        if pattern:
            return {
                'status': 'success',
                'pattern_detected': pattern['pattern_name'],
                'confidence': 'high',
                'engineer_message': pattern['solution_engineer'],
                'client_message': pattern['solution_client']
            }
        
        # If no pattern matched, try to find similar errors in our database
        similar_error = self._find_similar_error(log_text)
        
        if similar_error:
            return {
                'status': 'success',
                'pattern_detected': 'similar_error',
                'confidence': 'medium',
                'similar_job': similar_error.get('job', 'unknown'),
                'engineer_message': similar_error.get('solution_engineer', 'Similar error seen before, investigating...'),
                'client_message': similar_error.get('solution_client', 'We are working on resolving this issue.')
            }
        
        # If all else fails, return a generic message
        return {
            'status': 'success',
            'pattern_detected': None,
            'confidence': 'low',
            'engineer_message': 'Unknown error pattern. Manual investigation required.',
            'client_message': 'We are analyzing this issue and will update you shortly.'
        }
    
    def _find_similar_error(self, log_text, threshold=0.7):
        """Find similar errors in our database using TF-IDF and cosine similarity"""
        if not self.error_db:
            return None
            
        try:
            # Extract logs from error database
            logs = [entry.get('log', '') or entry.get('message', '') for entry in self.error_db]
            logs = [log for log in logs if log]  # Remove empty entries
            
            if not logs:
                return None
                
            # Add the current log to the list
            all_logs = logs + [log_text]
            
            # Create TF-IDF matrix
            vectors = self.vectorizer.fit_transform(all_logs)
            
            # Get the last vector (our query)
            query_vector = vectors[-1]
            
            # Calculate similarities
            similarities = []
            for i in range(len(logs)):
                similarity = np.dot(query_vector.toarray()[0], vectors[i].toarray()[0]) / (
                    np.linalg.norm(query_vector.toarray()[0]) * np.linalg.norm(vectors[i].toarray()[0])
                )
                similarities.append(similarity)
            
            # Find the best match
            if similarities:
                best_idx = np.argmax(similarities)
                if similarities[best_idx] >= threshold:
                    return self.error_db[best_idx]
        except Exception as e:
            logger.error(f"Error finding similar logs: {e}")
            
        return None
    
    def start_monitoring(self):
        """Start the monitoring thread"""
        if self.running:
            logger.warning("Monitor already running")
            return False
            
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        logger.info("Monitor thread started")
        return True
    
    def stop_monitoring(self):
        """Stop the monitoring thread"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Monitor thread stopped")
        return True
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Check for new error patterns
                self._update_clusters()
                
                # In a production system, we would also:
                # 1. Query job orchestration systems for failed jobs
                # 2. Check log storage for new error logs
                # 3. Trigger alerts for repeated errors
                
                # For demo purposes, we just log that we're monitoring
                logger.debug(f"Monitor tick: {len(self.error_db)} errors, {len(self.error_clusters)} clusters")
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
            
            # Sleep until next check
            time.sleep(CHECK_INTERVAL)
    
    def get_stats(self):
        """Get statistics about errors and clusters"""
        stats = {
            'total_errors': len(self.error_db),
            'error_clusters': len(self.error_clusters),
            'error_types': {},
            'job_stats': {}
        }
        
        # Count errors by type
        for error in self.error_db:
            error_type = error.get('type', 'unknown')
            job = error.get('job', 'unknown')
            
            if error_type not in stats['error_types']:
                stats['error_types'][error_type] = 0
            stats['error_types'][error_type] += 1
            
            if job not in stats['job_stats']:
                stats['job_stats'][job] = 0
            stats['job_stats'][job] += 1
        
        return stats

# Create global instance
mcp_server = MCPServer()

# API functions for Flask integration
def init_mcp_server():
    """Initialize the MCP server and start monitoring"""
    mcp_server.start_monitoring()
    return mcp_server

def add_error_to_mcp(error_data):
    """Add an error to the MCP server"""
    return mcp_server.add_error(error_data)

def analyze_log_with_mcp(log_text, job_name='unknown'):
    """Analyze a log entry with the MCP server"""
    return mcp_server.analyze_log(log_text, job_name)

def get_mcp_stats():
    """Get statistics from the MCP server"""
    return mcp_server.get_stats()

# For standalone testing
if __name__ == "__main__":
    print("Starting MCP Server in standalone mode")
    server = MCPServer()
    server.start_monitoring()
    
    # Example error data
    test_error = {
        "job": "test_job",
        "type": "column_mismatch",
        "log": "Error: Expected column 'customer_id' but found 'id' instead. Schema validation failed.",
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    server.add_error(test_error)
    
    # Keep running until interrupted
    try:
        while True:
            time.sleep(10)
            stats = server.get_stats()
            print(f"Current stats: {stats['total_errors']} errors, {stats['error_clusters']} clusters")
    except KeyboardInterrupt:
        print("Stopping MCP Server")
        server.stop_monitoring() 