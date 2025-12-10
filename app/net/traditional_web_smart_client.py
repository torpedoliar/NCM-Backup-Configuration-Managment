"""
Traditional WebSmart Switch Client (HTTP/HTTPS)
For Allied Telesis FS750, GS950 old models
Uses simple form POST authentication
"""
import logging
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)

class TraditionalWebSmartClient:
    """Client for traditional WebSmart switches (FS750, GS950 old models)"""
    
    def __init__(self, host: str, port: int = 80, username: str = "manager", 
                 password: str = "friend", timeout: int = 30):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self.base_url = f"http://{host}:{port}/"
        self.session = requests.Session()
        self.gambit_token = None
        
        # Common headers to mimic a browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })

    def connect(self):
        """
        Attempt to login to the switch.
        Note: Different firmware versions have different login paths.
        We try the most common ones.
        """
        logger.info(f"Connecting to WebSmart switch at {self.base_url}")
        
        # List of potential login endpoints and payload formats
        login_attempts = [
             # Pattern 4: FS750/GS950 /iss/ path structure
            {
                'url': 'iss/redirect.html',
                'method': 'POST',
                'data': {'Login': self.username, 'Password': self.password}
            },
            {
                'url': 'iss/login.cgi',
                'method': 'POST',
                'data': {'username': self.username, 'password': self.password, 'submit': 'Login'}
            },
            {
                'url': 'iss/login.html',
                'method': 'POST',
                'data': {'username': self.username, 'password': self.password, 'submit': 'Login'}
            },
            # Pattern 1: GS950 series (often /login.cgi or just /)
            {
                'url': 'login.cgi',
                'method': 'POST',
                'data': {'username': self.username, 'password': self.password, 'submit': 'Login'}
            },
            # Pattern 2: FS750 series (sometimes /logon.htm)
            {
                'url': 'logon.htm',
                'method': 'POST',
                'data': {'user': self.username, 'password': self.password}
            }
        ]

        for attempt in login_attempts:
            try:
                target_url = urljoin(self.base_url, attempt['url'])
                
                if attempt.get('auth'):
                    # Basic Auth
                    response = self.session.get(target_url, auth=attempt['auth'], timeout=self.timeout)
                elif attempt['method'] == 'POST':
                    # Form Login
                    # Use allow_redirects=False to capture tokens in response body before redirect
                    response = self.session.post(target_url, data=attempt['data'], timeout=self.timeout, allow_redirects=False)
                else:
                    continue

                # Check if login successful
                if response.status_code == 200:
                    # Always try to extract Gambit token first
                    match = re.search(r'name="Gambit" value="([^"]+)"', response.text)
                    if match:
                        self.gambit_token = match.group(1)
                        logger.info(f"Extracted Gambit token: {self.gambit_token}")

                    # If we are redirected to index or don't see login form
                    if "login" not in response.url.lower() and "logon" not in response.url.lower():
                        logger.info(f"Login successful via {attempt['url']}")
                        return True
                    
                    # Specific check for /iss/ structure
                    if "iss/" in response.url.lower():
                        logger.info(f"Login successful via {attempt['url']} (path check)")
                        return True
                        
                    # Content check
                    text_lower = response.text.lower()
                    if "invalid" not in text_lower and \
                       "fail" not in text_lower and \
                       "error_msg = 'error" not in text_lower and \
                       "wrong password" not in text_lower:
                        
                        logger.info(f"Login successful via {attempt['url']} (content check)")
                        return True
                    else:
                        logger.warning(f"Login failed via {attempt['url']}: Detected error message in response")

            except requests.RequestException as e:
                logger.debug(f"Login attempt failed for {attempt['url']}: {e}")
                continue

        raise ConnectionError("Failed to login to WebSmart switch. Check credentials or network.")

    def get_running_config(self) -> str:
        """
        Download the configuration file.
        Tries multiple known backup endpoints.
        """
        # List of potential backup endpoints
        backup_endpoints = [
            'iss/config_file_http.html',
            'config.bin',
            'backup.cgi',
            'config/backup.cgi',
            'system/config_backup.htm',
            'maintenance/upload_download.htm'
        ]
        
        # If we have a Gambit token, try the direct download endpoint first
        if self.gambit_token:
            backup_endpoints.insert(0, f"iss.conf?Gambit={self.gambit_token}")

        for endpoint in backup_endpoints:
            try:
                target_url = urljoin(self.base_url, endpoint)
                logger.debug(f"Trying to download config from {target_url}")
                
                response = self.session.get(target_url, timeout=self.timeout)
                
                if response.status_code == 200:
                    content_type = response.headers.get('Content-Type', '').lower()
                    
                    # Direct file download check
                    if 'text/html' not in content_type:
                        content = response.text
                        if len(content) > 100: 
                            logger.info(f"Config downloaded successfully from {endpoint}")
                            return content
                            
                    # HTML page with Backup button
                    if 'iss/config_file_http.html' in target_url and 'text/html' in content_type:
                        logger.info("Found backup page, attempting to click Backup button...")
                        try:
                            soup = BeautifulSoup(response.text, 'html.parser')
                            forms = soup.find_all('form')
                            for form in forms:
                                buttons = form.find_all(['input', 'button'])
                                backup_btn = None
                                for btn in buttons:
                                    if btn.get('value', '').lower() == 'backup' or 'backup' in btn.get('name', '').lower():
                                        backup_btn = btn
                                        break
                                
                                if backup_btn:
                                    action = form.get('action', '')
                                    post_url = urljoin(target_url, action) if action else target_url
                                    
                                    data = {}
                                    if backup_btn.get('name'):
                                        data[backup_btn['name']] = backup_btn.get('value', '')
                                    
                                    for hidden in form.find_all('input', type='hidden'):
                                        if hidden.get('name'):
                                            data[hidden['name']] = hidden.get('value', '')
                                            
                                    logger.info(f"Submitting backup form to {post_url}")
                                    file_response = self.session.post(post_url, data=data, timeout=self.timeout)
                                    
                                    if file_response.status_code == 200:
                                        if len(file_response.text) > 100 and 'text/html' not in file_response.headers.get('Content-Type', '').lower():
                                            return file_response.text
                                        if "config" in file_response.text[:100] or "sysname" in file_response.text[:100]:
                                            return file_response.text
                        except Exception as e:
                            logger.error(f"Error parsing/submitting backup form: {e}")

            except requests.RequestException:
                continue
        
        raise ValueError("Could not find a valid configuration download endpoint.")

    def disconnect(self):
        """Logout and close session"""
        try:
            logout_url = urljoin(self.base_url, 'logout.cgi')
            self.session.get(logout_url, timeout=5)
        except:
            pass
        self.session.close()
