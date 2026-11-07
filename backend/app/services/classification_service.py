import logging
import os
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

    def load(self) -> None:
        if os.getenv("LIGHTWEIGHT_MODE", "false").lower() == "true":
            return
        import torch
        from transformers import pipeline
        torch.set_num_threads(max(1, torch.get_num_threads()))
        self.text_classifier = pipeline("zero-shot-classification", model="typeform/distilbert-base-uncased-mnli")
        self.flood_classifier = pipeline("zero-shot-classification", model="typeform/distilbert-base-uncased-mnli")
        self.image_classifier = pipeline("zero-shot-image-classification", model="openai/clip-vit-base-patch32")

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
