import re

from rest_framework.test import APIClient

from cms.models import CMSPageSection


class SectionEditingClient(APIClient):
    """Open the editing session before testing an ordinary section save."""

    def _open_section(self, path):
        if not hasattr(self, "_section_leases"):
            self._section_leases = {}
        response = self.post(f"{path}lock/")
        if response.status_code == 200:
            self._section_leases[path] = response.data["edit_lease"]
        return self._section_leases.get(path)

    def _with_leases(self, path, data):
        if not isinstance(data, dict):
            return data
        section = re.fullmatch(r"/api/admin/cms/sections/(\d+)/", path)
        if section and "edit_lease" not in data:
            return {**data, "edit_lease": self._open_section(path)}
        module = re.fullmatch(r"/api/admin/cms/modules/([^/]+)/", path)
        sections = data.get("sections")
        if module and isinstance(sections, dict) and "section_leases" not in data:
            leases = {}
            for row in CMSPageSection.objects.filter(page__slug=module[1], section_key__in=sections):
                leases[row.section_key] = self._open_section(f"/api/admin/cms/sections/{row.pk}/")
            return {**data, "section_leases": leases}
        return data

    def patch(self, path, data=None, *args, **kwargs):
        return super().patch(path, self._with_leases(path, data), *args, **kwargs)

    def put(self, path, data=None, *args, **kwargs):
        return super().put(path, self._with_leases(path, data), *args, **kwargs)
