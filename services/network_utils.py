import urllib.request
import urllib.error
import ssl
import time
import logging

log = logging.getLogger("NetworkUtils")

def safe_urlopen(req, timeout=30, max_retries=3):
    """Wrapper for urlopen that handles SSL EOF errors and common network failures with backoff."""
    retry_count = 0
    base_delay = 2
    
    while retry_count < max_retries:
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return urllib.request.urlopen(req, timeout=timeout, context=ctx)
        except (ssl.SSLEOFError, ssl.SSLError) as e:
            # Common on busy servers or unstable networks
            retry_count += 1
            if retry_count >= max_retries:
                log.warning(f"Network: SSL error after {max_retries} retries: {e}")
                raise
            time.sleep(base_delay * retry_count)
        except urllib.error.URLError as e:
            if "SSL" in str(e):
                retry_count += 1
                if retry_count >= max_retries:
                    log.warning(f"Network: SSL/URLError after {max_retries} retries: {e}")
                    raise
                time.sleep(base_delay * retry_count)
            else:
                raise
    return None
