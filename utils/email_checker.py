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

    async def connect_to_imap(self):
        """Connect to the IMAP server"""
        try:
            self.imap = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.imap.login(self.email, self.password)
            logging.info(f"Successfully connected to {self.imap_server}")
        except Exception as e:
            logging.error(f"Failed to connect to IMAP server: {str(e)}")
            raise

    def get_new_emails(self, hours_back=24):
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
            
            if not message_numbers[0]:
                logging.info("No new unread Medium emails found")
                return []
            
            message_ids = message_numbers[0].split()
            logging.info(f"Found {len(message_ids)} new unread Medium emails")
            return message_ids
            
        except Exception as e:
            logging.error(f"Error getting new emails: {str(e)}")
            raise

    async def process_new_emails(self):
        """Process all new emails"""
        try:
            message_ids = self.get_new_emails()
            
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
                    logging.error(f"Error processing email {msg_id}: {str(e)}")
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
            # Store email checker in application context
            self.email_processor.application.email_checker = self
            
            # Start the Telegram bot
            bot_task = asyncio.create_task(self.email_processor.start())
            
            # Connect to email server
            await self.connect_to_imap()
            
            while True:
                try:
                    await self.process_new_emails()
                    logging.info(f"Waiting {check_interval} seconds before next check...")
                    await asyncio.sleep(check_interval)
                    
                except Exception as e:
                    logging.error(f"Error in main loop: {str(e)}")
                    await asyncio.sleep(60)  # Wait a minute before retrying
                    
        except Exception as e:
            logging.error(f"Fatal error: {str(e)}")
            raise
        finally:
            try:
                self.imap.logout()
            except:
                pass

async def main():
    """Main function to run the email checker"""
    checker = EmailChecker()
    await checker.run()

if __name__ == "__main__":
    asyncio.run(main()) 