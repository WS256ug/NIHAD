from django import forms
from django.contrib.auth.forms import SetPasswordForm
from apps.schools.models import AcademicClass, AcademicYear, Stream
from .models import Enrollment, Guardian, Student, StudentGuardian
from .photos import clean_photo


def set_date_widgets(form):
    for field in form.fields.values():
        if isinstance(field, forms.DateField):
            field.widget = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


def selected_pk(value):
    try:
        number = int(value)
        return number if 0 < number < 2**63 else None
    except (TypeError, ValueError):
        return None


class StudentForm(forms.ModelForm):
    photo = forms.FileField(required=False, widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}), help_text="JPEG, PNG or WebP; up to 5 MB and 16 million pixels.")
    remove_photo = forms.BooleanField(required=False, label="Remove the saved photo")

    class Meta:
        model = Student
        fields = ("first_name", "middle_name", "last_name", "gender", "date_of_birth", "admission_date", "admission_number", "photo", "religion")

    def __init__(self, *args, school, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.school = school
        set_date_widgets(self)
        if not self.instance.photo:
            self.fields.pop("remove_photo")

    def clean_photo(self):
        upload = self.files.get(self.add_prefix("photo"))
        return clean_photo(upload) if upload else self.instance.photo

    def clean(self):
        data = super().clean()
        if data.get("remove_photo") and self.files.get(self.add_prefix("photo")):
            raise forms.ValidationError("Choose either a new photo or removal of the saved photo.")
        return data


class StudentStatusForm(forms.Form):
    status = forms.ChoiceField(choices=Student.Status.choices)
    confirm = forms.BooleanField(label="I confirm this student status change.")


class PortalAccessForm(SetPasswordForm):
    is_active = forms.BooleanField(required=False, initial=True, label="Enable student portal access")
    confirm = forms.BooleanField(label="I will share this temporary password securely with the guardian.")


class GuardianForm(forms.ModelForm):
    class Meta:
        model = Guardian
        fields = ("first_name", "last_name", "phone", "nin", "email", "address")
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, school, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.school = school


class GuardianContactFields(forms.Form):
    existing_guardian = forms.ModelChoiceField(queryset=Guardian.objects.none(), required=False, label="Existing guardian contact", help_text="Select an existing contact for a sibling, or enter the details below.")
    guardian_first_name = forms.CharField(max_length=150, required=False)
    guardian_last_name = forms.CharField(max_length=150, required=False)
    guardian_phone = forms.CharField(max_length=40, required=False)
    guardian_nin = forms.CharField(max_length=50, required=False, label="Guardian NIN", help_text="National Identification Number, if available. For an existing guardian, update their profile.")
    guardian_email = forms.EmailField(required=False)
    guardian_address = forms.CharField(label="Address", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    relationship = forms.CharField(max_length=60, label="Relationship to student")
    is_emergency_contact = forms.BooleanField(required=False, initial=True)

    def clean(self):
        data = super().clean()
        if not data.get("existing_guardian"):
            for name in ("guardian_first_name", "guardian_last_name", "guardian_phone"):
                if not data.get(name):
                    self.add_error(name, "Enter this guardian detail or select an existing contact.")
        return data


class StudentRegistrationForm(GuardianContactFields, StudentForm):
    def __init__(self, *args, school, **kwargs):
        super().__init__(*args, school=school, **kwargs)
        self.fields["existing_guardian"].queryset = Guardian.objects.filter(school=school)


class AddGuardianContactForm(GuardianContactFields):
    def __init__(self, *args, student, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["existing_guardian"].queryset = Guardian.objects.filter(school_id=student.school_id).exclude(student_links__student=student)


class GuardianLinkForm(forms.ModelForm):
    class Meta:
        model = StudentGuardian
        fields = ("guardian", "relationship", "is_primary", "is_emergency_contact")

    def __init__(self, *args, student, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.student = student
        choices = Guardian.objects.filter(school_id=student.school_id)
        if self.instance.pk:
            self.fields["guardian"].disabled = True
            choices = choices.filter(pk=self.instance.guardian_id)
        else:
            choices = choices.exclude(student_links__student=student)
        self.fields["guardian"].queryset = choices


class LinkStatusForm(forms.Form):
    confirm = forms.BooleanField(label="I confirm this guardian link change.")


class EnrollmentForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = ("academic_year", "academic_class", "stream", "enrollment_date", "status", "completion_date")
        help_texts = {
            "status": "Use Current for an open enrollment. Use a completed status and date when recording past enrollment.",
            "completion_date": "Leave blank for a current enrollment.",
            "stream": "Optional. Choose a stream from the selected class.",
        }

    def __init__(self, *args, student, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.student = student
        self.fields["academic_year"].queryset = AcademicYear.objects.filter(school_id=student.school_id, is_active=True)
        self.fields["academic_class"].queryset = AcademicClass.objects.filter(section__school_id=student.school_id, section__is_active=True, is_active=True).select_related("section")
        streams = Stream.objects.filter(academic_class__section__school_id=student.school_id, academic_class__section__is_active=True, academic_class__is_active=True, is_active=True).select_related("academic_class__section")
        # Unbound forms list all qualified streams for the ordinary HTML fallback.
        if self.is_bound:
            streams = streams.filter(academic_class_id=selected_pk(self.data.get("academic_class")))
        self.fields["stream"].queryset = streams
        self.initial.setdefault("academic_year", student.school.current_academic_year_id)
        set_date_widgets(self)

    def clean(self):
        data = super().clean()
        classroom = data.get("academic_class")
        if classroom:
            self.instance.section = classroom.section
        return data


class CloseEnrollmentForm(forms.Form):
    status = forms.ChoiceField(choices=[choice for choice in Enrollment.Status.choices if choice[0] != Enrollment.Status.CURRENT])
    completion_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    confirm = forms.BooleanField(label="I confirm this enrollment is finished. Its history will be preserved.")
