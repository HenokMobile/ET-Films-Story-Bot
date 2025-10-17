import sqlite3
import config
import logging

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class DatabaseManager:
    def __init__(self):
        self.setup_databases()
        self.user_db_path = config.USER_DB_PATH # Store db paths for use in methods

    def setup_databases(self):
        """Setup all three databases"""
        # Users database
        with sqlite3.connect(config.USER_DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    phone_number TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    balance INTEGER DEFAULT 0,
                    referrer_id INTEGER DEFAULT NULL,
                    referral_count INTEGER DEFAULT 0,
                    total_referral_earnings INTEGER DEFAULT 0,
                    joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

        # Add balance column if it doesn't exist (for existing databases)
        with sqlite3.connect(config.USER_DB_PATH) as conn:
            try:
                conn.execute('ALTER TABLE users ADD COLUMN balance INTEGER DEFAULT 0')
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Add referral columns if they don't exist
            try:
                conn.execute('ALTER TABLE users ADD COLUMN referrer_id INTEGER DEFAULT NULL')
            except sqlite3.OperationalError:
                pass

            try:
                conn.execute('ALTER TABLE users ADD COLUMN referral_count INTEGER DEFAULT 0')
            except sqlite3.OperationalError:
                pass

            try:
                conn.execute('ALTER TABLE users ADD COLUMN total_referral_earnings INTEGER DEFAULT 0')
            except sqlite3.OperationalError:
                pass

            # Payments table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    method TEXT NOT NULL,
                    name TEXT,
                    phone TEXT,
                    account TEXT,
                    amount INTEGER NOT NULL,
                    photo_file_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    rejected_at TIMESTAMP
                )
            ''')
            
            # Add rejected_at column if it doesn't exist (for existing databases)
            try:
                conn.execute('ALTER TABLE payments ADD COLUMN rejected_at TIMESTAMP')
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Migration: Convert existing TEXT user_id to INTEGER if needed
            try:
                # Check if user_id is TEXT type (needs migration)
                cursor = conn.cursor()
                cursor.execute("SELECT type FROM pragma_table_info('payments') WHERE name='user_id'")
                user_id_type = cursor.fetchone()
                
                # Only migrate if user_id is TEXT (not INTEGER)
                if user_id_type and user_id_type[0] == 'TEXT':
                    # Create new table with correct schema (including rejected_at)
                    conn.execute('''
                        CREATE TABLE IF NOT EXISTS payments_new (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            method TEXT NOT NULL,
                            name TEXT,
                            phone TEXT,
                            account TEXT,
                            amount INTEGER NOT NULL,
                            photo_file_id TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            status TEXT DEFAULT 'pending',
                            rejected_at TIMESTAMP
                        )
                    ''')

                    # Check if rejected_at column exists in old table
                    cursor.execute("SELECT name FROM pragma_table_info('payments') WHERE name='rejected_at'")
                    has_rejected_at = cursor.fetchone() is not None
                    
                    # Copy data, converting user_id to INTEGER and preserving rejected_at if it exists
                    if has_rejected_at:
                        conn.execute('''
                            INSERT OR IGNORE INTO payments_new 
                            SELECT id, CAST(user_id AS INTEGER), method, name, phone, account, amount, photo_file_id, created_at, status, rejected_at
                            FROM payments
                        ''')
                    else:
                        conn.execute('''
                            INSERT OR IGNORE INTO payments_new 
                            SELECT id, CAST(user_id AS INTEGER), method, name, phone, account, amount, photo_file_id, created_at, status, NULL
                            FROM payments
                        ''')

                    # Drop old table and rename new one
                    conn.execute('DROP TABLE IF EXISTS payments')
                    conn.execute('ALTER TABLE payments_new RENAME TO payments')
            except Exception as e:
                logger.error(f"Migration error: {e}")
                pass  # Migration not needed or already done

        # Single movies database
        with sqlite3.connect(config.SINGLE_DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS single_movies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT UNIQUE,
                    message_id INTEGER,
                    file_unique_id TEXT,
                    file_name TEXT,
                    file_title TEXT,
                    channel_id INTEGER,
                    file_size INTEGER DEFAULT 0,
                    joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Add file_size column if it doesn't exist
            try:
                conn.execute('ALTER TABLE single_movies ADD COLUMN file_size INTEGER DEFAULT 0')
            except sqlite3.OperationalError:
                pass
            
            # Create indexes for faster search
            try:
                conn.execute('CREATE INDEX IF NOT EXISTS idx_single_filename ON single_movies(file_name)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_single_filesize ON single_movies(file_size)')
                logger.info("✅ Created indexes for single_movies")
            except sqlite3.OperationalError as e:
                logger.warning(f"Index creation warning: {e}")

        # Series database
        with sqlite3.connect(config.SERIES_DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS series (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT UNIQUE,
                    message_id INTEGER,
                    file_unique_id TEXT,
                    file_name TEXT,
                    file_title TEXT,
                    channel_id INTEGER,
                    file_size INTEGER DEFAULT 0,
                    joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Add file_size column if it doesn't exist
            try:
                conn.execute('ALTER TABLE series ADD COLUMN file_size INTEGER DEFAULT 0')
            except sqlite3.OperationalError:
                pass
            
            # Create indexes for faster search
            try:
                conn.execute('CREATE INDEX IF NOT EXISTS idx_series_filename ON series(file_name)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_series_filesize ON series(file_size)')
                logger.info("✅ Created indexes for series")
            except sqlite3.OperationalError as e:
                logger.warning(f"Index creation warning: {e}")
        
        # Download logs table in user database
        with sqlite3.connect(config.USER_DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS download_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    file_id TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_name TEXT,
                    download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    def add_user(self, user_id, username, phone_number, first_name=None, last_name=None):
        """Add user to database"""
        with sqlite3.connect(config.USER_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
            exists = cursor.fetchone() is not None

            if exists:
                cursor.execute('''
                    UPDATE users 
                    SET username = COALESCE(?, username),
                        phone_number = COALESCE(?, phone_number),
                        first_name = COALESCE(?, first_name),
                        last_name = COALESCE(?, last_name)
                    WHERE user_id = ?
                ''', (username, phone_number, first_name, last_name, user_id))
            else:
                cursor.execute('''
                    INSERT INTO users 
                    (user_id, username, phone_number, first_name, last_name)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, username, phone_number, first_name, last_name))
            conn.commit()

    def add_single_movie(self, file_id, message_id, file_unique_id, file_name, file_title, channel_id, file_size=0):
        """Add single movie to database"""
        with sqlite3.connect(config.SINGLE_DB_PATH) as conn:
            # Check if duplicate exists by name and size
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id FROM single_movies 
                WHERE file_name = ? AND file_size = ? AND file_size > 0
            ''', (file_name, file_size))
            
            if cursor.fetchone() and file_size > 0:
                logger.warning(f"Duplicate movie ignored: {file_name} ({file_size} bytes)")
                return False
            
            conn.execute('''
                INSERT OR REPLACE INTO single_movies 
                (file_id, message_id, file_unique_id, file_name, file_title, channel_id, file_size)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (file_id, message_id, file_unique_id, file_name, file_title, channel_id, file_size))
            return True

    def add_series(self, file_id, message_id, file_unique_id, file_name, file_title, channel_id, file_size=0):
        """Add series to database"""
        with sqlite3.connect(config.SERIES_DB_PATH) as conn:
            # Check if duplicate exists by name and size
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id FROM series 
                WHERE file_name = ? AND file_size = ? AND file_size > 0
            ''', (file_name, file_size))
            
            if cursor.fetchone() and file_size > 0:
                logger.warning(f"Duplicate series ignored: {file_name} ({file_size} bytes)")
                return False
            
            conn.execute('''
                INSERT OR REPLACE INTO series 
                (file_id, message_id, file_unique_id, file_name, file_title, channel_id, file_size)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (file_id, message_id, file_unique_id, file_name, file_title, channel_id, file_size))
            return True

    def search_single_movies(self, query):
        """Search single movies by name"""
        with sqlite3.connect(config.SINGLE_DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT file_id, file_name, file_title FROM single_movies 
                WHERE file_name LIKE ? OR file_title LIKE ?
                LIMIT 10
            ''', (f'%{query}%', f'%{query}%'))
            return cursor.fetchall()

    def search_series(self, query):
        """Search series by name"""
        with sqlite3.connect(config.SERIES_DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT file_id, file_name, file_title FROM series 
                WHERE file_name LIKE ? OR file_title LIKE ?
                LIMIT 10
            ''', (f'%{query}%', f'%{query}%'))
            return cursor.fetchall()

    def user_exists(self, user_id):
        """Check if user exists in database"""
        with sqlite3.connect(config.USER_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
            exists = cursor.fetchone() is not None
            return exists

    def get_user_balance(self, user_id):
        """Get user balance - returns integer"""
        try:
            with sqlite3.connect(self.user_db_path) as conn:
                cursor = conn.execute('SELECT COALESCE(balance, 0) FROM users WHERE user_id = ?', (user_id,))
                result = cursor.fetchone()
                if result:
                    balance = result[0]
                    # Convert to integer safely
                    if balance is None:
                        return 0
                    try:
                        return int(float(balance))
                    except (ValueError, TypeError):
                        logger.error(f"Invalid balance value for user {user_id}: {balance}")
                        return 0
                return 0
        except Exception as e:
            logger.error(f"Error getting balance for user {user_id}: {e}")
            return 0

    def set_referrer(self, user_id, referrer_id):
        """Set referrer for a user"""
        with sqlite3.connect(config.USER_DB_PATH) as conn:
            conn.execute('UPDATE users SET referrer_id = ? WHERE user_id = ?', (referrer_id, user_id))

    def get_referrer(self, user_id):
        """Get referrer ID for a user"""
        with sqlite3.connect(config.USER_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT referrer_id FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return result[0] if result else None

    def increment_referral_count(self, user_id):
        """Increment referral count for a user"""
        with sqlite3.connect(config.USER_DB_PATH) as conn:
            conn.execute('UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?', (user_id,))

    def add_referral_earnings(self, user_id, amount):
        """Add referral earnings to user's balance and total earnings"""
        with sqlite3.connect(config.USER_DB_PATH) as conn:
            conn.execute('''
                UPDATE users 
                SET balance = balance + ?, 
                    total_referral_earnings = total_referral_earnings + ? 
                WHERE user_id = ?
            ''', (amount, amount, user_id))

    def get_referral_stats(self, user_id):
        """Get referral statistics for a user"""
        with sqlite3.connect(config.USER_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT referral_count, total_referral_earnings 
                FROM users 
                WHERE user_id = ?
            ''', (user_id,))
            result = cursor.fetchone()
            if result:
                return {
                    'referral_count': result[0] if result[0] else 0,
                    'total_earnings': result[1] if result[1] else 0
                }
            return {'referral_count': 0, 'total_earnings': 0}

    def log_download(self, user_id, file_id, file_type, file_name=None):
        """Log a movie/series download"""
        try:
            with sqlite3.connect(config.USER_DB_PATH) as conn:
                conn.execute('''
                    INSERT INTO download_logs (user_id, file_id, file_type, file_name)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, file_id, file_type, file_name))
                conn.commit()
                logger.info(f"Download logged: user={user_id}, file={file_name}, type={file_type}")
        except Exception as e:
            logger.error(f"Error logging download: {e}")


# Global database instance
db = DatabaseManager()