"""
Fix group IDs in database to use correct format with -100 prefix.
This is needed because Telegram supergroups use -100XXXXXXXXX format.
"""
from database import get_database_from_env

def fix_group_ids():
    """Fix group IDs by converting to -100 prefix format."""
    db = get_database_from_env()
    
    print("🔧 Fixing group IDs in database...")
    
    with db.get_cursor() as cursor:
        # Get all telegram_groups that need fixing
        cursor.execute("""
            SELECT telegram_group_id, username, title
            FROM telegram_groups
            WHERE telegram_group_id > 0
            ORDER BY telegram_group_id
        """)
        groups = cursor.fetchall()
        
        if not groups:
            print("✅ No groups need fixing (all IDs already have correct format)")
            return
        
        print(f"\n📋 Found {len(groups)} group(s) to fix:\n")
        
        for group in groups:
            old_id = group['telegram_group_id']
            new_id = -1000000000000 - old_id  # Convert to -100XXXXXXXXX format
            username = group['username'] or 'N/A'
            title = group['title'] or 'Unknown'
            
            print(f"  {title}")
            print(f"    Old ID: {old_id}")
            print(f"    New ID: {new_id}")
            print(f"    Username: @{username}")
            print()
        
        response = input("Do you want to apply these changes? (yes/no): ").strip().lower()
        
        if response != 'yes':
            print("❌ Cancelled. No changes made.")
            return
        
        # Apply fixes
        for group in groups:
            old_id = group['telegram_group_id']
            new_id = -1000000000000 - old_id
            
            with db.get_connection() as conn:
                with conn.cursor() as update_cursor:
                    # Update telegram_groups table
                    update_cursor.execute("""
                        UPDATE telegram_groups
                        SET telegram_group_id = %s
                        WHERE telegram_group_id = %s
                    """, (new_id, old_id))
                    
                    # Update search_request_groups table (foreign key will handle this if cascading is set)
                    # But let's update explicitly to be safe
                    update_cursor.execute("""
                        UPDATE search_request_groups
                        SET telegram_group_id = %s
                        WHERE telegram_group_id = %s
                    """, (new_id, old_id))
                    
                    conn.commit()
            
            print(f"✅ Fixed: {old_id} -> {new_id}")
        
        print(f"\n✅ Successfully fixed {len(groups)} group(s)!")
        print("🔄 Restart your bot for changes to take effect.")
    
    db.close()

if __name__ == "__main__":
    fix_group_ids()

