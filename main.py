import argparse
import sys
import logging
import asyncio
from utils.email_checker import EmailChecker

# Configure root logger for detailed output
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def async_main(args):
    """
    Async main function to run the email checker
    """
    try:
        logging.info("=== Starting Medium email checker ===")
        logging.debug(f"Check interval: {args.interval} seconds")
        logging.debug(f"Verbose mode: {args.verbose}")
        
        checker = EmailChecker()
        await checker.run(check_interval=args.interval)
    except KeyboardInterrupt:
        logging.info("=== Shutting down gracefully... ===")
    except Exception as e:
        logging.error(f"=== Error during execution: {str(e)} ===")
        raise

def main():
    """
    Main function to handle command line arguments and run the async main
    """
    parser = argparse.ArgumentParser(
        description='Check for Medium emails and archive articles',
        epilog='Example: python main.py --interval 300'
    )
    parser.add_argument('--interval', type=int, default=300,
                       help='Time between checks in seconds (default: 300)')
    parser.add_argument('--verbose', '-v', action='store_true', default=True,
                       help='Enable verbose debug output (default: True)')
    parser.add_argument('--debug-email', '-d', action='store_true', default=True,
                       help='Print detailed email content for debugging (default: True)')
    
    args = parser.parse_args()
    
    print("\n=== Medium Article Archiver Debug Mode ===")
    print(f"Check interval: {args.interval} seconds")
    print(f"Verbose logging: {args.verbose}")
    print(f"Email debugging: {args.debug_email}\n")
    
    try:
        # Run the async main function
        asyncio.run(async_main(args))
    except KeyboardInterrupt:
        print("\n=== Bot stopped by user ===")
        logging.info("Shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        print(f"\n=== Fatal Error: {str(e)} ===")
        logging.error(f"Error during execution: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
