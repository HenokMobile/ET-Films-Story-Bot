
import asyncio
import sqlite3
import logging
from telegram import Bot
from datetime import datetime
from collections import deque
import config

logger = logging.getLogger(__name__)

class BackgroundWorker:
    def __init__(self):
        self.queue = deque()
        self.running = False
        self.bot = None
        self.stats = {
            'processed': 0,
            'duplicates_blocked': 0,
            'errors': 0
        }
    
    async def initialize(self, bot_token):
        """Initialize background worker with bot instance"""
        self.bot = Bot(token=bot_token)
        logger.info("🔧 Background Worker initialized")
    
    def add_to_queue(self, file_data):
        """Add file to processing queue"""
        self.queue.append(file_data)
        logger.info(f"📋 Added to queue: {file_data.get('file_name')} (Queue size: {len(self.queue)})")
    
    async def start(self):
        """Start background processing"""
        self.running = True
        logger.info("🚀 Background Worker started")
        
        while self.running:
            try:
                if self.queue:
                    file_data = self.queue.popleft()
                    await self.process_file(file_data)
                else:
                    # Wait a bit if queue is empty
                    await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"❌ Background worker error: {e}")
                self.stats['errors'] += 1
                await asyncio.sleep(1)
    
    async def process_file(self, file_data):
        """Process file with duplicate detection and database save"""
        try:
            file_name = file_data.get('file_name')
            file_size = file_data.get('file_size', 0)
            channel_id = file_data.get('channel_id')
            message_id = file_data.get('message_id')
            film_type = file_data.get('film_type')  # 'single' or 'series'
            
            # Determine database path
            db_path = config.SINGLE_DB_PATH if film_type == 'single' else config.SERIES_DB_PATH
            table_name = 'single_movies' if film_type == 'single' else 'series'
            
            # Check for duplicate
            is_duplicate = await self.check_duplicate(db_path, table_name, file_name, file_size)
            
            if is_duplicate:
                # Delete from channel
                try:
                    await self.bot.delete_message(chat_id=channel_id, message_id=message_id)
                    logger.info(f"🗑️ Deleted duplicate from channel: {file_name}")
                    self.stats['duplicates_blocked'] += 1
                except Exception as e:
                    logger.error(f"❌ Error deleting duplicate: {e}")
            else:
                # Save to database
                await self.save_to_database(db_path, table_name, file_data)
                logger.info(f"✅ Saved to database: {file_name}")
            
            self.stats['processed'] += 1
            
        except Exception as e:
            logger.error(f"❌ Error processing file: {e}")
            self.stats['errors'] += 1
    
    async def check_duplicate(self, db_path, table_name, file_name, file_size):
        """Check if file is duplicate"""
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(f'''
                    SELECT id FROM {table_name} 
                    WHERE file_name = ? AND (file_size = ? OR file_size = 0)
                ''', (file_name, file_size))
                
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"❌ Error checking duplicate: {e}")
            return False
    
    async def save_to_database(self, db_path, table_name, file_data):
        """Save file to database with atomic operation"""
        try:
            with sqlite3.connect(db_path) as conn:
                # Use INSERT OR IGNORE for atomic operation
                conn.execute(f'''
                    INSERT OR IGNORE INTO {table_name} 
                    (file_id, message_id, file_unique_id, file_name, file_title, channel_id, file_size)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    file_data['file_id'],
                    file_data['message_id'],
                    file_data['file_unique_id'],
                    file_data['file_name'],
                    file_data['file_title'],
                    file_data['channel_id'],
                    file_data['file_size']
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"❌ Error saving to database: {e}")
            raise
    
    def get_stats(self):
        """Get worker statistics"""
        return {
            'queue_size': len(self.queue),
            'processed': self.stats['processed'],
            'duplicates_blocked': self.stats['duplicates_blocked'],
            'errors': self.stats['errors']
        }
    
    async def stop(self):
        """Stop background worker"""
        self.running = False
        logger.info("🛑 Background Worker stopped")

# Global worker instance
background_worker = BackgroundWorker()
