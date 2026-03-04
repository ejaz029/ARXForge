import os
import logging
import yaml
from dotenv import load_dotenv
from langchain_groq import ChatGroq

# Load .env file as fallback
load_dotenv()

# ✅ Load config.yaml
def load_config():
    with open("config.yaml", "r") as file:
        return yaml.safe_load(file)

config = load_config()

class Config:
    """Configuration settings for the AUTOSAR Validator."""

    # ✅ AI Settings
    AI_PROVIDER = "groq"
    AI_MODEL = "llama-3.1-8b-instant"  # Updated to current working model
    GROQ_API_KEY = config.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")  # Try YAML first, then .env

    if not GROQ_API_KEY:
        raise ValueError("🚨 Missing GROQ_API_KEY in config.yaml!")

    # ✅ File Handling
    UPLOAD_FOLDER = "uploads"
    ALLOWED_EXTENSIONS = {"arxml"}

    # ✅ Validation Features
    ENABLE_RAG_VALIDATION = True
    ENABLE_SCHEMA_CHECK = True
    ENABLE_CONSISTENCY_CHECKS = True

    # ✅ Deployment
    DEPLOYMENT_ENV = "local"

    @staticmethod
    def is_allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

    @staticmethod
    def get_llm():
        """Returns a new instance of the LLM."""
        api_key = Config.GROQ_API_KEY
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in config.yaml or .env file!")
        return ChatGroq(
            model_name=Config.AI_MODEL,
            api_key=api_key
        )

# ✅ Logging Setup
LOG_LEVEL = "INFO"
LOG_FILE = "logs/app.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

log_dir = os.path.dirname(LOG_FILE)
if log_dir:
    os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("AUTOSAR_Validator")
logger.info("✅ Logging initialized.")
logger.info(f"AI Provider: {Config.AI_PROVIDER}, Model: {Config.AI_MODEL}")
