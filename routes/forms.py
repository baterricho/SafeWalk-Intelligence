from django import forms

from .models import RouteNote, SavedRoute


class RouteNoteForm(forms.ModelForm):
    class Meta:
        model = RouteNote
        fields = ["location_name", "latitude", "longitude", "safety_tip_type", "note"]
        labels = {"location_name": "Location details / landmark"}
        widgets = {
            "location_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "maxlength": 160,
                    "required": True,
                    "placeholder": "Example: Near PSU Main Gate, beside the waiting shed, near the dark shortcut",
                }
            ),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
            "safety_tip_type": forms.Select(attrs={"class": "form-select", "required": True}),
            "note": forms.Textarea(attrs={"class": "form-control", "rows": 4, "maxlength": 1000, "required": True}),
        }

    def clean_location_name(self):
        value = self.cleaned_data["location_name"].strip()
        if len(value) < 3:
            raise forms.ValidationError("Location details must be at least 3 characters long.")
        return value

    def clean_note(self):
        value = self.cleaned_data["note"].strip()
        if len(value) < 10:
            raise forms.ValidationError("Tip must be at least 10 characters long.")
        return value

    def clean(self):
        cleaned = super().clean()
        latitude = cleaned.get("latitude")
        longitude = cleaned.get("longitude")
        if latitude in [None, ""] or longitude in [None, ""]:
            raise forms.ValidationError("Please pin the safety tip location on the map before submitting.")
        return cleaned


class SavedRouteForm(forms.ModelForm):
    class Meta:
        model = SavedRoute
        fields = [
            "route_name",
            "start_location",
            "end_location",
            "start_latitude",
            "start_longitude",
            "end_latitude",
            "end_longitude",
            "usual_time",
            "notes",
            "route_geometry",
            "route_distance_km",
            "route_duration_min",
        ]
        labels = {
            "start_location": "Start point landmark",
            "end_location": "End point landmark",
            "usual_time": "Usual walking time",
        }
        widgets = {
            "route_name": forms.TextInput(attrs={"class": "form-control", "maxlength": 120, "required": True}),
            "start_location": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "maxlength": 160,
                    "required": True,
                    "placeholder": "Example: My boarding house near Valencia Street",
                }
            ),
            "end_location": forms.TextInput(
                attrs={"class": "form-control", "maxlength": 160, "required": True, "placeholder": "Example: PSU Main Gate"}
            ),
            "start_latitude": forms.HiddenInput(),
            "start_longitude": forms.HiddenInput(),
            "end_latitude": forms.HiddenInput(),
            "end_longitude": forms.HiddenInput(),
            "usual_time": forms.TimeInput(attrs={"class": "form-control", "type": "time", "required": True}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3, "maxlength": 1000}),
            "route_geometry": forms.HiddenInput(),
            "route_distance_km": forms.HiddenInput(),
            "route_duration_min": forms.HiddenInput(),
        }

    def clean(self):
        cleaned = super().clean()
        start_missing = cleaned.get("start_latitude") in [None, ""] or cleaned.get("start_longitude") in [None, ""]
        end_missing = cleaned.get("end_latitude") in [None, ""] or cleaned.get("end_longitude") in [None, ""]
        if start_missing and end_missing:
            raise forms.ValidationError("Please pin your start and end points on the map.")
        if start_missing:
            raise forms.ValidationError("Please pin your start point.")
        if end_missing:
            raise forms.ValidationError("Please pin your end point.")
        return cleaned
