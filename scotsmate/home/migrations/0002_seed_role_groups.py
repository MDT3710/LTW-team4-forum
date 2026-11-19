from datetime import date
from django.db import migrations


ROLE_NAMES = ('Admin', 'Giám đốc', 'Trưởng phòng', 'Trainer', 'Nhân viên')


def seed_role_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')
    Department = apps.get_model('home', 'Department')
    EmployeeInformation = apps.get_model('home', 'EmployeeInformation')

    groups = {name: Group.objects.get_or_create(name=name)[0] for name in ROLE_NAMES}
    manager_ids = set(
        Department.objects.exclude(manager_id__isnull=True).values_list('manager_id', flat=True)
    )

    for user in User.objects.all():
        if user.groups.filter(name__in=ROLE_NAMES).exists():
            continue

        emp_info = EmployeeInformation.objects.filter(emp_id_id=user.id).select_related('dep').first()
        dep = emp_info.dep if emp_info else None

        if user.is_superuser or (dep and dep.name == 'Phát triển & vận hành ứng dụng'):
            user.groups.add(groups['Admin'])
            continue

        if user.username == 'vuthimai' or (dep and dep.block == 'DIRECTOR'):
            user.groups.add(groups['Giám đốc'])
            continue

        user.groups.add(groups['Nhân viên'])
        if user.id in manager_ids:
            user.groups.add(groups['Trưởng phòng'])
        if user.username in ('minhanh', 'lethuha'):
            user.groups.add(groups['Trainer'])

    # Sửa lỗi năm sinh mẫu nếu có (1002 -> 2002)
    EmployeeInformation.objects.filter(
        emp_id__username='dangquanghuy',
        date_of_birth=date(1002, 4, 12),
    ).update(date_of_birth=date(2002, 4, 12))


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_role_groups, migrations.RunPython.noop),
    ]
