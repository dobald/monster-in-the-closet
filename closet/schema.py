"""The wardrobe data format every step shares: tagging, outfit planning, gap finder."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Category = Literal["top", "bottom", "dress", "outerwear", "shoes", "accessory", "other"]
Pattern = Literal["solid", "striped", "checked", "floral", "graphic", "print", "other"]
Formality = Literal["athleisure", "casual", "smart_casual", "business", "formal"]
Season = Literal["spring", "summer", "fall", "winter"]
Side = Literal["front", "back", "unknown"]


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
    fit: str = Field(
        description="Cut and fit as visible, e.g. 'wide-leg, loose, high-rise', 'boxy cropped', 'slim tapered', 'oversized'."
    )
    distinctive_details: str = Field(
        description="Logos, prints, buttons, distressing: anything a render must preserve. 'none' if plain."
    )
    visible_side: Side = Field(
        description="Which side faces the camera. 'back' if you see a back print, the back yoke, or no front "
        "placket/neckline dip; 'unknown' for shoes, accessories or unclear shots."
    )
    print_side: Side = Field(
        description="Where the main print or logo is: 'front', 'back', or 'unknown' if plain or unsure."
    )
    confidence: float = Field(description="0-1: how sure you are this is one complete, correctly identified item.")

    def render_line(self, color_hex: str | None = None, short: bool = False) -> str:
        """How this item is described to Muse Image so the render keeps its real cut, colour and print.

        `color_hex` is the garment's measured colour from the photo: Day-0 renders drifted
        on denim wash, and a measured value anchors it better than a colour name.
        `short` drops the free-text details, which can trip the content filter.
        """
        parts = [f"{self.primary_color} {self.subtype}", f"fit: {self.fit}"]
        if color_hex:
            parts.append(f"exact colour {color_hex}, do not lighten, fade or recolour it")
        if self.pattern != "solid":
            parts.append(f"pattern: {self.pattern}")
        if not short and self.distinctive_details and self.distinctive_details.lower() != "none":
            parts.append(f"details to keep exactly: {self.distinctive_details}")
        if self.print_side in ("front", "back"):
            parts.append(f"the main print is on the {self.print_side}")
        return "; ".join(parts)

    @field_validator("seasons", "secondary_colors")
    @classmethod
    def _dedupe(cls, v: list) -> list:
        # Muse Spark Open occasionally repeats list items ("summer", "summer").
        return list(dict.fromkeys(v))


Build = Literal["slim", "regular", "athletic", "curvy", "plus"]
Silhouette = Literal["feminine", "masculine", "neutral"]

# Skin tone swatches the app offers, lightest to deepest. Muse Image gets them as a mannequin
# *finish* colour: prompts mentioning "skin tone" next to body details trip its content filter.
SKIN_TONES = {
    1: ("#F6DCC9", "pale ivory"),
    2: ("#EBC3A4", "light beige"),
    3: ("#D9A57E", "sand"),
    4: ("#C08A5E", "warm tan"),
    5: ("#A26E45", "caramel brown"),
    6: ("#80522F", "chestnut brown"),
    7: ("#5E3A20", "dark brown"),
    8: ("#3F2614", "deep espresso"),
}
SILHOUETTE_WORDS = {"feminine": "feminine form", "masculine": "masculine form", "neutral": "gender-neutral form"}


class BodyProfile(BaseModel):
    """A no-photo stand-in for try-on: a faceless mannequin. Nothing here identifies the user.

    There is deliberately no headless variant: Muse Image kept drawing a featureless head
    even when told "no head at all", and the faceless mannequin is already anonymous.
    """

    height_cm: int = Field(ge=140, le=210)
    build: Build
    silhouette: Silhouette
    skin_tone: int = Field(ge=1, le=8, description="Index into SKIN_TONES, used as the mannequin's finish.")

    def describe(self, detail: int = 2) -> str:
        """Mannequin wording for Muse Image. detail=2 is full, 1 drops body details, 0 is bare."""
        figure = (f"a store display mannequin with a smooth featureless head, "
                  f"in a {SKIN_TONES[self.skin_tone][1]} matte finish")
        if detail >= 2:
            figure += (f", about {self.height_cm} cm tall, {self.build} build, "
                       f"{SILHOUETTE_WORDS[self.silhouette]}")
        elif detail == 1:
            figure += f", {SILHOUETTE_WORDS[self.silhouette]}"
        return figure if detail else "a white store display mannequin"


class PersonPhotoCheck(BaseModel):
    """Is a user's photo usable for the face version of try-on?"""

    one_person: bool
    full_body: bool = Field(description="Head to feet visible.")
    face_visible: bool = Field(description="Face clearly visible, not covered by a phone, hand, hair or mask.")
    ok: bool = Field(description="True only if all three checks pass.")
    advice: str = Field(description="One friendly sentence telling the user how to retake it, or 'Looks good.'")


class FidelityCheck(BaseModel):
    """Muse Spark's judgment of whether a render kept a real garment intact."""

    garment_visible: bool
    color_preserved: int = Field(description="1-5")
    pattern_preserved: int = Field(description="1-5")
    details_preserved: int = Field(description="1-5, logos/prints/buttons")
    cut_and_fit_preserved: int = Field(description="1-5")
    person_identity_preserved: int = Field(
        description="1-5, the person (or mannequin spec) is unchanged: face, body, skin tone. A mannequin must have no face."
    )
    differences: str = Field(description="Concrete differences between the real garment and the render.")
