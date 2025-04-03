import os
import imaplib
import email
import asyncio
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from utils.email_processor import EmailProcessor

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class EmailChecker:
    def __init__(self):
        """Initialize the EmailChecker with email and IMAP settings"""
        self.email = os.getenv('EMAIL_ADDRESS')
        self.password = os.getenv('EMAIL_PASSWORD')
        self.imap_server = os.getenv('IMAP_SERVER', 'imap.gmail.com')
        self.imap_port = int(os.getenv('IMAP_PORT', '993'))
        
        if not self.email or not self.password:
            raise ValueError("EMAIL_ADDRESS and EMAIL_PASSWORD must be set in .env file")
        
        # Initialize email processor with reference to this checker
        self.email_processor = EmailProcessor(email_checker=self)
        self.processed_emails = set()
        self.first_check = True
        self._stop_event = asyncio.Event()

    async def connect_to_imap(self):
        """Connect to the IMAP server"""
        try:
            self.imap = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.imap.login(self.email, self.password)
            logging.info(f"Successfully connected to {self.imap_server}")
            
            # Send connection status to Telegram
            await self.email_processor.application.bot.send_message(
                chat_id=self.email_processor.telegram_chat_id,
                text=f"📧 Connected to email server: {self.imap_server}\nMonitoring for new Medium articles...",
                parse_mode='HTML'
            )
        except Exception as e:
            error_msg = f"Failed to connect to IMAP server: {str(e)}"
            logging.error(error_msg)
            await self.email_processor.application.bot.send_message(
                chat_id=self.email_processor.telegram_chat_id,
                text=f"❌ {error_msg}",
                parse_mode='HTML'
            )
            raise

    async def get_new_emails(self, hours_back=24):
        """
        Get new unread emails from the Medium label
        
        Args:
            hours_back (int): Number of hours to look back for emails
            
        Returns:
            list: List of email message IDs
        """
        try:
            # Select the Medium label
            self.imap.select('"Medium"')
            
            # Calculate the date range
            date = (datetime.now() - timedelta(hours=hours_back)).strftime("%d-%b-%Y")
            
            # Search for unread emails from Medium
            _, message_numbers = self.imap.search(None, 
                f'(UNSEEN FROM "noreply@medium.com" SINCE "{date}")')
            
            message_ids = message_numbers[0].split() if message_numbers[0] else []
            
            # Send status message only on first check or if emails found
            if self.first_check or message_ids:
                status_msg = (
                    f"📬 Found {len(message_ids)} new unread Medium email(s)"
                    if message_ids else
                    "📭 No new unread Medium emails found"
                )
                await self.email_processor.application.bot.send_message(
                    chat_id=self.email_processor.telegram_chat_id,
                    text=status_msg,
                    parse_mode='HTML'
                )
                self.first_check = False
            
            return message_ids
            
        except Exception as e:
            error_msg = f"Error getting new emails: {str(e)}"
            logging.error(error_msg)
            await self.email_processor.application.bot.send_message(
                chat_id=self.email_processor.telegram_chat_id,
                text=f"❌ {error_msg}",
                parse_mode='HTML'
            )
            raise

    async def process_new_emails(self):
        """Process new emails when /run_now is called"""
        try:
            # Connect to email server
            await self.email_processor.application.bot.send_message(
                chat_id=self.email_processor.telegram_chat_id,
                text="🔄 Connecting to email server...",
                parse_mode='HTML'
            )
            
            await self.connect_to_imap()
            
            # Search for Medium emails
            emails = await self.get_new_emails()
            if not emails:
                await self.email_processor.application.bot.send_message(
                    chat_id=self.email_processor.telegram_chat_id,
                    text="ℹ️ No new Medium emails found",
                    parse_mode='HTML'
                )
                return
            
            # Process each email
            for email_id in emails:
                email_data = await self.fetch_email(email_id)
                await self.email_processor.process_email(email_data)
                await self.mark_as_read(email_id)
            
        except Exception as e:
            logging.error(f"Error processing emails: {str(e)}")
            await self.email_processor.application.bot.send_message(
                chat_id=self.email_processor.telegram_chat_id,
                text=f"❌ Error checking emails: {str(e)}",
                parse_mode='HTML'
            )
        finally:
            # Always disconnect from email server
            await self.disconnect()

    async def run_bot_only(self):
        """Run only the Telegram bot without interval checking"""
        try:
            # Initialize the email processor
            await self.email_processor.initialize()
            
            # Send startup message
            await self.email_processor.application.bot.send_message(
                chat_id=self.email_processor.telegram_chat_id,
                text="🤖 Bot is running!\nUse /run_now to check for new Medium articles\nUse /help to see all commands",
                parse_mode='HTML'
            )
            
            # Start the application
            await self.email_processor.application.initialize()
            await self.email_processor.application.start()
            await self.email_processor.application.updater.start_polling()
            
            # Keep the bot running until stop event is set
            await self._stop_event.wait()
            
            # Stop the bot
            await self.email_processor.application.updater.stop()
            await self.email_processor.application.stop()
            
        except Exception as e:
            logging.error(f"Error running bot: {str(e)}")
            raise
        finally:
            # Don't try to shutdown here - it will be handled by the main process
            pass

    async def stop(self):
        """Stop the bot"""
        self._stop_event.set()

    async def disconnect(self):
        """Disconnect from IMAP server"""
        try:
            if hasattr(self, 'imap'):
                self.imap.close()
                self.imap.logout()
        except Exception as e:
            logging.error(f"Error disconnecting from IMAP: {str(e)}")

    async def fetch_email(self, email_id):
        """Fetch email data by ID"""
        try:
            _, msg_data = self.imap.fetch(email_id, '(RFC822)')
            return msg_data[0][1]
        except Exception as e:
            logging.error(f"Error fetching email {email_id}: {str(e)}")
            raise

    async def mark_as_read(self, email_id):
        """Mark email as read"""
        try:
            self.imap.store(email_id, '+FLAGS', '(\Seen)')
            logging.info(f"Marked email {email_id} as read")
        except Exception as e:
            logging.error(f"Error marking email {email_id} as read: {str(e)}")
            raise

    async def initialize(self):
        """Initialize the email processor"""
        await self.email_processor.initialize()

    async def shutdown(self):
        """Shutdown the email processor"""
        if hasattr(self, 'email_processor'):
            await self.email_processor.shutdown()

async def main():
    """Main function to run the email checker"""
    checker = EmailChecker()
    await checker.run()

if __name__ == "__main__":
    asyncio.run(main()) 