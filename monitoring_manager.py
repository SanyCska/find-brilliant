"""
Monitoring Manager
Handles dynamic loading and management of search requests from database.
Maps groups to keywords and users for efficient message processing.
"""
import logging
from typing import Dict, List, Set, Tuple, Optional
from database import Database

logger = logging.getLogger(__name__)


class MonitoringManager:
    """
    Manages monitoring configuration loaded from database.
    Maintains mappings of groups to keywords and users for efficient lookup.
    """
    
    def __init__(self, db: Database):
        """
        Initialize the monitoring manager.
        
        Args:
            db: Database instance
        """
        self.db = db
        
        # Mapping of group_id -> list of (keywords_set, user_telegram_id, request_id)
        self.group_monitors: Dict[int, List[Tuple[Set[str], int, int]]] = {}
        
        # Set of all monitored group IDs for quick lookup
        self.monitored_group_ids: Set[int] = set()
        
        # Cache of all active search requests
        self.active_requests: List[Dict] = []
    
    def load_monitoring_data(self) -> None:
        """
        Load all active search requests from database and build monitoring mappings.
        This should be called on startup and periodically to refresh data.
        """
        logger.info("📊 Loading monitoring data from database...")
        
        try:
            # Get all active search requests with details
            requests = self.db.get_all_active_search_requests_with_details()
            
            if not requests:
                logger.warning("⚠️  No active search requests found in database")
                self.group_monitors = {}
                self.monitored_group_ids = set()
                self.active_requests = []
                return
            
            # Clear existing data
            self.group_monitors = {}
            self.monitored_group_ids = set()
            self.active_requests = requests
            
            # Build monitoring mappings
            for request in requests:
                request_id = request['id']
                user_telegram_id = request['user_telegram_id']
                keywords = request.get('keywords', [])
                groups = request.get('groups', [])
                
                logger.info(
                    f"📝 Processing request {request_id}: "
                    f"User={user_telegram_id}, Keywords={len(keywords)}, Groups={len(groups)}"
                )
                
                # Skip if no keywords or no groups
                if not keywords or not groups:
                    logger.warning(
                        f"⚠️  Request {request_id} has no keywords or groups, skipping"
                    )
                    continue
                
                # Extract keyword strings and convert to set for faster lookup
                keyword_set = {kw['keyword'].lower() for kw in keywords}
                logger.info(f"   Keywords for request {request_id}: {keyword_set}")
                
                # Add this request to each group's monitors
                for group in groups:
                    group_id = group['telegram_group_id']
                    group_title = group.get('title', 'Unknown')
                    
                    logger.info(
                        f"   Adding monitor: Group {group_id} ({group_title}) -> "
                        f"Request {request_id}"
                    )
                    
                    # Add to monitored groups set
                    self.monitored_group_ids.add(group_id)
                    
                    # Add mapping: group_id -> (keywords, user_id, request_id)
                    if group_id not in self.group_monitors:
                        self.group_monitors[group_id] = []
                    
                    self.group_monitors[group_id].append(
                        (keyword_set, user_telegram_id, request_id)
                    )
            
            # Log summary
            logger.info(f"✅ Loaded {len(requests)} active search requests")
            logger.info(f"📢 Monitoring {len(self.monitored_group_ids)} unique groups")
            
            # Log details for each monitored group
            for group_id in self.monitored_group_ids:
                monitors = self.group_monitors[group_id]
                logger.debug(
                    f"   Group {group_id}: {len(monitors)} active search request(s)"
                )
            
        except Exception as e:
            logger.error(f"❌ Error loading monitoring data: {e}", exc_info=True)
            raise
    
    def is_monitored_group(self, group_id: int) -> bool:
        """
        Check if a group is being monitored.
        
        Args:
            group_id: Telegram group ID
            
        Returns:
            True if group is monitored, False otherwise
        """
        return group_id in self.monitored_group_ids
    
    def check_message(
        self,
        group_id: int,
        message_text: Optional[str]
    ) -> List[Tuple[int, List[str], int]]:
        """
        Check if a message matches any keywords for the given group.
        
        Args:
            group_id: Telegram group ID
            message_text: Message text to check
            
        Returns:
            List of tuples (user_telegram_id, matched_keywords, request_id)
            for each matching search request
        """
        if not message_text:
            logger.info(f"🔍 check_message: No message text provided")
            return []
        
        if group_id not in self.group_monitors:
            logger.info(
                f"🔍 check_message: Group {group_id} NOT in monitored groups. "
                f"Monitored groups: {list(self.group_monitors.keys())}"
            )
            return []
        
        message_lower = message_text.lower()
        matches = []
        
        # Log what we're checking
        monitors_for_group = self.group_monitors[group_id]
        logger.info(
            f"🔍 Checking group {group_id} with {len(monitors_for_group)} monitor(s) "
            f"for message: '{message_lower[:50]}...'"
        )
        
        # Check each search request that monitors this group
        for keyword_set, user_telegram_id, request_id in monitors_for_group:
            logger.info(
                f"🔍 Request {request_id} - Checking keywords: {keyword_set}"
            )
            
            # Find which keywords match
            matched_keywords = [
                kw for kw in keyword_set
                if kw in message_lower
            ]
            
            # If any keywords matched, add to results
            if matched_keywords:
                logger.info(
                    f"✅ Match found! Request {request_id} - Keywords: {matched_keywords}"
                )
                matches.append((user_telegram_id, matched_keywords, request_id))
            else:
                logger.debug(
                    f"❌ No match for request {request_id}"
                )
        
        return matches
    
    def get_monitored_groups(self) -> Set[int]:
        """
        Get the set of all monitored group IDs.
        
        Returns:
            Set of Telegram group IDs
        """
        return self.monitored_group_ids.copy()
    
    def get_stats(self) -> Dict[str, any]:
        """
        Get statistics about current monitoring state.
        
        Returns:
            Dictionary with monitoring statistics
        """
        return {
            'active_requests': len(self.active_requests),
            'monitored_groups': len(self.monitored_group_ids),
            'total_monitors': sum(len(monitors) for monitors in self.group_monitors.values())
        }
    
    def refresh_if_needed(self) -> bool:
        """
        Check if monitoring data needs refresh and reload if necessary.
        This can be called periodically or triggered by database changes.
        
        Returns:
            True if data was refreshed, False otherwise
        """
        # For now, always refresh when called
        # In the future, could implement change detection
        try:
            self.load_monitoring_data()
            return True
        except Exception as e:
            logger.error(f"❌ Error refreshing monitoring data: {e}")
            return False

