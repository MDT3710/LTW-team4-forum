import json
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from home.models import Branch, Department, EmployeeInformation
from home.roles import ROLE_EMPLOYEE, ROLE_MANAGER, ensure_role_groups
from .models import (
    Survey,
    SurveyDetail,
    SurveyEssayQuestion,
    SurveyMultipleChoiceQuestion,
    SurveyQuestionChoice,
    SurveyResponse,
    SurveyResponseDetail,
)


class SurveyDynamicContentTypeAndFlowTests(TestCase):
    def setUp(self):
        self.groups = ensure_role_groups()
        self.branch = Branch.objects.create(name='Chi nhánh Test', region='NORTH', address='Hà Nội')
        self.dept = Department.objects.create(name='Phòng Test', block=Department.BlockChoices.OPERATION)

        self.manager = User.objects.create_user(
            username='mgr_survey',
            password='Password123!',
            email='',  # Kiểm tra fallback email khi user.email rỗng
            first_name='Minh',
            last_name='Trần',
            is_staff=True,
        )
        self.manager.groups.add(self.groups[ROLE_MANAGER], self.groups[ROLE_EMPLOYEE])
        self.dept.manager = self.manager
        self.dept.save()
        EmployeeInformation.objects.create(
            emp_id=self.manager,
            gender='MALE',
            NIN='001090000101',
            tel='0901000101',
            dep=self.dept,
            branch=self.branch,
            date_of_birth='1990-05-05',
        )

        self.employee = User.objects.create_user(
            username='emp_survey',
            password='Password123!',
            email='',  # Kiểm tra fallback email khi user.email rỗng (không AttributeError employee_info.email)
            first_name='Lan',
            last_name='Phạm',
            is_staff=True,
        )
        self.employee.groups.add(self.groups[ROLE_EMPLOYEE])
        EmployeeInformation.objects.create(
            emp_id=self.employee,
            gender='FEMALE',
            NIN='001095000102',
            tel='0901000102',
            dep=self.dept,
            branch=self.branch,
            date_of_birth='1995-06-06',
        )

        self.mc_ct = ContentType.objects.get_for_model(SurveyMultipleChoiceQuestion)
        self.essay_ct = ContentType.objects.get_for_model(SurveyEssayQuestion)

    def test_survey_create_renders_dynamic_content_type_ids(self):
        self.client.force_login(self.employee)
        res = self.client.get(reverse('SurveyCreate'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, f'data-mc-type-id="{self.mc_ct.id}"')
        self.assertContains(res, f'data-essay-type-id="{self.essay_ct.id}"')

    def test_survey_full_lifecycle_create_approve_take_report_export(self):
        # 1. Nhân viên tạo khảo sát gồm 1 câu trắc nghiệm (dùng dynamic ct id) + 1 câu tự luận (dùng fallback 'essay')
        self.client.force_login(self.employee)
        questions_payload = [
            {
                'id': 1,
                'caption': 'Bạn đánh giá môi trường làm việc thế nào?',
                'question_type_id': self.mc_ct.id,
                'is_required': True,
                'max_choice': 1,
                'choices': ['Rất tốt', 'Bình thường'],
            },
            {
                'id': 2,
                'caption': 'Đề xuất cải thiện thêm',
                'question_type_id': 'essay',
                'is_required': False,
                'max_character': 200,
            },
        ]
        res_create = self.client.post(reverse('SurveyCreate'), {
            'name': 'Khảo sát nội bộ Q4',
            'description': 'Mô tả khảo sát',
            'branches': [self.branch.id],
            'departments': [self.dept.id],
            'questions_data': json.dumps(questions_payload),
        })
        self.assertEqual(res_create.status_code, 302)
        self.assertEqual(res_create.url, reverse('MySurvey'))

        survey = Survey.objects.get(name='Khảo sát nội bộ Q4')
        self.assertFalse(survey.is_approved)
        details = list(SurveyDetail.objects.filter(survey=survey).order_by('id'))
        self.assertEqual(len(details), 2)
        self.assertEqual(details[0].question_type_id, self.mc_ct.id)
        self.assertEqual(details[1].question_type_id, self.essay_ct.id)

        mc_detail, essay_detail = details[0], details[1]
        choices = list(SurveyQuestionChoice.objects.filter(question_id=mc_detail.object_id).order_by('id'))
        self.assertEqual([c.content for c in choices], ['Rất tốt', 'Bình thường'])

        # 2. Trưởng phòng xem chi tiết thẩm định (email rỗng không lỗi) & phê duyệt
        self.client.force_login(self.manager)
        res_app_get = self.client.get(reverse('SurveyApproveDetail', args=[survey.id]))
        self.assertEqual(res_app_get.status_code, 200)
        self.assertContains(res_app_get, 'Rất tốt')
        self.assertContains(res_app_get, 'Đề xuất cải thiện thêm')
        self.assertContains(res_app_get, 'emp_survey@scotsenglish.edu.vn')

        res_app_post = self.client.post(reverse('SurveyApproveDetail', args=[survey.id]), {'action': 'approve'})
        self.assertEqual(res_app_post.status_code, 302)
        survey.refresh_from_db()
        self.assertTrue(survey.is_approved)

        # 3. Nhân viên làm bài khảo sát (GET + validation lỗi thiếu câu bắt buộc + POST submit)
        self.client.force_login(self.employee)
        res_take_get = self.client.get(reverse('SurveyTake', args=[survey.id]))
        self.assertEqual(res_take_get.status_code, 200)
        self.assertContains(res_take_get, 'Rất tốt')
        self.assertContains(res_take_get, 'Đề xuất cải thiện thêm')

        # Thiếu câu trắc nghiệm bắt buộc -> trả lại form với lỗi
        res_take_invalid = self.client.post(reverse('SurveyTake', args=[survey.id]), {
            'action': 'submit',
            f'question_{essay_detail.id}': 'Cần thêm cây xanh',
        })
        self.assertEqual(res_take_invalid.status_code, 200)
        self.assertContains(res_take_invalid, 'Vui lòng chọn câu trả lời cho câu hỏi bắt buộc này.')

        # Nộp hợp lệ
        res_take_ok = self.client.post(reverse('SurveyTake', args=[survey.id]), {
            'action': 'submit',
            f'question_{mc_detail.id}': str(choices[0].id),
            f'question_{essay_detail.id}': 'Cần thêm cây xanh',
        })
        self.assertEqual(res_take_ok.status_code, 302)
        self.assertEqual(res_take_ok.url, reverse('SurveyHistory'))

        resp = SurveyResponse.objects.get(survey=survey, respondent=self.employee)
        self.assertIsNotNone(resp.submission_date)
        self.assertEqual(SurveyResponseDetail.objects.filter(survey_response=resp).count(), 2)

        # 4. Trưởng phòng xem Published, Overview, Detail (email rỗng không lỗi), Export Excel
        self.client.force_login(self.manager)
        res_pub = self.client.get(reverse('SurveyPublished'))
        self.assertEqual(res_pub.status_code, 200)
        self.assertContains(res_pub, 'emp_survey@scotsenglish.edu.vn')

        res_ov = self.client.get(reverse('ResponseOverview', args=[survey.id]))
        self.assertEqual(res_ov.status_code, 200)
        self.assertContains(res_ov, 'Rất tốt')
        self.assertContains(res_ov, 'Cần thêm cây xanh')

        res_det = self.client.get(reverse('ResponseDetail', args=[survey.id]))
        self.assertEqual(res_det.status_code, 200)
        self.assertContains(res_det, 'emp_survey@scotsenglish.edu.vn')

        res_xlsx = self.client.get(reverse('SurveyExportExcel', args=[survey.id]))
        self.assertEqual(res_xlsx.status_code, 200)
        self.assertEqual(
            res_xlsx['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertGreater(len(res_xlsx.content), 500)

    def test_survey_create_invalid_form_shows_errors_and_preserves_questions(self):
        import html
        self.client.force_login(self.employee)
        payload = json.dumps([
            {
                'id': 1,
                'caption': 'Câu hỏi được giữ lại',
                'question_type_id': self.mc_ct.id,
                'is_required': True,
                'max_choice': 1,
                'choices': ['A', 'B'],
            }
        ], ensure_ascii=False)
        res = self.client.post(reverse('SurveyCreate'), {
            'name': 'Khảo sát lỗi giới hạn',
            'response_limit': 0,
            'questions_data': payload,
        })
        self.assertEqual(res.status_code, 200)
        body = html.unescape(res.content.decode('utf-8'))
        self.assertIn('Giới hạn lượt trả lời phải lớn hơn 0.', body)
        self.assertIn('Câu hỏi được giữ lại', body)
