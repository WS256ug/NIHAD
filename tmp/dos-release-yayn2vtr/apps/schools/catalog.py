"""The five configuration resources supported by the shared management pages."""
from dataclasses import dataclass

from .forms import AcademicClassForm, AcademicYearForm, SectionForm, StreamForm, TermForm
from .models import AcademicClass, AcademicYear, Section, Stream, Term


@dataclass(frozen=True)
class ConfigurationType:
    model: type
    form: type
    label: str
    singular: str
    scope: str
    parent: str = ""
    dates: bool = False

    def queryset(self, school):
        return self.model.objects.filter(**{self.scope: school}).select_related(self.scope)


CONFIGURATION_TYPES = {
    "sections": ConfigurationType(Section, SectionForm, "Sections", "section", "school"),
    "years": ConfigurationType(AcademicYear, AcademicYearForm, "Academic years", "academic year", "school", dates=True),
    "terms": ConfigurationType(Term, TermForm, "Terms", "term", "academic_year__school", "academic_year", True),
    "classes": ConfigurationType(AcademicClass, AcademicClassForm, "Classes", "class", "section__school", "section"),
    "streams": ConfigurationType(Stream, StreamForm, "Streams", "stream", "academic_class__section__school", "academic_class"),
}
