import os
import re
import logging
from datetime import datetime
from email import message_from_bytes
from email.header import decode_header
from dotenv import load_dotenv
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from .archive_scraper import get_archived_url

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')

class EmailProcessor:
    def __init__(self):
        """Initialize the EmailProcessor with Telegram bot token"""
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        if not self.telegram_bot_token or not self.telegram_chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env file")
        
        # Initialize the application
        self.application = Application.builder().token(self.telegram_bot_token).build()
        
        # Add command handlers
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("run_now", self.run_now_command))
        
        # Start the bot
        self.bot = self.application.bot

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /help command"""
        help_text = (
            "🤖 *Medium Article Archiver Bot*\n\n"
            "*Commands:*\n"
            "/help - Show this help message\n"
            "/run_now - Manually check for new Medium articles\n\n"
            "*Features:*\n"
            "• Automatically archives Medium articles from your email\n"
            "• Sends notifications when new articles are archived\n"
            "• Provides both original and archived URLs\n"
            "• Manual check option with /run_now command\n\n"
            "*How it works:*\n"
            "1. Monitors your email for Medium newsletters\n"
            "2. Extracts article URLs\n"
            "3. Archives them using archive.ph\n"
            "4. Sends you a notification with links\n\n"
            "*Need help?*\n"
            "If you encounter any issues, please check:\n"
            "• Email configuration in .env file\n"
            "• Telegram bot token and chat ID\n"
            "• Internet connection\n\n"
            "For more information, contact the administrator."
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def run_now_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /run_now command"""
        try:
            # Send initial status message
            status_message = await update.message.reply_text(
                "🔄 Checking for new Medium articles...",
                parse_mode='HTML'
            )
            
            # Get the email checker instance from context
            email_checker = context.application.email_checker
            
            # Process new emails
            await email_checker.process_new_emails()
            
            # Update status message
            await status_message.edit_text(
                "✅ Check completed! Check your notifications for any new articles.",
                parse_mode='HTML'
            )
            
        except Exception as e:
            error_message = f"❌ Error checking for new articles: {str(e)}"
            logging.error(error_message)
            await update.message.reply_text(error_message, parse_mode='HTML')

    def extract_article_url(self, email_content: str) -> str:
        """
        Extract the Medium article URL from the email content
        
        Args:
            email_content (str): The content of the email
            
        Returns:
            str: The extracted article URL
        """
        # Look for URLs in the email content
        urls = re.findall(r'https://medium\.com/[^\s<>"]+|https://[^\s<>"]+\.medium\.com/[^\s<>"]+', email_content)
        if not urls:
            raise ValueError("No Medium article URL found in the email")
        return urls[0]  # Return the first URL found

    def decode_header_value(self, header_value):
        """Decode email header value safely"""
        try:
            decoded_value = decode_header(header_value)[0][0]
            if isinstance(decoded_value, bytes):
                return decoded_value.decode()
            return decoded_value
        except Exception as e:
            logging.warning(f"Error decoding header value: {str(e)}")
            return str(header_value)

    async def process_email(self, email_data: bytes) -> None:
        """
        Process the email, extract the article URL, archive it, and send notification
        
        Args:
            email_data (bytes): Raw email data
        """
        try:
            # Parse the email
            email_message = message_from_bytes(email_data)
            
            # Get email subject
            subject = ""
            for header in email_message.get_all('subject', []):
                subject += self.decode_header_value(header)
            
            # Get email body
            body = ""
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode()
                        else:
                            body = part.get_payload()
                    except Exception as e:
                        logging.warning(f"Error decoding email body: {str(e)}")
                        body = part.get_payload()
                    break
            
            if not body:
                raise ValueError("Could not extract email body")
            
            # Extract and archive the article URL
            article_url = self.extract_article_url(body)
            archived_url = get_archived_url(article_url)
            
            # Prepare notification message
            message = (
                f"📚 New Medium Article Archived!\n\n"
                f"📌 Subject: {subject}\n"
                f"🔗 Original URL: {article_url}\n"
                f"📥 Archived URL: {archived_url}\n"
                f"⏰ Archived at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"Use /help to see available commands"
            )
            
            # Send Telegram notification
            await self.bot.send_message(
                chat_id=self.telegram_chat_id,
                text=message,
                parse_mode='HTML'
            )
            
            logging.info(f"Successfully processed and archived article: {article_url}")
            
        except Exception as e:
            error_message = f"Error processing email: {str(e)}"
            logging.error(error_message)
            # Send error notification to Telegram
            await self.bot.send_message(
                chat_id=self.telegram_chat_id,
                text=f"❌ {error_message}",
                parse_mode='HTML'
            )
            raise

    async def start(self):
        """Start the Telegram bot"""
        await self.application.initialize()
        await self.application.start()
        await self.application.run_polling() 