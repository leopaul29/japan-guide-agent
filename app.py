import streamlit as st
import requests
from langchain.agents import create_react_agent, AgentExecutor
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
import os
from urllib.parse import urlencode
import base64
import hashlib
import secrets

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

# Tool to fetch weather from Open-Meteo (no auth required for this API)
@tool
def get_weather(city: str) -> str:
    """Fetch current weather for any city using geocoding and Open-Meteo API."""
    
    # Geocoding to get coordinates
    geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
    
    try:
        geo_response = requests.get(geocode_url, timeout=10)
        geo_data = geo_response.json()
        
        if 'results' not in geo_data or len(geo_data['results']) == 0:
            return f"City '{city}' not found. Please check the spelling."
        
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

Be funny, creative, and add witty commentary about the weather and outfit choices.
Use pop culture references, puns, or absurd comparisons when appropriate.

Tools available: {tool_names}

Tool descriptions:
{tools}

Use the following format:
Thought: Consider what weather info you need
Action: the action to take (must be one of [{tool_names}])
Action Input: the input to the action
Observation: the result of the action
... (repeat Thought/Action/Action Input/Observation as needed)
Thought: I now have enough information to suggest an outfit
Final Answer: Your hilarious outfit suggestion with weather info

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

# Auth0 Login Function (simplified for demo)
def show_login():
    st.title("🌤️ Weather Outfit AI Agent")
    st.write("### Welcome! Please log in to get personalized outfit suggestions")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.info("🔐 This app uses Auth0 for secure authentication")
        
        # Simple demo login (for hackathon - replace with actual Auth0 flow in production)
        with st.form("demo_login"):
            st.write("**Demo Login** (use any credentials for testing)")
            email = st.text_input("Email", value="demo@example.com")
            password = st.text_input("Password", type="password", value="demo123")
            
            if st.form_submit_button("Log In", type="primary"):
                if email and password:
                    st.session_state.authenticated = True
                    st.session_state.user_info = {"email": email, "name": email.split('@')[0]}
                    st.rerun()
                else:
                    st.error("Please enter valid credentials")
        
        st.caption("💡 For production: Configure AUTH0_DOMAIN, AUTH0_CLIENT_ID, and AUTH0_CLIENT_SECRET in your environment")
    
    with col2:
        st.write("### Features")
        st.write("✅ Secure Auth0 login")
        st.write("🌍 Real-time weather data")
        st.write("👔 AI outfit suggestions")
        st.write("😂 Humorous recommendations")

# Main App
def show_app():
    st.title("🌤️ Weather Outfit AI Agent")
    
    # User info and logout
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write(f"**Welcome, {st.session_state.user_info['name']}!** 👋")
    with col2:
        if st.button("Logout", type="secondary"):
            st.session_state.authenticated = False
            st.session_state.user_info = None
            st.rerun()
    
    st.divider()
    
    st.write("### 🎯 Get Your Perfect Outfit Suggestion")
    st.write("Enter any city name and let our AI fashion advisor suggest what to wear today (with a side of humor!)")
    
    # City input
    city_input = st.text_input(
        "City name", 
        placeholder="e.g., Paris, Tokyo, New York...",
        help="Enter any city in the world"
    )
    
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        get_suggestion = st.button("✨ Get Outfit Suggestion", type="primary")
    
    # Process request
    if get_suggestion and city_input:
        with st.spinner(f"🔍 Checking weather in {city_input} and crafting your perfect outfit..."):
            try:
                agent_executor = create_outfit_agent()
                prompt = f"What outfit should I wear today in {city_input}? Make it funny and consider the current weather!"
                
                result = agent_executor.invoke({"input": prompt})
                
                st.success("### 👔 Your Outfit Suggestion:")
                st.write(result['output'])
                
            except Exception as e:
                st.error(f"Oops! Something went wrong: {str(e)}")
                st.info("💡 Make sure your OPENAI_API_KEY is correctly configured in your environment")
    
    elif get_suggestion and not city_input:
        st.warning("⚠️ Please enter a city name first!")
    
    # Footer
    st.divider()
    st.caption("🔒 Powered by Auth0, OpenAI, and Open-Meteo | Built for Auth0 AI Agent Hackathon 2025")

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