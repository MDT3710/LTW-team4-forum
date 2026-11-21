import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from home.models import Branch, Department, EmployeeInformation
from home.roles import ROLE_EMPLOYEE, ROLE_MANAGER, ensure_role_groups
from .models import Document, DocumentCategory, DocumentUpdateProposal

_TEMP_MEDIA = tempfile.mkdtemp(prefix='scotsmate_doc_tests_')


@override_settings(MEDIA_ROOT=_TEMP_MEDIA)
class DocumentsTemplateTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_TEMP_MEDIA, ignore_errors=True)
    def setUp(self):
        self.groups = ensure_role_groups()
        self.branch = Branch.objects.create(name='Chi nhánh HN', region='NORTH', address='Hà Nội')
        self.dept = Department.objects.create(name='Phòng Nhân sự', block=Department.BlockChoices.LEGAL_HR)
        self.emp = User.objects.create_user(username='doc_emp', password='Password123!', is_staff=True)
        self.emp.groups.add(self.groups[ROLE_EMPLOYEE])
        EmployeeInformation.objects.create(
            emp_id=self.emp, gender='MALE', NIN='001095000999',
            tel='0901000999', dep=self.dept, branch=self.branch, date_of_birth='1995-01-01',
        )
        self.mgr = User.objects.create_user(username='doc_mgr', password='Password123!', is_staff=True)
        self.mgr.groups.add(self.groups[ROLE_MANAGER])
        EmployeeInformation.objects.create(
            emp_id=self.mgr, gender='FEMALE', NIN='001095000888',
            tel='0901000888', dep=self.dept, branch=self.branch, date_of_birth='1994-01-01',
        )
        self.cat = DocumentCategory.objects.create(name='Quy trình', creator=self.mgr, display_order=1)

    def test_documents_index_renders_single_footer_and_doc_count(self):
        Document.objects.create(
            title='Tài liệu chuẩn',
            category=self.cat,
            creator=self.mgr,
            approver=self.mgr,
            status='APPROVED',
            access_scope='ALL',
            is_visible=True,
            file=SimpleUploadedFile('sample.pdf', b'%PDF-1.4\n%test', content_type='application/pdf'),
        )
        self.client.force_login(self.emp)
        res = self.client.get(reverse('documents'))
        self.assertEqual(res.status_code, 200)
        html = res.content.decode('utf-8')
        self.assertEqual(html.count('class="doc-table-pagination"'), 1)
        self.assertIn('1 tài liệu', html)
        self.assertIn('doc-filter-btn', html)

        cat_res = self.client.get(reverse('document_category', args=[self.cat.id]))
        self.assertEqual(cat_res.status_code, 200)
        cat_html = cat_res.content.decode('utf-8')
        self.assertIn('Tìm kiếm tài liệu trong danh mục này...', cat_html)
        self.assertIn('Xem trực tiếp', cat_html)

    def test_approved_doc_update_proposal_preserves_original_until_approved(self):
        doc = Document.objects.create(
            title='Quy trình gốc',
            category=self.cat,
            description='Mô tả gốc',
            creator=self.emp,
            approver=self.mgr,
            status='APPROVED',
            access_scope='ALL',
            is_visible=True,
            file=SimpleUploadedFile('orig.pdf', b'%PDF-1.4\n%orig', content_type='application/pdf'),
        )

        # Nhân viên đề xuất sửa bản đã duyệt -> bản gốc vẫn APPROVED & hiển thị bình thường
        self.client.force_login(self.emp)
        edit_res = self.client.post(
            reverse('document_edit', args=[doc.id]),
            {
                'title': 'Quy trình cập nhật v2',
                'category': self.cat.id,
                'description': 'Mô tả mới',
                'access_scope': 'ALL',
            },
        )
        self.assertEqual(edit_res.status_code, 302)
        doc.refresh_from_db()
        self.assertEqual(doc.status, 'APPROVED')
        self.assertEqual(doc.title, 'Quy trình gốc')
        self.assertEqual(DocumentUpdateProposal.objects.filter(document=doc, is_processed=False).count(), 1)

        my_res = self.client.get(reverse('document_my_docs'))
        self.assertIn('Chờ duyệt cập nhật', my_res.content.decode('utf-8'))

        # Trưởng phòng từ chối đề xuất -> bản gốc vẫn APPROVED, lưu lý do từ chối
        self.client.force_login(self.mgr)
        reject_res = self.client.post(
            reverse('document_approve_detail', args=[doc.id]),
            {'action': 'reject', 'rejection_reason': 'Thiếu biểu mẫu đính kèm'},
        )
        self.assertEqual(reject_res.status_code, 302)
        doc.refresh_from_db()
        self.assertEqual(doc.status, 'APPROVED')
        self.assertEqual(doc.title, 'Quy trình gốc')
        self.assertEqual(doc.rejection_reason, 'Thiếu biểu mẫu đính kèm')
        self.assertFalse(DocumentUpdateProposal.objects.filter(document=doc, is_processed=False).exists())

        # Nhân viên gửi lại đề xuất và được duyệt -> cập nhật vào bản gốc
        self.client.force_login(self.emp)
        self.client.post(
            reverse('document_edit', args=[doc.id]),
            {
                'title': 'Quy trình cập nhật v3',
                'category': self.cat.id,
                'description': 'Mô tả mới v3',
                'access_scope': 'ALL',
            },
        )
        self.client.force_login(self.mgr)
        approve_res = self.client.post(
            reverse('document_approve_detail', args=[doc.id]),
            {'action': 'approve'},
        )
        self.assertEqual(approve_res.status_code, 302)
        doc.refresh_from_db()
        self.assertEqual(doc.status, 'APPROVED')
        self.assertEqual(doc.title, 'Quy trình cập nhật v3')
        self.assertEqual(doc.rejection_reason, '')
