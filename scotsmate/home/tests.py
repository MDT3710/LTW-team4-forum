from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from home.models import Branch, Department, EmployeeInformation
from home.roles import (
    ROLE_ADMIN,
    ROLE_DIRECTOR,
    ROLE_EMPLOYEE,
    ROLE_MANAGER,
    ROLE_TRAINER,
    ensure_role_groups,
    get_primary_role_label,
    is_department_manager,
    is_director,
    is_it_admin,
    is_official_staff,
    is_trainer,
)
from posts.models import Post, PostComment
from courses.models import Course, CourseAccess, CourseEnrollment
from documents.models import Document, DocumentCategory
from surveys.models import Survey, SurveyAccess
from events.models import Event


class RBACAndModulesTests(TestCase):
    def setUp(self):
        self.groups = ensure_role_groups()
        self.branch = Branch.objects.create(name='Cơ sở Hà Nội', region='NORTH', address='Hà Nội')
        self.dept_hr = Department.objects.create(name='Phòng Nhân sự', block=Department.BlockChoices.LEGAL_HR)
        self.dept_training = Department.objects.create(name='Phòng Đào tạo', block=Department.BlockChoices.ACADEMY)

        # 1. Admin IT
        self.admin_user = User.objects.create_user(
            username='admin_it', password='Password123!', email='admin@scots.vn',
            first_name='Admin', last_name='IT', is_staff=True, is_superuser=True,
        )
        self.admin_user.groups.add(self.groups[ROLE_ADMIN])

        # 2. Giám đốc (even if listed as manager on an empty dept, must remain Director read-only)
        self.director = User.objects.create_user(
            username='giamdoc', password='Password123!', email='gd@scots.vn',
            first_name='Mai', last_name='Vũ Thị', is_staff=True,
        )
        self.director.groups.add(self.groups[ROLE_DIRECTOR])

        # 3. Trưởng phòng Nhân sự
        self.manager = User.objects.create_user(
            username='truongphong', password='Password123!', email='tp@scots.vn',
            first_name='Đức', last_name='Trần Minh', is_staff=True,
        )
        self.manager.groups.add(self.groups[ROLE_MANAGER], self.groups[ROLE_EMPLOYEE])
        self.dept_hr.manager = self.manager
        self.dept_hr.save()
        EmployeeInformation.objects.create(
            emp_id=self.manager, gender='MALE', NIN='001090000001',
            tel='0901000001', dep=self.dept_hr, branch=self.branch, date_of_birth='1990-01-01',
        )

        # 4. Trainer (Phòng Đào tạo)
        self.trainer = User.objects.create_user(
            username='trainer', password='Password123!', email='trainer@scots.vn',
            first_name='Ánh', last_name='Minh', is_staff=True,
        )
        self.trainer.groups.add(self.groups[ROLE_TRAINER], self.groups[ROLE_EMPLOYEE])
        EmployeeInformation.objects.create(
            emp_id=self.trainer, gender='FEMALE', NIN='001092000002',
            tel='0901000002', dep=self.dept_training, branch=self.branch, date_of_birth='1992-01-01',
        )

        # 5. Nhân viên chính thức (is_staff=True -> KHÔNG PHẢI trainer/admin!)
        self.employee = User.objects.create_user(
            username='nhanvien', password='Password123!', email='nv@scots.vn',
            first_name='Chi', last_name='Phạm Lan', is_staff=True,
        )
        self.employee.groups.add(self.groups[ROLE_EMPLOYEE])
        EmployeeInformation.objects.create(
            emp_id=self.employee, gender='FEMALE', NIN='001095000003',
            tel='0901000003', dep=self.dept_hr, branch=self.branch, date_of_birth='1995-01-01',
        )

        # 6. Cộng tác viên part-time (is_staff=False)
        self.ctv = User.objects.create_user(
            username='ctv_huy', password='Password123!', email='ctv@scots.vn',
            first_name='Huy', last_name='Đặng Quang', is_staff=False,
        )
        self.ctv.groups.add(self.groups[ROLE_EMPLOYEE])
        EmployeeInformation.objects.create(
            emp_id=self.ctv, gender='MALE', NIN='001097000004',
            tel='0901000004', dep=self.dept_hr, branch=self.branch, date_of_birth='1997-01-01',
        )

    def test_is_staff_meaning_vs_roles(self):
        """is_staff=1 là nhân viên chính thức, is_staff=0 là CTV part-time; KHÔNG biến nhân viên thành trainer/admin."""
        self.assertTrue(is_official_staff(self.employee))
        self.assertFalse(is_official_staff(self.ctv))
        self.assertFalse(is_trainer(self.employee))
        self.assertFalse(is_it_admin(self.employee))
        self.assertFalse(is_department_manager(self.employee))
        self.assertEqual(get_primary_role_label(self.ctv), 'Cộng tác viên (Part-time)')
        self.assertEqual(get_primary_role_label(self.employee), 'Nhân viên')
        self.assertEqual(get_primary_role_label(self.trainer), 'Giảng viên (Trainer)')
        self.assertEqual(get_primary_role_label(self.director), 'Giám đốc')
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

    def test_accounts_manage_admin_only_and_role_update(self):
        """Chỉ Admin IT được truy cập Quản lý tài khoản, cập nhật info & đổi role; nhân viên bị chặn và trả về referer."""
        self.client.force_login(self.employee)
        res_emp = self.client.get('/accounts/manage/', HTTP_REFERER='/home/')
        self.assertEqual(res_emp.status_code, 302)
        self.assertEqual(res_emp.url, '/home/')

        self.client.force_login(self.admin_user)
        res_ok = self.client.get('/accounts/manage/')
        self.assertEqual(res_ok.status_code, 200)

        res_upd = self.client.post('/accounts/manage/', {
            'action': 'update_account',
            'user_id': self.employee.id,
            'first_name': 'Chi Updated',
            'last_name': 'Phạm Lan',
            'email': 'chi_new@scots.vn',
            'role': ROLE_TRAINER,
            'is_staff': '1',
            'department_id': self.dept_training.id,
            'branch_id': self.branch.id,
            'tel': '0912345678',
        })
        self.assertEqual(res_upd.status_code, 302)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.first_name, 'Chi Updated')
        self.assertTrue(is_trainer(self.employee))

    def test_posts_director_cannot_delete_others_but_admin_can(self):
        """Giám đốc không thể xóa bài của người khác; Admin (Phòng IT) có quyền xóa bài viết vi phạm."""
        post = Post.objects.create(author=self.employee, title='Bài thảo luận', content='Nội dung thử nghiệm')

        # Xem chi tiết bài đăng hoạt động
        self.client.force_login(self.employee)
        res_detail = self.client.get(f'/posts/posts/{post.id}/')
        self.assertEqual(res_detail.status_code, 200)
        self.assertContains(res_detail, 'Bài thảo luận')

        # Giám đốc cố xóa -> 403
        self.client.force_login(self.director)
        res_dir = self.client.post(f'/posts/posts/{post.id}/delete/')
        self.assertEqual(res_dir.status_code, 403)
        self.assertTrue(Post.objects.filter(id=post.id).exists())

        # Admin IT xóa bài -> 200 OK
        self.client.force_login(self.admin_user)
        res_adm = self.client.post(f'/posts/posts/{post.id}/delete/')
        self.assertEqual(res_adm.status_code, 200)
        self.assertFalse(Post.objects.filter(id=post.id).exists())

    def test_courses_rbac_is_staff_employee_is_trainee_and_redirect_back(self):
        """Nhân viên (is_staff=1) là Trainee, bị chặn vào trang Thiết lập bài thi & quay về trang hiện tại."""
        course = Course.objects.create(
            creator=self.trainer, code='KH-RBAC', title='Khóa học test RBAC',
            date_start=date.today(), date_end=date.today() + timedelta(days=7), status='ongoing',
        )
        CourseAccess.objects.create(emp=self.trainer, course=course, role='trainer')

        # Nhân viên (is_staff=1) bấm link thiết lập bài thi -> bị chặn & trả về HTTP_REFERER
        self.client.force_login(self.employee)
        res = self.client.get(
            f'/courses/trainer/courses/{course.id}/exam/setup/',
            HTTP_REFERER='/courses/trainee/courses/',
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, '/courses/trainee/courses/')

        # Giám đốc xem dashboard khóa học được, nhưng tạo khóa học hoặc thiết lập bài thi bị chặn
        self.client.force_login(self.director)
        res_dash = self.client.get('/courses/trainer/courses/dashboard/')
        self.assertEqual(res_dash.status_code, 200)
        res_setup = self.client.get(
            f'/courses/trainer/courses/{course.id}/exam/setup/',
            HTTP_REFERER='/courses/trainer/courses/',
        )
        self.assertEqual(res_setup.status_code, 302)
        self.assertEqual(res_setup.url, '/courses/trainer/courses/')

        # Admin IT không tác động đào tạo
        self.client.force_login(self.admin_user)
        res_adm = self.client.get('/courses/', HTTP_REFERER='/home/')
        self.assertEqual(res_adm.status_code, 302)
        self.assertEqual(res_adm.url, '/home/')

    def test_documents_rbac_hide_edit_delete_and_director_readonly(self):
        """Trưởng phòng ẩn/sửa/xóa/duyệt tài liệu; Giám đốc chỉ xem; nhân viên thường không được duyệt hay ẩn."""
        cat = DocumentCategory.objects.create(name='Quy định chung', display_order=1)
        doc = Document.objects.create(
            category=cat, title='Tài liệu nội bộ', description='Mô tả',
            file=SimpleUploadedFile('test.pdf', b'%PDF-1.4 test'),
            creator=self.employee, status='APPROVED', access_scope='ALL',
        )

        # Nhân viên thường vào duyệt -> bị chặn & trả về referer
        self.client.force_login(self.employee)
        res_emp = self.client.get('/documents/approve/', HTTP_REFERER='/documents/')
        self.assertEqual(res_emp.status_code, 302)
        self.assertEqual(res_emp.url, '/documents/')

        # Trưởng phòng ẩn tài liệu
        self.client.force_login(self.manager)
        res_hide = self.client.post(f'/documents/{cat.id}/', {'toggle_visibility_id': doc.id})
        self.assertEqual(res_hide.status_code, 302)
        doc.refresh_from_db()
        self.assertFalse(doc.is_visible)

        # Nhân viên không thấy tài liệu đã ẩn; Trưởng phòng vẫn thấy để bật lại
        self.client.force_login(self.employee)
        res_cat_emp = self.client.get(f'/documents/{cat.id}/')
        self.assertEqual(res_cat_emp.context['documents'].count(), 0)

        # Hiện lại để Giám đốc xem
        self.client.force_login(self.manager)
        self.client.post(f'/documents/{cat.id}/', {'toggle_visibility_id': doc.id})

        self.client.force_login(self.director)
        res_dir = self.client.get(f'/documents/{cat.id}/')
        self.assertContains(res_dir, 'Tài liệu nội bộ')
        # Giám đốc không thể xóa tài liệu
        res_dir_del = self.client.post(f'/documents/{cat.id}/', {'delete_doc_id': doc.id}, HTTP_REFERER=f'/documents/{cat.id}/')
        self.assertEqual(res_dir_del.status_code, 302)
        self.assertTrue(Document.objects.filter(id=doc.id).exists())

    def test_surveys_rbac_and_events_rbac(self):
        """Khảo sát & Sự kiện: nhân viên thường không thể duyệt khảo sát hay tạo sự kiện; Giám đốc chỉ xem báo cáo khảo sát."""
        survey = Survey.objects.create(
            name='Khảo sát test', department=self.dept_hr, creator=self.employee, is_approved=True
        )
        SurveyAccess.objects.create(survey=survey, emp=self.employee, can_respond=True, can_view_responses=False)

        # Giám đốc xem tất cả khảo sát và báo cáo ở chế độ chỉ xem, không thể ẩn khảo sát
        self.client.force_login(self.director)
        res_pub = self.client.get('/surveys/published/')
        self.assertEqual(res_pub.status_code, 200)
        self.assertContains(res_pub, 'Khảo sát test')
        res_toggle = self.client.post(f'/surveys/published/{survey.id}/overview/', {'action': 'toggle_visible'}, HTTP_REFERER='/surveys/published/')
        self.assertEqual(res_toggle.status_code, 302)
        survey.refresh_from_db()
        self.assertTrue(survey.is_visible)

        # Nhân viên vào trang khảo sát thấy nút Xem chi tiết
        self.client.force_login(self.employee)
        res_my = self.client.get('/surveys/')
        self.assertEqual(res_my.status_code, 200)
        self.assertContains(res_my, 'Xem chi tiết')

        # Sự kiện: nhân viên thường (is_staff=1) không được tạo sự kiện -> quay về trang hiện tại
        self.client.force_login(self.employee)
        res_ev = self.client.get('/events/create/', HTTP_REFERER='/events/')
        self.assertEqual(res_ev.status_code, 302)
        self.assertEqual(res_ev.url, '/events/')

        # Trưởng phòng tạo được sự kiện
        self.client.force_login(self.manager)
        res_ev_mgr = self.client.get('/events/create/')
        self.assertEqual(res_ev_mgr.status_code, 200)
