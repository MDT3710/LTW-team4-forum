from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Branch, Department, EmployeeInformation


class EmployeeInformationInline(admin.StackedInline):
    model = EmployeeInformation
    can_delete = False
    verbose_name_plural = 'Thông tin nhân viên'


class ScotsmateUserAdmin(BaseUserAdmin):
    inlines = (EmployeeInformationInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'get_department', 'get_roles')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'groups')

    @admin.display(description='Phòng ban')
    def get_department(self, obj):
        emp = getattr(obj, 'employee_info', None)
        return emp.dep.name if emp and emp.dep else '-'

    @admin.display(description='Vai trò')
    def get_roles(self, obj):
        return ', '.join(obj.groups.values_list('name', flat=True)) or '-'


admin.site.unregister(User)
admin.site.register(User, ScotsmateUserAdmin)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'region', 'address')
    list_filter = ('region',)
    search_fields = ('name', 'address')


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'block', 'manager')
    list_filter = ('block',)
    search_fields = ('name',)


@admin.register(EmployeeInformation)
class EmployeeInformationAdmin(admin.ModelAdmin):
    list_display = ('emp_id', 'dep', 'branch', 'gender', 'tel', 'status')
    list_filter = ('status', 'dep', 'branch')
    search_fields = ('emp_id__username', 'emp_id__first_name', 'emp_id__last_name', 'NIN', 'tel')
