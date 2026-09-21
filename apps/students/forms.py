from django import forms
from django.contrib.auth.forms import UserCreationForm

from apps.accounts.models import User
from apps.accounts.permissions import manageable_accounts
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
        fields = ("first_name", "middle_name", "last_name", "gender", "date_of_birth", "admission_date", "admission_number", "photo", "address", "contact_phone")
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}

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


class GuardianRegistrationForm(UserCreationForm):
    phone = forms.CharField(max_length=40)
    address = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("first_name", "last_name", "email"):
            self.fields[name].required = True
        self.instance.role = User.Role.GUARDIAN


class GuardianForm(forms.ModelForm):
    class Meta:
        model = Guardian
        fields = ("user", "phone", "address")
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}
        labels = {"user": "Guardian account"}

    def __init__(self, *args, actor, school, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.school = school
        if self.instance.pk:
            self.fields["user"].disabled = True
            self.fields["user"].queryset = User.objects.filter(pk=self.instance.user_id)
        else:
            self.fields["user"].queryset = manageable_accounts(actor).filter(role=User.Role.GUARDIAN, is_active=True, guardian_profile__isnull=True)


class GuardianLinkForm(forms.ModelForm):
    class Meta:
        model = StudentGuardian
        fields = ("guardian", "relationship", "is_primary", "is_emergency_contact")

    def __init__(self, *args, student, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.student = student
        choices = Guardian.objects.filter(school_id=student.school_id).select_related("user")
        if self.instance.pk:
            self.fields["guardian"].disabled = True
            choices = choices.filter(pk=self.instance.guardian_id)
        else:
            choices = choices.filter(user__is_active=True, user__role=User.Role.GUARDIAN).exclude(student_links__student=student)
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
