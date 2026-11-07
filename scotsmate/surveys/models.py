from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

from home.models import *


class Survey(models.Model):
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='surveys',
        verbose_name="Phòng ban"
    )
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_surveys',
        verbose_name="Người tạo"
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='approved_surveys',
        verbose_name="Người duyệt"
    )
    name=models.CharField(max_length=100,verbose_name='Tên khảo sát')
    date_created = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")
    is_approved = models.BooleanField(default=False, verbose_name="Đã duyệt")
    is_respondable = models.BooleanField(default=True, verbose_name="Cho phép trả lời")
    is_visible = models.BooleanField(default=True, verbose_name="Hiển thị")
    description = models.TextField(blank=True, null=True, verbose_name="Mô tả")
    response_limit = models.IntegerField(null=True, verbose_name="Giới hạn lượt trả lời")

    class Meta:
        db_table = 'survey'

    def __str__(self) -> str:
        return self.name


class SurveyAccess(models.Model):
    emp = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='survey_accesses',
        verbose_name="Nhân viên"
    )
    survey = models.ForeignKey(
        Survey,
        on_delete=models.CASCADE,
        related_name='access_permissions',
        verbose_name="Khảo sát"
    )
    can_view_responses = models.BooleanField(default=False, verbose_name="Quyền xem kết quả")
    can_respond = models.BooleanField(default=True, verbose_name="Quyền tham gia trả lời")

    class Meta:
        db_table = 'survey_access'
        constraints = [
            models.UniqueConstraint(fields=['emp', 'survey'], name='unique_emp_survey_access')
        ]

    def __str__(self) -> str:
        if self.can_view_responses == False and self.can_respond == False:
            return f"User {self.emp.username} can not access to survey {self.survey.name}"
        elif self.can_view_responses == True and self.can_respond == False:
            return f"User {self.emp.username} can view responses of survey {self.survey_id}"
        elif self.can_view_responses == False and self.can_respond == True:
            return f"User {self.emp.username} can response survey {self.survey_id}"
        else:
            return f"User {self.emp.username} can response and view responses of survey {self.survey_id}"


class SurveyEssayQuestion(models.Model):
    max_character = models.IntegerField(verbose_name="Số ký tự tối đa")

    class Meta:
        db_table = 'survey_essay_question'

    def __str__(self) -> str:
        return f"Essay Question #{self.pk} (Max length: {self.max_character})"


class SurveyMultipleChoiceQuestion(models.Model):
    max_choice = models.IntegerField(default=1, verbose_name="Số phương án được chọn tối đa")

    class Meta:
        db_table = 'survey_multiple_choice_question'

    def __str__(self) -> str:
        return f"Multiple Choice Question #{self.pk} (Max choice: {self.max_choice})"


class SurveyQuestionChoice(models.Model):
    question = models.ForeignKey(
        SurveyMultipleChoiceQuestion,
        on_delete=models.CASCADE,
        related_name='choices',
        verbose_name="Câu hỏi trắc nghiệm"
    )
    content = models.TextField(verbose_name="Nội dung lựa chọn")

    class Meta:
        db_table = 'survey_question_choice'

    def __str__(self) -> str:
        return self.content


class SurveyDetail(models.Model):
    # Chi tiết từng câu hỏi trong bài khảo sát (survey_detail).
    # Sử dụng GenericForeignKey liên kết tới django_content_type.
    survey = models.ForeignKey(
        Survey,
        on_delete=models.CASCADE,
        related_name='details',
        verbose_name="Khảo sát"
    )
    question_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name="Loại câu hỏi (ContentType)"
    )
    object_id = models.IntegerField(verbose_name="ID câu hỏi cụ thể")
    question_object = GenericForeignKey('question_type', 'object_id')
    caption = models.TextField(verbose_name="Tiêu đề câu hỏi")
    is_required = models.BooleanField(default=True, verbose_name="Bắt buộc trả lời")

    class Meta:
        db_table = 'survey_detail'

    def __str__(self) -> str:
        return f"Question #{self.pk} in Survey #{self.survey_id}: {self.caption[:30]}"


class SurveyResponse(models.Model):
    survey = models.ForeignKey(
        Survey,
        on_delete=models.CASCADE,
        related_name='responses',
        verbose_name="Khảo sát"
    )
    respondant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='survey_responses',
        verbose_name="Người thực hiện khảo sát"
    )
    submission_date = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian nộp")

    class Meta:
        db_table = 'survey_response'

    def __str__(self) -> str:
        return f"Response #{self.pk} - {self.survey.name} by {self.respondant.username}"


class SurveyResponseDetail(models.Model):
    survey_response = models.ForeignKey(
        SurveyResponse,
        on_delete=models.CASCADE,
        related_name='details',
        verbose_name="Lượt phản hồi"
    )
    question = models.ForeignKey(
        SurveyDetail,
        on_delete=models.CASCADE,
        related_name='response_details',
        verbose_name="Câu hỏi"
    )
    answer = models.TextField(verbose_name="Câu trả lời")

    class Meta:
        db_table = 'survey_response_detail'
        constraints = [
            models.UniqueConstraint(fields=['survey_response', 'question'], name='unique_response_question')
        ]

    def __str__(self) -> str:
        return f"Answer for Question #{self.question_id} in Response #{self.survey_response_id}"