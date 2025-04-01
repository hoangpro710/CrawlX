from utils.archive_scraper import archive_and_save_content
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
        description='Archive webpage content using archive.ph',
        epilog=f'Example: python main.py "{example_url}"'
    )
    parser.add_argument('url', nargs='?', default=example_url,
                       help='URL to archive and extract content from (default: Towards AI article)')
    parser.add_argument('--output-dir', '-o', default='archived_content',
                       help='Directory to save the output (default: archived_content)')
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
        logging.info(f"Starting archive process for: {args.url}")
        md_file, html_file = archive_and_save_content(args.url, args.output_dir)
        print("\nArchive completed successfully!")
        print(f"Markdown content saved to: {md_file}")
        print(f"HTML content saved to: {html_file}")
    except Exception as e:
        logging.error(f"Error during archiving: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
