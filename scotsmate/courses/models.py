from django.db import models
from django.conf import settings

# ============================================================
# 1. BẢNG KHÓA HỌC (course) - Báo cáo trang 81
# Lưu trữ thông tin cơ bản về một khóa đào tạo trên hệ thống
# ============================================================
class Course(models.Model):
    STATUS_CHOICES = [
        ('ongoing', 'Đang triển khai'),
        ('draft', 'Bản nháp'),
        ('completed', 'Đã kết thúc'),
    ]

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_courses',
        verbose_name='Người tạo (Trainer)'
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Mã khóa học',
        help_text='Ví dụ: KH-1026, KH-1027'
    )
    title = models.CharField(
        max_length=255,
        verbose_name='Tên / Tiêu đề khóa học'
    )
    description = models.TextField(
        blank=True,
        default='',
        verbose_name='Mô tả khóa học'
    )
    date_start = models.DateField(
        verbose_name='Ngày bắt đầu'
    )
    date_end = models.DateField(
        verbose_name='Ngày kết thúc'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ongoing',
        verbose_name='Trạng thái'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Ngày tạo'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Cập nhật lần cuối'
    )

    class Meta:
        db_table = 'course'
        verbose_name = 'Khóa đào tạo'
        verbose_name_plural = 'Danh sách khóa đào tạo'
        ordering = ['-date_start', '-id']

    def __str__(self):
        return f"{self.code} • {self.title}"

    @property
    def total_enrolled(self):
        if hasattr(self, 'annotated_total_enrolled'):
            return self.annotated_total_enrolled
        return self.enrollments.count()

    @property
    def total_completed(self):
        if hasattr(self, 'annotated_total_completed'):
            return self.annotated_total_completed
        return self.enrollments.filter(is_completed=True).count()


# ============================================================
# 2. BẢNG PHÂN QUYỀN TRUY CẬP (course_access) - Báo cáo trang 81
# Quản lý quyền truy cập và phân vai trò của nhân viên đối với khóa học
# ============================================================
class CourseAccess(models.Model):
    ROLE_CHOICES = [
        ('trainer', 'Trainer / Giảng viên chính'),
        ('assistant', 'Trợ giảng / Phụ trách'),
        ('manager', 'Quản lý phòng ban'),
    ]

    emp = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='course_accesses',
        verbose_name='Nhân viên / Giảng viên'
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='access_list',
        verbose_name='Khóa học'
    )
    role = models.CharField(
        max_length=50,
        choices=ROLE_CHOICES,
        default='trainer',
        verbose_name='Vai trò'
    )

    class Meta:
        db_table = 'course_access'
        verbose_name = 'Phân quyền khóa học'
        verbose_name_plural = 'Danh sách phân quyền khóa học'
        unique_together = ('emp', 'course')

    def __str__(self):
        return f"{self.emp.username} - {self.course.code} ({self.get_role_display()})"


# ============================================================
# 3. BẢNG TÀI LIỆU BÀI GIẢNG (course_material) - Báo cáo trang 82
# Lưu trữ thông tin về các học liệu, tài liệu đính kèm của khóa đào tạo
# ============================================================
class CourseMaterial(models.Model):
    TYPE_CHOICES = [
        ('pdf', 'Tài liệu PDF (PDF)'),
        ('doc', 'Văn bản Word (DOC/DOCX)'),
        ('video', 'Video bài giảng (MP4)'),
        ('slide', 'Slide thuyết trình (PPT/PPTX)'),
        ('interactive', 'Tài liệu tương tác / Khác'),
    ]

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='materials',
        verbose_name='Thuộc khóa học'
    )
    name = models.CharField(
        max_length=255,
        verbose_name='Tên tài liệu / bài học'
    )
    file = models.FileField(
        upload_to='courses/materials/',
        blank=True,
        null=True,
        verbose_name='File đính kèm'
    )
    file_type = models.CharField(
        max_length=50,
        choices=TYPE_CHOICES,
        default='pdf',
        verbose_name='Loại tài liệu'
    )
    duration_minutes = models.PositiveIntegerField(
        default=30,
        verbose_name='Thời lượng học (phút)'
    )
    is_required = models.BooleanField(
        default=True,
        verbose_name='Bắt buộc hoàn thành'
    )
    order = models.PositiveIntegerField(
        default=1,
        verbose_name='Thứ tự bài'
    )
    summary = models.TextField(
        blank=True,
        default='',
        verbose_name='Tóm tắt bài học'
    )
    key_points = models.JSONField(
        blank=True,
        default=list,
        verbose_name='Các nguyên tắc cốt lõi (JSON list)'
    )
    scenario_title = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Tiêu đề tình huống thực tế'
    )
    scenario_content = models.TextField(
        blank=True,
        default='',
        verbose_name='Nội dung tình huống thực tế'
    )
    content = models.TextField(
        blank=True,
        default='',
        verbose_name='Nội dung chuyên sâu bài học'
    )

    class Meta:
        db_table = 'course_material'
        verbose_name = 'Tài liệu bài giảng'
        verbose_name_plural = 'Danh sách tài liệu bài giảng'
        ordering = ['course', 'order', 'id']

    def __str__(self):
        return f"[{self.course.code}] Bài {self.order}: {self.name}"

    @property
    def scenario_problem(self):
        """
        [CHƯƠNG 02 - MIS3010] Trích xuất mô tả tình huống thực tế / đề bài giả định.
        Hỗ trợ tách tự động nếu giảng viên nhập 'Tình huống: ... Cách xử lý: ...'
        """
        if not self.scenario_content:
            return ""
        content = self.scenario_content
        if "Cách xử lý:" in content:
            part = content.split("Cách xử lý:")[0].strip()
            if part.startswith("Tình huống:"):
                part = part[len("Tình huống:"):].strip()
            return part
        elif "Cách xử lý chuẩn:" in content:
            part = content.split("Cách xử lý chuẩn:")[0].strip()
            if part.startswith("Tình huống:"):
                part = part[len("Tình huống:"):].strip()
            return part
        return content

    @property
    def scenario_solution(self):
        """
        [CHƯƠNG 02 - MIS3010] Trích xuất hướng dẫn / cách xử lý chuẩn Scots English.
        Dữ liệu này được giấu theo mặc định và chỉ hiển thị khi học viên bấm nút xem.
        """
        if not self.scenario_content:
            return ""
        content = self.scenario_content
        if "Cách xử lý:" in content:
            return content.split("Cách xử lý:")[1].strip()
        elif "Cách xử lý chuẩn:" in content:
            return content.split("Cách xử lý chuẩn:")[1].strip()
        return ""


# ============================================================
# 4. BẢNG CẤU HÌNH BÀI THI (course_exam) - Báo cáo trang 82
# Thiết lập cấu hình cho bài kiểm tra của khóa học
# ============================================================
class CourseExam(models.Model):
    course = models.OneToOneField(
        Course,
        on_delete=models.CASCADE,
        related_name='exam',
        verbose_name='Khóa học'
    )
    title = models.CharField(
        max_length=255,
        default='Bài thi trắc nghiệm đánh giá năng lực',
        verbose_name='Tiêu đề bài thi'
    )
    passcode = models.CharField(
        max_length=50,
        default='SCOTS2026',
        verbose_name='Mã bảo mật (Passcode)',
        help_text='Mã mở đề thi dành cho nhân viên'
    )
    duration = models.PositiveIntegerField(
        default=45,
        verbose_name='Thời gian làm bài (phút)'
    )
    passing_score = models.FloatField(
        default=80.0,
        verbose_name='Điểm chuẩn để đạt (thang 100)'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Kích hoạt đợt thi'
    )

    class Meta:
        db_table = 'course_exam'
        verbose_name = 'Cấu hình bài thi'
        verbose_name_plural = 'Danh sách cấu hình bài thi'

    def __str__(self):
        return f"Bài thi: {self.course.code} - {self.course.title}"


# ============================================================
# 5. BẢNG NGÂN HÀNG CÂU HỎI (course_exam_question) - Báo cáo trang 82
# Lưu trữ ngân hàng câu hỏi thuộc một bài kiểm tra
# ============================================================
class CourseExamQuestion(models.Model):
    exam = models.ForeignKey(
        CourseExam,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name='Bài thi'
    )
    question_number = models.PositiveIntegerField(
        default=1,
        verbose_name='Câu số'
    )
    caption = models.TextField(
        verbose_name='Nội dung câu hỏi'
    )
    correct_choice = models.PositiveIntegerField(
        default=1,
        verbose_name='Đáp án đúng (1: A, 2: B, 3: C, 4: D)'
    )

    class Meta:
        db_table = 'course_exam_question'
        verbose_name = 'Câu hỏi bài thi'
        verbose_name_plural = 'Ngân hàng câu hỏi'
        ordering = ['exam', 'question_number', 'id']

    def __str__(self):
        return f"Đề [{self.exam.course.code}] - Câu {self.question_number}: {self.caption[:60]}..."


# ============================================================
# 6. BẢNG PHƯƠNG ÁN LỰA CHỌN (course_question_choice) - Báo cáo trang 82
# Lưu trữ các phương án lựa chọn (đáp án) cho từng câu hỏi
# ============================================================
class CourseQuestionChoice(models.Model):
    question = models.ForeignKey(
        CourseExamQuestion,
        on_delete=models.CASCADE,
        related_name='choices',
        verbose_name='Thuộc câu hỏi'
    )
    choice_number = models.PositiveIntegerField(
        default=1,
        verbose_name='Thứ tự đáp án (1: A, 2: B, 3: C, 4: D)'
    )
    content = models.TextField(
        verbose_name='Nội dung phương án'
    )

    class Meta:
        db_table = 'course_question_choice'
        verbose_name = 'Phương án lựa chọn'
        verbose_name_plural = 'Các phương án trả lời'
        ordering = ['question', 'choice_number']

    def __str__(self):
        label = {1: 'A', 2: 'B', 3: 'C', 4: 'D', 5: 'E'}.get(self.choice_number, str(self.choice_number))
        return f"({label}) {self.content[:50]}"


# ============================================================
# 7. BẢNG GHI DANH HỌC VIÊN (course_enrollment) - Báo cáo trang 82
# Lưu trữ danh sách học viên và tiến độ học tập chung của họ
# ============================================================
class CourseEnrollment(models.Model):
    emp = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='course_enrollments',
        verbose_name='Học viên (Nhân sự)'
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='enrollments',
        verbose_name='Khóa học tham gia'
    )
    enrollment_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Ngày phân công / ghi danh'
    )
    study_process = models.PositiveIntegerField(
        default=0,
        verbose_name='Tiến độ học tập (%)',
        help_text='Từ 0% đến 100%'
    )
    exam = models.ForeignKey(
        CourseExam,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='enrollments',
        verbose_name='Bài kiểm tra cuối khóa'
    )
    is_pass = models.BooleanField(
        default=False,
        verbose_name='Đã đỗ bài thi'
    )
    is_completed = models.BooleanField(
        default=False,
        verbose_name='Đã hoàn thành khóa học'
    )
    is_assigned = models.BooleanField(
        default=True,
        verbose_name='Do Trainer phân công (Bắt buộc)',
        help_text='True: Khóa học bắt buộc do Trainer phân công; False: Khóa học tự chọn do học viên tự đăng ký'
    )

    class Meta:
        db_table = 'course_enrollment'
        verbose_name = 'Ghi danh khóa học'
        verbose_name_plural = 'Danh sách học viên tham gia'
        unique_together = ('emp', 'course')

    def __str__(self):
        return f"{self.emp.username} -> {self.course.code} (Tiến độ: {self.study_process}%)"


# ============================================================
# 8. BẢNG LƯỢT LÀM BÀI THI (course_exam_response) - Báo cáo trang 83
# Lưu thông tin về lượt làm bài thi của nhân viên
# ============================================================
class CourseExamResponse(models.Model):
    emp = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='exam_responses',
        verbose_name='Nhân viên dự thi'
    )
    exam = models.ForeignKey(
        CourseExam,
        on_delete=models.CASCADE,
        related_name='responses',
        verbose_name='Bài thi'
    )
    passcode = models.CharField(
        max_length=50,
        verbose_name='Mã passcode đã nhập'
    )
    duration = models.PositiveIntegerField(
        default=0,
        verbose_name='Thời gian làm bài thực tế (phút)'
    )
    submission_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Thời điểm nộp bài'
    )
    score = models.FloatField(
        default=0.0,
        verbose_name='Điểm số đạt được'
    )
    is_passed = models.BooleanField(
        default=False,
        verbose_name='Kết quả (Đạt / Không đạt)'
    )

    class Meta:
        db_table = 'course_exam_response'
        verbose_name = 'Lượt nộp bài thi'
        verbose_name_plural = 'Lịch sử làm bài thi'
        ordering = ['-submission_date']

    def __str__(self):
        return f"{self.emp.username} - {self.exam.course.code}: {self.score} điểm ({'ĐẠT' if self.is_passed else 'TRƯỢT'})"


# ============================================================
# 9. BẢNG CHI TIẾT CÂU TRẢ LỜI (course_exam_response_detail) - Báo cáo trang 83
# Lưu chi tiết từng câu trả lời của nhân viên cho các câu hỏi trong đề thi
# ============================================================
class CourseExamResponseDetail(models.Model):
    response = models.ForeignKey(
        CourseExamResponse,
        on_delete=models.CASCADE,
        related_name='details',
        verbose_name='Lượt thi'
    )
    question = models.ForeignKey(
        CourseExamQuestion,
        on_delete=models.CASCADE,
        related_name='responses',
        verbose_name='Câu hỏi'
    )
    answer = models.PositiveIntegerField(
        verbose_name='Đáp án học viên chọn (1, 2, 3, 4)'
    )
    is_correct = models.BooleanField(
        default=False,
        verbose_name='Đúng / Sai'
    )

    class Meta:
        db_table = 'course_exam_response_detail'
        verbose_name = 'Chi tiết câu trả lời'
        verbose_name_plural = 'Chi tiết câu trả lời bài thi'
        unique_together = ('response', 'question')

    def __str__(self):
        return f"Lượt {self.response.id} - Câu {self.question.question_number}: {'Đúng' if self.is_correct else 'Sai'}"
