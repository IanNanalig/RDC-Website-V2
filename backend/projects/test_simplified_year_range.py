from django.test import SimpleTestCase
from rest_framework import serializers

from .serializers import ProjectSerializer
from .views import _validate_simplified_funding


class SimplifiedYearRangeTests(SimpleTestCase):
    def test_reversed_range_is_rejected_by_both_write_paths(self):
        simplified = {"startYear": "2028", "endYear": "2027"}

        with self.assertRaisesMessage(serializers.ValidationError, "End Year must be the same as or later than Start Year"):
            ProjectSerializer()._validate_simplified_funding(simplified)
        self.assertEqual(
            _validate_simplified_funding({"simplified_form": simplified}),
            "End Year must be the same as or later than Start Year.",
        )

    def test_equal_and_fifteen_year_ranges_remain_valid(self):
        for start, end in (("2026", "2026"), ("2026", "2041")):
            with self.subTest(start=start, end=end):
                simplified = {"startYear": start, "endYear": end}
                ProjectSerializer()._validate_simplified_funding(simplified)
                self.assertIsNone(_validate_simplified_funding({"simplified_form": simplified}))

    def test_more_than_fifteen_years_remains_invalid(self):
        simplified = {"startYear": "2026", "endYear": "2042"}
        with self.assertRaisesMessage(serializers.ValidationError, "max 15 years"):
            ProjectSerializer()._validate_simplified_funding(simplified)
        self.assertEqual(
            _validate_simplified_funding({"simplified_form": simplified}),
            "Year range is too large (max 15 years).",
        )
