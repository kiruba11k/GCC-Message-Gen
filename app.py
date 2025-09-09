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
    st.session_state.api_usage = {"NewsAPI": 0, "Newsdata": 0, "GNews": 0, "Tavily": 0}

if 'search_cache' not in st.session_state:
    st.session_state.search_cache = {}

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
    # st.header("API Configuration")
    # st.info("Get free API keys from the links below")
    newsapi_key = st.secrets["NEWS_API_KEY"]  
    newsdata_key=st.secrets["NEWS_DATA"]
    gnews_key=st.secrets["GNEWS"]
    groq_key=st.secrets["GROQ"]
    tavily_key=st.secrets["TAVELLY"]

    client = TavilyClient(tavily_key)
    
    # newsapi_key = st.text_input("NewsAPI Key", type="password", 
    #                            help="Get from https://newsapi.org/register")
    # newsdata_key = st.text_input("Newsdata.io Key", type="password",
    #                             help="Get from https://newsdata.io/pricing")
    # gnews_key = st.text_input("GNews Key", type="password",
    #                          help="Get from https://gnews.io/register")
    # groq_key = st.text_input("Groq API Key", type="password",
    #                         help="Get from https://console.groq.com/keys")
    
    st.divider()
    st.caption("Made with ❤️ using Streamlit, Groq, and free news APIs")

# Track API usage
def track_usage(api_name):
    """Track API usage to stay within free limits"""
    if api_name in st.session_state.api_usage:
        st.session_state.api_usage[api_name] += 1
    else:
        st.session_state.api_usage[api_name] = 1
    
    # Show warning if approaching limits
    limits = {"NewsAPI": 900, "Newsdata": 180, "GNews": 90,"Tavily":100}
    if api_name in limits and st.session_state.api_usage[api_name] > limits[api_name]:
        st.warning(f"Approaching free limit for {api_name}. Some features may be limited.")

# Process API results
def process_newsapi_results(articles):
    """Process NewsAPI results into standardized format"""
    processed = []
    for article in articles:
        processed.append({
            'title': article.get('title', ''),
            'snippet': article.get('description', ''),
            'url': article.get('url', ''),
            'date': article.get('publishedAt', ''),
            'source': article.get('source', {}).get('name', '')
        })
    return processed

def process_newsdata_results(articles):
    """Process Newsdata.io results into standardized format"""
    processed = []
    for article in articles:
        processed.append({
            'title': article.get('title', ''),
            'snippet': article.get('description', ''),
            'url': article.get('link', ''),
            'date': article.get('pubDate', ''),
            'source': article.get('source_id', '')
        })
    return processed

def process_gnews_results(articles):
    """Process GNews results into standardized format"""
    processed = []
    for article in articles:
        processed.append({
            'title': article.get('title', ''),
            'snippet': article.get('description', ''),
            'url': article.get('url', ''),
            'date': article.get('publishedAt', ''),
            'source': article.get('source', {}).get('name', '')
        })
    return processed

# Search for recent content
def search_recent_content(person_name, company=None, designation=None):
    """Search for recent content using free APIs with fallback logic"""
    # Create cache key
    cache_key = f"{person_name}_{company}_{designation}"
    
    # Check cache first
    if cache_key in st.session_state.search_cache:
        cached_data = st.session_state.search_cache[cache_key]
        # Check if cache is still valid (1 hour)
        if datetime.now() - cached_data['timestamp'] < timedelta(hours=1):
            return cached_data['results']
    
    query = f"{person_name} {company} {designation}".strip()
    results = []
    
    # Try NewsAPI first if key is provided
    if newsapi_key:
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": query,
                "pageSize": 5,
                "sortBy": "publishedAt",
                "apiKey": newsapi_key
            }
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get('status') == 'ok' and data.get('totalResults', 0) > 0:
                results = process_newsapi_results(data['articles'])
                track_usage("NewsAPI")
        except Exception as e:
            st.sidebar.error(f"NewsAPI error: {str(e)}")
    
    # Try Newsdata.io as second option if no results and key provided
    if not results and newsdata_key:
        try:
            url = "https://newsdata.io/api/1/news"
            params = {
                "q": query,
                "language": "en",
                "apikey": newsdata_key
            }
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get('status') == 'success' and data.get('totalResults', 0) > 0:
                results = process_newsdata_results(data.get('results', []))
                track_usage("Newsdata")
        except Exception as e:
            st.sidebar.error(f"Newsdata.io error: {str(e)}")
    
    # Try GNews as third option if no results and key provided
    if not results and gnews_key:
        try:
            url = "https://gnews.io/api/v4/search"
            params = {
                "q": query,
                "max": 5,
                "apikey": gnews_key
            }
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get('totalArticles', 0) > 0:
                results = process_gnews_results(data.get('articles', []))
                track_usage("GNews")
        except Exception as e:
            st.sidebar.error(f"GNews error: {str(e)}")
    
    # Cache the results
    st.session_state.search_cache[cache_key] = {
        'results': results,
        'timestamp': datetime.now()
    }

    if not results and tavily_key:
        try:
            client = TavilyClient(tavily_key)
            query_parts = [person_name]
            if company:
                query_parts.append(company)
            if designation:
                query_parts.append(designation)
            query_string = " ".join(query_parts)
            
            response = client.search(query=query_string)
            if response and "results" in response and response["results"]:
                results = []
                for item in response["results"][:5]:
                    results.append({
                        'title': item.get('title', ''),
                        'snippet': item.get('snippet', ''),
                        'url': item.get('url', ''),
                        'date': item.get('publishedAt', ''),
                        'source': 'Tavily'
                    })
                st.sidebar.success("Tavily search found results!")
                track_usage("Tavily")

        except Exception as e:
            st.sidebar.error(f"Tavily Search error: {str(e)}")

    
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
        for i, content in enumerate(content_data[:3]):  # Use top 2 results
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
        
        submitted = st.form_submit_button("Generate Message")
        
    if submitted:
        if not person_name:
            st.error("Please provide at least a person name")
        else:
            with st.spinner("Searching for recent content..."):
                # Search for content
                content_data = search_recent_content(person_name, company, designation)
                
                if not content_data:
                    st.warning(f"No recent content found for {person_name}. Try providing more details like company or designation.")
                    
                    # Offer manual input as fallback
                    with st.expander("Manual Content Input"):
                        st.info("Since we couldn't find recent content automatically, you can add details manually:")
                        manual_title = st.text_input("Article/Post Title")
                        manual_content = st.text_area("Content Summary")
                        
                        if manual_title and manual_content:
                            content_data = [{
                                'title': manual_title,
                                'snippet': manual_content,
                                'url': '',
                                'date': '',
                                'source': 'Manual Input'
                            }]
                else:
                    st.success(f"Found {len(content_data)} relevant content pieces")
            
            if content_data:
                with st.spinner("Generating message..."):
                    # Generate message
                    message = generate_message(person_name, content_data, company, designation)
                
                if message:
                    # Display results
                    st.success("Message generated successfully!")
                    st.text_area("Generated Message", message, height=150, key="message_output")
                    st.caption(f"Character count: {len(message)}/250")
                    
                    # Show source content
                    with st.expander("Source Content Used"):
                        for i, content in enumerate(content_data[:2]):  # Show top 2 sources
                            st.write(f"**Source {i+1}:** {content['title']}")
                            st.write(f"**Summary:** {content['snippet']}")
                            if content['url']:
                                st.write(f"**URL:** {content['url']}")
                            if content['source']:
                                st.write(f"**Source:** {content['source']}")
                            if i < len(content_data) - 1:
                                st.divider()
                    
                    # Copy button
                    if st.button("Copy Message to Clipboard"):
                        st.write(" Message copied to clipboard!")
                        # Note: Streamlit doesn't directly support clipboard operations
                        # This is a visual indication only
                else:
                    st.error("Failed to generate message. Please check your Groq API key.")
    
    # Display API usage in sidebar
    with st.sidebar:
        st.divider()
        st.subheader("API Usage Today")
        for api, count in st.session_state.api_usage.items():
            st.write(f"{api}: {count} requests")

# Run the app
if __name__ == "__main__":
    main()
