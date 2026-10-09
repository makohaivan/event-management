from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    UserCreationForm,
)

from .models import User


class BootstrapFormMixin:
    """Adds Bootstrap 5 classes to every widget (reuse this in all forms)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                css_class = "form-check-input"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                css_class = "form-select"
            else:
                css_class = "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css_class}".strip()

    def full_clean(self):
        super().full_clean()
        # Mark invalid fields so Bootstrap shows them in red
        for name in self.errors:
            if name not in self.fields:  # skip form-level errors ("__all__")
                continue
            widget = self.fields[name].widget
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} is-invalid".strip()


class UniqueEmailMixin:
    """Email must be unique, ignoring upper/lower case."""

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        taken = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if taken.exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class StudentSignUpForm(UniqueEmailMixin, BootstrapFormMixin, UserCreationForm):
    """Public sign-up. The role is NOT a form field: everyone who signs up is a student."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email",
                  "student_number", "faculty", "phone")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["email"].required = True

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.STUDENT
        if commit:
            user.save()
        return user


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    error_messages = {
        "invalid_login": "Invalid username or password. Please try again.",
        "inactive": "This account is inactive. Please contact the administrator.",
    }


class ProfileForm(UniqueEmailMixin, BootstrapFormMixin, forms.ModelForm):
    """Users edit their own details. Role is deliberately not included."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone",
                  "student_number", "faculty", "profile_photo")


class StyledPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    pass
