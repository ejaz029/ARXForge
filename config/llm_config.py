from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv
import yaml

# Load environment variables from .env file
# Try multiple paths to find .env file
env_paths = [
    os.path.join(os.path.dirname(__file__), "..", ".env"),  # Relative to config folder
    os.path.join(os.getcwd(), ".env"),  # Current working directory
    ".env"  # Default location
]

for env_path in env_paths:
    abs_path = os.path.abspath(env_path)
    if os.path.exists(abs_path):
        load_dotenv(abs_path)
        break
else:
    # If no .env found, try default location
    load_dotenv()

def get_llm():
    # Try multiple sources for API key
    api_key = os.getenv("GROQ_API_KEY")
    
    # If not in environment, try config.yaml
    if not api_key:
        try:
            with open("config.yaml", "r") as f:
                config = yaml.safe_load(f)
                api_key = config.get("GROQ_API_KEY", "").strip('"').strip("'")
        except Exception:
            pass
    
    # Validate API key
    if not api_key or len(api_key) < 20:
        raise ValueError(
            "GROQ_API_KEY not found or invalid! "
            "Please set it in .env file or config.yaml"
        )
    
    return ChatGroq(
        temperature=0.2,
        model_name="llama-3.1-8b-instant",  # Current working model
        api_key=api_key
    )
