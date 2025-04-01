import argparse
import sys
import logging
import asyncio
from utils.email_checker import EmailChecker

def main():
    """
    Main function to run the email checker
    """
    parser = argparse.ArgumentParser(
        description='Check for Medium emails and archive articles',
        epilog='Example: python main.py --interval 300'
    )
    parser.add_argument('--interval', type=int, default=300,
                       help='Time between checks in seconds (default: 300)')
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
        logging.info("Starting Medium email checker...")
        checker = EmailChecker()
        asyncio.run(checker.run(check_interval=args.interval))
    except KeyboardInterrupt:
        logging.info("Shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Error during execution: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
