import streamlit as st
import requests
from langchain.agents import create_react_agent, AgentExecutor
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
import os
from auth0.authentication import GetToken

# Load environment variables (from secrets.toml)
DOMAIN = os.getenv("AUTH0_DOMAIN")
CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
get_token = GetToken(DOMAIN, CLIENT_ID, CLIENT_SECRET)

# Tool to fetch weather from Open-Meteo
@tool
def get_japan_weather(city: str) -> str:
    """Fetch current weather for a Japanese city using Open-Meteo."""
    coords = {"Tokyo": (35.6895, 139.6917), "Kyoto": (35.0116, 135.7681)}
    if city not in coords:
        return "City not supported (try Tokyo or Kyoto)."
    lat, lon = coords[city]
    # Simulate Auth0 Token Vault for secure API call
    token = get_token("https://api.open-meteo.com/.default")['access_token']
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,precipitation&timezone=Asia/Tokyo"
    response = requests.get(url, headers=headers).json()
    temp = response['current']['temperature_2m']
    precip = response['current']['precipitation']
    return f"Weather in {city}: {temp}°C, Precipitation: {precip}mm."

# Setup agent with ReAct prompt
llm = ChatOpenAI(temperature=0.7, model="gpt-3.5-turbo", api_key=os.getenv("OPENAI_API_KEY"))
tools = [get_japan_weather]
prompt_template = """
You are a Japanese guide. Suggest a traditional outfit based on weather. Use tools to get weather data.

Tools available: {tool_names}

{tools}

User input: {input}

{agent_scratchpad}

Provide your final answer in the format: [FINAL ANSWER] Your suggestion here
"""
prompt = PromptTemplate.from_template(prompt_template)
agent = create_react_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, handle_parsing_errors=True)

# Streamlit UI
st.title("Japan Guide AI")
st.write("Log in via Auth0, then enter a city (e.g., Tokyo) for an outfit suggestion.")
st.write("Test login: test@ex.com / password123")
user_input = st.text_input("Enter your request (e.g., 'Outfit for Tokyo')")
if st.button("Get Suggestion"):
    result = agent_executor.invoke({"input": user_input})['output']
    st.write(result)  # E.g., "Tokyo 22°C, wear a light yukata!"