# ET Films Story Bot

## Overview

ET Films Story Bot is a Telegram bot for managing and distributing Ethiopian film content. The bot serves as a comprehensive media management platform that handles both single movies and TV series, with integrated payment processing, referral rewards, and administrative controls. Users can search for content, manage their account balance, make deposits, and earn rewards by inviting friends. The bot includes dual-language support (English/Amharic) and provides a complete finance management system for administrators.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Bot Framework
- **Technology**: Python Telegram Bot library (python-telegram-bot v20.7)
- **Architecture Pattern**: Handler-based event-driven architecture
- **Rationale**: The bot uses telegram.ext's Application framework with separate handlers for commands, messages, and callbacks. This modular approach allows clean separation of concerns and easy feature extension.

### Database Architecture
- **Technology**: SQLite3 (no ORM)
- **Schema Design**: Three separate databases for different concerns:
  - `single.db` - Stores single movie metadata (file_id, file_name, file_title, channel_id, file_size)
  - `series.db` - Stores TV series metadata (same structure as single.db)
  - `user.db` - Stores user data including balance, referrals, and payment records
- **Rationale**: Separation by content type allows independent scaling and management. SQLite chosen for simplicity and zero-configuration deployment. Direct SQL queries used instead of ORM for performance and explicit control.

### Content Management System
- **Dual Content Types**: Separate handlers for single movies (`single.py`) and series (`series.py`)
- **Unified Search**: `all_film.py` provides cross-database search functionality
- **Channel Integration**: Movies stored in Telegram channels with IDs configurable via admin panel
- **Deduplication**: File size and name matching prevents duplicate content storage
- **Design Decision**: Content stored in Telegram channels (not local storage) leverages Telegram's CDN and eliminates storage costs

### Payment & Finance System
- **Payment Methods**: Supports Telebirr, CBEbirr, CBE Bank, and Card payments
- **Validation**: Phone number validation for telecom networks (Ethio Telecom: 09, Safaricom: 07), bank account validation for CBE (must start with 1000, 13-16 digits)
- **Minimum Deposits**: 10 Birr for all payment methods
- **Payment Flow**: User selects method → submits transaction details → admin approval workflow
- **Finance Dashboard**: Admin panel tracks pending/approved/rejected payments with search functionality
- **Rationale**: Manual approval system chosen for fraud prevention and transaction verification in Ethiopian banking context

### Referral & Rewards System
- **Welcome Bonus**: New users receive 5 Birr on registration
- **Referral Rewards**: 2 Birr earned per successful referral
- **Tracking**: Database stores referrer_id, referral_count, and total_referral_earnings per user
- **Link Generation**: Deep links with format `invite_{user_id}` for tracking
- **Notification System**: Real-time notifications sent to referrers on successful conversions
- **Design Decision**: Fixed reward amounts stored in code (configurable via constants) rather than database for performance

### Admin Panel Architecture
- **Access Control**: Single admin user ID (`ADMIN_USER_ID = 6918848131`) with full privileges
- **Modular Admin Components**:
  - `admin.py` - Main admin panel and config management
  - `admin_balance.py` - Finance and balance management dashboard
- **Configuration Management**: Dynamic config file updates with module reloading for runtime changes
- **State Management**: Dictionary-based user state tracking (`user_states`) for multi-step admin workflows
- **Rationale**: Single admin model suitable for small-scale operation; can be extended to role-based system if needed

### State Management
- **User States**: Global dictionary tracking user conversation states (contact sharing, search queries, admin operations)
- **State Types**: 
  - `WAITING_FOR_CONTACT` - Phone number collection
  - `WAITING_FOR_MOVIE_SEARCH` - Single movie search input
  - `WAITING_FOR_SERIES_SEARCH` - Series search input
  - `WAITING_FOR_ALL_SEARCH` - Combined search input
  - Admin-specific states for channel configuration
- **Trade-offs**: In-memory state storage (lost on restart) chosen for simplicity; persistent state possible via database if needed

### UI/UX Design
- **Keyboard Interface**: ReplyKeyboardMarkup for main navigation (pre-built for performance)
- **Inline Keyboards**: InlineKeyboardMarkup for search results and admin operations
- **Dual Language**: Amharic labels for user-facing features, English for technical operations
- **Menu Structure**: 
  - Main menu: Series, Single movies, All films, Balance, Deposit, Referral, Help
  - Admin menu: Finance dashboard, Payment management, Reports
- **Rationale**: Reply keyboards reduce typing; Amharic interface serves Ethiopian market

### Error Handling & Logging
- **Logging Framework**: Python's built-in logging module with INFO level
- **Error Strategy**: Try-catch blocks with graceful degradation and user feedback
- **Database Resilience**: Context managers (`with` statements) ensure connection cleanup
- **Migration Support**: Column existence checks before ALTER TABLE operations
- **Rationale**: Defensive programming approach handles schema evolution and runtime errors

### Configuration Management
- **Environment Variables**: Bot token loaded from `.env` file via python-dotenv
- **Static Config**: `config.py` stores channel IDs, database paths, reward amounts
- **Dynamic Updates**: Admin panel can modify config.py using regex replacement and module reloading
- **Rationale**: Hybrid approach balances security (env vars for secrets) with runtime flexibility (file-based config for business logic)

## External Dependencies

### Telegram Bot API
- **Library**: python-telegram-bot v20.7
- **Purpose**: Core bot functionality, message handling, inline keyboards
- **Integration Points**: All bot interaction logic depends on this library
- **Key Features Used**: Application framework, handlers (Command, Message, CallbackQuery), Update/Context types

### SQLite Database
- **Purpose**: Data persistence for movies, series, users, payments
- **Integration**: Direct sqlite3 module usage (Python stdlib)
- **Schema**: Three separate .db files (single.db, series.db, user.db)
- **Note**: Architecture supports future migration to PostgreSQL if needed

### Python Standard Library
- **sqlite3**: Database operations
- **logging**: Application logging and debugging
- **datetime**: Timestamp management for payments and user registration
- **re**: Regular expressions for config file updates
- **importlib**: Dynamic module reloading for config changes
- **asyncio**: Async/await pattern for Telegram bot operations

### Environment Configuration
- **python-dotenv**: Loads BOT_TOKEN from .env file
- **Purpose**: Keeps sensitive credentials out of source code

### Disabled Integrations
- **AI Search (Gemini)**: Configuration present (`GEMINI_API_KEY = None`) but feature disabled
- **Rationale**: AI search commented out, likely for cost/complexity reasons

### Telegram Channels
- **Single Movie Channel**: ID -1003169574565
- **Series Channel**: ID -1002955565679
- **Purpose**: Content storage and distribution via Telegram's infrastructure
- **Integration**: Bot reads from these channels and forwards content to users