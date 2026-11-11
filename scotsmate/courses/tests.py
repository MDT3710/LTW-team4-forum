from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from datetime import date, timedelta
from .models import (
    Course,
    CourseAccess,
    CourseMaterial,
    CourseExam,
    CourseExamQuestion,
    CourseQuestionChoice,
    CourseEnrollment,
    CourseExamResponse,
    CourseExamResponseDetail,
)

class CoursesLmsTests(TestCase):
    def setUp(self):
        # Tạo Trainer (Giảng viên)
        self.trainer = User.objects.create_user(
            username='trainer_test',
            password='Password123!',
            first_name='Đức',
            last_name='Trần Minh',
            is_staff=True,
        )

        # Tạo Trainee (Học viên)
        self.trainee = User.objects.create_user(
            username='trainee_test',
            password='Password123!',
            first_name='Anh',
            last_name='Nguyễn Minh',
            is_staff=False,
        )

        # Tạo Khóa học thử nghiệm
        self.course = Course.objects.create(
            creator=self.trainer,
            code='KH-TEST01',
            title='Nghiệp vụ Scots English Test',
            description='Khóa học phục vụ kiểm thử hệ thống LMS',
            date_start=date.today(),
            date_end=date.today() + timedelta(days=30),
            status='ongoing',
        )

        # Quyền truy cập
        CourseAccess.objects.create(emp=self.trainer, course=self.course, role='trainer')

        # Thêm 2 bài giảng
        self.mat1 = CourseMaterial.objects.create(
            course=self.course,
            name='Bài 1: Tổng quan quy trình',
            file_type='video',
            duration_minutes=20,
            order=1,
            summary='Tóm tắt quy trình chuẩn Scots',
            key_points=[{'title': 'Nguyên tắc 1', 'desc': 'Mô tả nguyên tắc 1'}],
            scenario_title='Tình huống 1',
            scenario_content='Nội dung tình huống 1',
            content='Lý thuyết bài 1',
        )
        self.mat2 = CourseMaterial.objects.create(
            course=self.course,
            name='Bài 2: Xử lý tình huống phụ huynh',
            file_type='pdf',
            duration_minutes=30,
            order=2,
            summary='Tóm tắt bài 2',
            key_points=[],
            scenario_title='',
            scenario_content='',
            content='Lý thuyết bài 2',
        )

        # Ghi danh Trainee
        self.enrollment = CourseEnrollment.objects.create(
            emp=self.trainee,
            course=self.course,
            study_process=0,
            is_pass=False,
            is_completed=False,
        )

        # Tạo Bài thi
        self.exam = CourseExam.objects.create(
            course=self.course,
            title='Bài kiểm tra năng lực cuối khóa',
            passcode='SCOTS2026',
            duration=30,
            passing_score=80.0,
            is_active=True,
        )

        # Tạo 2 câu hỏi trắc nghiệm
        self.q1 = CourseExamQuestion.objects.create(
            exam=self.exam,
            question_number=1,
            caption='Câu hỏi trắc nghiệm số 1?',
            correct_choice=2,
        )
        CourseQuestionChoice.objects.create(question=self.q1, choice_number=1, content='Đáp án A sai')
        CourseQuestionChoice.objects.create(question=self.q1, choice_number=2, content='Đáp án B đúng')
        CourseQuestionChoice.objects.create(question=self.q1, choice_number=3, content='Đáp án C sai')
        CourseQuestionChoice.objects.create(question=self.q1, choice_number=4, content='Đáp án D sai')

        self.q2 = CourseExamQuestion.objects.create(
            exam=self.exam,
            question_number=2,
            caption='Câu hỏi trắc nghiệm số 2?',
            correct_choice=1,
        )
        CourseQuestionChoice.objects.create(question=self.q2, choice_number=1, content='Đáp án A đúng')
        CourseQuestionChoice.objects.create(question=self.q2, choice_number=2, content='Đáp án B sai')
        CourseQuestionChoice.objects.create(question=self.q2, choice_number=3, content='Đáp án C sai')
        CourseQuestionChoice.objects.create(question=self.q2, choice_number=4, content='Đáp án D sai')

        self.client = Client()

    def test_routing_home_gateway(self):
        """Kiểm tra cổng phân luồng /courses/ theo vai trò người dùng"""
        # Chưa đăng nhập -> redirect /login/?next=/courses/
        res = self.client.get('/courses/')
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login/', res.url)

        # Đăng nhập Trainee -> redirect /courses/trainee/courses/
        self.client.force_login(self.trainee)
        res = self.client.get('/courses/')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, '/courses/trainee/courses/')

        # Đăng nhập Trainer -> redirect /courses/trainer/courses/
        self.client.force_login(self.trainer)
        res = self.client.get('/courses/')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, '/courses/trainer/courses/')

    def test_strict_rbac_protection(self):
        """Kiểm tra phân quyền 2 chiều chặt chẽ (Strict RBAC)"""
        # Trainee cố truy cập URL Trainer -> chuyển hướng về trainee_courses
        self.client.force_login(self.trainee)
        res = self.client.get('/courses/trainer/courses/')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, '/courses/trainee/courses/')

        res = self.client.get(f'/courses/trainer/courses/{self.course.id}/')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, '/courses/trainee/courses/')

        # Trainer cố truy cập URL Trainee -> chuyển hướng về trainer_courses
        self.client.force_login(self.trainer)
        res = self.client.get('/courses/trainee/courses/')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, '/courses/trainer/courses/')

    def test_material_view_updates_study_process(self):
        """Học viên mở bài học -> cập nhật study_process"""
        self.client.force_login(self.trainee)
        res = self.client.get(f'/courses/trainee/course/{self.course.id}/{self.mat1.id}/')
        self.assertEqual(res.status_code, 200)

        # Bài 1 / 2 bài -> tiến độ được cập nhật
        self.enrollment.refresh_from_db()
        self.assertGreater(self.enrollment.study_process, 0)

    def test_exam_lockout_logic(self):
        """Khóa phòng thi tuyệt đối khi học viên đã thi đạt"""
        self.client.force_login(self.trainee)

        # Khi chưa đạt -> vào phòng thi bình thường (HTTP 200)
        res = self.client.get(f'/courses/trainee/course/{self.course.id}/exam/')
        self.assertEqual(res.status_code, 200)

        # Cập nhật kết quả thi đạt
        self.enrollment.is_pass = True
        self.enrollment.is_completed = True
        self.enrollment.study_process = 100
        self.enrollment.save()

        # Khi đã đạt -> truy cập /exam/ PHẢI redirect 302 về /exam/result/
        res = self.client.get(f'/courses/trainee/course/{self.course.id}/exam/')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, f'/courses/trainee/course/{self.course.id}/exam/result/')

    def test_exam_submission_and_auto_grading(self):
        """Tự động chấm điểm trắc nghiệm và lưu chi tiết từng câu trả lời"""
        self.client.force_login(self.trainee)

        # Nộp bài: chọn đúng cả 2 câu (q1: choice 2, q2: choice 1)
        post_data = {
            'passcode': 'SCOTS2026',
            f'question_{self.q1.id}': '2',
            f'question_{self.q2.id}': '1',
        }
        res = self.client.post(f'/courses/trainee/course/{self.course.id}/exam/', post_data)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, f'/courses/trainee/course/{self.course.id}/exam/result/')

        # Kiểm tra kết quả ghi nhận
        response = CourseExamResponse.objects.filter(exam=self.exam, emp=self.trainee).latest('submission_date')
        self.assertEqual(response.score, 100.0)
        self.assertTrue(response.is_passed)

        # Kiểm tra chi tiết từng câu trả lời (CourseExamResponseDetail)
        details = CourseExamResponseDetail.objects.filter(response=response)
        self.assertEqual(details.count(), 2)
        for d in details:
            self.assertTrue(d.is_correct)

        # Kiểm tra enrollment được cập nhật
        self.enrollment.refresh_from_db()
        self.assertTrue(self.enrollment.is_pass)
        self.assertTrue(self.enrollment.is_completed)
        self.assertEqual(self.enrollment.study_process, 100)

    def test_trainer_create_course_3_step_wizard(self):
        """Luồng 3 bước khởi tạo khóa học mới của Trainer"""
        self.client.force_login(self.trainer)

        # Bước 1: Thông tin
        step1_data = {
            'title': 'Khóa học Wizard Test',
            'code': 'KH-WIZ01',
            'description': 'Mô tả khóa học',
            'date_start': str(date.today()),
            'date_end': str(date.today() + timedelta(days=60)),
            'status': 'ongoing',
        }
        res = self.client.post('/courses/trainer/courses/create/info/', step1_data)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, '/courses/trainer/courses/create/assign/')

        # Bước 2: Phân công
        res = self.client.post('/courses/trainer/courses/create/assign/', {'trainee_ids': [str(self.trainee.id)]})
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, '/courses/trainer/courses/create/review/')

        # Bước 3: Xuất bản
        res = self.client.post('/courses/trainer/courses/create/review/', {'action': 'publish'})
        self.assertEqual(res.status_code, 302)

        # Khóa học mới đã được lưu vào DB
        new_course = Course.objects.get(code='KH-WIZ01')
        self.assertEqual(new_course.title, 'Khóa học Wizard Test')
        self.assertEqual(new_course.creator, self.trainer)

        # Học viên đã được ghi danh
        self.assertTrue(CourseEnrollment.objects.filter(emp=self.trainee, course=new_course).exists())

    def test_trainer_publish_draft_course(self):
        """Khóa học bản nháp có thể xuất bản sang Đang triển khai"""
        draft_course = Course.objects.create(
            creator=self.trainer,
            code='KH-DRAFT01',
            title='Khóa học Nháp',
            date_start=date.today(),
            date_end=date.today() + timedelta(days=10),
            status='draft',
        )
        self.client.force_login(self.trainer)
        res = self.client.post(f'/courses/trainer/courses/{draft_course.id}/publish/')
        self.assertEqual(res.status_code, 302)
        draft_course.refresh_from_db()
        self.assertEqual(draft_course.status, 'ongoing')

    def test_trainer_edit_course_info(self):
        """Giảng viên có thể cập nhật thông tin khóa học trực tiếp"""
        self.client.force_login(self.trainer)
        res = self.client.post(f'/courses/trainer/courses/{self.course.id}/', {
            'action': 'update_info',
            'title': 'Tiêu đề Khóa học Đã Cập Nhật',
            'description': 'Mô tả mới',
            'status': 'ongoing',
            'date_start': str(date.today()),
            'date_end': str(date.today() + timedelta(days=45)),
        })
        self.assertEqual(res.status_code, 302)
        self.course.refresh_from_db()
        self.assertEqual(self.course.title, 'Tiêu đề Khóa học Đã Cập Nhật')
        self.assertEqual(self.course.description, 'Mô tả mới')

    def test_trainer_edit_material(self):
        """Giảng viên có thể chỉnh sửa trực tiếp nội dung bài giảng hiện có"""
        self.client.force_login(self.trainer)

        # 1. GET ?edit=<id> trả về 200 và có editing_material trong context
        res = self.client.get(f'/courses/trainer/courses/{self.course.id}/materials/?edit={self.mat1.id}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['editing_material'].id, self.mat1.id)

        # 2. POST cập nhật bài giảng
        res = self.client.post(f'/courses/trainer/courses/{self.course.id}/materials/', {
            'material_id': str(self.mat1.id),
            'name': 'Bài 1: Tên Đã Cập Nhật',
            'file_type': 'video',
            'duration_minutes': 45,
            'is_required': 'on',
            'content': 'Nội dung lý thuyết cập nhật mới',
            'scenario_title': 'Tình huống cập nhật',
            'scenario_content': 'Cách xử lý cập nhật',
        })
        self.assertEqual(res.status_code, 302)
        self.mat1.refresh_from_db()
        self.assertEqual(self.mat1.name, 'Bài 1: Tên Đã Cập Nhật')
        self.assertEqual(self.mat1.duration_minutes, 45)
        self.assertEqual(self.mat1.content, 'Nội dung lý thuyết cập nhật mới')

    def test_enterprise_session_security_settings(self):
        """Đảm bảo thiết lập đóng trình duyệt là kết thúc phiên đăng nhập (SESSION_EXPIRE_AT_BROWSER_CLOSE)"""
        from django.conf import settings
        self.assertTrue(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)

    def test_flexible_choices_two_to_five(self):
        """Kiểm tra thiết lập câu hỏi trắc nghiệm hỗ trợ linh hoạt 2 đến 5 đáp án"""
        self.client.force_login(self.trainer)
        
        # 1. Cấu hình câu hỏi 1 chỉ có 2 đáp án (A, B - dạng True/False)
        # và câu hỏi 2 có đủ 5 đáp án (A, B, C, D, E)
        post_data = {
            'title': 'Đề thi linh hoạt số lượng đáp án',
            'duration': '30',
            'passing_score': '80',
            'passcode': 'SCOTS2026',
            'is_active': 'on',
            'total_questions': '2',
            # Câu 1: 2 đáp án (A, B)
            'question_1_caption': 'Quy chuẩn tác nghiệp Scots có bắt buộc kiểm tra ID phụ huynh?',
            'question_1_correct': '1',
            'question_1_choice_1': 'Đúng, bắt buộc tuân thủ 100%',
            'question_1_choice_2': 'Sai, không cần thiết',
            # Câu 2: 5 đáp án (A, B, C, D, E)
            'question_2_caption': 'Các tiêu chuẩn chất lượng tại Scots English?',
            'question_2_correct': '5',
            'question_2_choice_1': 'Tiêu chuẩn A',
            'question_2_choice_2': 'Tiêu chuẩn B',
            'question_2_choice_3': 'Tiêu chuẩn C',
            'question_2_choice_4': 'Tiêu chuẩn D',
            'question_2_choice_5': 'Tất cả các tiêu chuẩn trên đều đúng',
        }

        res = self.client.post(f'/courses/trainer/courses/{self.course.id}/exam/setup/', post_data)
        self.assertEqual(res.status_code, 302)

        # Kiểm tra database:
        exam = CourseExam.objects.get(course=self.course)
        q1 = exam.questions.get(question_number=1)
        self.assertEqual(q1.choices.count(), 2) # Chỉ có 2 đáp án!
        self.assertEqual(q1.correct_choice, 1)

        q2 = exam.questions.get(question_number=2)
        self.assertEqual(q2.choices.count(), 5) # Có đủ 5 đáp án!
        self.assertEqual(q2.correct_choice, 5)

    def test_draft_course_hides_progress_dashboard(self):
        """Khóa học bản nháp không hiển thị tiến độ học viên và chặn truy cập dashboard tiến độ"""
        draft_course = Course.objects.create(
            creator=self.trainer,
            code='KH-DRAFT02',
            title='Khóa học Demo Bản nháp',
            date_start=date.today(),
            date_end=date.today() + timedelta(days=20),
            status='draft',
        )
        self.client.force_login(self.trainer)

        # 1. Truy cập trực tiếp dashboard tiến độ -> Tự động chuyển hướng về trang chi tiết khóa học
        res = self.client.get(f'/courses/trainer/courses/{draft_course.id}/dashboard/')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, f'/courses/trainer/courses/{draft_course.id}/')

        # 2. Trang chi tiết của khóa học bản nháp hiển thị 'Bản nháp nội bộ'
        res = self.client.get(f'/courses/trainer/courses/{draft_course.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Bản nháp')
        # Không có link tab Tiến độ học viên
        self.assertNotContains(res, f'/courses/trainer/courses/{draft_course.id}/dashboard/')

    def test_trainer_can_preview_lesson_and_exam(self):
        """Giảng viên có thể xem trước nội dung bài giảng và đề thi mà không bị redirect chặn"""
        self.client.force_login(self.trainer)

        # Xem trước bài giảng: không bị redirect chặn mà trả về 200
        res = self.client.get(f'/courses/trainee/course/{self.course.id}/{self.mat1.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context['is_preview'])

        # Xem trước đề thi: không bị redirect chặn mà trả về 200
        res = self.client.get(f'/courses/trainee/course/{self.course.id}/exam/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context['is_preview'])

    def test_trainer_delete_material(self):
        """Giảng viên có thể xóa bài giảng khỏi khóa học an toàn"""
        self.client.force_login(self.trainer)
        res = self.client.post(f'/courses/trainer/courses/{self.course.id}/materials/', {
            'action': 'delete',
            'material_id': str(self.mat2.id),
        })
        self.assertEqual(res.status_code, 302)
        self.assertFalse(CourseMaterial.objects.filter(id=self.mat2.id).exists())

    def test_exam_lock_policy_no_retake(self):
        """Học viên sau khi nộp bài (kể cả chưa đạt) thì phòng thi sẽ khóa vĩnh viễn, không được làm bài lại; xem lại bài làm và đối soát đáp án đúng/sai"""
        self.client.force_login(self.trainee)

        # 1. Nộp bài nhưng chọn sai cả 2 câu -> 0 điểm
        post_fail = {
            'passcode': 'SCOTS2026',
            f'question_{self.q1.id}': '1',  # sai (đúng là 2)
            f'question_{self.q2.id}': '2',  # sai (đúng là 1)
        }
        res = self.client.post(f'/courses/trainee/course/{self.course.id}/exam/', post_fail)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, f'/courses/trainee/course/{self.course.id}/exam/result/')

        # Kiểm tra kết quả trượt
        resp_fail = CourseExamResponse.objects.filter(exam=self.exam, emp=self.trainee).latest('submission_date')
        self.assertEqual(resp_fail.score, 0.0)
        self.assertFalse(resp_fail.is_passed)

        self.enrollment.refresh_from_db()
        self.assertFalse(self.enrollment.is_pass)
        self.assertFalse(self.enrollment.is_completed)

        # 2. Học viên truy cập lại phòng thi -> BỊ CHẶN (302 redirect về trang kết quả) vì không được thi lại
        res_get = self.client.get(f'/courses/trainee/course/{self.course.id}/exam/')
        self.assertEqual(res_get.status_code, 302)
        self.assertEqual(res_get.url, f'/courses/trainee/course/{self.course.id}/exam/result/')

        # 3. Học viên cố tình gửi POST nộp bài lại -> BỊ CHẶN (302 redirect về trang kết quả)
        post_attempt = {
            'passcode': 'SCOTS2026',
            f'question_{self.q1.id}': '2',
            f'question_{self.q2.id}': '1',
        }
        res_post = self.client.post(f'/courses/trainee/course/{self.course.id}/exam/', post_attempt)
        self.assertEqual(res_post.status_code, 302)
        self.assertEqual(res_post.url, f'/courses/trainee/course/{self.course.id}/exam/result/')

        # 4. Truy cập trang kết quả: kiểm tra không có chữ 'Thi lại', có đối soát chi tiết đáp án
        res_result = self.client.get(f'/courses/trainee/course/{self.course.id}/exam/result/')
        self.assertEqual(res_result.status_code, 200)
        content_str = res_result.content.decode('utf-8')
        self.assertNotIn('Thi lại →', content_str)
        self.assertNotIn('Vui lòng ôn lại bài giảng và thi lại', content_str)
        self.assertIn('Chi tiết bài làm', content_str)
        self.assertIn('Bạn đã chọn', content_str)
        self.assertIn('Đáp án đúng', content_str)

    def test_exam_empty_submission(self):
        """Nộp bài trắng không chọn đáp án nào -> 0.0 điểm, không gây lỗi máy chủ"""
        self.client.force_login(self.trainee)
        res = self.client.post(f'/courses/trainee/course/{self.course.id}/exam/', {
            'passcode': 'SCOTS2026',
        })
        self.assertEqual(res.status_code, 302)
        latest_resp = CourseExamResponse.objects.filter(exam=self.exam, emp=self.trainee).latest('submission_date')
        self.assertEqual(latest_resp.score, 0.0)
        self.assertFalse(latest_resp.is_passed)

    def test_trainer_preview_exam_submission_not_saved(self):
        """Giảng viên nộp thử bài thi trong chế độ xem trước được tính điểm mẫu và chuyển hướng đến trang kết quả (?preview=1)"""
        self.client.force_login(self.trainer)

        res = self.client.post(f'/courses/trainee/course/{self.course.id}/exam/', {
            'passcode': 'SCOTS2026',
            f'question_{self.q1.id}': '2',
        })
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, f'/courses/trainee/course/{self.course.id}/exam/result/?preview=1')
        trainer_resp = CourseExamResponse.objects.filter(exam=self.exam, emp=self.trainer).first()
        self.assertIsNotNone(trainer_resp)
        # Điểm của Trainer được tính mẫu và không làm ảnh hưởng tới enrollment của học viên
        self.assertFalse(CourseEnrollment.objects.filter(emp=self.trainer, course=self.course).exists())

    def test_choice_model_str_label_e(self):
        """Kiểm tra CourseQuestionChoice.__str__ hiển thị chuẩn nhãn (E)"""
        c5 = CourseQuestionChoice.objects.create(question=self.q1, choice_number=5, content='Phương án E nâng cao')
        self.assertIn('(E)', str(c5))

    def test_draft_course_in_trainer_courses_dashboard(self):
        """Bảng thống kê tổng quan không có liên kết Báo cáo đối với khóa học bản nháp"""
        draft_course = Course.objects.create(
            creator=self.trainer,
            code='KH-DRAFT-DASH',
            title='Khóa học Nháp Dashboard Test',
            date_start=date.today(),
            date_end=date.today() + timedelta(days=15),
            status='draft',
        )
        self.client.force_login(self.trainer)
        res = self.client.get('/courses/trainer/courses/dashboard/')
        self.assertEqual(res.status_code, 200)
        # Khóa ongoing có link báo cáo
        self.assertContains(res, f'/courses/trainer/courses/{self.course.id}/dashboard/')
        # Khóa draft KHÔNG có link báo cáo
        self.assertNotContains(res, f'/courses/trainer/courses/{draft_course.id}/dashboard/')

    def test_clean_routing_standard(self):
        """Đảm bảo các URL chuẩn mực RESTful/Clean URL hoạt động chính xác theo chuẩn Django"""
        self.client.force_login(self.trainer)
        res = self.client.get('/courses/trainer/courses/')
        self.assertEqual(res.status_code, 200)

        res = self.client.get(f'/courses/trainer/courses/{self.course.id}/')
        self.assertEqual(res.status_code, 200)

        self.client.force_login(self.trainee)
        res = self.client.get('/courses/trainee/courses/')
        self.assertEqual(res.status_code, 200)

    def test_draft_course_isolation_for_trainee(self):
        """Khóa học bản nháp hoàn toàn cách ly khỏi học viên (không thấy trong danh sách và không truy cập được)"""
        draft_c = Course.objects.create(
            creator=self.trainer,
            code='KH-DRAFT-ISO',
            title='Khóa học Tuyệt mật Bản nháp',
            date_start=date.today(),
            date_end=date.today() + timedelta(days=20),
            status='draft',
        )
        CourseEnrollment.objects.create(emp=self.trainee, course=draft_c, study_process=0)
        draft_mat = CourseMaterial.objects.create(course=draft_c, name='Tài liệu nháp', file_type='pdf', order=1)
        draft_exam = CourseExam.objects.create(course=draft_c, title='Bài thi nháp', passcode='DRAFT123')

        self.client.force_login(self.trainee)

        # 1. Danh sách khóa học của học viên không hiển thị khóa học bản nháp
        res = self.client.get('/courses/trainee/courses/')
        self.assertEqual(res.status_code, 200)
        self.assertNotContains(res, 'KH-DRAFT-ISO')
        self.assertNotContains(res, 'Khóa học Tuyệt mật Bản nháp')

        # 2. Học viên cố truy cập chi tiết khóa học nháp -> Bị redirect về danh sách
        res = self.client.get(f'/courses/trainee/courses/{draft_c.id}/')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, '/courses/trainee/courses/')

        # 3. Học viên cố truy cập bài giảng của khóa học nháp -> Bị redirect về danh sách
        res = self.client.get(f'/courses/trainee/course/{draft_c.id}/{draft_mat.id}/')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, '/courses/trainee/courses/')

        # 4. Học viên cố truy cập phòng thi của khóa học nháp -> Bị redirect về danh sách
        res = self.client.get(f'/courses/trainee/course/{draft_c.id}/exam/')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, '/courses/trainee/courses/')

        # 5. Giảng viên xem trước khóa học nháp qua preview=1 -> Thành công HTTP 200
        self.client.force_login(self.trainer)
        res = self.client.get(f'/courses/trainee/courses/{draft_c.id}/?preview=1')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context['is_preview'])

    def test_exam_passcode_validation_security(self):
        """Bảo mật phòng thi: Sai Passcode sẽ bị từ chối truy cập và nộp bài"""
        self.client.force_login(self.trainee)

        # 1. Nhập sai passcode trên GET query param -> Bị chuyển về trang chi tiết khóa học
        res = self.client.get(f'/courses/trainee/course/{self.course.id}/exam/?passcode=WRONGCODE')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, f'/courses/trainee/courses/{self.course.id}/')

        # 2. Gửi POST với passcode sai -> Bị từ chối và không ghi nhận điểm
        init_count = CourseExamResponse.objects.filter(exam=self.exam).count()
        post_wrong = {
            'passcode': 'WRONGPASS',
            f'question_{self.q1.id}': '2',
            f'question_{self.q2.id}': '1',
        }
        res = self.client.post(f'/courses/trainee/course/{self.course.id}/exam/', post_wrong)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, f'/courses/trainee/courses/{self.course.id}/')
        self.assertEqual(CourseExamResponse.objects.filter(exam=self.exam).count(), init_count)

        # 3. Gửi POST với passcode đúng -> Thành công
        post_correct = {
            'passcode': 'SCOTS2026',
            f'question_{self.q1.id}': '2',
            f'question_{self.q2.id}': '1',
        }
        res = self.client.post(f'/courses/trainee/course/{self.course.id}/exam/', post_correct)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, f'/courses/trainee/course/{self.course.id}/exam/result/')
        self.assertEqual(CourseExamResponse.objects.filter(exam=self.exam).count(), init_count + 1)

    def test_trainer_preview_trainee_course_detail(self):
        """Giảng viên có thể xem trước trang tổng quan học viên qua ?preview=1"""
        self.client.force_login(self.trainer)

        # Không có ?preview=1 -> redirect sang trainer_course_detail
        res = self.client.get(f'/courses/trainee/courses/{self.course.id}/')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, f'/courses/trainer/courses/{self.course.id}/')

        # Có ?preview=1 -> Trả về 200 và có cờ is_preview=True
        res = self.client.get(f'/courses/trainee/courses/{self.course.id}/?preview=1')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context['is_preview'])

    def test_trainer_update_course_date_validation(self):
        """Giảng viên cập nhật thông tin: Ngày kết thúc phải sau ngày bắt đầu"""
        self.client.force_login(self.trainer)
        orig_start = self.course.date_start
        orig_end = self.course.date_end

        # Gửi ngày kết thúc trước ngày bắt đầu -> Không áp dụng thay đổi ngày sai
        res = self.client.post(f'/courses/trainer/courses/{self.course.id}/', {
            'action': 'update_info',
            'title': self.course.title,
            'description': self.course.description,
            'status': self.course.status,
            'date_start': str(date.today() + timedelta(days=10)),
            'date_end': str(date.today()),
        })
        self.assertEqual(res.status_code, 302)
        self.course.refresh_from_db()
        self.assertEqual(self.course.date_start, orig_start)
        self.assertEqual(self.course.date_end, orig_end)

    def test_chapter4_forms_validation(self):
        """Kiểm tra các ModelForm và Form chuẩn Chương 04 (Làm việc với Form)"""
        from courses.forms import CourseForm, CourseMaterialForm, CourseExamConfigForm, UserRegisterForm

        # 1. CourseForm: date_end < date_start gây lỗi validation
        invalid_course_form = CourseForm(data={
            'code': 'KH-TEST-CH4',
            'title': 'Test Course Ch4',
            'description': 'Description',
            'date_start': str(date.today() + timedelta(days=5)),
            'date_end': str(date.today()),
            'status': 'draft',
        })
        self.assertFalse(invalid_course_form.is_valid())
        self.assertIn('date_end', invalid_course_form.errors)

        # 2. CourseMaterialForm: duration_minutes <= 0
        invalid_material_form = CourseMaterialForm(data={
            'name': 'Bài giảng Ch4',
            'file_type': 'pdf',
            'duration_minutes': -5,
        })
        self.assertFalse(invalid_material_form.is_valid())
        self.assertIn('duration_minutes', invalid_material_form.errors)

        # 3. CourseExamConfigForm: passcode rỗng
        invalid_exam_form = CourseExamConfigForm(data={
            'title': 'Exam Ch4',
            'passcode': '',
            'duration': 45,
            'passing_score': 80,
        })
        self.assertFalse(invalid_exam_form.is_valid())
        self.assertIn('passcode', invalid_exam_form.errors)

        # 4. UserRegisterForm: password < 6 ký tự
        invalid_reg_form = UserRegisterForm(data={
            'fullname': 'Nguyen Van A',
            'username': 'nguyenvana_ch4',
            'email': 'a@scots.edu.vn',
            'password': '123',
            'password_confirm': '123',
        })
        self.assertFalse(invalid_reg_form.is_valid())
        self.assertIn('password', invalid_reg_form.errors)

    def test_chapter5_rest_api_endpoints(self):
        """Kiểm tra các REST API Endpoints chuẩn Chương 05 (DRF)"""
        # 1. API danh sách khóa học
        res = self.client.get('/courses/api/courses/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('courses', data)
        self.assertGreaterEqual(data['total'], 1)

        # 2. API chi tiết khóa học
        res = self.client.get(f'/courses/api/courses/{self.course.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['code'], self.course.code)

        # 3. API học liệu của khóa học
        res = self.client.get(f'/courses/api/courses/{self.course.id}/materials/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('materials', res.json())

    def test_chapter7_session_tracking_viewed_courses(self):
        """Kiểm tra tính năng lưu trữ lịch sử khóa học vừa xem vào session (Chương 07 - Lab VI)"""
        self.client.force_login(self.trainee)
        # Truy cập chi tiết khóa học đang triển khai
        res = self.client.get(f'/courses/trainee/courses/{self.course.id}/')
        self.assertEqual(res.status_code, 200)

        # Kiểm tra session
        session = self.client.session
        self.assertIn('viewed_courses', session)
        viewed_ids = [item['id'] for item in session['viewed_courses']]
        self.assertIn(self.course.id, viewed_ids)

    def test_material_file_type_isolation_and_upload_validation(self):
        """Kiểm tra phân định rạch ròi các định dạng tài liệu (doc, pdf, video, slide) và ràng buộc upload tệp"""
        from courses.forms import CourseMaterialForm
        from django.core.files.uploadedfile import SimpleUploadedFile

        # 1. Kiểm tra tải lên tệp mp4 nhưng lại chọn loại pdf -> Bị từ chối
        mismatched_file = SimpleUploadedFile("video_lecture.mp4", b"fake mp4 video content", content_type="video/mp4")
        form_invalid = CourseMaterialForm(
            data={
                'name': 'Bài học kiểm thử định dạng',
                'file_type': 'pdf',
                'duration_minutes': 30,
            },
            files={'file': mismatched_file}
        )
        self.assertFalse(form_invalid.is_valid())
        self.assertIn('file', form_invalid.errors)

        # 2. Kiểm tra tải lên tệp docx khi chọn loại doc -> Hợp lệ
        valid_doc_file = SimpleUploadedFile("huong_dan_tac_nghiep.docx", b"fake docx content", content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        form_valid_doc = CourseMaterialForm(
            data={
                'name': 'Hướng dẫn tác nghiệp Word',
                'file_type': 'doc',
                'duration_minutes': 25,
            },
            files={'file': valid_doc_file}
        )
        self.assertTrue(form_valid_doc.is_valid(), f"Errors: {form_valid_doc.errors}")

        # 3. Kiểm tra tải lên tệp pdf khi chọn loại pdf -> Hợp lệ
        valid_pdf_file = SimpleUploadedFile("quy_trinh.pdf", b"%PDF-1.4 fake pdf content", content_type="application/pdf")
        form_valid_pdf = CourseMaterialForm(
            data={
                'name': 'Quy trình hoạt động PDF',
                'file_type': 'pdf',
                'duration_minutes': 20,
            },
            files={'file': valid_pdf_file}
        )
        self.assertTrue(form_valid_pdf.is_valid(), f"Errors: {form_valid_pdf.errors}")

        # 4. Kiểm tra giao diện quản lý học liệu có modal popup thêm mới và ô nhập nội dung bài học thuần túy
        self.client.force_login(self.trainer)
        res = self.client.get(f'/courses/trainer/courses/{self.course.id}/materials/')
        self.assertEqual(res.status_code, 200)
        content_str = res.content.decode('utf-8')
        self.assertIn('addMaterialModal', content_str)
        self.assertIn('name="content"', content_str)
        self.assertIn('Văn bản Word (DOC/DOCX)', content_str)
        self.assertIn('Tài liệu PDF (PDF)', content_str)

    def test_trainer_course_assign_and_mandatory_elective_logic(self):
        """
        Kiểm tra phân công học viên của Trainer (Bắt buộc, is_assigned=True)
        và quyền tự đăng ký của Trainee (Tự chọn, is_assigned=False)
        """
        # 1. Trainee không được phép truy cập trang phân công học viên
        self.client.force_login(self.trainee)
        res_trainee = self.client.get(f'/courses/trainer/courses/{self.course.id}/assign/')
        self.assertEqual(res_trainee.status_code, 302)

        # 2. Trainer truy cập trang phân công học viên
        self.client.force_login(self.trainer)
        res_assign = self.client.get(f'/courses/trainer/courses/{self.course.id}/assign/')
        self.assertEqual(res_assign.status_code, 200)
        content = res_assign.content.decode('utf-8')
        self.assertIn('Phân công & Ghi danh học viên', content)
        self.assertIn('trainee_ids', content)
        # Đã thay thế 3 nút bằng ô checkbox chọn tất cả theo bộ lọc
        self.assertIn('selectAllVisibleCheckbox', content)
        self.assertIn('Chọn tất cả theo bộ lọc', content)
        self.assertNotIn('Chọn phòng ban này', content)

        # 3. Trainer phân công học viên vào khóa học -> Bắt buộc (is_assigned=True)
        post_res = self.client.post(
            f'/courses/trainer/courses/{self.course.id}/assign/',
            data={'action': 'save_assign', 'trainee_ids': [self.trainee.id]}
        )
        self.assertRedirects(post_res, f'/courses/trainer/courses/{self.course.id}/')
        
        enr = CourseEnrollment.objects.get(course=self.course, emp=self.trainee)
        self.assertTrue(enr.is_assigned, "Học viên được Trainer phân công phải là Bắt buộc (is_assigned=True)")

        # 4. Kiểm tra hiển thị trong giao diện của học viên có badge 'Bắt buộc'
        self.client.force_login(self.trainee)
        res_trainee_list = self.client.get('/courses/trainee/courses/')
        self.assertEqual(res_trainee_list.status_code, 200)
        self.assertIn('Bắt buộc', res_trainee_list.content.decode('utf-8'))

        # 5. Kiểm tra Trainer hủy ghi danh học viên
        self.client.force_login(self.trainer)
        del_res = self.client.post(
            f'/courses/trainer/courses/{self.course.id}/assign/',
            data={'action': 'remove_trainee', 'emp_id': self.trainee.id}
        )
        self.assertRedirects(del_res, f'/courses/trainer/courses/{self.course.id}/assign/')
        self.assertFalse(CourseEnrollment.objects.filter(course=self.course, emp=self.trainee).exists())

        # 6. Học viên tự đăng ký khóa học tự chọn -> is_assigned=False
        self.client.force_login(self.trainee)
        self_res = self.client.post(f'/courses/trainee/courses/{self.course.id}/self-enroll/')
        self.assertRedirects(self_res, f'/courses/trainee/courses/{self.course.id}/')
        
        enr_elective = CourseEnrollment.objects.get(course=self.course, emp=self.trainee)
        self.assertFalse(enr_elective.is_assigned, "Học viên tự đăng ký phải là Tự chọn (is_assigned=False)")

        # Kiểm tra hiển thị trong giao diện học viên có badge 'Tự chọn'
        res_trainee_list2 = self.client.get('/courses/trainee/courses/')
        self.assertIn('Tự chọn', res_trainee_list2.content.decode('utf-8'))

    def test_trainer_preview_exam_and_dashboard_analytics(self):
        """
        Kiểm tra:
        1. Giảng viên (Trainer) thi thử nghiệm bài thi và được tính điểm, lưu kết quả.
        2. Màn hình kết quả bài thi của Trainer (?preview=1) hiển thị banner Trainer và link về Dashboard.
        3. Dashboard của Trainer hiển thị đầy đủ: Điểm số của Trainer, 4 thẻ KPI,
           Phân tích chi tiết câu hỏi (Item Analysis - điểm học viên hay sai nhất),
           và nút xem bài làm chi tiết từng học viên.
        """
        # 1. Trainee nộp bài thi (chọn đúng Q1, sai Q2)
        resp_trainee = CourseExamResponse.objects.create(
            emp=self.trainee,
            exam=self.exam,
            passcode='SCOTS2026',
            duration=15,
            score=50.0,
            is_passed=False
        )
        CourseExamResponseDetail.objects.create(
            response=resp_trainee, question=self.q1, answer=2, is_correct=True
        )
        CourseExamResponseDetail.objects.create(
            response=resp_trainee, question=self.q2, answer=2, is_correct=False
        )

        # 2. Trainer làm bài thi thử nghiệm với ?preview=1 (chọn đúng cả 2 câu: Q1=2, Q2=1)
        self.client.force_login(self.trainer)
        exam_submit_res = self.client.post(
            f'/courses/trainee/course/{self.course.id}/exam/?preview=1',
            data={
                'passcode': 'SCOTS2026',
                f'question_{self.q1.id}': '2',
                f'question_{self.q2.id}': '1',
            }
        )
        self.assertRedirects(exam_submit_res, f'/courses/trainee/course/{self.course.id}/exam/result/?preview=1')

        # 3. Kiểm tra màn hình kết quả bài thi của Trainer (?preview=1)
        result_res = self.client.get(f'/courses/trainee/course/{self.course.id}/exam/result/?preview=1')
        self.assertEqual(result_res.status_code, 200)
        result_content = result_res.content.decode('utf-8')
        self.assertIn('Chế độ xem trước của Giảng viên (Trainer)', result_content)
        self.assertIn('100.0', result_content)
        self.assertIn('Thi thử nghiệm lại (Trainer)', result_content)
        self.assertIn('/courses/trainer/courses/', result_content)

        # 4. Kiểm tra Trainer Dashboard: Báo cáo học viên & Cột số câu đúng
        dash_res = self.client.get(f'/courses/trainer/courses/{self.course.id}/dashboard/')
        self.assertEqual(dash_res.status_code, 200)
        dash_content = dash_res.content.decode('utf-8')

        # 4 thẻ KPI
        self.assertIn('Tổng số học viên', dash_content)
        self.assertIn('Đã nộp bài kiểm tra', dash_content)
        self.assertIn('Điểm trung bình học viên', dash_content)
        self.assertIn('Tỷ lệ đạt chuẩn nghiệp vụ', dash_content)

        # Cột số câu đúng và bảng học viên
        self.assertIn('Số câu đúng', dash_content)
        self.assertIn('Xem bài làm', dash_content)
        self.assertIn(f'modal_{self.trainee.id}', dash_content)

        # Các phần thi thử nghiệm của trainer và item analysis đã được giản lược theo yêu cầu
        self.assertNotIn('KẾT QUẢ BÀI KIỂM TRA THỬ NGHIỆM CỦA GIẢNG VIÊN', dash_content)
        self.assertNotIn('Phân tích chi tiết câu hỏi & Điểm học viên hay sai', dash_content)

    def test_trainer_courses_dashboard_reactive_filters(self):
        """
        Kiểm tra Dashboard tổng quan (/courses/trainer/courses/dashboard/):
        - Chứa cấu trúc JSON toàn bộ khóa học và phân bổ phòng ban phục vụ lọc tương tác thời gian thực.
        - Chứa các thẻ KPI có ID đồng bộ động (kpiOngoingCount, kpiEnrollmentCount, kpiOverallProgress, kpiTotalCourses).
        - Chứa hàm lọc filterDashboard() và nút đặt lại bộ lọc resetDashboardFilters().
        """
        self.client.force_login(self.trainer)
        res = self.client.get('/courses/trainer/courses/dashboard/')
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        self.assertIn('allCoursesData', content)
        self.assertIn('kpiOngoingCount', content)
        self.assertIn('kpiEnrollmentCount', content)
        self.assertIn('kpiOverallProgress', content)
        self.assertIn('kpiTotalCourses', content)
        self.assertIn('filterDashboard()', content)
        self.assertIn('resetDashboardFilters()', content)
        self.assertIn('dashStatusFilter', content)
        self.assertIn('dashTrainerFilter', content)
        self.assertIn('dashDeptFilter', content)
        self.assertIn('dashSearchInput', content)

