#!/usr/bin/env python3
"""
Database utilities for initializing and managing the PostgreSQL database.
Can be run as a standalone script or imported as a module.
"""
import sys
import os
from database import get_database_from_env


def init_database():
    """
    Initialize the database by running the init_db.sql script.
    Note: The init_db.sql script is automatically run by PostgreSQL
    when the container starts for the first time via docker-entrypoint-initdb.d
    
    This function is here for manual initialization if needed.
    """
    print("Database initialization is handled by Docker automatically.")
    print("The init_db.sql script runs on first container startup.")
    print("\nIf you need to reset the database:")
    print("  1. Stop the containers: docker compose down")
    print("  2. Remove the volume: docker volume rm find-brilliant_postgres_data")
    print("  3. Start again: docker compose up -d")


def test_connection():
    """Test database connection and display tables."""
    try:
        db = get_database_from_env()
        print("✓ Successfully connected to database!")
        
        with db.get_cursor() as cursor:
            # Get list of tables
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            tables = cursor.fetchall()
            
            print("\nDatabase tables:")
            for table in tables:
                print(f"  - {table['table_name']}")
                
                # Get row count for each table
                cursor.execute(f"SELECT COUNT(*) as count FROM {table['table_name']}")
                count = cursor.fetchone()
                print(f"    ({count['count']} rows)")
        
        db.close()
        return True
    except Exception as e:
        print(f"✗ Failed to connect to database: {e}")
        return False


def create_sample_data():
    """Create sample data for testing."""
    try:
        db = get_database_from_env()
        print("Creating sample data...")
        
        # Create a test user
        user_id = db.create_user(
            telegram_id=123456789,
            username="test_user",
            first_name="Test",
            last_name="User"
        )
        print(f"✓ Created test user (ID: {user_id})")
        
        # Create a search request
        request_id = db.create_search_request(
            user_id=user_id,
            title="iPhone Search",
            is_active=True
        )
        print(f"✓ Created search request (ID: {request_id})")
        
        # Add keywords
        keywords = ["iphone", "iphone 14", "iphone 15"]
        keyword_ids = db.add_keywords(request_id, keywords)
        print(f"✓ Added {len(keyword_ids)} keywords")
        
        # Add groups (will be stored in telegram_groups table if not exists)
        groups = [
            {"telegram_group_id": -1001234567890, "username": "testgroup", "title": "Test Group"},
            {"telegram_group_id": -1009876543210, "username": "anothergroup", "title": "Another Group"},
        ]
        group_ids = db.add_groups(request_id, groups)
        print(f"✓ Added {len(group_ids)} groups")
        print("  (Groups stored in telegram_groups table and linked to request)")
        
        # Display the created data
        print("\nSample search request created:")
        requests = db.get_all_active_search_requests_with_details()
        for req in requests:
            print(f"\n  Request ID: {req['id']}")
            print(f"  Title: {req['title']}")
            print(f"  User: @{req['user_username']}")
            print(f"  Keywords: {[k['keyword'] for k in req['keywords']]}")
            print(f"  Groups: {[g['username'] for g in req['groups']]}")
        
        # Show unique groups in telegram_groups table
        with db.get_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM telegram_groups")
            result = cursor.fetchone()
            print(f"\n✓ Total unique groups in database: {result['count']}")
        
        db.close()
        return True
    except Exception as e:
        print(f"✗ Failed to create sample data: {e}")
        return False


def display_all_requests():
    """Display all active search requests with details."""
    try:
        db = get_database_from_env()
        requests = db.get_all_active_search_requests_with_details()
        
        if not requests:
            print("No active search requests found.")
            return True
        
        print(f"\nFound {len(requests)} active search request(s):\n")
        for req in requests:
            print("=" * 60)
            print(f"Request ID: {req['id']}")
            print(f"Title: {req['title'] or '(no title)'}")
            print(f"User: @{req['user_username']} (Telegram ID: {req['user_telegram_id']})")
            print(f"Created: {req['created_at']}")
            
            keywords = req['keywords']
            print(f"\nKeywords ({len(keywords)}):")
            for kw in keywords:
                print(f"  - {kw['keyword']}")
            
            groups = req['groups']
            print(f"\nGroups ({len(groups)}):")
            for grp in groups:
                print(f"  - {grp['title'] or grp['username']} (ID: {grp['telegram_group_id']})")
            print()
        
        db.close()
        return True
    except Exception as e:
        print(f"✗ Failed to display requests: {e}")
        return False


def display_all_groups():
    """Display all unique Telegram groups in the database."""
    try:
        db = get_database_from_env()
        
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    tg.telegram_group_id,
                    tg.username,
                    tg.title,
                    tg.created_at,
                    tg.updated_at,
                    COUNT(srg.id) as usage_count
                FROM telegram_groups tg
                LEFT JOIN search_request_groups srg ON tg.telegram_group_id = srg.telegram_group_id
                GROUP BY tg.telegram_group_id, tg.username, tg.title, tg.created_at, tg.updated_at
                ORDER BY usage_count DESC, tg.title
            """)
            groups = cursor.fetchall()
        
        if not groups:
            print("No Telegram groups found in database.")
            return True
        
        print(f"\n{'='*70}")
        print(f"Unique Telegram Groups in Database: {len(groups)}")
        print(f"{'='*70}\n")
        
        for group in groups:
            print(f"Group ID: {group['telegram_group_id']}")
            print(f"Username: @{group['username'] or 'N/A'}")
            print(f"Title: {group['title'] or 'N/A'}")
            print(f"Used in: {group['usage_count']} search request(s)")
            print(f"Created: {group['created_at']}")
            print(f"Updated: {group['updated_at']}")
            print(f"{'-'*70}")
        
        db.close()
        return True
    except Exception as e:
        print(f"✗ Failed to display groups: {e}")
        return False


def main():
    """Main entry point for the script."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Database utilities for find-brilliant"
    )
    parser.add_argument(
        "command",
        choices=["init", "test", "sample", "list", "groups"],
        help="Command to run: init (show init info), test (test connection), sample (create sample data), list (display all requests), groups (display all unique groups)"
    )
    
    args = parser.parse_args()
    
    if args.command == "init":
        init_database()
    elif args.command == "test":
        success = test_connection()
        sys.exit(0 if success else 1)
    elif args.command == "sample":
        success = create_sample_data()
        sys.exit(0 if success else 1)
    elif args.command == "list":
        success = display_all_requests()
        sys.exit(0 if success else 1)
    elif args.command == "groups":
        success = display_all_groups()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

