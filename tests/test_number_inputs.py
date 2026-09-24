from decimal import Decimal
from django import forms
from django.template import Context, Template
from django.test import SimpleTestCase


class NumberDisplayTests(SimpleTestCase):
    def test_numeric_inputs_trim_only_trailing_zeros(self):
        class AmountForm(forms.Form):
            amount = forms.DecimalField(decimal_places=2)
        for value, expected in [('500.00', '500'), ('500.50', '500.5'), ('0.00', '0'), ('0.01', '0.01')]:
            with self.subTest(value=value):
                self.assertIn(f'value="{expected}"', str(AmountForm(initial={'amount': Decimal(value)})['amount']))
                form = AmountForm({'amount': value})
                self.assertTrue(form.is_valid())
                self.assertEqual(form.cleaned_data['amount'], Decimal(value))
        self.assertNotIn('value=', str(AmountForm()['amount']))

    def test_shared_display_retains_fractional_precision(self):
        template = Template('{{ value|report_number }}')
        self.assertEqual(template.render(Context({'value': Decimal('500.00')})), '500')
        self.assertEqual(template.render(Context({'value': Decimal('500.50')})), '500.5')
        self.assertEqual(template.render(Context({'value': Decimal('0.00120')})), '0.0012')
