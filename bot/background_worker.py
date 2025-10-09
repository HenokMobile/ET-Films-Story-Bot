
import asyncio
import aiosqlite
import logging
from telegram import Bot
from datetime import datetime
from collections import deque
import config

logger = logging.getLogger(__name__)

MAX_QUEUE_SIZE = 10000

class BackgroundWorker:
    def __init__(self):
        self.queue = deque()
        self.running = False
        self.bot = None
        self.stats = {
            'processed': 0,
            'duplicates_blocked': 0,
            'errors': 0,
            'queue_rejections': 0
        }
    
    async def initialize(self, bot_token):
        """Initialize background worker with bot instance"""
        self.bot = Bot(token=bot_token)
        await self._enable_wal_mode()
        logger.info("🔧 Background Worker initialized with WAL mode")
    
    async def _enable_wal_mode(self):
        """Enable WAL mode for better concurrent access"""
        for db_path in [config.SINGLE_DB_PATH, config.SERIES_DB_PATH]:
            try:
                async with aiosqlite.connect(db_path) as db:
                    await db.execute('PRAGMA journal_mode=WAL')
                    await db.execute('PRAGMA busy_timeout=5000')
                    await db.commit()
            except Exception as e:
                logger.warning(f"WAL mode setup warning for {db_path}: {e}")
    
    def add_to_queue(self, file_data):
        """Add file to processing queue with size limit"""
        if len(self.queue) >= MAX_QUEUE_SIZE:
            logger.warning(f"⚠️ Queue FULL ({MAX_QUEUE_SIZE})! Rejecting: {file_data.get('file_name')}")
            self.stats['queue_rejections'] += 1
            return False
        
        self.queue.append(file_data)
        logger.info(f"📋 Added to queue: {file_data.get('file_name')} (Queue size: {len(self.queue)})")
        return True
    
    async def start(self):
        """Start background processing with concurrent workers for 10x speed"""
        self.running = True
        num_workers = 10  # Process 10 files simultaneously
        logger.info(f"🚀 Background Worker started with {num_workers} parallel workers!")
        
        # Create worker pool
        workers = []
        for i in range(num_workers):
            workers.append(asyncio.create_task(self._worker(i)))
        
        # Wait for all workers
        await asyncio.gather(*workers, return_exceptions=True)
    
    async def _worker(self, worker_id):
        """Individual worker to process files concurrently"""
        logger.info(f"👷 Worker #{worker_id} started")
        
        while self.running:
            try:
                if self.queue:
                    file_data = self.queue.popleft()
                    await self.process_file(file_data)
                else:
                    await asyncio.sleep(0.01)  # Very brief pause when queue empty
            except IndexError:
                # Queue was empty, another worker got the item
                await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"❌ Worker #{worker_id} error: {e}")
                self.stats['errors'] += 1
                await asyncio.sleep(0.1)
    
    async def process_file(self, file_data):
        """Process file with atomic duplicate detection and database save"""
        try:
            file_name = file_data.get('file_name')
            file_size = file_data.get('file_size', 0)
            channel_id = file_data.get('channel_id')
            message_id = file_data.get('message_id')
            film_type = file_data.get('film_type')
            
            db_path = config.SINGLE_DB_PATH if film_type == 'single' else config.SERIES_DB_PATH
            table_name = 'single_movies' if film_type == 'single' else 'series'
            
            async with aiosqlite.connect(db_path) as db:
                await db.execute('PRAGMA busy_timeout=5000')
                
                cursor = await db.execute(f'''
                    SELECT id, file_size FROM {table_name} 
                    WHERE file_name = ? AND file_size > 0
                ''', (file_name,))
                
                existing = await cursor.fetchone()
                
                if existing and existing[1] == file_size:
                    try:
                        await self.bot.delete_message(chat_id=channel_id, message_id=message_id)
                        logger.info(f"🗑️ Deleted duplicate from channel: {file_name}")
                        self.stats['duplicates_blocked'] += 1
                    except Exception as e:
                        logger.error(f"❌ Error deleting duplicate: {e}")
                else:
                    await db.execute(f'''
                        INSERT INTO {table_name} 
                        (file_id, message_id, file_unique_id, file_name, file_title, channel_id, file_size)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(file_id) DO UPDATE SET
                            message_id = excluded.message_id,
                            file_size = excluded.file_size,
                            file_title = excluded.file_title
                    ''', (
                        file_data['file_id'],
                        file_data['message_id'],
                        file_data['file_unique_id'],
                        file_data['file_name'],
                        file_data['file_title'],
                        file_data['channel_id'],
                        file_data['file_size']
                    ))
                    await db.commit()
                    logger.info(f"✅ Saved/Updated to database: {file_name}")
            
            self.stats['processed'] += 1
            
        except Exception as e:
            logger.error(f"❌ Error processing file: {e}")
            self.stats['errors'] += 1
    
    def get_stats(self):
        """Get worker statistics"""
        return {
            'queue_size': len(self.queue),
            'processed': self.stats['processed'],
            'duplicates_blocked': self.stats['duplicates_blocked'],
            'errors': self.stats['errors'],
            'queue_rejections': self.stats['queue_rejections']
        }
    
    def log_stats(self):
        """Log comprehensive statistics"""
        stats = self.get_stats()
        logger.info(
            f"📊 Background Worker Stats:\n"
            f"   Queue: {stats['queue_size']}\n"
            f"   Processed: {stats['processed']}\n"
            f"   Duplicates: {stats['duplicates_blocked']}\n"
            f"   Errors: {stats['errors']}\n"
            f"   Rejections: {stats['queue_rejections']}"
        )
    
    async def stop(self):
        """Stop background worker"""
        self.running = False
        logger.info("🛑 Background Worker stopped")

background_worker = BackgroundWorker()
