import os
import imaplib
import email
import asyncio
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from .email_processor import EmailProcessor

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
        
        if not all([self.email, self.password]):
            raise ValueError("EMAIL_ADDRESS and EMAIL_PASSWORD must be set in .env file")
        
        self.email_processor = EmailProcessor()
        self.processed_emails = set()
        self.first_check = True

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
        """Process all new emails"""
        try:
            message_ids = await self.get_new_emails()
            
            for msg_id in message_ids:
                if msg_id in self.processed_emails:
                    continue
                    
                try:
                    _, msg_data = self.imap.fetch(msg_id, '(RFC822)')
                    email_body = msg_data[0][1]
                    
                    # Process the email
                    await self.email_processor.process_email(email_body)
                    
                    # Mark as processed
                    self.processed_emails.add(msg_id)
                    
                    # Mark email as read
                    self.imap.store(msg_id, '+FLAGS', '(\Seen)')
                    logging.info(f"Marked email {msg_id} as read")
                    
                except Exception as e:
                    error_msg = f"Error processing email {msg_id}: {str(e)}"
                    logging.error(error_msg)
                    await self.email_processor.application.bot.send_message(
                        chat_id=self.email_processor.telegram_chat_id,
                        text=f"❌ {error_msg}",
                        parse_mode='HTML'
                    )
                    continue
                    
        except Exception as e:
            logging.error(f"Error in process_new_emails: {str(e)}")
            raise

    async def run(self, check_interval=300):
        """
        Run the email checker continuously
        
        Args:
            check_interval (int): Time between checks in seconds (default: 5 minutes)
        """
        try:
            # Initialize the bot
            await self.email_processor.initialize()
            
            # Store email checker in application context
            self.email_processor.application.email_checker = self
            
            # Connect to email server
            await self.connect_to_imap()
            
            # Start bot polling in the background
            polling_task = asyncio.create_task(self.email_processor.run_polling())
            
            try:
                # Do first check immediately
                await self.process_new_emails()
                
                while True:
                    try:
                        # Send status message about next check
                        next_check = datetime.now() + timedelta(seconds=check_interval)
                        await self.email_processor.application.bot.send_message(
                            chat_id=self.email_processor.telegram_chat_id,
                            text=f"⏳ Next check in {check_interval//60} minutes (at {next_check.strftime('%H:%M:%S')})",
                            parse_mode='HTML'
                        )
                        
                        # Wait for next check
                        await asyncio.sleep(check_interval)
                        
                        # Perform the check
                        await self.process_new_emails()
                        
                    except Exception as e:
                        error_msg = f"Error in main loop: {str(e)}"
                        logging.error(error_msg)
                        await self.email_processor.application.bot.send_message(
                            chat_id=self.email_processor.telegram_chat_id,
                            text=f"❌ {error_msg}\nRetrying in 1 minute...",
                            parse_mode='HTML'
                        )
                        await asyncio.sleep(60)  # Wait a minute before retrying
                        
            except asyncio.CancelledError:
                logging.info("Shutting down email checker...")
                await self.email_processor.application.bot.send_message(
                    chat_id=self.email_processor.telegram_chat_id,
                    text="🛑 Bot is shutting down...",
                    parse_mode='HTML'
                )
            finally:
                # Clean up
                await self.email_processor.shutdown()
                try:
                    self.imap.logout()
                except:
                    pass
                    
        except Exception as e:
            error_msg = f"Fatal error: {str(e)}"
            logging.error(error_msg)
            await self.email_processor.application.bot.send_message(
                chat_id=self.email_processor.telegram_chat_id,
                text=f"❌ {error_msg}",
                parse_mode='HTML'
            )
            raise

async def main():
    """Main function to run the email checker"""
    checker = EmailChecker()
    await checker.run()

if __name__ == "__main__":
    asyncio.run(main()) 