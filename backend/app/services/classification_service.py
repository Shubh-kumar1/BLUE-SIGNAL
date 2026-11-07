import logging
import os
import threading
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    class_name: str
    confidence: float

    def model_dump(self) -> dict:
        return {"class_name": self.class_name, "confidence": self.confidence}


@dataclass
class ImageClassificationResult:
    type: str
    confidence: float
    prediction: str

    def model_dump(self) -> dict:
        return {"type": self.type, "confidence": self.confidence, "prediction": self.prediction}


class ClassificationService:
    def __init__(self) -> None:
        self.text_classifier = None
        self.flood_classifier = None
        self.image_classifier = None
        self._load_lock = threading.Lock()
        self._loading = False
        self.loaded = False

    def load(self) -> None:
        with self._load_lock:
            if self.loaded or self._loading:
                return
            self._loading = True

        try:
            logger.info("Loading AI models in the background")
            import torch
            from transformers import pipeline
            torch.set_num_threads(max(1, torch.get_num_threads()))
            self.text_classifier = pipeline("zero-shot-classification", model="typeform/distilbert-base-uncased-mnli")
            self.flood_classifier = pipeline("zero-shot-classification", model="typeform/distilbert-base-uncased-mnli")
            self.image_classifier = pipeline("zero-shot-image-classification", model="openai/clip-vit-base-patch32")
            self.loaded = True
            logger.info("AI models loaded successfully")
        except Exception as exc:
            logger.exception("AI model loading failed: %s", exc)
        finally:
            with self._load_lock:
                self._loading = False

    def load_in_background(self) -> None:
        if os.getenv("LIGHTWEIGHT_MODE", "false").strip().lower() == "true":
            logger.info("LIGHTWEIGHT_MODE enabled; AI model loading is disabled")
            return
        load_ai_models = os.getenv("LOAD_AI_MODELS")
        if load_ai_models is not None and load_ai_models.strip().lower() not in {"1", "true", "yes", "on"}:
            logger.info("LOAD_AI_MODELS disabled AI model loading")
            return
        threading.Thread(target=self.load, daemon=True, name="bluesignal-ai-loader").start()

    def classify_urgency(self, text: str) -> ClassificationResult:
        try:
            if self.text_classifier is None:
                raise RuntimeError("text_classifier not initialized")
            result = self.text_classifier(text, ["Urgent Panic", "Alert Caution", "Safe Normal"])
            return ClassificationResult(result["labels"][0], round(float(result["scores"][0]), 3))
        except Exception as exc:
            logger.error("Urgency classification failed: %s", exc)
            return ClassificationResult("Pipeline Error", 0.0)

    def classify_flood_type(self, text: str) -> ClassificationResult:
        try:
            if self.flood_classifier is None:
                raise RuntimeError("flood_classifier not initialized")
            labels = ["Urban Flooding", "River Overflow", "Flash Flood", "Drainage Failure", "Heavy Rain Accumulation", "Dam or Levee Breach", "Sewer Backup", "Groundwater Rise", "Landslide-Induced Flooding", "Coastal Storm Surge", "Other/Unknown Flood"]
            result = self.flood_classifier(text, labels)
            return ClassificationResult(result["labels"][0], round(float(result["scores"][0]), 3))
        except Exception as exc:
            logger.error("Flood classification failed: %s", exc)
            return ClassificationResult("Pipeline Error", 0.0)

    def classify_image(self, image_path: str) -> ImageClassificationResult:
        try:
            if self.image_classifier is None:
                raise RuntimeError("image_classifier not initialized")
            labels = ["severe urban flooding with shoulder-level stagnant water on streets", "severe urban flooding with streets and vehicles submerged", "moderate street flooding with pooled rainwater", "flash flood with rapid water flow in streets", "river overflow flooding nearby neighborhoods", "drainage failure causing waterlogging", "heavy rain accumulation on roads and low-lying areas", "dam or levee breach with downstream flooding", "sewer backup causing localized flooding", "groundwater rise flooding basements", "landslide-induced flooding with mud and water", "coastal storm surge flooding coastal roads", "normal street scene with no flooding"]
            result = self.image_classifier(image_path, candidate_labels=labels)
            mapping = {"severe urban flooding with shoulder-level stagnant water on streets": "Urban Flooding (Severe, Stagnant)", "severe urban flooding with streets and vehicles submerged": "Urban Flooding (Severe)", "moderate street flooding with pooled rainwater": "Urban Flooding (Moderate)", "flash flood with rapid water flow in streets": "Flash Flood", "river overflow flooding nearby neighborhoods": "River Overflow", "drainage failure causing waterlogging": "Drainage Failure", "heavy rain accumulation on roads and low-lying areas": "Heavy Rain Accumulation", "dam or levee breach with downstream flooding": "Dam or Levee Breach", "sewer backup causing localized flooding": "Sewer Backup", "groundwater rise flooding basements": "Groundwater Rise", "landslide-induced flooding with mud and water": "Landslide-Induced Flooding", "coastal storm surge flooding coastal roads": "Coastal Storm Surge", "normal street scene with no flooding": "No Flooding"}
            prediction = result[0]["label"]
            return ImageClassificationResult(mapping.get(prediction, "Unknown"), round(float(result[0]["score"]), 3), prediction)
        except Exception as exc:
            logger.error("Image classification failed: %s", exc)
            return ImageClassificationResult("Pipeline Error", 0.0, "error")
