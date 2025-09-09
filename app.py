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

# Set page config
st.set_page_config(
    page_title="Free Personalized Message Generator",
    layout="centered"
)

# App title and description
st.title("✉ AI-Powered Personalized Message Generator")
st.caption("Generate professional messages based on recent content - completely free!")

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

# Search for content specifically by the person
def search_content_by_person(person_name, company=None, designation=None):
    """Search for articles, blogs, news, and posts by the person using Tavily API"""
    # Create cache key
    cache_key = f"{person_name}_{company}_{designation}_by_author"
    
    # Check cache first
    if cache_key in st.session_state.search_cache:
        cached_data = st.session_state.search_cache[cache_key]
        # Check if cache is still valid (1 hour)
        if datetime.now() - cached_data['timestamp'] < timedelta(hours=1):
            return cached_data['results']
    
    results = []
    
    # Use Tavily for search with author-specific queries
    if tavily_key:
        try:
            client = TavilyClient(tavily_key)
            
            # Create queries specifically to find content by the person
            queries = [
                f'"{person_name}" article OR blog OR post OR "written by" OR "authored by"',
                f'"{person_name}" interview OR podcast OR "guest post" OR "thought leadership"'
            ]
            
            if company:
                queries.append(f'"{person_name}" "{company}" article OR blog OR post')
            if designation:
                queries.append(f'"{person_name}" "{designation}" article OR blog OR post')
            
            # Execute all queries and combine results
            all_results = []
            for query in queries:
                try:
                    response = client.search(
                        query=query,
                        max_results=3,  # Fewer results per query to stay within limits
                        search_depth="advanced",
                        include_answer=False
                    )
                    
                    if response and "results" in response and response["results"]:
                        all_results.extend(response["results"])
                        track_usage("Tavily")
                except Exception as e:
                    st.sidebar.warning(f"Query '{query}' failed: {str(e)}")
                    continue
            
            # Remove duplicates by URL
            seen_urls = set()
            unique_results = []
            for result in all_results:
                if result.get('url') and result['url'] not in seen_urls:
                    seen_urls.add(result['url'])
                    unique_results.append(result)
            
            if unique_results:
                results = process_tavily_results(unique_results)
                st.sidebar.success(f"Found {len(results)} content pieces by {person_name}")
            else:
                st.sidebar.info(f"No content directly by {person_name} found. Trying general search.")
                # Fallback to general search if no author-specific content found
                general_query = f"{person_name} {company} {designation}".strip()
                response = client.search(
                    query=general_query,
                    max_results=5,
                    search_depth="advanced"
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

# Enforce message constraints
def enforce_constraints(message):
    """Ensure message meets all constraints"""
    # Remove prohibited words
    prohibited_words = [
        "exploring", "interested", "learning", "No easy feat", "Impressive",
        "Noteworthy", "Remarkable", "Fascinating", "Admiring", "Inspiring",
        "No small feat", "No easy task", "Stood out"
    ]
    
    for word in prohibited_words:
        message = re.sub(r'\b' + word + r'\b', '', message, flags=re.IGNORECASE)
    
    # Clean up extra spaces
    message = re.sub(r'\s+', ' ', message).strip()
    
    # Trim to 250 characters
    if len(message) > 250:
        message = message[:247] + "..."
    
    return message

# Generate message with Groq
def generate_message(person_name, content_data, company=None, designation=None):
    """Generate personalized message using Groq API"""
    if not groq_key:
        st.error("Please add your Groq API key in the sidebar")
        return None
    
    try:
        client = Groq(api_key=groq_key)
        
        # Prepare content context from search results
        content_context = ""
        for i, content in enumerate(content_data[:2]):  # Use top 2 results
            content_context += f"{i+1}. {content['title']}: {content['snippet']}\n"
        
        # Construct precise prompt with constraints
        prompt = f"""
        Create a personalized message for {person_name} referencing their recent content.
        MAXIMUM 250 CHARACTERS. Be concise and professional.
        
        STRICTLY AVOID these words: exploring, interested, learning, No easy feat, 
        Impressive, Noteworthy, Remarkable, Fascinating, Admiring, Inspiring, 
        No small feat, No easy task, Stood out.
        
        Follow this pattern from these examples:
        - "Hi Niall, Saw your note on how fast digital marketing is evolving, completely agree, especially with how nuanced brand-building is getting across markets. I think a lot about where performance meets storytelling. Let's connect and exchange ideas."
        - "Hi Shane, Saw your post on Pinterest as the 'farmers market of search', timely and sharp. As someone working on digital and content experiences for brands, I'd love to connect and exchange ideas on how discovery trends might reshape content planning."
        
        Recent content to reference:
        {content_context}
        
        Generate a similar message for {person_name}:
        """
        
        # Call Groq API
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",  # Fast and cost-effective
            temperature=0.7,
            max_tokens=150
        )
        
        message = chat_completion.choices[0].message.content.strip()
        
        # Ensure character limit and remove prohibited words
        message = enforce_constraints(message)
        return message
        
    except Exception as e:
        st.error(f"Error generating message: {str(e)}")
        return None

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
                        for i, content in enumerate(content_data[:2]):  # Show top 2 sources
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
                with st.spinner("Generating message..."):
                    # Generate message
                    message = generate_message(person_name, content_data, company, designation)
                
                if message:
                    # Display results
                    st.success("Message generated successfully!")
                    st.text_area("Generated Message", message, height=150, key="message_output")
                    st.caption(f"Character count: {len(message)}/250")
                    
                    # Copy button
                    if st.button("Copy Message to Clipboard"):
                        st.write("Message copied to clipboard!")
                else:
                    st.error("Failed to generate message. Please check your Groq API key.")
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
                                st.text_area("Generated Message", message, height=150, key="manual_message_output")
                                st.caption(f"Character count: {len(message)}/250")
                        else:
                            st.error("Please provide both a title and content summary")
    
    # Display API usage in sidebar
    with st.sidebar:
        st.divider()
        st.subheader("API Usage Today")
        for api, count in st.session_state.api_usage.items():
            st.write(f"{api}: {count} requests")

# Run the app
if __name__ == "__main__":
    main()
