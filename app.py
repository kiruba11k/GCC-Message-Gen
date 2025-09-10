import streamlit as st
import requests
from groq import Groq
import re
import json
import os
from datetime import datetime, timedelta
from tavily import TavilyClient

# Initialize session state
if 'api_usage' not in st.session_state:
    st.session_state.api_usage = {"Tavily": 0}

if 'search_cache' not in st.session_state:
    st.session_state.search_cache = {}

if 'content_data' not in st.session_state:
    st.session_state.content_data = None

if 'searched' not in st.session_state:
    st.session_state.searched = False

if 'content_rotation_index' not in st.session_state:
    st.session_state.content_rotation_index = 0

if 'generated_messages' not in st.session_state:
    st.session_state.generated_messages = []

if 'current_message_index' not in st.session_state:
    st.session_state.current_message_index = -1

# Set page config
st.set_page_config(
    page_title="GCC Message Generator",
    layout="centered"
)

# App title and description
st.title("✉ GCC Message Generator")
st.caption("Generate professional messages based on recent content")

# Sidebar for API configuration
with st.sidebar:
    # Get API keys from secrets
    tavily_key = st.secrets["TAVELLY"]
    groq_key = st.secrets["GROQ"]
    
    st.divider()
    st.caption("Made with ❤️ using Streamlit, Groq, and Tavily API")

# Track API usage
def track_usage(api_name):
    """Track API usage to stay within free limits"""
    if api_name in st.session_state.api_usage:
        st.session_state.api_usage[api_name] += 1
    else:
        st.session_state.api_usage[api_name] = 1
    
    # Show warning if approaching limits
    limits = {"Tavily": 1000}
    if api_name in limits and st.session_state.api_usage[api_name] > limits[api_name]:
        st.warning(f"Approaching free limit for {api_name}. Some features may be limited.")

# Process Tavily results
def process_tavily_results(results):
    """Process Tavily results into standardized format"""
    processed = []
    for item in results:
        processed.append({
            'title': item.get('title', ''),
            'snippet': item.get('content', ''),
            'url': item.get('url', ''),
            'date': item.get('published_date', ''),
            'source': 'Tavily Search'
        })
    return processed

# Search for recent content specifically by the person
def search_content_by_person(person_name, company=None, designation=None):
    """Search for recent articles, blogs, news, and posts by the person using Tavily API"""
    # Create cache key
    cache_key = f"{person_name}_{company}_{designation}_author_content"
    
    # Check cache first
    if cache_key in st.session_state.search_cache:
        cached_data = st.session_state.search_cache[cache_key]
        # Check if cache is still valid (1 hour)
        if datetime.now() - cached_data['timestamp'] < timedelta(hours=1):
            return cached_data['results']
    
    results = []
    
    # Use Tavily for search with author-specific queries focused on recent content
    if tavily_key:
        try:
            client = TavilyClient(tavily_key)
            
            # First try: Search with person + company (if company is provided)
            if company:
                company_queries = [
                    f'"{person_name}" "{company}" article OR blog OR post OR "written by" OR "authored by"',
                    f'"{person_name}" "{company}" interview OR podcast OR "guest post" OR "thought leadership"',
                    f'"{person_name}" "{company}" recent publications OR latest articles OR recent posts',
                    f'"{person_name}" site:{company.replace(" ", "").lower()}.com'
                ]
                
                # Execute company-specific queries first
                all_results = []
                for query in company_queries:
                    try:
                        response = client.search(
                            query=query,
                            max_results=3,
                            search_depth="advanced",
                            days=30,
                            include_answer=False
                        )
                        
                        if response and "results" in response and response["results"]:
                            all_results.extend(response["results"])
                            track_usage("Tavily")
                    except Exception as e:
                        st.sidebar.warning(f"Query '{query}' failed: {str(e)}")
                        continue
                
                # Remove duplicates by URL and ensure content is actually by the author
                seen_urls = set()
                unique_results = []
                for result in all_results:
                    if (result.get('url') and 
                        result['url'] not in seen_urls and 
                        (person_name.lower() in result.get('content', '').lower() or 
                         person_name.lower() in result.get('title', '').lower())):
                        seen_urls.add(result['url'])
                        unique_results.append(result)
                
                if unique_results:
                    results = process_tavily_results(unique_results)
                    st.sidebar.success(f"Found {len(results)} content pieces by {person_name} at {company}")
                    
                    # Cache the results
                    st.session_state.search_cache[cache_key] = {
                        'results': results,
                        'timestamp': datetime.now()
                    }
                    
                    return results
            
            # Second try: If no results with company or no company provided, search by person only
            person_queries = [
                f'"{person_name}" article OR blog OR post OR "written by" OR "authored by"',
                f'"{person_name}" interview OR podcast OR "guest post" OR "thought leadership"',
                f'"{person_name}" recent publications OR latest articles OR recent posts'
            ]
            
            if designation:
                person_queries.append(f'"{person_name}" "{designation}" recent publications')
            
            # Execute person-only queries
            all_results = []
            for query in person_queries:
                try:
                    response = client.search(
                        query=query,
                        max_results=3,
                        search_depth="advanced",
                        days=30,
                        include_answer=False
                    )
                    
                    if response and "results" in response and response["results"]:
                        all_results.extend(response["results"])
                        track_usage("Tavily")
                except Exception as e:
                    st.sidebar.warning(f"Query '{query}' failed: {str(e)}")
                    continue
            
            # Remove duplicates by URL and ensure content is actually by the author
            seen_urls = set()
            unique_results = []
            for result in all_results:
                if (result.get('url') and 
                    result['url'] not in seen_urls and 
                    (person_name.lower() in result.get('content', '').lower() or 
                     person_name.lower() in result.get('title', '').lower())):
                    seen_urls.add(result['url'])
                    unique_results.append(result)
            
            if unique_results:
                results = process_tavily_results(unique_results)
                st.sidebar.success(f"Found {len(results)} content pieces by {person_name}")
            else:
                st.sidebar.info(f"No recent content directly by {person_name} found. Trying general search.")
                # Fallback to general search with time restriction
                general_query = f"{person_name} {company} {designation}".strip()
                response = client.search(
                    query=general_query,
                    max_results=5,
                    search_depth="advanced",
                    days=30
                )
                if response and "results" in response and response["results"]:
                    results = process_tavily_results(response["results"])
                    track_usage("Tavily")
                    
        except Exception as e:
            st.sidebar.error(f"Tavily Search error: {str(e)}")
    else:
        st.sidebar.error("Tavily API key is missing")
    
    # Cache the results
    st.session_state.search_cache[cache_key] = {
        'results': results,
        'timestamp': datetime.now()
    }
    
    return results

# Enforce message constraints with new character limits
def enforce_constraints(message, company=None, designation=None):
    """Ensure message meets all constraints including character limits"""
    # Remove prohibited words
    prohibited_words = [
        "exploring", "interested", "learning", "No easy feat", "Impressive",
        "Noteworthy", "Remarkable", "Fascinating", "Admiring", "Inspiring",
        "No small feat", "No easy task", "Stood out", "rare to see", "it's rare to see"
    ]
    
    for word in prohibited_words:
        message = re.sub(r'\b' + word + r'\b', '', message, flags=re.IGNORECASE)
    
    # Remove company name if provided
    if company:
        message = re.sub(r'\b' + re.escape(company) + r'\b', '', message, flags=re.IGNORECASE)
    
    # Remove designation if provided
    if designation:
        message = re.sub(r'\b' + re.escape(designation) + r'\b', '', message, flags=re.IGNORECASE)
    
    # Clean up extra spaces
    message = re.sub(r'\s+', ' ', message).strip()
    
    # Remove any signature at the end (Regards, Kingshuk or similar)
    message = re.sub(r'\n*(Best|Regards|Thanks|Sincerely),?\s*\n*Kingshuk.*$', '', message, flags=re.IGNORECASE)
    
    # Ensure the message has a proper structure
    connection_phrases = ["Would love to connect", "Would be glad to connect", "I'd love to connect", "Let's connect"]
    if not any(phrase in message for phrase in connection_phrases):
        if "connect" in message.lower():
            # Find where "connect" appears and format from there
            connect_index = message.lower().find("connect")
            if connect_index > 0:
                message = message[:connect_index] + "Would love to connect."
            else:
                message = message + "\n\nWould love to connect."
        else:
            message = message + "\n\nWould love to connect."
    
    # Enforce character limits (200-270)
    if len(message) > 270:
        # Try to preserve the connection phrase
        if "Would love to connect" in message:
            main_content = message.split("Would love to connect")[0]
            if len(main_content) > 240:
                # Find the last complete sentence before 240 characters
                last_period = main_content[:240].rfind('.')
                if last_period > 0:
                    main_content = main_content[:last_period+1]
                else:
                    main_content = main_content[:237] + "..."
            message = main_content + "Would love to connect."
        else:
            # Find the last complete sentence before 270 characters
            last_period = message[:270].rfind('.')
            if last_period > 0:
                message = message[:last_period+1]
            else:
                message = message[:267] + "..."
    
    # Check if message is too short - enhance it instead of rejecting
    if len(message) < 200:
        # Enhance short messages with additional content
        enhancement_phrases = [
            "I found your perspective particularly insightful.",
            "This offers a fresh take on the challenges we're seeing in the industry.",
            "Your approach to this topic is quite innovative.",
            "This gives me a new perspective on the matter."
        ]
        
        import random
        enhancement = random.choice(enhancement_phrases)
        
        # Insert enhancement before the connection phrase
        if "Would love to connect" in message:
            parts = message.split("Would love to connect")
            message = parts[0] + enhancement + " Would love to connect" + parts[1] if len(parts) > 1 else parts[0] + enhancement + " Would love to connect"
        else:
            message = message + " " + enhancement
    
    return message

# Generate message with Groq using dynamic patterns
def generate_message(person_name, content_data, company=None, designation=None):
    """Generate personalized message using Groq API with content rotation"""
    if not groq_key:
        st.error("Please add your Groq API key in the sidebar")
        return None
    
    # Rotate through available content for variety
    if content_data:
        rotation_index = st.session_state.content_rotation_index % len(content_data)
        selected_content = content_data[rotation_index]
        st.session_state.content_rotation_index += 1
    else:
        selected_content = None
    
    try:
        client = Groq(api_key=groq_key)
        
        # Prepare content context - use the rotated content
        content_context = ""
        if selected_content:
            content_context = f"Title: {selected_content['title']}\nContent: {selected_content['snippet']}\n"
        else:
            content_context = "No specific content found for reference."
        
        # More specific prompt with clearer examples (no signature in examples)
        prompt = f"""
        Create a professional first-level outreach message for {person_name} based on their specific content.
        The message must be between 200-270 characters. Be concise, professional, and reference the specific content.
        
        STRICTLY AVOID these words and phrases: exploring, interested, learning, No easy feat, 
        Impressive, Noteworthy, Remarkable, Fascinating, Admiring, Inspiring, 
        No small feat, No easy task, Stood out, rare to see, resonates with my own experience.
        
        IMPORTANT: 
        - Do not mention the person's company name or designation
        - Do NOT include any signature like "Regards, Kingshuk" at the end
        - Make each message unique and creative
        - Avoid using the same phrases repeatedly
        - Ensure the message is complete and makes sense
        - Focus on specific insights, not general praise
        
        Use these EXACT patterns as templates but adapt them creatively:

        PATTERN 1 (Specific insight):
        "Hi [Name],
        I appreciated your perspective on [topic]—specifically your point about [specific insight]. [Add creative observation about why this matters]. Would love to connect."

        PATTERN 2 (Industry relevance):
        "Hi [Name],
        Your take on [topic] caught my attention, especially how you framed [specific aspect]. [Connect to broader industry context or challenge]. I'd be glad to connect."

        PATTERN 3 (Practical application):
        "Hi [Name],
        Found your perspective on [topic] quite practical—your approach to [specific method/technique] offers a fresh take on [challenge/opportunity]. Let's connect."

        PATTERN 4 (Timely perspective):
        "Hi [Name],
        Your thoughts on [topic] are particularly relevant now as [industry/field] navigates [current challenge]. The way you highlighted [specific insight] stood out. Would love to connect."

        PATTERN 5 (Nuanced understanding):
        "Hi [Name],
        The nuance in your perspective on [topic] is refreshing—especially how you differentiate between [concept A] and [concept B]. [Add brief personal insight]. Let's connect."

        Content to reference:
        {content_context}
        
        Generate a unique, creative message for {person_name} that follows one of these patterns but with fresh language and perspectives.
        Make it specific to their content, not generic.
        """
        
        # Call Groq API
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.8,  # Higher temperature for more creativity
            max_tokens=200  # Increased tokens for more detailed messages
        )
        
        message = chat_completion.choices[0].message.content.strip()
        
        # Ensure character limit and remove prohibited words
        message = enforce_constraints(message, company, designation)
        
        # Store the generated message with its source info
        if message and selected_content:
            message_data = {
                "message": message,
                "source_title": selected_content['title'],
                "source_snippet": selected_content['snippet'],
                "source_url": selected_content.get('url', ''),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            st.session_state.generated_messages.append(message_data)
            st.session_state.current_message_index = len(st.session_state.generated_messages) - 1
        
        return message
        
    except Exception as e:
        st.error(f"Error generating message: {str(e)}")
        return None

# Navigation functions
def show_previous_message():
    """Show the previous generated message"""
    if st.session_state.current_message_index > 0:
        st.session_state.current_message_index -= 1

def show_next_message():
    """Show the next generated message"""
    if st.session_state.current_message_index < len(st.session_state.generated_messages) - 1:
        st.session_state.current_message_index += 1

# Main app interface
def main():
    # Input form
    with st.form("input_form"):
        col1, col2 = st.columns(2)
        with col1:
            person_name = st.text_input("Person Name*", placeholder="e.g., Dr. Pawan Gupta")
        with col2:
            company = st.text_input("Company", placeholder="e.g., ICanCare")
        designation = st.text_input("Designation", placeholder="e.g., Cybersecurity Expert")
        
        col1, col2 = st.columns(2)
        with col1:
            search_submitted = st.form_submit_button("Search Content")
        with col2:
            generate_submitted = st.form_submit_button("Generate Message")
        
    if search_submitted:
        if not person_name:
            st.error("Please provide at least a person name")
        else:
            with st.spinner("Searching for content by this person..."):
                # Search for content using Tavily with author-specific queries
                content_data = search_content_by_person(person_name, company, designation)
                st.session_state.content_data = content_data
                st.session_state.searched = True
                
                if not content_data:
                    st.warning(f"No content found by {person_name}. Try providing more details like company or designation.")
                else:
                    st.success(f"Found {len(content_data)} content pieces by {person_name}")
                    
                    # Show source content
                    with st.expander("Source Content Found"):
                        for i, content in enumerate(content_data[:]):  
                            st.write(f"**Source {i+1}:** {content['title']}")
                            st.write(f"**Summary:** {content['snippet']}")
                            if content['url']:
                                st.write(f"**URL:** {content['url']}")
                            if content['source']:
                                st.write(f"**Source:** {content['source']}")
                            if i < len(content_data) - 1:
                                st.divider()
    
    if generate_submitted:
        if not person_name:
            st.error("Please provide at least a person name")
        else:
            # Use cached content if available, otherwise search
            if st.session_state.content_data is None or not st.session_state.searched:
                st.info("No content has been searched yet. Searching for content first...")
                with st.spinner("Searching for content by this person..."):
                    content_data = search_content_by_person(person_name, company, designation)
                    st.session_state.content_data = content_data
                    st.session_state.searched = True
                    
                    if not content_data:
                        st.warning(f"No content found by {person_name}. Try providing more details like company or designation.")
            else:
                content_data = st.session_state.content_data
            
            if content_data:
                with st.spinner("Generating professional message..."):
                    # Generate message
                    message = generate_message(person_name, content_data, company, designation)
                
                if message:
                    # Display results
                    st.success("Message generated successfully!")
                    st.caption(f"Character count: {len(message)}/270")
                else:
                    st.error("Failed to generate a valid message. Please try again.")
            else:
                # Offer manual input as fallback
                with st.expander("Manual Content Input"):
                    st.info("Since we couldn't find content by this person automatically, you can add details manually:")
                    manual_title = st.text_input("Article/Post Title")
                    manual_content = st.text_area("Content Summary")
                    
                    if st.button("Generate from Manual Content"):
                        if manual_title and manual_content:
                            content_data = [{
                                'title': manual_title,
                                'snippet': manual_content,
                                'url': '',
                                'date': '',
                                'source': 'Manual Input'
                            }]
                            
                            with st.spinner("Generating message..."):
                                message = generate_message(person_name, content_data, company, designation)
                            
                            if message:
                                st.success("Message generated successfully!")
                                st.caption(f"Character count: {len(message)}/270")
                            else:
                                st.error("Failed to generate a valid message. Please try again.")
                        else:
                            st.error("Please provide both a title and content summary")
    
    # Display generated messages with navigation if available
    if st.session_state.generated_messages:
        st.divider()
        st.subheader("Generated Messages")
        
        # Navigation buttons
        if len(st.session_state.generated_messages) > 1:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if st.button("← Previous", on_click=show_previous_message, 
                            disabled=st.session_state.current_message_index <= 0):
                    pass
            with col2:
                current_idx = st.session_state.current_message_index + 1
                total_msgs = len(st.session_state.generated_messages)
                st.caption(f"Message {current_idx} of {total_msgs}")
            with col3:
                if st.button("Next →", on_click=show_next_message,
                            disabled=st.session_state.current_message_index >= len(st.session_state.generated_messages) - 1):
                    pass
        
        # Display current message
        if 0 <= st.session_state.current_message_index < len(st.session_state.generated_messages):
            current_msg = st.session_state.generated_messages[st.session_state.current_message_index]
            st.text_area("Generated Message", current_msg["message"], height=150, key="message_output")
            st.caption(f"Character count: {len(current_msg['message'])}/270")
            
            # Show source info for this message
            with st.expander("View Source Info"):
                st.write(f"**Source Title:** {current_msg['source_title']}")
                st.write(f"**Source Content:** {current_msg['source_snippet']}")
                if current_msg.get('source_url'):
                    st.write(f"**Source URL:** {current_msg['source_url']}")
                st.write(f"**Generated at:** {current_msg['timestamp']}")
            
            # Copy button
            if st.button("Copy Message to Clipboard", key="copy_button"):
                st.write("Message copied to clipboard!")
    
    # Display API usage in sidebar
    with st.sidebar:
        st.divider()
        st.subheader("API Usage Today")
        for api, count in st.session_state.api_usage.items():
            st.write(f"{api}: {count} requests")

# Run the app
if __name__ == "__main__":
    main()
