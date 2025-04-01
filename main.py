from utils.archive_scraper import get_archived_url
import argparse
import sys
import logging

def main():
    """
    Main function to handle URL archiving from command line
    """
    # Example URL from Towards AI article about Gemma 3 + MistralOCR + RAG
    example_url = "https://pub.towardsai.net/gemma-3-mistralocr-rag-just-revolutionized-agent-ocr-forever-e69d1f2a67e5"
    
    parser = argparse.ArgumentParser(
        description='Get archived URL from archive.ph',
        epilog=f'Example: python main.py "{example_url}"'
    )
    parser.add_argument('url', nargs='?', default=example_url,
                       help='URL to archive (default: Towards AI article)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose debug output')
    
    args = parser.parse_args()
    
    # Configure logging based on verbose flag
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    try:
        logging.info(f"Getting archived URL for: {args.url}")
        archived_url = get_archived_url(args.url)
        print(archived_url)
    except Exception as e:
        logging.error(f"Error during archiving: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
