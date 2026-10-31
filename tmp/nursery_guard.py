from pathlib import Path
exec(Path('tmp/implement_nursery.py').read_text().split("m='apps/academics/models.py'")[0])
edit('apps/academics/models.py','preserve_fields(self, ("name", "mode", "aggregate_mode", "best_n", "is_active"))','preserve_fields(self, ("name", "mode", "aggregate_mode", "best_n", "is_active", "nursery_only"))')
edit('apps/academics/models.py','        if self.mode == self.Mode.DESCRIPTIVE and self.aggregate_mode', '        if self.nursery_only and self.mode != self.Mode.DESCRIPTIVE:\n            raise ValidationError("Nursery-only schemes require descriptive levels.")\n        if self.mode == self.Mode.DESCRIPTIVE and self.aggregate_mode')
