from django.urls import path
from . import views
from . import api_views

urlpatterns = [
    # Mặc định /courses/ -> Tự động xác minh danh tính & điều hướng phân quyền thực tế
    path('', views.courses_home, name='courses_home'),
    path('login/', views.login_view, name='courses_login'),
    path('register/', views.register_view, name='courses_register'),
    path('logout/', views.logout_view, name='courses_logout'),

    # ----------------- REST API (CHƯƠNG 05 - MIS3010) -----------------
    path('api/courses/', api_views.api_courses_list, name='api_courses_list'),
    path('api/courses/<int:course_id>/', api_views.api_course_detail, name='api_course_detail'),
    path('api/courses/<int:course_id>/materials/', api_views.api_course_materials, name='api_course_materials'),
    path('api/courses/<int:course_id>/exam/', api_views.api_course_exam, name='api_course_exam'),

    
    # ----------------- TRAINER ROUTES (Figma 479:xxx) -----------------
    path('trainer/courses/', views.trainer_courses, name='trainer_courses'),
    path('trainer/courses/<int:course_id>/', views.trainer_course_detail, name='trainer_course_detail'),
    path('trainer/courses/<int:course_id>/assign/', views.trainer_course_assign, name='trainer_course_assign'),
    path('trainer/courses/<int:course_id>/dashboard/', views.trainer_course_dashboard, name='trainer_course_dashboard'),
    path('trainer/courses/<int:course_id>/materials/', views.trainer_course_materials, name='trainer_course_materials'),
    path('trainer/courses/<int:course_id>/exam/setup/', views.trainer_course_exam_setup, name='trainer_course_exam_setup'),
    path('trainer/courses/dashboard/', views.trainer_courses_dashboard, name='trainer_courses_dashboard'),
    path('trainer/courses/create/info/', views.trainer_courses_create_info, name='trainer_courses_create_info'),
    path('trainer/courses/create/assign/', views.trainer_courses_create_assign, name='trainer_courses_create_assign'),
    path('trainer/courses/create/review/', views.trainer_courses_create_review, name='trainer_courses_create_review'),
    path('trainer/courses/<int:course_id>/delete/', views.trainer_course_delete, name='trainer_course_delete'),
    path('trainer/courses/<int:course_id>/publish/', views.trainer_course_publish, name='trainer_course_publish'),

    # ----------------- TRAINEE ROUTES (Figma 249:xxx) -----------------
    path('trainee/courses/', views.trainee_courses, name='trainee_courses'),
    path('trainee/courses/<int:course_id>/', views.trainee_course_detail, name='trainee_course_detail'),
    path('trainee/courses/<int:course_id>/self-enroll/', views.trainee_course_self_enroll, name='trainee_course_self_enroll'),
    path('trainee/course/<int:course_id>/<int:materials_id>/', views.trainee_course_material, name='trainee_course_material'),
    path('trainee/course/<int:course_id>/exam/', views.trainee_course_exam, name='trainee_course_exam'),
    path('trainee/course/<int:course_id>/exam/result/', views.trainee_course_exam_result, name='trainee_course_exam_result'),
]
