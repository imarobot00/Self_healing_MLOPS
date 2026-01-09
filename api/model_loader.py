import dill
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime
from feature_engineer import FeatureEngineer

logger = logging.getLogger(__name__)

class ModelManager:
    """Manages loading, versioning, and switching of ML models"""
    
    def __init__(self, models_dir: str = None):
        if models_dir is None or models_dir == "":
            # Try relative path first, then absolute
            models_dir = Path("../training/models")
            if not models_dir.exists():
                models_dir = Path(__file__).parent.parent / "training" / "models"
        
        self.models_dir = Path(models_dir)
        self.current_model = None
        self.model_metadata = {}
        self.feature_engineer = FeatureEngineer()
        
    def load_latest_model(self):
        """Load the most recent model"""
        model_files = sorted(self.models_dir.glob("arf_model_*.pkl"))
        
        if not model_files:
            raise FileNotFoundError(f"No models found in {self.models_dir}")
        
        latest_model_path = model_files[-1]
        return self.load_model(latest_model_path)
    
    def load_model(self, model_path: Path):
        """Load a specific model"""
        logger.info(f"Loading model from {model_path}")
        
        with open(model_path, 'rb') as f:
            model = dill.load(f)
        
        # Extract metadata from filename
        # Format: arf_model_20251214_213238.pkl
        timestamp_str = model_path.stem.replace('arf_model_', '')
        
        self.current_model = model
        self.model_metadata = {
            'path': str(model_path),
            'version': timestamp_str,
            'loaded_at': datetime.now().isoformat()
        }
        
        logger.info(f"Model loaded successfully: {self.model_metadata}")
        return model
    
    def predict(self, features: dict, location_id: int = 6142174) -> float:
        """
        Make a prediction with automatic feature engineering.
        
        Parameters:
        -----------
        features : dict
            Basic sensor readings (pm25, pm1, temperature, relativehumidity, um003)
        location_id : int
            Location ID for loading historical data (default: 6142174 Ranibari)
        
        Returns:
        --------
        float : Predicted AQI
        """
        if self.current_model is None:
            raise RuntimeError("No model loaded")
        
        # Generate all 65 features from basic inputs
        logger.info(f"Generating features from {len(features)} basic inputs")
        full_features = self.feature_engineer.create_features(features, location_id)
        logger.info(f"Generated {len(full_features)} features for prediction")
        
        # Make prediction
        prediction = self.current_model.predict_one(full_features)
        return prediction
        return self.current_model.predict_one(features)
    
    def update_model(self, features: dict, target: float):
        """Update model with new data (online learning)"""
        if self.current_model is None:
            raise RuntimeError("No model loaded")
        
        self.current_model.learn_one(features, target)
        logger.info(f"Model updated with new sample: target={target}")
    
    def get_metadata(self) -> dict:
        """Get current model metadata"""
        return self.model_metadata
