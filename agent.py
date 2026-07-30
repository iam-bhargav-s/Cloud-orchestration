import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from tools import switch_dashboard_mode

# Import BOTH tools from your tools.py file
from tools import get_ec2_hourly_price, execute_terraform_deployment

# Load environment variables
load_dotenv()

# Initialize the AI Model (Gemini)
from langchain_groq import ChatGroq

# Initialize the AI Model (Groq)
llm = ChatGroq(
    model="llama-3.1-8b-instant", # The current supported fast/free model
    temperature=0,
    api_key=os.getenv("GROQ_API_KEY")
)

# Add BOTH tools to the agent's toolkit
tools = [get_ec2_hourly_price, execute_terraform_deployment , switch_dashboard_mode]

# Define the System Prompt
system_prompt = "You are EcoOps, an intelligent Cloud FinOps Agent. Your job is to help users estimate costs and deploy cloud infrastructure sustainably. Always use your provided tools to fetch real-time pricing information before giving an estimate, and use the deployment tool when the user asks to provision or destroy resources. Always output your final answer in Markdown."

# Set up the memory checkpointer
memory = MemorySaver()

# Construct the Agent using LangGraph
# We use 'prompt' for the system message and pass the checkpointer
agent_executor = create_react_agent(
    llm, 
    tools, 
    prompt=system_prompt,
    checkpointer=memory
)