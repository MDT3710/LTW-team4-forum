"""
REST API Endpoints cho Module courses
Chuẩn học thuật MIS3010 - Chương 05 (Xây dựng REST API)
Sử dụng decorator @api_view và lớp Response theo đúng hướng dẫn giáo trình & slide.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Course, CourseMaterial, CourseExam
from .serializers import CourseSerializer, CourseMaterialSerializer, CourseExamSerializer


@api_view(['GET'])
@permission_classes([AllowAny])
def api_courses_list(request):
    """
    API danh sách khóa học (Chương 05 - LO1 & LO2)
    Hỗ trợ lọc theo trạng thái (?status=ongoing / draft / completed)
    """
    status_filter = request.GET.get('status')
    courses = Course.objects.select_related('creator', 'exam').prefetch_related('materials')
    if status_filter:
        courses = courses.filter(status=status_filter)
    serializer = CourseSerializer(courses, many=True)
    return Response({
        'total': courses.count(),
        'courses': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_course_detail(request, course_id):
    """
    API chi tiết một khóa học (Chương 05 - LO2)
    """
    course = get_object_or_404(
        Course.objects.select_related('creator', 'exam').prefetch_related('materials'),
        id=course_id
    )
    serializer = CourseSerializer(course)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_course_materials(request, course_id):
    """
    API danh sách học liệu của khóa học (Chương 05)
    """
    course = get_object_or_404(Course, id=course_id)
    materials = course.materials.all().order_by('order')
    serializer = CourseMaterialSerializer(materials, many=True)
    return Response({
        'course_code': course.code,
        'course_title': course.title,
        'total_materials': materials.count(),
        'materials': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_course_exam(request, course_id):
    """
    API thông tin cấu hình bài thi của khóa học
    """
    course = get_object_or_404(Course, id=course_id)
    try:
        exam = course.exam
        serializer = CourseExamSerializer(exam)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except CourseExam.DoesNotExist:
        return Response(
            {'message': 'Khóa học này chưa được cấu hình bài thi.'},
            status=status.HTTP_404_NOT_FOUND
        )
