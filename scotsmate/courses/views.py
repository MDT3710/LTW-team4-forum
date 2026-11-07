from django.shortcuts import render
from django.http import HttpResponse

def trainer_courses(request, *args, **kwargs):
    return HttpResponse("Trainer Courses")

def trainer_course_detail(request, *args, **kwargs):
    return HttpResponse("Trainer Course Detail")

def trainer_course_dashboard(request, *args, **kwargs):
    return HttpResponse("Trainer Course Dashboard")

def trainer_course_materials(request, *args, **kwargs):
    return HttpResponse("Trainer Course Materials")

def trainer_course_exam_setup(request, *args, **kwargs):
    return HttpResponse("Trainer Course Exam Setup")

def trainer_courses_dashboard(request, *args, **kwargs):
    return HttpResponse("Trainer Courses Dashboard")

def trainer_courses_create_info(request, *args, **kwargs):
    return HttpResponse("Trainer Courses Create Info")

def trainer_courses_create_assign(request, *args, **kwargs):
    return HttpResponse("Trainer Courses Create Assign")

def trainer_courses_create_review(request, *args, **kwargs):
    return HttpResponse("Trainer Courses Create Review")

def trainee_courses(request, *args, **kwargs):
    return HttpResponse("Trainee Courses")

def trainee_course_detail(request, *args, **kwargs):
    return HttpResponse("Trainee Course Detail")

def trainee_course_material(request, *args, **kwargs):
    return HttpResponse("Trainee Course Material")

def trainee_course_exam(request, *args, **kwargs):
    return HttpResponse("Trainee Course Exam")

def trainee_course_exam_result(request, *args, **kwargs):
    return HttpResponse("Trainee Course Exam Result")
