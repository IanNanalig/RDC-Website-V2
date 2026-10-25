from django.test import SimpleTestCase

from .public_summary import build_public_summary
from .utils import derive_ncr_lgus, format_project_locations


class ProjectLocationMultiselectTests(SimpleTestCase):
    def test_selected_locations_are_formatted_for_readable_outputs(self):
        selected = ["Pasig", "Quezon City", "Pasig", ""]

        self.assertEqual(format_project_locations(selected), "Pasig, Quezon City")
        self.assertEqual(derive_ncr_lgus(selected), ["Pasig", "Quezon City"])

    def test_public_summary_uses_readable_selected_locations(self):
        summary = build_public_summary({
            "agencyName": "DENR",
            "projectActivity": "Urban River Rehabilitation",
            "location": ["Pasig", "Marikina"],
        })

        self.assertEqual(summary["key_facts"]["location"], "Pasig, Marikina")
        self.assertIn("Pasig, Marikina", summary["text"])

    def test_legacy_text_locations_remain_supported(self):
        self.assertEqual(
            derive_ncr_lgus("Selected sites in Makati and Taguig"),
            ["Makati", "Taguig"],
        )
