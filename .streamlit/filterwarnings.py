"""Warning filters for Streamlit app"""
import warnings
import os

# Suppress all deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Suppress LangChain deprecation warnings
warnings.filterwarnings("ignore", message=".*HuggingFaceEmbeddings.*deprecated.*")
warnings.filterwarnings("ignore", message=".*Chain.run.*deprecated.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain_community")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain.chains")

# Suppress PyTorch warnings
warnings.filterwarnings("ignore", message=".*torch.classes.*")
warnings.filterwarnings("ignore", message=".*RuntimeError.*no running event loop.*")
warnings.filterwarnings("ignore", category=UserWarning, module="torch")

# Suppress TensorFlow warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="tensorflow")
warnings.filterwarnings("ignore", message=".*tf.losses.*deprecated.*")
warnings.filterwarnings("ignore", message=".*tf.reset_default_graph.*deprecated.*")
warnings.filterwarnings("ignore", message=".*oneDNN.*")

# Set environment variable to suppress TensorFlow oneDNN warnings
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
