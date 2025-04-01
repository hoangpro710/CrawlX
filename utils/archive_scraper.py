import hrequests
from selectolax.parser import HTMLParser, Node
import time
import os
from pathlib import Path
import logging
from urllib.parse import quote, urljoin
import re
import shutil

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(levelname)s - %(message)s')

def clean_text(text):
    """Clean and format text while preserving structure"""
    # Remove multiple newlines but preserve paragraph breaks
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    # Remove trailing/leading whitespace from lines while preserving indentation
    text = '\n'.join(line.rstrip() for line in text.split('\n'))
    return text

def get_inline_styles(node: Node) -> str:
    """Extract inline styles from node"""
    styles = []
    if 'style' in node.attributes:
        style_str = node.attributes['style']
        if 'bold' in style_str or 'font-weight' in style_str:
            styles.append('**')
        if 'italic' in style_str or 'font-style: italic' in style_str:
            styles.append('_')
    return ''.join(styles)

def clean_content_keep_essential(node: Node) -> None:
    """Keep only essential content (text and images) and remove everything else"""
    # Elements to remove completely
    remove_selectors = [
        "header", ".header", "#header",
        "nav", ".nav", "#nav", ".navigation",
        "aside", ".aside", "#aside", ".sidebar",
        "footer", ".footer", "#footer",
        ".ad", ".ads", ".advertisement",
        ".social", ".share", ".sharing",
        ".author", ".bio", ".profile",
        ".tags", ".categories",
        ".related", ".recommendations",
        ".comments", "#comments",
        ".subscription", ".newsletter",
        ".medium-footer", ".post-footer",
        ".js-post-footer", ".metabar",
        ".post-meta", ".article-meta",
        "script", "style", "noscript",
        ".button", ".btn", ".actions",
        ".clap", ".responses",
        ".progressiveMedia-thumbnail"  # Medium's low-res image placeholder
    ]
    
    # Remove unwanted elements
    for selector in remove_selectors:
        elements = node.css(selector)
        for element in elements:
            if element:
                element.decompose()

def extract_formatted_content(node: Node, base_url: str = '') -> str:
    """
    Extract only essential content (text and images) while preserving structure
    """
    if not node or not isinstance(node, Node):
        return ""
    
    content = []
    
    # Handle different HTML elements
    tag_name = node.tag
    
    # Skip unwanted elements
    if tag_name in ['script', 'style', 'noscript', 'button', 'iframe']:
        return ""
    
    # Get text content safely
    try:
        node_text = node.text().strip() if node.text() else ""
    except (AttributeError, TypeError):
        node_text = ""
    
    # Process based on tag type
    if tag_name == 'h1':
        if node_text:
            content.append(f"\n# {node_text}\n")
    elif tag_name == 'h2':
        if node_text:
            content.append(f"\n## {node_text}\n")
    elif tag_name == 'h3':
        if node_text:
            content.append(f"\n### {node_text}\n")
    elif tag_name == 'p':
        if node_text:
            content.append(f"\n{node_text}\n")
    elif tag_name == 'img':
        try:
            if node.attributes:
                src = node.attributes.get('src', '')
                alt = node.attributes.get('alt', '')
                # Skip small images and icons
                if src and not (src.endswith('.ico') or 'icon' in src.lower()):
                    # Handle relative URLs
                    if src.startswith('/'):
                        src = urljoin(base_url, src)
                    # Handle data URLs
                    if not src.startswith('data:'):
                        content.append(f"\n![{alt}]({src})\n")
        except (AttributeError, TypeError):
            pass
    elif tag_name == 'figure':
        # Handle figure elements with images
        try:
            img = node.css_first('img')
            if img and img.attributes:
                src = img.attributes.get('src', '')
                alt = img.attributes.get('alt', '')
                if src and not (src.endswith('.ico') or 'icon' in src.lower()):
                    if src.startswith('/'):
                        src = urljoin(base_url, src)
                    if not src.startswith('data:'):
                        content.append(f"\n![{alt}]({src})\n")
            
            # Get figure caption if exists
            figcaption = node.css_first('figcaption')
            if figcaption and figcaption.text():
                caption_text = figcaption.text().strip()
                if caption_text:
                    content.append(f"*{caption_text}*\n")
        except (AttributeError, TypeError):
            pass
    
    # Recursively process child nodes
    try:
        if hasattr(node, 'iter'):
            for child in node.iter():
                if isinstance(child, Node) and child != node:
                    child_content = extract_formatted_content(child, base_url)
                    if child_content:
                        content.append(child_content)
    except (AttributeError, TypeError) as e:
        logging.debug(f"Error processing children of node {tag_name}: {str(e)}")
    
    return ''.join(content)

def save_html_content(content: str, output_dir: str, filename: str) -> str:
    """Save raw HTML content to file"""
    html_dir = os.path.join(output_dir, "html")
    os.makedirs(html_dir, exist_ok=True)
    
    # Create HTML filename
    html_filename = filename.replace(".md", ".html")
    html_path = Path(html_dir) / html_filename
    
    # Save HTML content
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return str(html_path)

def archive_and_save_content(target_url: str, output_dir: str = "archived_content") -> tuple[str, str]:
    """
    Archives a webpage using archive.ph and extracts its content.
    
    Args:
        target_url (str): The URL to archive and extract content from
        output_dir (str): Directory to save the markdown output
        
    Returns:
        tuple[str, str]: Paths to the saved markdown and HTML files
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
    time.sleep(5)
    
    # Step 3: Get the archived content
    logging.info("Fetching archived content")
    resp = session.get(archived_url)
    if not resp.ok:
        logging.error(f"Failed to get archived content: Status {resp.status_code}")
        raise Exception(f"Failed to get archived content: {resp.status_code}")
    
    # Step 4: Parse the content
    logging.info("Parsing content")
    parser = HTMLParser(resp.text)
    
    # Try to find the main content area
    content_selectors = [
        "article",
        "main",
        ".article-content",
        ".post-content",
        ".entry-content",
        "div.body",
        ".article-body",
        ".post-body",
        ".story-content",
        "#content",
        ".content"
    ]
    
    content_node = None
    for selector in content_selectors:
        content_node = parser.css_first(selector)
        if content_node:
            break
    
    if not content_node:
        logging.error("Could not find content div")
        raise Exception("Could not find content div")
    
    # Get the raw HTML content before cleaning
    raw_html = content_node.html
    
    # Clean the content to keep only essential elements
    clean_content_keep_essential(content_node)
    
    # Extract formatted content
    try:
        content = extract_formatted_content(content_node, base_url=archived_url)
        content = clean_text(content)
        
        # Remove excessive newlines
        content = re.sub(r'\n{3,}', '\n\n', content)
        
    except Exception as e:
        logging.error(f"Error extracting content: {str(e)}")
        raise Exception(f"Failed to extract content: {str(e)}")
    
    # Step 5: Save content
    os.makedirs(output_dir, exist_ok=True)
    
    # Create filename from URL
    filename = target_url.split("/")[-1].replace("-", "_")
    if not filename.endswith(".md"):
        filename = f"{filename}.md"
    
    # Save markdown version
    output_path = Path(output_dir) / filename
    logging.info(f"Saving markdown content to {output_path}")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# Archived Content from {target_url}\n\n")
        f.write(f"Archive URL: {archived_url}\n\n")
        f.write(content)
    
    # Save HTML version
    html_path = save_html_content(raw_html, output_dir, filename)
    logging.info(f"Saved HTML content to {html_path}")
    
    session.close()
    logging.info("Archive process completed successfully")
    return str(output_path), html_path

if __name__ == "__main__":
    # Example usage
    url = "https://pub.towardsai.net/gemma-3-mistralocr-rag-just-revolutionized-agent-ocr-forever-e69d1f2a67e5"
    try:
        output_file, html_file = archive_and_save_content(url)
        print(f"Content saved to: {output_file}")
        print(f"HTML content saved to: {html_file}")
    except Exception as e:
        print(f"Error: {e}") 