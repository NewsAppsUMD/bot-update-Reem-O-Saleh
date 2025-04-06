import os
import json
import re
from datetime import datetime
import requests
from slack import WebClient
from slack.errors import SlackApiError

def load_previous_recalls():
    try:
        with open('previous_recalls.json') as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []

def save_previous_recalls(recalls):
    with open('previous_recalls.json', 'w') as f:
        json.dump(recalls, f)

# Get recalls from FDA API with date range option
def get_recalls_from_api(limit=100, days_back=None):
    base_url = "https://api.fda.gov/food/enforcement.json"
    
    # Build the query parameters
    params = {
        "limit": limit,
        "sort": "report_date:desc"
    }
    
    # Add date range if specified
    if days_back:
        from datetime import datetime, timedelta
        # Calculate the date X days ago in FDA format (YYYYMMDD)
        start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")
        # FDA API format requires a range search
        params["search"] = f"report_date:[{start_date}+TO+99991231]"
        print(f"Fetching recalls from {start_date} to present")
    
    # Build URL with parameters
    url_params = "&".join([f"{k}={v}" for k, v in params.items()])
    url = f"{base_url}?{url_params}"
    
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        data = response.json()
        if "results" in data:
            # Print date range of returned results for debugging
            if data["results"]:
                dates = [r.get("report_date", "Unknown") for r in data["results"]]
                print(f"Retrieved recalls ranging from {min(dates)} to {max(dates)}")
            return data["results"]
        else:
            print("No results found in API response")
            return []
    except Exception as e:
        print(f"Error getting recalls from API: {e}")
        return []

# Categorize allergens from reason for recall
def categorize_allergen(reason):
    reason = reason.lower()
    allergens = {
        'milk': ['milk', 'dairy', 'lactose', 'whey'],
        'eggs': ['egg'],
        'fish': ['fish', 'shellfish', 'seafood'],
        'crustacean': ['crab', 'lobster', 'shrimp', 'crustacean'],
        'tree nuts': ['almond', 'walnut', 'cashew', 'pecan', 'pistachio', 'hazelnut', 'macadamia', 'tree nut'],
        'peanuts': ['peanut', 'arachis'],
        'wheat': ['wheat', 'gluten'],
        'soy': ['soy', 'soya', 'soybean'],
        'sesame': ['sesame'],
        'sulfites': ['sulfite', 'sulphite']
    }
    
    found_allergens = []
    for allergen, keywords in allergens.items():
        if any(keyword in reason for keyword in keywords):
            found_allergens.append(allergen)
    
    return found_allergens

# Categorize the type of recall
def categorize_recall_type(reason):
    reason = reason.lower()
    
    # Define patterns for different recall types
    patterns = {
        'allergen': ['undeclared', 'allergen', 'allergic', 'allergy'],
        'bacteria': ['listeria', 'e. coli', 'e.coli', 'salmonella', 'botulism', 'clostridium'],
        'foreign_material': ['foreign', 'metal', 'plastic', 'glass', 'wood', 'extraneous material'],
        'mislabeling': ['mislabel', 'misbranded', 'incorrect label', 'improper label'],
        'quality': ['quality', 'mold', 'spoilage', 'deterioration'],
        'processing': ['processing', 'underprocessed', 'under-processed', 'temperature abuse'],
        'unauthorized': ['unapproved', 'unauthorized', 'not approved', 'illegal']
    }
    
    # Check for matches
    for recall_type, keywords in patterns.items():
        if any(keyword in reason for keyword in keywords):
            return recall_type
            
    return 'other'

# Determine priority level based on reason and other factors
def determine_priority(recall):
    reason = recall.get('reason_for_recall', '').lower()
    classification = recall.get('classification', '')
    
    # Class I is highest risk
    if 'class i' in classification.lower():
        return 'high'
    
    # High priority for serious issues
    if any(term in reason for term in ['listeria', 'e. coli', 'e.coli', 'salmonella', 'botulism']):
        return 'high'
    
    # Common but serious allergens
    if any(term in reason for term in ['peanut', 'tree nut', 'milk', 'egg']):
        return 'high'
        
    # Class II with health implications
    if 'class ii' in classification.lower() and any(term in reason for term in ['undeclared', 'allergen']):
        return 'medium'
        
    # Class II - less serious issues
    if 'class ii' in classification.lower():
        return 'medium'
    
    # Default to low
    return 'low'

# Extract states from distribution pattern
def extract_states(distribution_pattern):
    # US state abbreviations
    states = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", 
              "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", 
              "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", 
              "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", 
              "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC"]
    
    # Full state names
    state_names = ["Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", 
                   "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho", 
                   "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", 
                   "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota", 
                   "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", 
                   "New Hampshire", "New Jersey", "New Mexico", "New York", 
                   "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon", 
                   "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota", 
                   "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington", 
                   "West Virginia", "Wisconsin", "Wyoming", "District of Columbia"]
    
    found_states = set()
    
    # Check for "nationwide" or "national"
    if distribution_pattern.lower().find("nationwide") != -1 or distribution_pattern.lower().find("national") != -1:
        return ["Nationwide"]
    
    # Extract state abbreviations
    for state in states:
        # Look for state abbreviations surrounded by spaces or punctuation
        pattern = r'(?:^|\W)' + state + r'(?:$|\W)'
        if re.search(pattern, distribution_pattern):
            found_states.add(state)
    
    # Extract full state names
    for state in state_names:
        if state.lower() in distribution_pattern.lower():
            # Get the abbreviation
            idx = state_names.index(state)
            found_states.add(states[idx])
    
    if not found_states:
        return ["Unspecified"]
    
    return sorted(list(found_states))

# Format a single recall for display in Slack without type emojis
def format_recall_for_slack(recall):
    # Extract recall details
    try:
        display_date = datetime.strptime(recall["report_date"], "%Y%m%d")
        formatted_date = display_date.strftime("%B %-d, %Y")
    except (ValueError, KeyError):
        formatted_date = "Recent"
    
    product_description = recall.get('product_description', "No description available")
    reason_for_recall = recall.get('reason_for_recall', "See product description")
    recalling_firm = recall.get('recalling_firm', "Not specified")
    distribution_pattern = recall.get('distribution_pattern', "Not specified")
    classification = recall.get('classification', "Not specified")
    
    # Truncate overly long texts
    max_text_length = 1000  # Shorter for better display
    if len(product_description) > max_text_length:
        product_description = product_description[:max_text_length] + "..."
    if len(reason_for_recall) > max_text_length:
        reason_for_recall = reason_for_recall[:max_text_length] + "..."
    
    # Enhance with categorization
    recall_type = categorize_recall_type(reason_for_recall)
    allergens = categorize_allergen(reason_for_recall)
    priority = determine_priority(recall)
    states = extract_states(distribution_pattern)
    
    # Format recall type for display
    recall_type_display = recall_type.replace('_', ' ').title()
    
    # Set priority indicator
    if priority == 'high':
        priority_indicator = "🔴"
    elif priority == 'medium':
        priority_indicator = "🟠"
    else:
        priority_indicator = "🔵"
    
    # Create a cleaner headline - NO TYPE EMOJI
    headline = f"{priority_indicator} *FDA Recall Alert:* *{recall_type_display}*"
    
    # Format as a single attachment with all content
    text = f"{headline}\n\n"
    text += f"*Product:* {product_description.strip()}\n\n"
    text += f"*Company:* {recalling_firm}\n\n"
    text += f"*Reason:* {reason_for_recall}\n\n"
    text += f"*Recall Date:* {formatted_date}    *Classification:* {classification}\n\n"
    
    # Add allergen information if relevant
    if allergens and (recall_type == 'allergen' or recall_type == 'mislabeling'):
        allergen_text = ", ".join(allergens)
        text += f"*Allergens:* {allergen_text}\n\n"
    
    # Add distribution information
    distribution_text = "Nationwide" if states[0] == "Nationwide" else ", ".join(states)
    text += f"*Distribution:* {distribution_text}\n\n"
    
    # Add link
    text += "<https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts|View more information on FDA website>"
    
    # Set color based on priority
    if priority == 'high':
        color = "#FF0000"  # Red
    elif priority == 'medium':
        color = "#FFA500"  # Orange
    else:
        color = "#2196F3"  # Blue
    
    # Use a single attachment with the text and color
    attachments = [
        {
            "color": color,
            "text": text,
            "mrkdwn_in": ["text"]
        }
    ]
    
    # Use ONLY attachments, not blocks
    return {
        "attachments": attachments,
        "text": ""  # Empty text to avoid duplication
    }

# Identify new recalls by comparing with previous ones and checking dates
def identify_new_recalls(current_recalls, previous_recalls):
    # Track both product descriptions and report dates
    previous_products = {recall.get('product_description', ''): True for recall in previous_recalls}
    
    # Get the most recent date from previous recalls (if any)
    most_recent_date = None
    if previous_recalls:
        try:
            date_sorted = sorted(previous_recalls, 
                                key=lambda x: x.get('report_date', '00000000'), 
                                reverse=True)
            most_recent_date = date_sorted[0].get('report_date', None)
            print(f"Most recent previously processed recall date: {most_recent_date}")
        except (IndexError, KeyError, ValueError):
            most_recent_date = None
    
    new_recalls = []
    for recall in current_recalls:
        product = recall.get('product_description', '')
        report_date = recall.get('report_date', '00000000')
        
        # Consider a recall new if:
        # 1. We haven't seen this product description before, OR
        # 2. The report date is newer than our most recent processed recall
        if product not in previous_products or (most_recent_date and report_date > most_recent_date):
            new_recalls.append(recall)
    
    # Sort by report date (newest first)
    return sorted(new_recalls, key=lambda x: x.get('report_date', '00000000'), reverse=True)

# Extract date as a datetime object for sorting
def get_recall_date(recall):
    try:
        return datetime.strptime(recall["report_date"], "%Y%m%d")
    except (ValueError, KeyError):
        return datetime(1900, 1, 1)

# Generate recall statistics summary from a larger set
def generate_recall_stats(recalls, limit=1000, days_for_stats=90):
    if not recalls:
        return "No data available for statistics."
    
    # Get more recalls for better statistics, using a wider date range
    if len(recalls) < limit:
        recalls = get_recalls_from_api(limit=limit, days_back=days_for_stats)
        print(f"Fetched {len(recalls)} recalls from the last {days_for_stats} days for statistics")
    
    # Count by type
    type_counts = {}
    allergen_counts = {}
    state_counts = {}
    
    for recall in recalls:
        reason = recall.get('reason_for_recall', '')
        distribution = recall.get('distribution_pattern', '')
        
        # Count recall types
        recall_type = categorize_recall_type(reason)
        type_counts[recall_type] = type_counts.get(recall_type, 0) + 1
        
        # Count allergens
        allergens = categorize_allergen(reason)
        for allergen in allergens:
            allergen_counts[allergen] = allergen_counts.get(allergen, 0) + 1
        
        # Count states
        states = extract_states(distribution)
        for state in states:
            if state != "Nationwide" and state != "Unspecified":
                state_counts[state] = state_counts.get(state, 0) + 1
    
    # Format statistics for Slack
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":bar_chart: FDA Recall Statistics"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Based on the last {len(recalls)} FDA food recalls*"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Top Recall Types:*"
            }
        }
    ]
    
    # Format top recall types
    sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
    type_text = "\n".join([f"• {recall_type.replace('_', ' ').title()}: {count} recalls ({count/len(recalls)*100:.1f}%)" 
                           for recall_type, count in sorted_types[:5]])
    
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": type_text
        }
    })
    
    # Add allergen stats if available
    if allergen_counts:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Top Allergen Concerns:*"
            }
        })
        
        sorted_allergens = sorted(allergen_counts.items(), key=lambda x: x[1], reverse=True)
        allergen_text = "\n".join([f"• {allergen.title()}: {count} recalls" 
                                 for allergen, count in sorted_allergens[:5]])
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": allergen_text
            }
        })
    
    return {
        "blocks": blocks,
        "text": "FDA Recall Statistics Summary",  # Fallback text
        "color": "#2196F3"  # Blue
    }

# Send message to Slack
def send_to_slack(payload, token, channel="#slack-bots"):
    try:
        client = WebClient(token=token)
        
        # Validate token and channel
        if not token:
            print("Error: No Slack API token provided")
            return False
            
        # Create a more detailed error message
        try:
            # Only include attachments, not blocks
            response = client.chat_postMessage(
                channel=channel,
                attachments=payload.get("attachments", []),
                text=payload.get("text", "FDA Recall Alert")  # Use a default if text is empty
            )
            print(f"Message posted to {channel}")
            return True
        except SlackApiError as e:
            error_message = str(e)
            if "channel_not_found" in error_message:
                print(f"Error: Channel '{channel}' not found. Make sure the channel exists and the bot has been invited to it.")
            elif "invalid_auth" in error_message:
                print("Error: Authentication failed. Check your Slack API token.")
            elif "not_in_channel" in error_message:
                print(f"Error: Bot is not a member of channel '{channel}'. Please invite the bot to the channel.")
            else:
                print(f"Error posting to Slack: {e}")
            return False
    except Exception as e:
        print(f"Unexpected error when sending to Slack: {str(e)}")
        return False

def main():
    try:
        # Configure Slack token and channel settings
        slack_token = os.environ.get("SLACK_API_TOKEN")
        slack_channel = os.environ.get("SLACK_CHANNEL", "#slack-bots")  
        
        # Check if we should attempt to send to Slack
        should_use_slack = bool(slack_token)
        if should_use_slack:
            print(f"Slack integration enabled. Will send to channel: {slack_channel}")
        else:
            print("Slack integration disabled (no token). Will output to console only.")
        
        # Get date range configuration
        days_back = os.environ.get("DAYS_BACK")
        if days_back:
            try:
                days_back = int(days_back)
                print(f"Configured to look back {days_back} days for recalls")
            except ValueError:
                print(f"Invalid DAYS_BACK value: {days_back}. Using default (no date filter).")
                days_back = None
            
        print("Fetching FDA recall data...")
        
        # Get recalls from the API
        api_recalls = get_recalls_from_api(days_back=days_back)
        print(f"Got {len(api_recalls)} recalls from FDA API")
        
        if not api_recalls:
            print("No recalls retrieved from API. Check your internet connection or FDA API availability.")
            return
        
        # Load previous recalls
        previous_recalls = load_previous_recalls()
        print(f"Loaded {len(previous_recalls)} previous recalls")
        
        # Identify new recalls
        new_recalls = identify_new_recalls(api_recalls, previous_recalls)
        print(f"Found {len(new_recalls)} new recalls")
        
        # Save current recalls for future comparison
        save_previous_recalls(api_recalls[:50])  # Save top 50 recalls
        
        # Get notification limit from environment or use default
        notification_limit = int(os.environ.get("NOTIFICATION_LIMIT", "1"))  # Default to 1 notification
        
        if new_recalls:
            # Sort new recalls by priority and date
            prioritized_recalls = sorted(
                new_recalls, 
                key=lambda r: (
                    0 if determine_priority(r) == "high" else 
                    1 if determine_priority(r) == "medium" else 2, 
                    -get_recall_date(r).timestamp()
                )
            )
            
            print(f"Processing {min(notification_limit, len(prioritized_recalls))} of {len(prioritized_recalls)} new recalls...")
            print(f"Only sending the highest priority recall (set NOTIFICATION_LIMIT environment variable to change this)")
            
            # Initialize success counter
            successful_notifications = 0
            
            for i, recall in enumerate(prioritized_recalls[:notification_limit]):  # Limit to configurable number
                slack_message = format_recall_for_slack(recall)
                priority = determine_priority(recall)
                
                print(f"\nProcessing recall {i+1}/{min(notification_limit, len(prioritized_recalls))} (Priority: {priority}):")
                
                if should_use_slack:
                    success = send_to_slack(slack_message, slack_token, slack_channel)
                    if success:
                        successful_notifications += 1
                else:
                    # For testing without Slack, print to console
                    print(json.dumps(slack_message, indent=2))
                    successful_notifications += 1
            
            print(f"\nSent {successful_notifications} of {min(notification_limit, len(prioritized_recalls))} recall notifications")
            
            # Generate and send statistics if needed
            stats_frequency = os.environ.get("STATS_FREQUENCY", "weekly")
            current_day = datetime.now().strftime("%A").lower()
            days_for_stats = int(os.environ.get("DAYS_FOR_STATS", "90"))
            
            # Force statistics if no previous stats have been sent or according to config
            if ((stats_frequency == "weekly" and current_day == "monday") or 
                stats_frequency == "always" or 
                os.environ.get("SEND_STATS_NOW", "false").lower() == "true"):
                
                print("Generating recall statistics...")
                stats_message = generate_recall_stats(api_recalls, days_for_stats=days_for_stats)
                
                if should_use_slack:
                    send_to_slack(stats_message, slack_token, slack_channel)
                else:
                    print("\nRECALL STATISTICS:")
                    print(json.dumps(stats_message, indent=2))
        else:
            print("No new recalls found.")
            
            # Show the most recent recall anyway if configured to do so
            if api_recalls and os.environ.get("SEND_SUMMARY_WHEN_NO_NEWS", "false").lower() == "true":
                newest_recall = sorted(api_recalls, key=get_recall_date, reverse=True)[0]
                print("\nMOST RECENT FDA RECALL (FOR REFERENCE):")
                slack_message = format_recall_for_slack(newest_recall)
                
                if should_use_slack:
                    send_to_slack(slack_message, slack_token, slack_channel)
                else:
                    print(json.dumps(slack_message, indent=2))
    
    except Exception as e:
        print(f"Error in FDA recall bot: {str(e)}")
        import traceback
        traceback.print_exc()  

if __name__ == "__main__":
    main()