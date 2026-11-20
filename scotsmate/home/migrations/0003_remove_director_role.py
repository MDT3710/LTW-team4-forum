from django.db import migrations


def remove_director_role(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')
    Department = apps.get_model('home', 'Department')

    director_group = Group.objects.filter(name='Giám đốc').first()
    emp_group, _ = Group.objects.get_or_create(name='Nhân viên')
    mgr_group, _ = Group.objects.get_or_create(name='Trưởng phòng')

    if director_group:
        for user in User.objects.filter(groups=director_group):
            user.groups.remove(director_group)
            if not user.is_superuser:
                user.groups.add(emp_group)
                if Department.objects.filter(manager_id=user.id).exists():
                    user.groups.add(mgr_group)
        director_group.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0002_seed_role_groups'),
    ]

    operations = [
        migrations.RunPython(remove_director_role, migrations.RunPython.noop),
    ]
