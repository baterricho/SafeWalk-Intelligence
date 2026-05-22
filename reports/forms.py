from django import forms
from django.core.exceptions import ValidationError

from .models import SafetyReport


ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_PHOTO_SIZE = 5 * 1024 * 1024


class SafetyReportForm(forms.ModelForm):
    class Meta:
        model = SafetyReport
        fields = [
            "title",
            "category",
            "description",
            "location_name",
            "latitude",
            "longitude",
            "risk_level",
            "time_observed",
            "day_type",
            "lighting_condition",
            "crowd_level",
            "is_anonymous",
            "visibility_level",
            "photo",
        ]
        labels = {
            "location_name": "Location details / landmark",
            "photo": "Upload photo evidence",
        }
        help_texts = {
            "photo": "Optional: Upload a photo of the unsafe area, broken street light, flooded road, or other safety concern.",
        }
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "maxlength": 120, "required": True}),
            "category": forms.Select(attrs={"class": "form-select", "required": True}),
            "description": forms.Textarea(
                attrs={"class": "form-control", "rows": 5, "maxlength": 2000, "required": True}
            ),
            "location_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "maxlength": 160,
                    "required": True,
                    "placeholder": "Example: Near PSU Main Gate, beside the waiting shed, in front of the boarding house",
                }
            ),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
            "risk_level": forms.Select(attrs={"class": "form-select", "required": True}),
            "time_observed": forms.TimeInput(attrs={"class": "form-control", "type": "time", "required": True}),
            "day_type": forms.Select(attrs={"class": "form-select", "required": True}),
            "lighting_condition": forms.Select(attrs={"class": "form-select", "required": True}),
            "crowd_level": forms.Select(attrs={"class": "form-select", "required": True}),
            "is_anonymous": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "visibility_level": forms.Select(attrs={"class": "form-select", "required": True}),
            "photo": forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": ".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"}
            ),
        }

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if len(title) < 6:
            raise forms.ValidationError("Title must be at least 6 characters long.")
        return title

    def clean_description(self):
        description = self.cleaned_data["description"].strip()
        if len(description) < 20:
            raise forms.ValidationError("Description must be at least 20 characters long.")
        return description

    def clean_location_name(self):
        location_name = self.cleaned_data["location_name"].strip()
        if len(location_name) < 3:
            raise forms.ValidationError("Location details must be at least 3 characters long.")
        return location_name

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if not photo:
            return photo
        if not hasattr(photo, "content_type"):
            return photo
        content_type = getattr(photo, "content_type", "")
        if content_type not in ALLOWED_PHOTO_TYPES:
            raise ValidationError("Upload a JPG, JPEG, PNG, or WEBP image.")
        if photo.size > MAX_PHOTO_SIZE:
            raise ValidationError("Photo must be 5MB or smaller.")
        return photo

    def clean(self):
        cleaned = super().clean()
        latitude = cleaned.get("latitude")
        longitude = cleaned.get("longitude")
        if latitude in [None, ""] or longitude in [None, ""]:
            raise forms.ValidationError("Please pin the unsafe location on the map before submitting.")
        if latitude is not None and not (-90 <= float(latitude) <= 90):
            self.add_error("latitude", "Latitude must be between -90 and 90.")
        if longitude is not None and not (-180 <= float(longitude) <= 180):
            self.add_error("longitude", "Longitude must be between -180 and 180.")
        if cleaned.get("is_anonymous") and cleaned.get("visibility_level") == SafetyReport.VisibilityLevel.PUBLIC:
            cleaned["visibility_level"] = SafetyReport.VisibilityLevel.ANONYMOUS_PUBLIC
        return cleaned
