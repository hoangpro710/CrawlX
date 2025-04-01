import hrequests
from selectolax.parser import HTMLParser
import time
import logging
from urllib.parse import quote

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(levelname)s - %(message)s')

def get_archived_url(target_url: str, output_dir: str = "archived_content") -> str:
    """
    Archives a webpage using archive.ph and returns the archived URL.
    
    Args:
        target_url (str): The URL to archive
        output_dir (str): Directory to save the output (unused)
        
    Returns:
        str: The URL of the archived content
    """
    # Create session with custom headers
    session = hrequests.Session()
    session.headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "vi,en;q=0.9,en-US;q=0.8",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "priority": "u=0, i",
        "sec-ch-ua": '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
    }
    
    # Step 1: Access archive.ph to get submitid
    archive_url = "https://archive.ph/"
    logging.info(f"Accessing {archive_url}")
    resp = session.get(archive_url)
    if not resp.ok:
        logging.error(f"Failed to access archive.ph: Status {resp.status_code}")
        raise Exception(f"Failed to access archive.ph: {resp.status_code}")
    
    # Extract submitid from the HTML
    parser = HTMLParser(resp.text)
    submit_input = parser.css_first('input[name="submitid"]')
    if not submit_input:
        logging.error("Could not find submitid in the page")
        raise Exception("Could not find submitid")
    
    submitid = submit_input.attributes.get('value', '')
    logging.info(f"Found submitid: {submitid}")
    
    # Step 2: Submit URL to archive with submitid
    logging.info(f"Submitting URL: {target_url}")
    
    # Construct the submit URL with parameters
    encoded_url = quote(target_url)
    submit_url = f"https://archive.ph/submit/?submitid={submitid}&url={encoded_url}"
    logging.info(f"Submit URL: {submit_url}")
    
    # Add referer header
    session.headers.update({
        "referer": "https://archive.ph/"
    })
    
    # Submit URL and follow redirects
    resp = session.get(submit_url, allow_redirects=True)
    
    if not resp.ok:
        logging.error(f"Failed to submit URL: Status {resp.status_code}")
        logging.debug(f"Response content: {resp.text[:500]}...")  # Log first 500 chars of response
        raise Exception(f"Failed to submit URL: {resp.status_code}")
    
    # Get the final archived URL
    archived_url = resp.url
    logging.info(f"Archive URL: {archived_url}")
    
    # Add delay to allow processing
    time.sleep(10)
    
    # Step 3: Get the url of the archived content
    return archived_url

if __name__ == "__main__":
    # Example usage
    url = "https://pub.towardsai.net/gemma-3-mistralocr-rag-just-revolutionized-agent-ocr-forever-e69d1f2a67e5"
    try:
        archived_url = get_archived_url(url)
        print(f"Archived URL: {archived_url}")
    except Exception as e:
        print(f"Error: {e}") 