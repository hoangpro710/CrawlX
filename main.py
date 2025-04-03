import sys
import logging
import asyncio
import signal
import traceback
import platform
from utils.email_checker import EmailChecker

# Configure root logger for detailed output
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def shutdown(checker, signal=None):
    """Cleanup function to handle graceful shutdown"""
    if signal:
        logger.info(f"Received exit signal {signal.name}...")
    
    try:
        # Stop the bot first
        if checker:
            await checker.stop()
        
        # Wait for tasks to complete
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        
        logger.info(f"Cancelling {len(tasks)} outstanding tasks")
        await asyncio.gather(*tasks, return_exceptions=True)
        
        if hasattr(checker, 'email_processor'):
            await checker.email_processor.shutdown()
        
        logger.info("Shutdown complete.")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")
        logger.debug(traceback.format_exc())

async def async_main():
    """
    Async main function to run the bot
    """
    checker = None
    try:
        # Create the email checker
        checker = EmailChecker()
        
        # Setup signal handlers based on platform
        if platform.system() != 'Windows':
            # Unix-like systems can use add_signal_handler
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(
                    sig,
                    lambda s=sig: asyncio.create_task(shutdown(checker, s))
                )
        else:
            # Windows doesn't support add_signal_handler, use signal.signal instead
            def signal_handler(sig, frame):
                logger.info(f"Received signal {sig}")
                asyncio.create_task(shutdown(checker, signal.Signals(sig)))
            
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        
        print("\n=== Medium Article Archiver Bot ===")
        print("Bot is starting... Use /run_now in Telegram to check emails")
        print("Press Ctrl+C to stop the bot\n")
        
        # Run the bot
        await checker.run_bot_only()
        
    except asyncio.CancelledError:
        logger.info("Main task cancelled")
    except Exception as e:
        logger.error(f"Error during execution: {str(e)}")
        logger.debug(traceback.format_exc())
        raise
    finally:
        if checker:
            await shutdown(checker)

def main():
    """
    Main function to start the bot
    """
    try:
        # Set up the event loop policy for Windows
        if platform.system() == 'Windows':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        # Run the async main function
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\n=== Bot stopped by user ===")
    except Exception as e:
        error_msg = str(e) if str(e) else "Unknown error occurred"
        print(f"\n=== Fatal Error: {error_msg} ===")
        logger.error(f"Error during execution: {error_msg}")
        logger.debug(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
