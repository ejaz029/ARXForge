import os
import warnings
import logging
import numpy as np
from sklearn.ensemble import IsolationForest
from sentence_transformers import SentenceTransformer
import xml.etree.ElementTree as ET
from config.device_utils import get_device, get_device_name

# Suppress TensorFlow warnings
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
logging.getLogger('tensorflow').setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="tensorflow")
warnings.filterwarnings("ignore", message=".*tf.losses.*deprecated.*")

class AnomalyDetector:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        """
        Initializes the anomaly detector with an embedding model and Isolation Forest.
        Automatically uses GPU if available.
        """
        device = get_device()
        self.encoder = SentenceTransformer(model_name, device=device)
        self.model = IsolationForest(contamination=0.05, random_state=42)
        self.fitted = False
        print(f"AnomalyDetector initialized on {get_device_name()}")
    
    def extract_text_data(self, root):
        """
        Extracts textual elements from ARXML for anomaly detection.
        """
        text_data = [elem.text.strip() for elem in root.iter() if elem.text and elem.text.strip()]
        return text_data if text_data else ["No meaningful text found"]
    
    def train_anomaly_model(self, normal_data):
        """
        Trains the Isolation Forest on normal ARXML data.
        """
        if not normal_data:
            raise ValueError("Training data is empty! Provide valid ARXML text for training.")
        
        try:
            embeddings = self.encoder.encode(normal_data)
            self.model.fit(embeddings)
            self.fitted = True
        except Exception as e:
            raise RuntimeError(f"Error during training: {str(e)}")
    
    def detect_anomalies(self, arxml_data):
        """
        Detects anomalies in ARXML data based on trained model.
        """
        if not self.fitted:
            raise ValueError("Model not trained! Provide normal data for training first.")
        
        try:
            embeddings = self.encoder.encode(arxml_data)
            predictions = self.model.predict(embeddings)
            anomalies = [arxml_data[i] for i in range(len(predictions)) if predictions[i] == -1]
            return anomalies
        except Exception as e:
            raise RuntimeError(f"Error during anomaly detection: {str(e)}")

# Example Usage
if __name__ == "__main__":
    file_path = "example.arxml"
    
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        detector = AnomalyDetector()
        extracted_data = detector.extract_text_data(root)
        
        # Train with normal dataset (should be collected separately)
        normal_data = extracted_data[:50]  # Example: First 50 entries as normal
        detector.train_anomaly_model(normal_data)
        
        anomalies = detector.detect_anomalies(extracted_data)
        
        if anomalies:
            print("❌ Anomalies Detected:")
            for anomaly in anomalies:
                print(anomaly)
        else:
            print("✅ No anomalies found.")
    
    except FileNotFoundError:
        print(f"⚠️ Error: File '{file_path}' not found!")
    except Exception as e:
        print(f"⚠️ Unexpected Error: {str(e)}")
