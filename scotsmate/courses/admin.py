from django.contrib import admin
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

# Inline: Tài liệu trong Khóa học
class CourseMaterialInline(admin.TabularInline):
    model = CourseMaterial
    extra = 1

# Inline: Phân quyền trong Khóa học
class CourseAccessInline(admin.TabularInline):
    model = CourseAccess
    extra = 1

# Inline: Phương án trắc nghiệm trong Câu hỏi
class CourseQuestionChoiceInline(admin.TabularInline):
    model = CourseQuestionChoice
    extra = 4

# Inline: Câu hỏi trong Bài thi
class CourseExamQuestionInline(admin.StackedInline):
    model = CourseExamQuestion
    extra = 1

# Inline: Chi tiết câu trả lời trong Lượt thi
class CourseExamResponseDetailInline(admin.TabularInline):
    model = CourseExamResponseDetail
    extra = 0
    readonly_fields = ('question', 'answer', 'is_correct')


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'creator', 'date_start', 'date_end', 'status', 'total_enrolled', 'total_completed')
    list_filter = ('status', 'date_start', 'date_end')
    search_fields = ('code', 'title', 'description', 'creator__username', 'creator__first_name', 'creator__last_name')
    inlines = [CourseMaterialInline, CourseAccessInline]


@admin.register(CourseAccess)
class CourseAccessAdmin(admin.ModelAdmin):
    list_display = ('emp', 'course', 'role')
    list_filter = ('role', 'course')
    search_fields = ('emp__username', 'course__code', 'course__title')


@admin.register(CourseMaterial)
class CourseMaterialAdmin(admin.ModelAdmin):
    list_display = ('name', 'course', 'file_type', 'duration_minutes', 'is_required', 'order')
    list_filter = ('file_type', 'is_required', 'course')
    search_fields = ('name', 'course__code', 'course__title')


@admin.register(CourseExam)
class CourseExamAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'passcode', 'duration', 'passing_score', 'is_active')
    list_filter = ('is_active', 'duration')
    search_fields = ('title', 'course__code', 'course__title', 'passcode')
    inlines = [CourseExamQuestionInline]


@admin.register(CourseExamQuestion)
class CourseExamQuestionAdmin(admin.ModelAdmin):
    list_display = ('exam', 'question_number', 'caption', 'correct_choice')
    list_filter = ('exam',)
    search_fields = ('caption', 'exam__title')
    inlines = [CourseQuestionChoiceInline]


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ('emp', 'course', 'enrollment_date', 'study_process', 'is_pass', 'is_completed')
    list_filter = ('is_pass', 'is_completed', 'course')
    search_fields = ('emp__username', 'course__code', 'course__title')


@admin.register(CourseExamResponse)
class CourseExamResponseAdmin(admin.ModelAdmin):
    list_display = ('emp', 'exam', 'score', 'is_passed', 'duration', 'submission_date')
    list_filter = ('is_passed', 'submission_date')
    search_fields = ('emp__username', 'exam__course__code')
    inlines = [CourseExamResponseDetailInline]
