"""The wardrobe data format every step shares: tagging, outfit planning, gap finder."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["top", "bottom", "dress", "outerwear", "shoes", "accessory", "other"]
Pattern = Literal["solid", "striped", "checked", "floral", "graphic", "print", "other"]
Formality = Literal["athleisure", "casual", "smart_casual", "business", "formal"]
Season = Literal["spring", "summer", "fall", "winter"]


class Garment(BaseModel):
    """What Muse Spark returns for one SAM cutout."""

    is_garment: bool = Field(
        description="False if the cutout is not a wearable item (hanger, bed, wall, partial blur)."
    )
    category: Category
    subtype: str = Field(description="Specific item name, e.g. 'oxford shirt', 'straight-leg jeans'.")
    primary_color: str
    secondary_colors: list[str]
    pattern: Pattern
    material_guess: str
    warmth: int = Field(description="1 = very light summer wear, 5 = heavy winter wear.")
    formality: Formality
    seasons: list[Season]
    distinctive_details: str = Field(
        description="Logos, prints, buttons, distressing: anything a render must preserve. 'none' if plain."
    )
    confidence: float = Field(description="0-1: how sure you are this is one complete, correctly identified item.")


class FidelityCheck(BaseModel):
    """Muse Spark's judgment of whether a render kept a real garment intact."""

    garment_visible: bool
    color_preserved: int = Field(description="1-5")
    pattern_preserved: int = Field(description="1-5")
    details_preserved: int = Field(description="1-5, logos/prints/buttons")
    cut_and_fit_preserved: int = Field(description="1-5")
    person_identity_preserved: int = Field(description="1-5, face and body unchanged")
    differences: str = Field(description="Concrete differences between the real garment and the render.")
