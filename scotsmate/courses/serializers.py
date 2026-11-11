"""
Django REST Framework Serializers cho Module courses
Chuẩn học thuật MIS3010 - Chương 05 (Xây dựng REST API)
Tuân thủ LO2: Tuần tự hóa dữ liệu sử dụng ModelSerializer
"""

from rest_framework import serializers
from .models import Course, CourseMaterial, CourseExam, CourseExamQuestion, CourseQuestionChoice


class CourseQuestionChoiceSerializer(serializers.ModelSerializer):
    """Tuần tự hóa các phương án trắc nghiệm"""
    class Meta:
        model = CourseQuestionChoice
        fields = ['id', 'choice_number', 'content']


class CourseExamQuestionSerializer(serializers.ModelSerializer):
    """Tuần tự hóa câu hỏi bài thi kèm các lựa chọn (Nested Serializer)"""
    choices = CourseQuestionChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = CourseExamQuestion
        fields = ['id', 'question_number', 'caption', 'choices']


class CourseExamSerializer(serializers.ModelSerializer):
    """Tuần tự hóa bài thi và quy chuẩn kiểm tra"""
    questions_count = serializers.IntegerField(source='questions.count', read_only=True)

    class Meta:
        model = CourseExam
        fields = ['id', 'title', 'duration', 'passing_score', 'is_active', 'questions_count']


class CourseMaterialSerializer(serializers.ModelSerializer):
    """Tuần tự hóa học liệu và bài giảng đa phương tiện"""
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = CourseMaterial
        fields = [
            'id', 'name', 'file_type', 'duration_minutes', 
            'is_required', 'order', 'file_url', 'summary'
        ]

    def get_file_url(self, obj):
        if obj.file:
            return obj.file.url
        return None


class CourseSerializer(serializers.ModelSerializer):
    """Tuần tự hóa danh sách và chi tiết khóa học"""
    materials = CourseMaterialSerializer(many=True, read_only=True)
    exam = CourseExamSerializer(read_only=True)
    creator_name = serializers.CharField(source='creator.get_full_name', read_only=True)

    class Meta:
        model = Course
        fields = [
            'id', 'code', 'title', 'description', 'status', 
            'date_start', 'date_end', 'total_enrolled', 'total_completed',
            'creator_name', 'materials', 'exam'
        ]
