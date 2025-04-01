import os
import re
import logging
import asyncio
from datetime import datetime
from email import message_from_bytes
from email.header import decode_header
from dotenv import load_dotenv
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from utils.archive_scraper import get_archived_url

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
        self.application.add_handler(CommandHandler("start", self.start_command))

    async def initialize(self):
        """Initialize the bot application"""
        await self.application.initialize()
        await self.application.start()
        await self.application.bot.send_message(
            chat_id=self.telegram_chat_id,
            text="🚀 Bot has started! Use /help to see available commands.",
            parse_mode='HTML'
        )

    async def shutdown(self):
        """Shutdown the bot application"""
        await self.application.stop()
        await self.application.shutdown()

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /start command"""
        welcome_text = (
            "👋 Welcome to Medium Article Archiver Bot!\n\n"
            "I will help you archive Medium articles from your email.\n"
            "Use /help to see all available commands.\n\n"
            "Current status: Bot is running and monitoring your emails."
        )
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
        # Send help message after welcome
        await self.help_command(update, context)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /help command"""
        help_text = (
            "🤖 *Medium Article Archiver Bot*\n\n"
            "*Commands:*\n"
            "/start - Start the bot\n"
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
            if not email_checker:
                await status_message.edit_text(
                    "❌ Error: Email checker not initialized. Please wait a moment and try again.",
                    parse_mode='HTML'
                )
                return
            
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

    def get_email_body(self, email_message) -> str:
        """Extract email body safely"""
        for part in email_message.walk():
            if part.get_content_type() == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    if isinstance(payload, bytes):
                        return payload.decode('utf-8', errors='ignore')
                    elif isinstance(payload, str):
                        return payload
                    elif isinstance(payload, list):
                        # Handle multipart messages
                        return '\n'.join(str(p) for p in payload)
                    else:
                        return str(payload)
                except Exception as e:
                    logging.warning(f"Error getting email body: {str(e)}")
                    return part.get_payload()
        return ""

    def extract_article_url(self, email_content: str) -> str:
        """Extract the Medium article URL from the email content"""
        # First try to find URL before "Today's highlights"
        highlights_match = re.search(r'(https://[^\s<>"]+)\s*Today\'s highlights', email_content)
        if highlights_match:
            return highlights_match.group(1)
        
        # If not found, look for any Medium URL
        urls = re.findall(r'https://medium\.com/[^\s<>"]+|https://[^\s<>"]+\.medium\.com/[^\s<>"]+', email_content)
        if urls:
            return urls[0]
            
        raise ValueError("No Medium article URL found in the email")

    def decode_header_value(self, header_value):
        """Decode email header value safely"""
        try:
            decoded_parts = []
            for decoded_str, charset in decode_header(header_value):
                if isinstance(decoded_str, bytes):
                    if charset:
                        decoded_parts.append(decoded_str.decode(charset, errors='ignore'))
                    else:
                        decoded_parts.append(decoded_str.decode('utf-8', errors='ignore'))
                else:
                    decoded_parts.append(str(decoded_str))
            return ' '.join(decoded_parts)
        except Exception as e:
            logging.warning(f"Error decoding header value: {str(e)}")
            return str(header_value)

    def extract_email_content(self, email_message) -> str:
        """Extract and format email content"""
        content = []
        
        # Get email subject
        subject = ""
        for header in email_message.get_all('subject', []):
            subject += self.decode_header_value(header)
        content.append(f"📌 Subject: {subject}\n")
        
        # Get email body
        body = self.get_email_body(email_message)
        
        if body:
            # Clean up the body text
            body = body.strip()
            
            # Find the URL before "Today's highlights"
            highlights_match = re.search(r'(https://[^\s<>"]+)\s*Today\'s highlights', body)
            if highlights_match:
                url_before_highlights = highlights_match.group(1)
                content.append(f"🔗 Article URL: {url_before_highlights}\n")
            
            # Get the content after "Today's highlights"
            highlights_index = body.find("Today's highlights")
            if highlights_index != -1:
                body = body[highlights_index:]
            
            # Remove multiple newlines and clean up whitespace
            body = re.sub(r'\n\s*\n', '\n\n', body)
            body = re.sub(r'\s+', ' ', body)
            
            # Limit the content length
            if len(body) > 1000:
                body = body[:1000] + "...\n\n(Content truncated due to length)"
            content.append("📝 Content:\n" + body)
        
        return "\n".join(content)

    async def process_email(self, email_data: bytes) -> None:
        """Process the email and send notification"""
        try:
            # Parse the email
            email_message = message_from_bytes(email_data)
            
            # Get email body
            body = self.get_email_body(email_message)
            if not body:
                raise ValueError("Could not extract email body")
            
            # Extract article URL
            article_url = self.extract_article_url(body)
            archived_url = get_archived_url(article_url)
            
            # Extract email content
            email_content = self.extract_email_content(email_message)
            
            # Prepare notification message
            message = (
                f"📚 New Medium Article Archived!\n\n"
                f"{email_content}\n\n"
                f"📥 Archived URL: {archived_url}\n"
                f"⏰ Archived at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"Use /help to see available commands"
            )
            
            # Send Telegram notification
            await self.application.bot.send_message(
                chat_id=self.telegram_chat_id,
                text=message,
                parse_mode='HTML'
            )
            
            logging.info(f"Successfully processed and archived article: {article_url}")
            
        except Exception as e:
            error_message = f"Error processing email: {str(e)}"
            logging.error(error_message)
            await self.application.bot.send_message(
                chat_id=self.telegram_chat_id,
                text=f"❌ {error_message}",
                parse_mode='HTML'
            )
            raise

    async def run_polling(self):
        """Run the bot polling in the background"""
        await self.application.run_polling(drop_pending_updates=True) 