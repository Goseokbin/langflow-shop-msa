"""
Add ai_summary column to orders table
"""
import psycopg2
import os
import sys

def add_ai_summary_column():
    """Add ai_summary column to orders table"""
    
    # Database connection parameters
    db_params = {
        'host': os.getenv('DB_HOST', 'postgresql'),
        'port': os.getenv('DB_PORT', '5432'),
        'database': os.getenv('DB_NAME', 'order_db'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'postgres')
    }
    
    try:
        # Connect to database
        print(f"Connecting to database: {db_params['database']}@{db_params['host']}")
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='orders' AND column_name='ai_summary'
        """)
        
        if cursor.fetchone():
            print("Column 'ai_summary' already exists in orders table")
        else:
            # Add ai_summary column
            print("Adding ai_summary column to orders table...")
            cursor.execute("""
                ALTER TABLE orders 
                ADD COLUMN ai_summary TEXT
            """)
            conn.commit()
            print("✅ Successfully added ai_summary column")
        
        cursor.close()
        conn.close()
        print("Database migration completed successfully")
        
    except Exception as e:
        print(f"❌ Error during migration: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    add_ai_summary_column()

# Made with Bob
