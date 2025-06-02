from flask import Flask, render_template, request, jsonify, send_file
import pytest
import os
import sys
import time
import subprocess
import psutil
from pathlib import Path
from datetime import datetime
import logging
import pyodbc
from threading import Thread

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define constants first
REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports')

# Initialize Flask app
app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['STATIC_FOLDER'] = os.path.abspath(REPORTS_DIR)

# Create reports directory if it doesn't exist
os.makedirs(REPORTS_DIR, exist_ok=True)

# Dictionary to store test results
test_results = {}

# Database connection parameters
server = os.getenv('DB_HOST')
database = os.getenv('DB_NAME')
username = os.getenv('DB_USER')
password = os.getenv('DB_PASS')
driver = '{ODBC Driver 17 for SQL Server}'

def get_emails():
    try:
        conn = pyodbc.connect(
        f'DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password};TrustServerCertificate=yes;Connection Timeout=5'
        )
        print(f"Connecting to DB with SERVER={server}, DATABASE={database}, UID={username}")


        cursor = conn.cursor()
        cursor.execute("SELECT email FROM tenant WHERE isDeleted=0")
        emails = [row[0] for row in cursor.fetchall()]
        conn.close()
        return emails
    except Exception as e:
        print(f"Database connection failed: {e}")
        return []

@app.route('/api/emails', methods=['GET'])
def fetch_emails():
    emails = get_emails()
    return jsonify(emails)


# Store test results and current step
test_results = {}

def kill_chrome_processes():
    """Kill all Chrome processes"""
    try:
        logger.info("Attempting to kill Chrome processes")
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                # Only kill Chrome processes that were started by automation
                if proc.info['name'] == 'chrome.exe' and '--test-type' in proc.cmdline():
                    logger.info(f"Terminating Chrome process {proc.info['pid']}")
                    proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.error(f"Error handling Chrome process: {e}")
        time.sleep(2)
    except Exception as e:
        logger.error(f"Error in kill_chrome_processes: {e}")

def ensure_chrome_not_running():
    """Ensure no Chrome instances are running"""
    logger.info("Ensuring no Chrome instances are running")
    kill_chrome_processes()

def generate_report_name(email):
    """Generate a unique report name based on email and timestamp"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"report_{email.split('@')[0]}_{timestamp}.html"

def run_pytest_for_email(email, url):
    """Run pytest with given email and url"""
    try:
        logger.info(f"Starting test for {email} on {url}")
        
        # Set environment variables BEFORE running pytest
        os.environ['TEST_EMAIL'] = email
        os.environ['TEST_URL'] = url
        logger.info(f"Set environment variables - Email: {email}, URL: {url}")
        
        # Create reports directory if it doesn't exist
        os.makedirs(REPORTS_DIR, exist_ok=True)
        
        # Generate unique report name
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_name = f"report_{email.split('@')[0]}_{timestamp}.html"
        report_path = os.path.join(REPORTS_DIR, report_name)
        
        # Store initial test state
        test_results[email] = {
            'status': 'running',
            'currentStep': 'setup',
            'url': url,
            'email': email,
            'report_name': report_name,
            'report_path': report_path
        }
        
        def target():
            try:
                # Verify environment variables are set
                logger.info(f"Verifying env vars before test - Email: {os.environ.get('TEST_EMAIL')}, URL: {os.environ.get('TEST_URL')}")
                
                # Run pytest with HTML report
                result = pytest.main([
                    'test_cases.py',
                    '-v',
                    f'--html={report_path}',
                    '--self-contained-html'
                ])
                
                if os.path.exists(report_path):
                    logger.info(f"Report generated successfully at {report_path}")
                    test_results[email].update({
                        'status': 'completed' if result == 0 else 'failed',
                        'completion_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'report_url': f'/static/reports/{report_name}',
                        'report_download_url': f'/download/report/{report_name}'  # Add download URL
                    })
                else:
                    raise FileNotFoundError(f"Report file not generated at {report_path}")
                    
            except Exception as e:
                logger.error(f"Error in test execution: {e}")
                test_results[email].update({
                    'status': 'error',
                    'error': str(e)
                })
            finally:
                # Clean up environment variables
                os.environ.pop('TEST_EMAIL', None)
                os.environ.pop('TEST_URL', None)

        thread = Thread(target=target)
        thread.daemon = True
        thread.start()
        
        return jsonify({'status': 'started'})
        
    except Exception as e:
        logger.error(f"Error starting test: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            # Handle JSON request
            if request.is_json:
                data = request.get_json()
                email = data.get('email')
                url = data.get('url')
            else:
                # Handle form data request
                email = request.form.get('email')
                url = request.form.get('url')
            
            if not email or not url:
                return jsonify({
                    'status': 'error',
                    'message': 'Email and URL are required'
                }), 400
            
            # Create reports directory if it doesn't exist
            Path('static/reports').mkdir(parents=True, exist_ok=True)
            
            # Ensure no Chrome instances are running
            ensure_chrome_not_running()
            
            # Initialize test status
            test_results[email] = {
                'status': 'initializing',
                'currentStep': 'setup',
                'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'progress': 0
            }
            
            # Start the tests in a separate thread
            thread = Thread(
                target=run_pytest_for_email,
                args=(email, url)
            )
            thread.daemon = True
            thread.start()
            
            return jsonify({
                'status': 'started',
                'message': 'Test execution started'
            })
            
        except Exception as e:
            logger.error(f"Error in index route: {e}")
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500
    
    return render_template('index.html')

@app.route('/test-status')
def test_status():
    """Return the current status of tests for a given email"""
    try:
        email = request.args.get('email')
        if not email:
            return jsonify({'status': 'error', 'message': 'Email parameter required'}), 400
            
        if email in test_results:
            return jsonify({
                'status': test_results[email]['status'],
                'currentStep': test_results[email].get('currentStep'),
                'completion_time': test_results[email].get('completion_time'),
                'report_url': test_results[email].get('report_url'),
                'error': test_results[email].get('error'),
                'progress': test_results[email].get('progress', 0)
            })
        return jsonify({'status': 'not_found'})
    except Exception as e:
        logger.error(f"Error in status route: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/static/reports/<path:filename>')
def serve_report(filename):
    """Serve the test report"""
    try:
        # Use absolute path
        report_path = os.path.abspath(os.path.join(REPORTS_DIR, filename))
        logger.info(f"Attempting to serve report from: {report_path}")
        
        if not os.path.exists(report_path):
            logger.error(f"Report file not found: {report_path}")
            return "Report not found", 404
            
        return send_file(
            report_path,
            mimetype='text/html',
            as_attachment=False,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"Error serving report: {e}", exc_info=True)
        return str(e), 404

@app.route('/download/report/<path:filename>')
def download_report(filename):
    """Download the test report"""
    try:
        # Use absolute path
        report_path = os.path.abspath(os.path.join(REPORTS_DIR, filename))
        logger.info(f"Attempting to download report from: {report_path}")
        
        if not os.path.exists(report_path):
            logger.error(f"Report file not found: {report_path}")
            return "Report file not found", 404
        
        logger.info(f"Sending file: {report_path}")
        return send_file(
            report_path,
            mimetype='text/html',
            as_attachment=True,
            download_name=filename,
            etag=True,
            conditional=True,
            max_age=0
        )
    except Exception as e:
        logger.error(f"Error downloading report: {e}", exc_info=True)
        return str(e), 500

if __name__ == '__main__':
    app.run(debug=True)