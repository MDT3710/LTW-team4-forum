from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from home.models import Branch, Department, EmployeeInformation
from home.roles import ROLE_EMPLOYEE, ensure_role_groups
from .models import DocumentCategory


class DocumentsTemplateTests(TestCase):
    def test_documents_index_renders_single_footer(self):
        groups = ensure_role_groups()
        branch = Branch.objects.create(name='Chi nhánh HN', region='NORTH', address='Hà Nội')
        dept = Department.objects.create(name='Phòng Nhân sự', block=Department.BlockChoices.LEGAL_HR)
        user = User.objects.create_user(username='doc_emp', password='Password123!', is_staff=True)
        user.groups.add(groups[ROLE_EMPLOYEE])
        EmployeeInformation.objects.create(
            emp_id=user, gender='MALE', NIN='001095000999',
            tel='0901000999', dep=dept, branch=branch, date_of_birth='1995-01-01',
        )
        DocumentCategory.objects.create(name='Quy trình', display_order=1)

        self.client.force_login(user)
        res = self.client.get(reverse('documents'))
        self.assertEqual(res.status_code, 200)
        html = res.content.decode('utf-8')
        self.assertEqual(html.count('class="doc-table-pagination"'), 1)
