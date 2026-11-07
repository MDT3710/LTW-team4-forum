from django.urls import path
from . import views

urlpatterns = [
    # Mặc định /courses/ -> Trang Quản lý đào tạo (Trainer Courses - Figma 479:1593)
    path('', views.trainer_courses, name='courses_home'),
    
    # ----------------- TRAINER ROUTES (Figma 479:xxx) -----------------
    path('trainer/courses/', views.trainer_courses, name='trainer_courses'),
    path('trainer/courses/<int:course_id>/', views.trainer_course_detail, name='trainer_course_detail'),
    path('trainer/courses/<int:course_id>/dashboard/', views.trainer_course_dashboard, name='trainer_course_dashboard'),
    path('trainer/courses/<int:course_id>/materials/', views.trainer_course_materials, name='trainer_course_materials'),
    path('trainer/courses/<int:course_id>/exam/setup/', views.trainer_course_exam_setup, name='trainer_course_exam_setup'),
    path('trainer/courses/dashboard/', views.trainer_courses_dashboard, name='trainer_courses_dashboard'),
    path('trainer/courses/create/info/', views.trainer_courses_create_info, name='trainer_courses_create_info'),
    path('trainer/courses/create/assign/', views.trainer_courses_create_assign, name='trainer_courses_create_assign'),
    path('trainer/courses/create/review/', views.trainer_courses_create_review, name='trainer_courses_create_review'),

    # ----------------- TRAINEE ROUTES (Figma 249:xxx) -----------------
    path('trainee/courses/', views.trainee_courses, name='trainee_courses'),
    path('trainee/courses/<int:course_id>/', views.trainee_course_detail, name='trainee_course_detail'),
    path('trainee/course/<int:course_id>/<int:materials_id>/', views.trainee_course_material, name='trainee_course_material'),
    path('trainee/course/<int:course_id>/exam/', views.trainee_course_exam, name='trainee_course_exam'),
    path('trainee/course/<int:course_id>/exam/result/', views.trainee_course_exam_result, name='trainee_course_exam_result'),

    # ----------------- DIRECT TEMPLATE ALIASES -----------------
    path('trainer_courses.html', views.trainer_courses),
    path('trainer_courses_{id}.html', views.trainer_course_detail),
    path('trainer_courses_<int:course_id>.html', views.trainer_course_detail),
    path('trainer_courses_{id}_dashboard.html', views.trainer_course_dashboard),
    path('trainer_courses_<int:course_id>_dashboard.html', views.trainer_course_dashboard),
    path('trainer_courses_{id}_materials.html', views.trainer_course_materials),
    path('trainer_courses_<int:course_id>_materials.html', views.trainer_course_materials),
    path('trainer_courses_{id}_exam_setup.html', views.trainer_course_exam_setup),
    path('trainer_courses_<int:course_id>_exam_setup.html', views.trainer_course_exam_setup),
    path('trainer_courses_dashboard.html', views.trainer_courses_dashboard),
    path('trainer_courses_create_info.html', views.trainer_courses_create_info),
    path('trainer_courses_create_assign.html', views.trainer_courses_create_assign),
    path('trainer_courses_create_review.html', views.trainer_courses_create_review),

    path('trainee_courses.html', views.trainee_courses),
    path('trainee_courses_{id}.html', views.trainee_course_detail),
    path('trainee_courses_<int:course_id>.html', views.trainee_course_detail),
    path('trainee_course_{id}_{materials_id}.html', views.trainee_course_material),
    path('trainee_course_<int:course_id>_<int:materials_id>.html', views.trainee_course_material),
    path('trainee_course_{id}_exam.html', views.trainee_course_exam),
    path('trainee_course_<int:course_id>_exam.html', views.trainee_course_exam),
    path('trainee_course_{id}_exam_result.html', views.trainee_course_exam_result),
    path('trainee_course_<int:course_id>_exam_result.html', views.trainee_course_exam_result),
]
