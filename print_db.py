#!/usr/bin/env python3
"""Simple script to read and print the annotations database content."""

import sqlite3
import sys
from pathlib import Path

def print_db_content(db_path):
    """Print the content of the annotations database."""
    db_file = Path(db_path)
    
    if not db_file.exists():
        print(f"Database file not found: {db_path}")
        return
    
    print(f"Reading database: {db_path}")
    print("=" * 80)
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Get table info
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Tables in database: {[table[0] for table in tables]}")
        print()
        
        # Read annotations table
        cursor.execute("SELECT * FROM annotation ORDER BY id")
        rows = cursor.fetchall()
        
        # Get column names
        cursor.execute("PRAGMA table_info(annotation)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"Columns: {columns}")
        print()
        
        print(f"Total records: {len(rows)}")
        print("-" * 80)
        
        # Print header
        header = " | ".join(f"{col:15}" for col in columns)
        print(header)
        print("-" * len(header))
        
        # Print rows
        for row in rows:
            row_str = " | ".join(f"{str(val)[:15]:15}" for val in row)
            print(row_str)
            
        print("-" * 80)
        
        # Summary statistics
        cursor.execute("SELECT rating, COUNT(*) FROM annotation WHERE rating > 0 GROUP BY rating ORDER BY rating")
        rating_counts = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(*) FROM annotation WHERE marked = 1")
        marked_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM annotation WHERE rating = 0")
        unrated_count = cursor.fetchone()[0]
        
        print("\nSummary:")
        print(f"- Unrated images: {unrated_count}")
        print(f"- Marked images: {marked_count}")
        print("- Rating distribution:")
        for rating, count in rating_counts:
            print(f"  Rating {rating}: {count} images")
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    
    finally:
        conn.close()

if __name__ == "__main__":
    # Default path
    db_path = "new/2024_SIN_R_PER_T2_L45_1-22-13/annotations.db"
    
    # Allow command line argument
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    print_db_content(db_path)