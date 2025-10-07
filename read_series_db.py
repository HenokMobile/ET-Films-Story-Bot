
import sqlite3
import sys

# Connect to series.db
conn = sqlite3.connect('series.db')
cursor = conn.cursor()

# Get total count
cursor.execute("SELECT COUNT(*) FROM series")
total = cursor.fetchone()[0]
print(f"\n📊 Total Series in Database: {total}\n")

# Get all series
cursor.execute("""
    SELECT id, file_name, file_size, channel_id, added_date 
    FROM series 
    ORDER BY added_date DESC
""")

print("=" * 100)
print(f"{'ID':<6} {'File Name':<50} {'Size (MB)':<12} {'Channel':<15} {'Date':<20}")
print("=" * 100)

for row in cursor.fetchall():
    id_val, file_name, file_size, channel_id, added_date = row
    file_size_mb = file_size / (1024 * 1024) if file_size else 0
    print(f"{id_val:<6} {file_name[:48]:<50} {file_size_mb:<12.2f} {channel_id:<15} {added_date:<20}")

print("=" * 100)

# Get statistics
cursor.execute("SELECT SUM(file_size) FROM series")
total_size = cursor.fetchone()[0] or 0
total_size_gb = total_size / (1024 * 1024 * 1024)

print(f"\n📈 Statistics:")
print(f"   Total Files: {total}")
print(f"   Total Size: {total_size_gb:.2f} GB")

conn.close()
