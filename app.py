import streamlit as st
import requests
from langchain.agents import create_react_agent, AgentExecutor
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
import os

# Auth0 Configuration (for future use)
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_info' not in st.session_state:
    st.session_state.user_info = None

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
    
    prompt_template = """You are a hilarious Japanese fashion advisor with expertise in traditional and modern Japanese clothing styles.
Your job is to suggest Japanese-inspired outfits based on current weather conditions.

IMPORTANT: You MUST use the get_weather tool to fetch real weather data before suggesting an outfit.
Do NOT make up weather information or suggest outfits without checking the weather first.

Suggest outfits that include Japanese clothing elements such as:
- Traditional: Kimono, Yukata, Hakama, Haori, Geta, Zori, Tabi socks
- Modern Japanese streetwear: Techwear, minimalist fashion, Uniqlo style
- Seasonal Japanese fashion: Light fabrics for summer (natsu), layers for winter (fuyu)

Be funny, creative, and add witty commentary about the weather and outfit choices.
Use Japanese fashion references, anime comparisons, or cultural elements when appropriate.
You can mix traditional and modern pieces for a unique "Japanese fusion" style.

Tools available: {tool_names}

Tool descriptions:
{tools}

Use the following format:
Thought: I need to get the weather data for the city
Action: get_weather
Action Input: the city name
Observation: the weather result
Thought: Now I can suggest a Japanese-inspired outfit based on this weather
Final Answer: Your hilarious Japanese fashion suggestion mentioning the city, weather, and specific Japanese clothing items

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

# Simple Login Page (Demo for Hackathon)
def show_login():
    st.title("🎌 Japanese Fashion AI Agent")
    st.write("### Welcome! Please log in to continue")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.info("🔐 Simple demo authentication for hackathon")
        st.write("**Features:**")
        st.write("🎌 Japanese-inspired fashion suggestions")
        st.write("🌍 Real-time weather data worldwide")
        st.write("👘 Traditional & modern Japanese clothing")
        st.write("😂 Humorous AI recommendations")
        
        st.divider()
        
        # Simple login form
        with st.form("login_form"):
            st.write("**Enter any credentials to continue**")
            email = st.text_input("Email", value="demo@example.com")
            password = st.text_input("Password", type="password", value="demo123")
            
            if st.form_submit_button("🔑 Log In", type="primary", use_container_width=True):
                if email and password:
                    st.session_state.authenticated = True
                    st.session_state.user_info = {
                        "email": email, 
                        "name": email.split('@')[0].capitalize()
                    }
                    st.rerun()
                else:
                    st.error("Please enter both email and password")
        
        st.caption("💡 This is a demo login. In production, this would use Auth0 OAuth 2.0")
    
    with col2:
        st.write("### Quick Start")
        st.write("1. Enter any email/password")
        st.write("2. Click Log In")
        st.write("3. Get Japanese outfit ideas!")
        st.write("")
        st.info("🎯 Try cities like:\n- Tokyo 🗼\n- Kyoto 🏯\n- Paris 🗼\n- New York 🗽")

# Main App
def show_app():
    st.title("🎌 Japanese Fashion AI Agent")
    
    # User info and logout
    col1, col2 = st.columns([3, 1])
    with col1:
        user_name = st.session_state.user_info.get('name', st.session_state.user_info.get('email', 'User'))
        st.write(f"**ようこそ (Welcome), {user_name}!** 👋")
    with col2:
        if st.button("Logout", type="secondary"):
            st.session_state.authenticated = False
            st.session_state.user_info = None
            st.rerun()
    
    st.divider()
    
    st.write("### 🎯 Get Your Japanese-Inspired Outfit")
    st.write("Enter any city and discover what traditional or modern Japanese clothing would be perfect for today's weather!")
    
    # City input with validation
    city_input = st.text_input(
        "City name", 
        placeholder="e.g., Paris, Tokyo, New York, London...",
        help="Enter any city in the world (minimum 2 characters)"
    )
    
    # Popular cities suggestions
    st.caption("💡 Try Japanese cities: Tokyo, Kyoto, Osaka, Sapporo, Fukuoka | Or any city worldwide!")
    
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
                    prompt = f"What Japanese-inspired outfit should I wear today in {city_input.strip()}? Check the weather and suggest traditional or modern Japanese clothing with humor!"
                    
                    result = agent_executor.invoke({"input": prompt})
                    
                    st.success("### 👘 Your Japanese Fashion Suggestion:")
                    st.write(result['output'])
                    
                except Exception as e:
                    st.error(f"Oops! Something went wrong: {str(e)}")
                    st.info("💡 Make sure your OPENAI_API_KEY is correctly configured")
    
    # Footer
    st.divider()
    st.caption("🎌 Japanese Fashion AI powered by OpenAI GPT-4 & Open-Meteo")
    st.caption("🔒 Secured by Auth0 | Built for Auth0 AI Agent Hackathon 2025")

# Main entry point
def main():
    st.set_page_config(
        page_title="Japanese Fashion AI",
        page_icon="🎌",
        layout="centered"
    )
    
    # Check authentication
    if not st.session_state.authenticated:
        show_login()
    else:
        show_app()

if __name__ == "__main__":
    main()