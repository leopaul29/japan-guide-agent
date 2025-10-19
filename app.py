import streamlit as st
import requests
from langchain.agents import create_react_agent, AgentExecutor
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
import os
from urllib.parse import urlencode, parse_qs
import secrets
import hashlib
import base64

# Auth0 Configuration
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
AUTH0_CALLBACK_URL = os.getenv("AUTH0_CALLBACK_URL", "http://localhost:8501")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_info' not in st.session_state:
    st.session_state.user_info = None
if 'code_verifier' not in st.session_state:
    st.session_state.code_verifier = None
if 'state' not in st.session_state:
    st.session_state.state = None

# PKCE Helper Functions
def generate_code_verifier():
    """Generate a cryptographically random code verifier"""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')

def generate_code_challenge(verifier):
    """Generate code challenge from verifier using SHA256"""
    digest = hashlib.sha256(verifier.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')

# Auth0 Functions
def get_auth0_login_url():
    """Generate Auth0 authorization URL with PKCE"""
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    state = secrets.token_urlsafe(32)
    
    # Store in session state
    st.session_state.code_verifier = code_verifier
    st.session_state.state = state
    
    params = {
        'response_type': 'code',
        'client_id': AUTH0_CLIENT_ID,
        'redirect_uri': AUTH0_CALLBACK_URL,
        'scope': 'openid profile email',
        'state': state,
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256'
    }
    
    auth_url = f"https://{AUTH0_DOMAIN}/authorize?{urlencode(params)}"
    return auth_url

def exchange_code_for_token(code):
    """Exchange authorization code for access token"""
    token_url = f"https://{AUTH0_DOMAIN}/oauth/token"
    
    data = {
        'grant_type': 'authorization_code',
        'client_id': AUTH0_CLIENT_ID,
        'client_secret': AUTH0_CLIENT_SECRET,
        'code': code,
        'redirect_uri': AUTH0_CALLBACK_URL,
        'code_verifier': st.session_state.code_verifier
    }
    
    try:
        response = requests.post(token_url, json=data, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Token exchange failed: {str(e)}")
        return None

def get_user_info(access_token):
    """Fetch user information from Auth0"""
    userinfo_url = f"https://{AUTH0_DOMAIN}/userinfo"
    headers = {'Authorization': f'Bearer {access_token}'}
    
    try:
        response = requests.get(userinfo_url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to fetch user info: {str(e)}")
        return None

# Tool to fetch weather from Open-Meteo
@tool
def get_weather(city: str) -> str:
    """Fetch current weather for any city using geocoding and Open-Meteo API.
    
    Args:
        city: Name of the city (e.g., 'Paris', 'Tokyo', 'New York')
    
    Returns:
        Weather information string or error message
    """
    
    # Validate city input
    if not city or len(city.strip()) < 2:
        return "Invalid city name. Please provide a valid city name with at least 2 characters."
    
    city = city.strip()
    
    # Geocoding to get coordinates
    geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
    
    try:
        geo_response = requests.get(geocode_url, timeout=10)
        geo_data = geo_response.json()
        
        if 'results' not in geo_data or len(geo_data['results']) == 0:
            return f"City '{city}' not found. Please check the spelling or try a different city."
        
        location = geo_data['results'][0]
        lat = location['latitude']
        lon = location['longitude']
        city_name = location['name']
        country = location.get('country', '')
        
        # Get weather data
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,precipitation,weather_code,wind_speed_10m&timezone=auto"
        weather_response = requests.get(weather_url, timeout=10)
        weather_data = weather_response.json()
        
        temp = weather_data['current']['temperature_2m']
        precip = weather_data['current']['precipitation']
        weather_code = weather_data['current']['weather_code']
        wind_speed = weather_data['current']['wind_speed_10m']
        
        # Interpret weather code
        conditions = {
            0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
            45: "foggy", 48: "foggy", 51: "light drizzle", 53: "drizzle", 
            55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
            71: "light snow", 73: "snow", 75: "heavy snow", 95: "thunderstorm"
        }
        condition = conditions.get(weather_code, "unknown conditions")
        
        return f"Weather in {city_name}, {country}: {temp}°C, {condition}, precipitation: {precip}mm, wind: {wind_speed} km/h"
    
    except Exception as e:
        return f"Error fetching weather data: {str(e)}"

# Setup AI agent
def create_outfit_agent():
    llm = ChatOpenAI(
        temperature=0.9, 
        model="gpt-4o-mini", 
        api_key=OPENAI_API_KEY
    )
    
    tools = [get_weather]
    
    prompt_template = """You are a hilarious fashion advisor with a quirky sense of humor. 
Your job is to suggest outfits based on current weather conditions.

IMPORTANT: You MUST use the get_weather tool to fetch real weather data before suggesting an outfit.
Do NOT make up weather information or suggest outfits without checking the weather first.

Be funny, creative, and add witty commentary about the weather and outfit choices.
Use pop culture references, puns, or absurd comparisons when appropriate.

Tools available: {tool_names}

Tool descriptions:
{tools}

Use the following format:
Thought: I need to get the weather data for the city
Action: get_weather
Action Input: the city name
Observation: the weather result
Thought: Now I can suggest an outfit based on this weather
Final Answer: Your hilarious outfit suggestion mentioning the city and weather

User request: {input}

{agent_scratchpad}"""

    prompt = PromptTemplate.from_template(prompt_template)
    agent = create_react_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent, 
        tools=tools, 
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=5
    )
    
    return agent_executor

# Auth0 Login Page
def show_login():
    st.title("🌤️ Weather Outfit AI Agent")
    st.write("### Welcome! Please log in with Auth0 to continue")
    
    # Check for OAuth callback
    query_params = st.query_params
    
    # Handle OAuth callback
    if 'code' in query_params and 'state' in query_params:
        code = query_params['code']
        state = query_params['state']
        
        # Verify state to prevent CSRF
        if state != st.session_state.state:
            st.error("Invalid state parameter. Possible CSRF attack.")
            return
        
        with st.spinner("Authenticating with Auth0..."):
            # Exchange code for token
            token_data = exchange_code_for_token(code)
            
            if token_data and 'access_token' in token_data:
                # Get user info
                user_info = get_user_info(token_data['access_token'])
                
                if user_info:
                    st.session_state.authenticated = True
                    st.session_state.user_info = user_info
                    
                    # Clear query params
                    st.query_params.clear()
                    st.rerun()
                else:
                    st.error("Failed to retrieve user information")
            else:
                st.error("Authentication failed. Please try again.")
        return
    
    # Show login button
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.info("🔐 This app uses Auth0 for secure authentication")
        st.write("**Features:**")
        st.write("✅ OAuth 2.0 with PKCE flow")
        st.write("🌍 Real-time weather data for any city")
        st.write("👔 AI-powered outfit suggestions")
        st.write("😂 Humorous fashion advice")
        
        st.divider()
        
        if not AUTH0_DOMAIN or not AUTH0_CLIENT_ID:
            st.warning("⚠️ Auth0 credentials not configured. Please set AUTH0_DOMAIN and AUTH0_CLIENT_ID in your environment.")
            st.code("""
# Add to .streamlit/secrets.toml:
AUTH0_DOMAIN = "your-domain.auth0.com"
AUTH0_CLIENT_ID = "your_client_id"
AUTH0_CLIENT_SECRET = "your_client_secret"
AUTH0_CALLBACK_URL = "http://localhost:8501"
            """)
        else:
            auth_url = get_auth0_login_url()
            st.markdown(f"[🔑 **Log in with Auth0**]({auth_url})", unsafe_allow_html=True)
            st.caption("You'll be redirected to Auth0's secure login page")
    
    with col2:
        st.write("### Quick Start")
        st.write("1. Click 'Log in with Auth0'")
        st.write("2. Enter credentials")
        st.write("3. Get outfit suggestions!")

# Main App
def show_app():
    st.title("🌤️ Weather Outfit AI Agent")
    
    # User info and logout
    col1, col2 = st.columns([3, 1])
    with col1:
        user_name = st.session_state.user_info.get('name', st.session_state.user_info.get('email', 'User'))
        st.write(f"**Welcome, {user_name}!** 👋")
    with col2:
        if st.button("Logout", type="secondary"):
            st.session_state.authenticated = False
            st.session_state.user_info = None
            st.session_state.code_verifier = None
            st.session_state.state = None
            st.rerun()
    
    st.divider()
    
    st.write("### 🎯 Get Your Perfect Outfit Suggestion")
    st.write("Enter any city name and let our AI fashion advisor suggest what to wear today!")
    
    # City input with validation
    city_input = st.text_input(
        "City name", 
        placeholder="e.g., Paris, Tokyo, New York, London...",
        help="Enter any city in the world (minimum 2 characters)"
    )
    
    # Popular cities suggestions
    st.caption("💡 Popular cities: Paris, Tokyo, New York, London, Dubai, Sydney")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        get_suggestion = st.button("✨ Get Outfit", type="primary")
    
    # Input validation
    if get_suggestion:
        if not city_input:
            st.warning("⚠️ Please enter a city name first!")
        elif len(city_input.strip()) < 2:
            st.warning("⚠️ City name must be at least 2 characters long")
        elif any(char.isdigit() for char in city_input):
            st.warning("⚠️ City names shouldn't contain numbers. Please enter a valid city.")
        else:
            # Process request
            with st.spinner(f"🔍 Checking weather in {city_input.strip()} and crafting your perfect outfit..."):
                try:
                    agent_executor = create_outfit_agent()
                    prompt = f"What outfit should I wear today in {city_input.strip()}? Check the weather and make it funny!"
                    
                    result = agent_executor.invoke({"input": prompt})
                    
                    st.success("### 👔 Your Outfit Suggestion:")
                    st.write(result['output'])
                    
                except Exception as e:
                    st.error(f"Oops! Something went wrong: {str(e)}")
                    st.info("💡 Make sure your OPENAI_API_KEY is correctly configured")
    
    # Footer
    st.divider()
    st.caption("🔒 Secured by Auth0 OAuth 2.0 | Powered by OpenAI GPT-4 & Open-Meteo")
    st.caption("Built for Auth0 AI Agent Hackathon 2025")

# Main entry point
def main():
    st.set_page_config(
        page_title="Weather Outfit AI",
        page_icon="🌤️",
        layout="centered"
    )
    
    # Check authentication
    if not st.session_state.authenticated:
        show_login()
    else:
        show_app()

if __name__ == "__main__":
    main()