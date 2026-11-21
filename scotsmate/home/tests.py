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
from courses.models import Course, CourseAccess, CourseEnrollment
from documents.models import Document, DocumentCategory
from surveys.models import Survey, SurveyAccess, SurveyResponse
from events.models import Event, EventRegistration
from message.models import Conversation, ConversationMember, Message


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
        self.assertEqual(doc_hr.status, 'APPROVED')
        self.assertEqual(doc_hr.request_type, 'UPDATE')
        self.assertEqual(doc_hr.access_permissions.count(), 0)
        self.assertEqual(doc_hr.proposals.filter(is_processed=False).count(), 1)

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


class HomeViewAndNotificationsTests(TestCase):
    """Kiểm thử HomeView (tìm kiếm, Lịch của bạn, sự kiện sắp tới), thông báo thật và loại bỏ /register/."""

    def setUp(self):
        self.groups = ensure_role_groups()
        self.branch = Branch.objects.create(name='Cơ sở Cầu Giấy', region='NORTH', address='Hà Nội')
        self.dept = Department.objects.create(name='Nhân sự', block=Department.BlockChoices.LEGAL_HR)
        self.user = User.objects.create_user(
            username='home_emp', password='pw', first_name='An', last_name='Nguyễn', is_staff=True
        )
        self.user.groups.add(self.groups[ROLE_EMPLOYEE])
        EmployeeInformation.objects.create(
            emp_id=self.user, gender='MALE', NIN='009990000001',
            tel='0909000001', dep=self.dept, branch=self.branch, date_of_birth='1995-03-03',
        )
        self.other = User.objects.create_user(
            username='home_sender', password='pw', first_name='Bình', last_name='Lê', is_staff=True
        )
        self.other.groups.add(self.groups[ROLE_EMPLOYEE])

    def test_index_home_search_header_and_register_removed(self):
        res_anon = self.client.get('/')
        self.assertRedirects(res_anon, '/login/', fetch_redirect_response=False)

        # Trang login không còn nút Đăng ký và route /register/ bị loại bỏ
        res_login = self.client.get('/login/')
        self.assertEqual(res_login.status_code, 200)
        res_reg_anon = self.client.get('/register/')
        self.assertEqual(res_reg_anon.status_code, 302)
        self.assertIn('/login/', res_reg_anon.url)

        Post.objects.create(author=self.user, title='Bản tin đào tạo', content='Nội dung tìm kiếm Alpha')
        Post.objects.create(author=self.user, title='Bản tin khác', content='Nội dung Beta')

        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/register/').status_code, 404)
        self.assertEqual(self.client.get('/courses/register/').status_code, 404)

        res_home = self.client.get('/home/')
        self.assertEqual(res_home.status_code, 200)
        self.assertContains(res_home, 'placeholder="Tìm kiếm bài viết..."')
        self.assertNotContains(res_home, '>Đăng ký<')
        self.assertNotContains(res_home, '/courses/trainee/courses/2/exam/')

        res_search = self.client.get('/home/?q=Alpha')
        self.assertContains(res_search, 'Nội dung tìm kiếm Alpha')
        self.assertNotContains(res_search, 'Nội dung Beta')

        # Trên /profile/, tab Bảng tin không còn bị active nhầm
        res_prof = self.client.get('/profile/')
        self.assertEqual(res_prof.status_code, 200)
        self.assertNotContains(res_prof, 'class="nav-tab active" href="/home/"')

    def test_calendar_schedule_excludes_draft_and_unregistered_events(self):
        now = timezone.now()
        upcoming_ev = Event.objects.create(
            title='Hội thảo chưa đăng ký',
            description='Mô tả hội thảo',
            organizer=self.other,
            date_start=now + timedelta(days=2),
            date_end=now + timedelta(days=2, hours=2),
            location='Hà Nội',
            status=Event.STATUS_UPCOMING,
        )
        draft_course = Course.objects.create(
            creator=self.other,
            code='KH-DRAFT',
            title='Khóa nháp không được hiện',
            date_start=date.today(),
            date_end=date.today() + timedelta(days=10),
            status='draft',
        )
        CourseEnrollment.objects.create(emp=self.user, course=draft_course, is_completed=False)

        self.client.force_login(self.user)
        res = self.client.get('/home/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['calendar_schedule'], [])
        self.assertContains(res, 'Bạn chưa có lịch trình nào sắp tới.')
        self.assertEqual(len(res.context['upcoming_events']), 1)
        self.assertFalse(res.context['upcoming_events'][0].is_registered)

        # Khi tham gia khóa học ongoing và đăng ký sự kiện -> hiển thị vào Lịch của bạn
        ongoing_course = Course.objects.create(
            creator=self.other,
            code='KH-ONGOING',
            title='Khóa hội nhập Scots',
            date_start=date.today(),
            date_end=date.today() + timedelta(days=5),
            status='ongoing',
        )
        CourseEnrollment.objects.create(emp=self.user, course=ongoing_course, is_completed=False)
        EventRegistration.objects.create(event=upcoming_ev, user=self.user)

        res2 = self.client.get('/home/')
        self.assertTrue(len(res2.context['calendar_schedule']) >= 1)
        titles = [item['title'] for day in res2.context['calendar_schedule'] for item in day['items']]
        self.assertIn('Khóa: Khóa hội nhập Scots', titles)
        self.assertIn('Hội thảo chưa đăng ký', titles)
        self.assertNotIn('Khóa: Khóa nháp không được hiện', titles)

    def test_real_notifications_and_mark_read_persistence(self):
        now = timezone.now()
        course = Course.objects.create(
            creator=self.other,
            code='KH-NOTIF',
            title='Khóa thông báo thật',
            date_start=date.today(),
            date_end=date.today() + timedelta(days=3),
            status='ongoing',
        )
        CourseEnrollment.objects.create(emp=self.user, course=course, is_completed=False)

        cat = DocumentCategory.objects.create(name='Quy trình nội bộ', display_order=1)
        doc = Document.objects.create(
            category=cat,
            title='Tài liệu thông báo thật',
            description='Mô tả',
            file=SimpleUploadedFile('tb.pdf', b'%PDF-1.4 tb'),
            creator=self.other,
            status='APPROVED',
            access_scope='ALL',
            is_visible=True,
        )
        ev = Event.objects.create(
            title='Sự kiện thông báo thật',
            description='Mô tả sự kiện',
            organizer=self.other,
            date_start=now + timedelta(days=1),
            date_end=now + timedelta(days=1, hours=2),
            location='Hội trường',
            status=Event.STATUS_UPCOMING,
        )
        conv = Conversation.objects.create(conversation_type=Conversation.TYPE_DIRECT)
        ConversationMember.objects.create(conversation=conv, user=self.user)
        ConversationMember.objects.create(conversation=conv, user=self.other)
        msg = Message.objects.create(conversation=conv, sender=self.other, content='Chào bạn mới')

        self.client.force_login(self.user)
        res = self.client.get('/home/')
        self.assertEqual(res.status_code, 200)
        notif_ids = [n['id'] for n in res.context['header_notifications']]
        self.assertIn(f'course-{course.id}', notif_ids)
        self.assertIn(f'doc-{doc.id}', notif_ids)
        self.assertIn(f'event-{ev.id}', notif_ids)
        self.assertIn(f'msg-{msg.id}', notif_ids)
        initial_unread = res.context['header_unread_notifications_count']
        self.assertEqual(initial_unread, len(notif_ids))

        # Đánh dấu đọc 1 thông báo -> lưu session & giảm unread_count
        res_mark_one = self.client.post('/notifications/read/', {'notif_id': f'msg-{msg.id}'})
        self.assertEqual(res_mark_one.status_code, 200)
        self.assertEqual(res_mark_one.json()['unread_count'], initial_unread - 1)

        # Đánh dấu tất cả là đã đọc -> unread_count = 0 và giữ nguyên khi tải lại trang
        res_mark_all = self.client.post('/notifications/read/', {'all': '1'})
        self.assertEqual(res_mark_all.status_code, 200)
        self.assertEqual(res_mark_all.json()['unread_count'], 0)

        res_after = self.client.get('/home/')
        self.assertEqual(res_after.context['header_unread_notifications_count'], 0)
