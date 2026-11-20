from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from home.models import Branch, Department, EmployeeInformation
from home.roles import (
    ROLE_ADMIN,
    ROLE_EMPLOYEE,
    ROLE_MANAGER,
    ROLE_TRAINER,
    ensure_role_groups,
    get_primary_role_label,
    is_department_manager,
    is_it_admin,
    is_official_staff,
    is_trainer,
)
from posts.models import Post
from courses.models import Course, CourseAccess
from documents.models import Document, DocumentCategory
from surveys.models import Survey, SurveyAccess, SurveyResponse
from events.models import Event
from message.models import Conversation, ConversationMember


class RBACAndModulesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.groups = ensure_role_groups()
        cls.branch = Branch.objects.create(name='Cơ sở Hà Nội', region='NORTH', address='Hà Nội')
        cls.dept_hr = Department.objects.create(name='Phòng Nhân sự', block=Department.BlockChoices.LEGAL_HR)
        cls.dept_training = Department.objects.create(name='Phòng Đào tạo', block=Department.BlockChoices.ACADEMY)

        # 1. Admin (Phòng IT) — toàn quyền 7 phân hệ + /admin/
        cls.admin_user = User.objects.create_user(
            username='admin_it', password='Password123!', email='admin@scots.vn',
            first_name='Admin', last_name='IT', is_staff=True, is_superuser=True,
        )
        cls.admin_user.groups.add(cls.groups[ROLE_ADMIN])

        # 2. Trưởng phòng Nhân sự
        cls.manager = User.objects.create_user(
            username='truongphong_hr', password='Password123!', email='tphr@scots.vn',
            first_name='Đức', last_name='Trần Minh', is_staff=True,
        )
        cls.manager.groups.add(cls.groups[ROLE_MANAGER], cls.groups[ROLE_EMPLOYEE])
        cls.dept_hr.manager = cls.manager
        cls.dept_hr.save()
        EmployeeInformation.objects.create(
            emp_id=cls.manager, gender='MALE', NIN='001090000001',
            tel='0901000001', dep=cls.dept_hr, branch=cls.branch, date_of_birth='1990-01-01',
        )

        # 3. Trưởng phòng Đào tạo
        cls.training_manager = User.objects.create_user(
            username='truongphong_dt', password='Password123!', email='tpdt@scots.vn',
            first_name='Hà', last_name='Lê Thu', is_staff=True,
        )
        cls.training_manager.groups.add(cls.groups[ROLE_MANAGER], cls.groups[ROLE_EMPLOYEE])
        cls.dept_training.manager = cls.training_manager
        cls.dept_training.save()
        EmployeeInformation.objects.create(
            emp_id=cls.training_manager, gender='FEMALE', NIN='001090000099',
            tel='0901000099', dep=cls.dept_training, branch=cls.branch, date_of_birth='1990-02-02',
        )

        # 4. Trainer (Phòng Đào tạo)
        cls.trainer = User.objects.create_user(
            username='trainer', password='Password123!', email='trainer@scots.vn',
            first_name='Ánh', last_name='Minh', is_staff=True,
        )
        cls.trainer.groups.add(cls.groups[ROLE_TRAINER], cls.groups[ROLE_EMPLOYEE])
        EmployeeInformation.objects.create(
            emp_id=cls.trainer, gender='FEMALE', NIN='001092000002',
            tel='0901000002', dep=cls.dept_training, branch=cls.branch, date_of_birth='1992-01-01',
        )

        # 5. Nhân viên chính thức phòng Nhân sự (is_staff=True -> KHÔNG PHẢI trainer/admin!)
        cls.employee = User.objects.create_user(
            username='nhanvien', password='Password123!', email='nv@scots.vn',
            first_name='Chi', last_name='Phạm Lan', is_staff=True,
        )
        cls.employee.groups.add(cls.groups[ROLE_EMPLOYEE])
        EmployeeInformation.objects.create(
            emp_id=cls.employee, gender='FEMALE', NIN='001095000003',
            tel='0901000003', dep=cls.dept_hr, branch=cls.branch, date_of_birth='1995-01-01',
        )

        # 6. Nhân viên phòng Đào tạo
        cls.training_emp = User.objects.create_user(
            username='nv_daotao', password='Password123!', email='nvdt@scots.vn',
            first_name='Nam', last_name='Hoàng', is_staff=True,
        )
        cls.training_emp.groups.add(cls.groups[ROLE_EMPLOYEE])
        EmployeeInformation.objects.create(
            emp_id=cls.training_emp, gender='MALE', NIN='001095000010',
            tel='0901000010', dep=cls.dept_training, branch=cls.branch, date_of_birth='1995-05-05',
        )

        # 7. Cộng tác viên part-time (is_staff=False)
        cls.ctv = User.objects.create_user(
            username='ctv_huy', password='Password123!', email='ctv@scots.vn',
            first_name='Huy', last_name='Đặng Quang', is_staff=False,
        )
        cls.ctv.groups.add(cls.groups[ROLE_EMPLOYEE])
        EmployeeInformation.objects.create(
            emp_id=cls.ctv, gender='MALE', NIN='001097000004',
            tel='0901000004', dep=cls.dept_hr, branch=cls.branch, date_of_birth='1997-01-01',
        )

    def test_roles_no_director_and_is_staff_meaning(self):
        """Hệ thống chỉ còn 4 nhóm quyền (không có Giám đốc); is_staff=1 không biến nhân viên thành Trainer/Admin."""
        self.assertFalse(Group.objects.filter(name='Giám đốc').exists())
        self.assertTrue(is_official_staff(self.employee))
        self.assertFalse(is_official_staff(self.ctv))
        self.assertFalse(is_trainer(self.employee))
        self.assertFalse(is_it_admin(self.employee))
        self.assertFalse(is_department_manager(self.employee))
        self.assertTrue(is_it_admin(self.admin_user))

        self.assertEqual(get_primary_role_label(self.ctv), 'Cộng tác viên (Part-time)')
        self.assertEqual(get_primary_role_label(self.employee), 'Nhân viên')
        self.assertEqual(get_primary_role_label(self.trainer), 'Giảng viên (Trainer)')
        self.assertEqual(get_primary_role_label(self.manager), 'Trưởng phòng')
        self.assertEqual(get_primary_role_label(self.admin_user), 'Admin')

    def test_password_reset_built_in_view(self):
        """Nhân viên sử dụng Django built-in PasswordResetView để tự đặt lại mật khẩu."""
        res = self.client.get('/password-reset/')
        self.assertEqual(res.status_code, 200)
        res_post = self.client.post('/password-reset/', {'email': 'nv@scots.vn'})
        self.assertEqual(res_post.status_code, 302)
        self.assertEqual(res_post.url, '/password-reset/done/')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/reset/', mail.outbox[0].body)

    def test_django_admin_access_for_admin_only(self):
        """Admin (Phòng IT) quản trị tài khoản qua /admin/; nhân viên (is_staff=1) bị middleware chặn khỏi /admin/."""
        self.client.force_login(self.employee)
        res_emp = self.client.get('/admin/', HTTP_REFERER='/home/')
        self.assertEqual(res_emp.status_code, 302)
        self.assertEqual(res_emp.url, '/home/')

        self.client.force_login(self.admin_user)
        res_adm = self.client.get('/admin/')
        self.assertEqual(res_adm.status_code, 200)

    def test_posts_and_courses_admin_full_access(self):
        """Admin IT có toàn quyền trên Bài đăng & Đào tạo; nhân viên (is_staff=1) chỉ là Trainee trong Đào tạo."""
        post = Post.objects.create(author=self.employee, title='Bài thảo luận', content='Nội dung thử nghiệm')
        self.client.force_login(self.manager)
        res_mgr_del = self.client.post(f'/posts/posts/{post.id}/delete/')
        self.assertEqual(res_mgr_del.status_code, 403)

        self.client.force_login(self.admin_user)
        res_adm_del = self.client.post(f'/posts/posts/{post.id}/delete/')
        self.assertEqual(res_adm_del.status_code, 200)
        self.assertFalse(Post.objects.filter(id=post.id).exists())

        course = Course.objects.create(
            creator=self.trainer, code='KH-RBAC', title='Khóa học test RBAC',
            date_start=date.today(), date_end=date.today() + timedelta(days=7), status='ongoing',
        )
        CourseAccess.objects.create(emp=self.trainer, course=course, role='trainer')

        # Nhân viên (is_staff=1) và CTV (is_staff=0) đều bị chặn vào trang thiết lập đề thi Trainer
        for trainee in (self.employee, self.ctv):
            self.client.force_login(trainee)
            res = self.client.get(
                f'/courses/trainer/courses/{course.id}/exam/setup/',
                HTTP_REFERER='/courses/trainee/courses/',
            )
            self.assertEqual(res.status_code, 302)
            self.assertEqual(res.url, '/courses/trainee/courses/')

        # Admin IT truy cập được toàn bộ quản lý khóa học & tạo đề thi
        self.client.force_login(self.admin_user)
        res_adm_course = self.client.get(f'/courses/trainer/courses/{course.id}/')
        self.assertEqual(res_adm_course.status_code, 200)
        res_adm_setup = self.client.get(f'/courses/trainer/courses/{course.id}/exam/setup/')
        self.assertEqual(res_adm_setup.status_code, 200)

    def test_documents_usecase_category_create_and_department_scope(self):
        """Use case Tài liệu mới: Chỉ Trưởng phòng/Admin tạo-sửa-xóa danh mục; Nhân viên xem danh mục & tự sửa-xóa tài liệu mình tạo; Từ chối bắt buộc nhập lý do."""
        cat = DocumentCategory.objects.create(name='Quy định chung', display_order=1)

        # 1. Nhân viên chỉ được xem danh mục, KHÔNG được tạo/sửa/xóa danh mục
        self.client.force_login(self.employee)
        res_doc_list = self.client.get('/documents/')
        self.assertEqual(res_doc_list.status_code, 200)
        self.assertNotContains(res_doc_list, 'Tạo danh mục')
        self.assertEqual(self.client.get('/documents/category/create/').status_code, 302)
        self.client.post('/documents/category/create/', {'name': 'Danh mục trái phép', 'description': 'x'})
        self.assertFalse(DocumentCategory.objects.filter(name='Danh mục trái phép').exists())
        self.assertEqual(self.client.get(f'/documents/category/{cat.id}/edit/').status_code, 302)
        self.client.post('/documents/', {'delete_cat_id': cat.id})
        self.assertTrue(DocumentCategory.objects.filter(id=cat.id).exists())

        # Trưởng phòng toàn quyền tạo/sửa/xóa mọi danh mục
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get('/documents/category/create/').status_code, 200)
        self.client.post('/documents/category/create/', {'name': 'Danh mục Trưởng phòng tạo', 'description': 'Mô tả'})
        mgr_cat = DocumentCategory.objects.get(name='Danh mục Trưởng phòng tạo')
        self.client.post(f'/documents/category/{mgr_cat.id}/edit/', {'name': 'Danh mục TP đã sửa', 'description': 'Mới'})
        mgr_cat.refresh_from_db()
        self.assertEqual(mgr_cat.name, 'Danh mục TP đã sửa')

        # 2. Mô tả quá 300 ký tự bị từ chối khi nhân viên tạo tài liệu
        self.client.force_login(self.employee)
        res_too_long = self.client.post('/documents/create/', {
            'title': 'Tài liệu mô tả dài',
            'category': cat.id,
            'access_scope': 'ALL',
            'description': 'x' * 301,
            'file': SimpleUploadedFile('long.pdf', b'%PDF-1.4 long'),
        })
        self.assertEqual(res_too_long.status_code, 200)
        self.assertFalse(Document.objects.filter(title='Tài liệu mô tả dài').exists())

        # Nhân viên đăng tài liệu hợp lệ -> phải PENDING
        long_valid_desc = 'A' * 120
        res_emp_doc = self.client.post('/documents/create/', {
            'title': 'Tài liệu nhân viên gửi',
            'category': cat.id,
            'access_scope': 'ALL',
            'description': long_valid_desc,
            'file': SimpleUploadedFile('emp.pdf', b'%PDF-1.4 emp'),
        })
        self.assertEqual(res_emp_doc.status_code, 302)
        doc_hr = Document.objects.get(title='Tài liệu nhân viên gửi')
        self.assertEqual(doc_hr.status, 'PENDING')

        # Tài liệu phòng Đào tạo gửi duyệt -> Trưởng phòng thấy và duyệt được; từ chối trống lý do bị chặn
        doc_dt = Document.objects.create(
            category=cat, title='Tài liệu phòng Đào tạo', description='ĐT ' * 40,
            file=SimpleUploadedFile('dt.pdf', b'%PDF-1.4 dt'),
            creator=self.training_emp, status='PENDING', request_type='NEW',
        )

        # Trưởng phòng đăng tài liệu mới -> APPROVED ngay không cần chờ duyệt
        self.client.force_login(self.manager)
        self.client.post('/documents/create/', {
            'title': 'Quy định Trưởng phòng đăng',
            'category': cat.id,
            'access_scope': 'ALL',
            'description': 'Nội dung trưởng phòng ban hành',
            'file': SimpleUploadedFile('mgr.pdf', b'%PDF-1.4 mgr'),
        })
        doc_mgr = Document.objects.get(title='Quy định Trưởng phòng đăng')
        self.assertEqual(doc_mgr.status, 'APPROVED')

        # Từ chối để trống lý do -> KHÔNG đổi sang REJECTED
        self.client.post(f'/documents/approve/{doc_dt.id}/', {'action': 'reject', 'rejection_reason': '   '})
        doc_dt.refresh_from_db()
        self.assertEqual(doc_dt.status, 'PENDING')

        # Trưởng phòng thấy CẢ doc_hr lẫn doc_dt ở /documents/approve/ và duyệt được
        res_app_list = self.client.get('/documents/approve/')
        self.assertContains(res_app_list, 'Tài liệu nhân viên gửi')
        self.assertContains(res_app_list, 'Tài liệu phòng Đào tạo')
        self.client.post(f'/documents/approve/{doc_dt.id}/', {'action': 'approve'})
        doc_dt.refresh_from_db()
        self.assertEqual(doc_dt.status, 'APPROVED')
        self.client.post(f'/documents/approve/{doc_hr.id}/', {'action': 'approve'})
        doc_hr.refresh_from_db()
        self.assertEqual(doc_hr.status, 'APPROVED')

        # 3. Trong danh mục: Nhân viên bấm tên để xem chi tiết đầy đủ, có nút Tải về (không có nút Chi tiết riêng ở cột Thao tác)
        self.client.force_login(self.employee)
        res_cat_view = self.client.get(f'/documents/{cat.id}/')
        self.assertContains(res_cat_view, long_valid_desc)
        self.assertContains(res_cat_view, 'Tải về')

        # Kiểm tra sửa file sai định dạng bị từ chối ở DocumentEditForm
        res_bad_ext = self.client.post(f'/documents/my_docs/{doc_hr.id}/edit/', {
            'title': 'Sai đuôi',
            'category': cat.id,
            'access_scope': 'ALL',
            'description': 'Test',
            'file': SimpleUploadedFile('malware.exe', b'MZ'),
        })
        self.assertEqual(res_bad_ext.status_code, 200)

        # Sửa tài liệu Đã duyệt sang DEPARTMENT nhưng chưa duyệt -> không ghi đè DocumentAccess gốc
        self.client.post(f'/documents/my_docs/{doc_hr.id}/edit/', {
            'title': 'Tài liệu nhân viên sửa',
            'category': cat.id,
            'access_scope': 'DEPARTMENT',
            'departments': [self.dept_hr.id],
            'description': 'Mô tả mới sau sửa',
        })
        doc_hr.refresh_from_db()
        self.assertEqual(doc_hr.status, 'PENDING')
        self.assertEqual(doc_hr.request_type, 'UPDATE')
        self.assertEqual(doc_hr.access_permissions.count(), 0)

        # Không xóa được tài liệu của người khác (doc_dt), nhưng xóa được tài liệu của mình
        self.client.post(f'/documents/{cat.id}/', {'delete_doc_id': doc_dt.id})
        self.assertTrue(Document.objects.filter(id=doc_dt.id).exists())
        self.client.post('/documents/my_docs/', {'delete_doc_id': doc_hr.id})
        self.assertFalse(Document.objects.filter(id=doc_hr.id).exists())

        # Trưởng phòng xóa được danh mục vừa tạo và ẩn/hiện tài liệu
        self.client.force_login(self.manager)
        self.client.post('/documents/', {'delete_cat_id': mgr_cat.id})
        self.assertFalse(DocumentCategory.objects.filter(id=mgr_cat.id).exists())
        self.client.post(f'/documents/{cat.id}/', {'toggle_visibility_id': doc_dt.id})
        doc_dt.refresh_from_db()
        self.assertFalse(doc_dt.is_visible)

    def test_surveys_and_events_admin_manager_creator(self):
        """Khảo sát: creator + Trưởng phòng + Admin xem được phản hồi; Sự kiện: Trưởng phòng + Admin tạo/sửa/xóa."""
        survey = Survey.objects.create(
            name='Khảo sát test HR', department=self.dept_hr, creator=self.employee, is_approved=True
        )
        SurveyAccess.objects.create(survey=survey, emp=self.employee, can_respond=True, can_view_responses=False)
        SurveyResponse.objects.create(survey=survey, respondent=self.ctv, submission_date=timezone.now())

        # Creator xem được báo cáo khảo sát (theo yêu cầu người dùng)
        self.client.force_login(self.employee)
        res_creator_ov = self.client.get(f'/surveys/published/{survey.id}/overview/')
        self.assertEqual(res_creator_ov.status_code, 200)

        # Admin toàn quyền xem phản hồi, duyệt khảo sát và tạo sự kiện
        self.client.force_login(self.admin_user)
        res_adm_pub = self.client.get('/surveys/published/')
        self.assertContains(res_adm_pub, 'Khảo sát test HR')
        res_adm_ev = self.client.get('/events/create/')
        self.assertEqual(res_adm_ev.status_code, 200)

        # Nhân viên thường bị chặn tạo sự kiện
        self.client.force_login(self.employee)
        res_emp_ev = self.client.get('/events/create/', HTTP_REFERER='/events/')
        self.assertEqual(res_emp_ev.status_code, 302)
        self.assertEqual(res_emp_ev.url, '/events/')

    def test_messaging_group_lifecycle_usecase(self):
        """Nhân viên được nhắn tin & rời nhóm; Trưởng phòng & QTV/Admin tạo nhóm, thêm/xóa thành viên, trao QTV, xóa nhóm."""
        # Nhân viên thường không được tạo nhóm mới
        self.client.force_login(self.employee)
        res_create_denied = self.client.get('/message/group/create/', HTTP_REFERER='/message/')
        self.assertEqual(res_create_denied.status_code, 302)
        self.assertEqual(res_create_denied.url, '/message/')

        # Trưởng phòng tạo nhóm mới
        self.client.force_login(self.manager)
        res_create = self.client.post('/message/group/create/', {
            'title': 'Nhóm HR Test',
            'branch': 'Chi nhánh Cầu Giấy',
            'members': [self.employee.id, self.ctv.id],
        })
        self.assertEqual(res_create.status_code, 302)
        group = Conversation.objects.get(title='Nhóm HR Test')
        self.assertTrue(group.members.filter(id=self.employee.id).exists())

        # Nhân viên rời nhóm
        self.client.force_login(self.employee)
        res_leave = self.client.post(f'/message/group/{group.id}/leave/')
        self.assertEqual(res_leave.status_code, 302)
        self.assertFalse(ConversationMember.objects.filter(conversation=group, user=self.employee).exists())

        # Trưởng phòng thêm lại thành viên, trao quyền QTV cho nhân viên, rồi xóa CTV khỏi nhóm
        self.client.force_login(self.manager)
        self.client.post(f'/message/group/{group.id}/members/add/', {'user_id': self.employee.id})
        self.assertTrue(ConversationMember.objects.filter(conversation=group, user=self.employee).exists())

        self.client.post(f'/message/group/{group.id}/members/{self.employee.id}/grant-admin/')
        ms_emp = ConversationMember.objects.get(conversation=group, user=self.employee)
        self.assertEqual(ms_emp.role, ConversationMember.ROLE_ADMIN)

        # Nhân viên sau khi được trao QTV có thể xóa CTV khỏi nhóm
        self.client.force_login(self.employee)
        self.client.post(f'/message/group/{group.id}/members/{self.ctv.id}/remove/')
        self.assertFalse(ConversationMember.objects.filter(conversation=group, user=self.ctv).exists())

        # Trưởng phòng xóa nhóm chat
        self.client.force_login(self.manager)
        self.client.post(f'/message/group/{group.id}/delete/')
        self.assertFalse(Conversation.objects.filter(id=group.id).exists())
