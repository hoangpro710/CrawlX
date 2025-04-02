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

    def extract_urls_from_html(self, html_content: str) -> list:
        """Extract Medium article URLs from HTML content"""
        urls = []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Get all links from href attributes
            for link in soup.find_all('a', href=True):
                url = link['href'].strip()
                
                # Match only URLs in format: https://medium.com/@username/article-slug
                if re.match(r'https://medium\.com/@[\w.-]+/[^?]+', url):
                    # Remove any query parameters
                    clean_url = url.split('?')[0]
                    if clean_url not in urls:
                        urls.append(clean_url)
            
            print(f"\nFound {len(urls)} Medium article URLs:")
            for idx, url in enumerate(urls, 1):
                print(f"{idx}. {url}")
                
        except Exception as e:
            print(f"Error extracting URLs from HTML: {str(e)}")
            # Fallback to regex-based extraction
            all_urls = re.findall(r'https://medium\.com/@[\w.-]+/[^?\s<>"]+', html_content)
            urls = [url.split('?')[0] for url in all_urls if url not in urls]
            
        return urls

    def get_email_body(self, email_message) -> tuple:
        """Extract email body and URLs from HTML content"""
        print("\n=== Email Message Structure ===")
        print(f"Content type: {email_message.get_content_type()}")
        print(f"Subject: {email_message.get('subject')}")
        print(f"From: {email_message.get('from')}")
        print(f"To: {email_message.get('to')}")
        print(f"Date: {email_message.get('date')}")
        print("=== End Message Structure ===\n")

        # Find HTML part
        html_part = None
        for part in email_message.walk():
            if part.get_content_type() == "text/html":
                html_part = part
                break
        
        if not html_part:
            print("No HTML content found in email")
            return "", []

        try:
            # Get and decode HTML content
            payload = html_part.get_payload(decode=True)
            if not payload:
                print("Empty HTML payload")
                return "", []

            print("\n=== Processing HTML Content ===")
            print(f"Raw HTML length: {len(payload)}")
            
            # Decode HTML content
            if isinstance(payload, bytes):
                html_content = payload.decode('utf-8', errors='ignore')
            else:
                html_content = str(payload)
            
            # Extract URLs first from the raw HTML
            urls = self.extract_urls_from_html(html_content)
                
            # Then extract text content
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Remove unwanted elements
                for element in soup(["script", "style", "head", "title", "meta", "[document]"]):
                    element.decompose()
                
                # Get text content
                body = soup.get_text(separator=' ', strip=True)
                print(f"Extracted text length: {len(body)}")
                
            except ImportError:
                print("BeautifulSoup not available, using basic HTML cleanup")
                # Basic HTML cleanup if BeautifulSoup is not available
                body = re.sub(r'<[^>]+>', ' ', html_content)
                body = re.sub(r'\s+', ' ', body).strip()
            
            # Clean up the extracted text
            body = re.sub(r'\n\s*\n', '\n\n', body)  # Remove multiple blank lines
            body = re.sub(r'\s+', ' ', body)  # Normalize whitespace
            body = body.strip()
            
            # Print debug information
            print("\n=== Extracted Content ===")
            print("First 500 characters:")
            print("-" * 50)
            print(body[:500])
            print("-" * 50)
            print("\nLast 500 characters:")
            print("-" * 50)
            print(body[-500:] if len(body) > 500 else body)
            print("-" * 50)
            print(f"\nTotal length: {len(body)} characters")
            
            return body, urls
            
        except Exception as e:
            print(f"Error processing HTML content: {str(e)}")
            return "", []

    def extract_article_urls(self, email_content: str, all_urls: list) -> dict:
        """Extract and categorize URLs from email content"""
        urls = {
            'highlights_url': None,
            'medium_urls': [],
            'other_urls': []
        }
        
        # First try to find URL before "Today's highlights"
        highlights_match = re.search(r'(https://medium\.com/@[\w.-]+/[^?\s<>"]+)\s*Today\'s highlights', email_content)
        if highlights_match:
            urls['highlights_url'] = highlights_match.group(1).split('?')[0]
        
        # Add other Medium article URLs
        for url in all_urls:
            # Skip if it's the highlights URL we already found
            if url == urls['highlights_url']:
                continue
                
            # Only add URLs in the correct format
            if re.match(r'https://medium\.com/@[\w.-]+/[^?]+', url):
                if url not in urls['medium_urls']:
                    urls['medium_urls'].append(url)
        
        print("\n=== URL Categorization Results ===")
        print(f"Highlights URL: {urls['highlights_url']}")
        print(f"Medium URLs found: {len(urls['medium_urls'])}")
        for idx, url in enumerate(urls['medium_urls'], 1):
            print(f"{idx}. {url}")
        print("=== End URL Categorization ===\n")
        
        if not urls['highlights_url'] and not urls['medium_urls']:
            raise ValueError("No Medium article URLs found in the email")
            
        return urls

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
        body, urls = self.get_email_body(email_message)
        
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
        """Process the email and archive URLs"""
        try:
            print("\n" + "="*50)
            print("Starting Email Processing")
            print("="*50)
            
            # Parse the email
            email_message = message_from_bytes(email_data)
            
            # Get URLs from email
            print("\n=== Extracting URLs ===")
            _, all_urls = self.get_email_body(email_message)
            
            # Process Medium URLs
            processed_articles = []
            for url in all_urls:
                try:
                    # Only process URLs in the correct format
                    if re.match(r'https://medium\.com/@[\w.-]+/[^?]+', url):
                        clean_url = url.split('?')[0]  # Remove query parameters
                        print(f"\n=== Processing URL: {clean_url} ===")
                        archived_url = get_archived_url(clean_url)
                        processed_articles.append({
                            'original_url': clean_url,
                            'archived_url': archived_url
                        })
                except Exception as e:
                    print(f"Error processing URL {url}: {str(e)}")
                    logging.warning(f"Failed to process URL {url}: {str(e)}")
            
            if not processed_articles:
                raise ValueError("No Medium articles were found to archive")
            
            # Prepare notification message
            message_parts = [
                "📚 New Medium Articles Archived!\n",
                "📥 Archived Articles:"
            ]
            
            for idx, article in enumerate(processed_articles, 1):
                message_parts.append(
                    f"\n{idx}. Original: {article['original_url']}"
                    f"\n   Archived: {article['archived_url']}"
                )
            
            message_parts.extend([
                f"\n\n⏰ Processed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "\nUse /help to see available commands"
            ])
            
            message = '\n'.join(message_parts)
            
            print("\n=== Sending Notification ===")
            # Send Telegram notification
            await self.application.bot.send_message(
                chat_id=self.telegram_chat_id,
                text=message,
                parse_mode='HTML'
            )
            
            print("\n=== Processing Complete ===")
            logging.info(f"Successfully archived {len(processed_articles)} articles")
            
        except Exception as e:
            error_message = f"Error processing email: {str(e)}"
            logging.error(error_message)
            print(f"\n=== Processing Error ===")
            print(f"Error: {str(e)}")
            print(f"Error type: {type(e)}")
            print("=== End Error ===\n")
            await self.application.bot.send_message(
                chat_id=self.telegram_chat_id,
                text=f"❌ {error_message}",
                parse_mode='HTML'
            )
            raise

    async def run_polling(self):
        """Run the bot polling in the background"""
        await self.application.run_polling(drop_pending_updates=True) 