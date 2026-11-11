"""
Django Forms & ModelForms cho Phân hệ Đào tạo (Module courses)
Dự án: ScotsMate LMS - Scots English Australia
Tuân thủ chuẩn học thuật MIS3010 - Chương 04 (Làm việc với Form) & Chương 06 (Quản lý tập tin)
"""

from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from .models import Course, CourseMaterial, CourseExam


class CourseForm(forms.ModelForm):
    """
    ModelForm tạo mới Khóa học (Chương 04 - LO4)
    Bao gồm kiểm tra tính hợp lệ và làm sạch dữ liệu tùy chỉnh bằng clean_<field>() và clean()
    """
    class Meta:
        model = Course
        fields = ['code', 'title', 'description', 'date_start', 'date_end', 'status']
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'w-full px-3.5 py-2.5 rounded-lg border border-slate-200 text-sm uppercase focus:outline-none focus:border-[#134c81]',
            }),
            'title': forms.TextInput(attrs={
                'class': 'w-full px-3.5 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-[#134c81]',
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-3.5 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-[#134c81] resize-y',
                'rows': 4,
            }),
            'date_start': forms.DateInput(attrs={
                'class': 'w-full px-3.5 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-[#134c81]',
                'type': 'date'
            }),
            'date_end': forms.DateInput(attrs={
                'class': 'w-full px-3.5 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-[#134c81]',
                'type': 'date'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full px-3.5 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-[#134c81] bg-white'
            }),
        }

    def clean_code(self):
        """Làm sạch và kiểm tra mã khóa học: Viết hoa, không khoảng trắng thừa, đảm bảo tính duy nhất"""
        code = self.cleaned_data.get('code', '').strip().upper()
        if not code:
            raise ValidationError('Mã khóa học không được để trống.')
        qs = Course.objects.filter(code=code)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(f'Mã khóa học "{code}" đã tồn tại trong hệ thống. Vui lòng chọn mã khác.')
        return code

    def clean(self):
        """Kiểm tra logic đa trường (Chương 04): Ngày kết thúc phải diễn ra sau hoặc bằng ngày bắt đầu"""
        cleaned_data = super().clean()
        date_start = cleaned_data.get('date_start')
        date_end = cleaned_data.get('date_end')

        if date_start and date_end and date_end < date_start:
            self.add_error('date_end', 'Ngày kết thúc khóa học phải diễn ra sau hoặc bằng ngày bắt đầu.')
        return cleaned_data


class CourseUpdateForm(forms.ModelForm):
    """
    ModelForm cập nhật thông tin khóa học hiện có (Chương 04)
    Cho phép điều chỉnh tên, mô tả, ngày triển khai và trạng thái
    """
    class Meta:
        model = Course
        fields = ['title', 'description', 'date_start', 'date_end', 'status']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-[#134c81]',
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-[#134c81] resize-y',
                'rows': 3,
            }),
            'date_start': forms.DateInput(attrs={
                'class': 'w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-[#134c81]',
                'type': 'date'
            }),
            'date_end': forms.DateInput(attrs={
                'class': 'w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-[#134c81]',
                'type': 'date'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-[#134c81] bg-white'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        date_start = cleaned_data.get('date_start')
        date_end = cleaned_data.get('date_end')
        if date_start and date_end and date_end < date_start:
            self.add_error('date_end', 'Ngày kết thúc khóa học phải diễn ra sau hoặc bằng ngày bắt đầu.')
        return cleaned_data


class CourseMaterialForm(forms.ModelForm):
    """
    ModelForm quản lý học liệu và bài giảng (PDF, Video MP4, Slide, Word)
    Áp dụng Chương 04 & Chương 06 (Quản lý tập tin với FileField và request.FILES)
    """
    class Meta:
        model = CourseMaterial
        fields = [
            'name', 'file_type', 'file', 'duration_minutes', 
            'is_required', 'content', 'summary', 
            'scenario_title', 'scenario_content'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3.5 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-[#134c81]',
            }),
            'file_type': forms.Select(attrs={
                'class': 'w-full px-3.5 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-[#134c81] bg-white'
            }),
            'duration_minutes': forms.NumberInput(attrs={
                'class': 'w-full px-3.5 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-[#134c81]',
                'min': 1, 'max': 300
            }),
            'content': forms.Textarea(attrs={
                'class': 'w-full px-3.5 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-[#134c81] resize-y',
                'rows': 5,
            }),
            'scenario_title': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 rounded-lg border border-slate-200 text-xs focus:outline-none focus:border-[#134c81]',
            }),
            'scenario_content': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 rounded-lg border border-slate-200 text-xs focus:outline-none focus:border-[#134c81] resize-y',
                'rows': 3,
            }),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise ValidationError('Tên bài giảng / tài liệu không được để trống.')
        return name

    def clean_duration_minutes(self):
        duration = self.cleaned_data.get('duration_minutes')
        if duration is not None and duration <= 0:
            raise ValidationError('Thời lượng học dự kiến phải lớn hơn 0 phút.')
        return duration or 30

    def clean_file(self):
        """Kiểm tra phần mở rộng tệp tin an toàn khi tải lên máy chủ web (Chương 06)"""
        uploaded_file = self.cleaned_data.get('file')
        if uploaded_file:
            allowed_extensions = ['.pdf', '.mp4', '.pptx', '.ppt', '.doc', '.docx', '.png', '.jpg', '.jpeg']
            file_name = uploaded_file.name.lower()
            if not any(file_name.endswith(ext) for ext in allowed_extensions):
                raise ValidationError(
                    f'Định dạng tệp không được hỗ trợ. Vui lòng tải lên các định dạng: {", ".join(allowed_extensions)}'
                )
        return uploaded_file

    def clean(self):
        """Kiểm tra sự tương thích giữa loại bài học đã chọn và phần mở rộng của file đính kèm"""
        cleaned_data = super().clean()
        file_type = cleaned_data.get('file_type')
        uploaded_file = cleaned_data.get('file')

        if uploaded_file and file_type:
            file_name = uploaded_file.name.lower()
            ext_map = {
                'pdf': (['.pdf'], 'Tài liệu PDF (.pdf)'),
                'doc': (['.doc', '.docx'], 'Văn bản Word (.doc, .docx)'),
                'video': (['.mp4', '.m4v', '.webm', '.mov'], 'Video bài giảng MP4 (.mp4)'),
                'slide': (['.ppt', '.pptx'], 'Slide thuyết trình (.ppt, .pptx)'),
                'interactive': (['.pdf', '.doc', '.docx', '.ppt', '.pptx', '.mp4', '.zip', '.html', '.htm', '.png', '.jpg', '.jpeg'], 'Tài liệu tương tác / Khác'),
            }
            if file_type in ext_map:
                allowed_exts, label = ext_map[file_type]
                if not any(file_name.endswith(ext) for ext in allowed_exts):
                    self.add_error(
                        'file',
                        f'Tệp tải lên không khớp với định dạng đã chọn ({label}). Vui lòng tải đúng tệp (đuôi {", ".join(allowed_exts)}) hoặc đổi định dạng bài học.'
                    )
        return cleaned_data


class CourseExamConfigForm(forms.ModelForm):
    """
    ModelForm cấu hình quy chuẩn bài thi trắc nghiệm (Chương 04)
    """
    class Meta:
        model = CourseExam
        fields = ['title', 'passcode', 'duration', 'passing_score', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-[#134c81]',
            }),
            'passcode': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2.5 rounded-lg border border-slate-200 text-sm uppercase focus:outline-none focus:border-[#134c81]',
            }),
            'duration': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-[#134c81]',
                'min': 5, 'max': 180
            }),
            'passing_score': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-[#134c81]',
                'min': 1, 'max': 100
            }),
        }

    def clean_passcode(self):
        passcode = self.cleaned_data.get('passcode', '').strip().upper()
        if not passcode:
            raise ValidationError('Passcode bài thi không được để trống.')
        return passcode

    def clean_duration(self):
        duration = self.cleaned_data.get('duration')
        if duration is not None and (duration < 5 or duration > 180):
            raise ValidationError('Thời gian làm bài phải từ 5 đến 180 phút.')
        return duration or 45

    def clean_passing_score(self):
        score = self.cleaned_data.get('passing_score')
        if score is not None and (score < 1 or score > 100):
            raise ValidationError('Điểm đạt yêu cầu phải nằm trong khoảng từ 1 đến 100 điểm.')
        return score or 80.0


class UserRegisterForm(forms.ModelForm):
    """
    ModelForm đăng ký tài khoản nhân viên (Chuẩn Chương 07 - Built-in Auth)
    Mặc định tạo tài khoản Học viên (is_staff=False)
    """
    fullname = forms.CharField(
        label='Họ và tên đầy đủ',
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full pl-10 pr-3.5 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-800 focus:outline-none focus:border-[#134c81] focus:ring-2 focus:ring-[#134c81]/15 transition',
        })
    )
    password = forms.CharField(
        label='Mật khẩu',
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'w-full pl-10 pr-3 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-800 focus:outline-none focus:border-[#134c81] focus:ring-2 focus:ring-[#134c81]/15 transition',
        })
    )
    password_confirm = forms.CharField(
        label='Xác nhận mật khẩu',
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'w-full pl-10 pr-3 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-800 focus:outline-none focus:border-[#134c81] focus:ring-2 focus:ring-[#134c81]/15 transition',
        })
    )

    class Meta:
        model = User
        fields = ['username', 'email']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'w-full pl-10 pr-3 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-800 focus:outline-none focus:border-[#134c81] focus:ring-2 focus:ring-[#134c81]/15 transition',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full pl-10 pr-3 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-800 focus:outline-none focus:border-[#134c81] focus:ring-2 focus:ring-[#134c81]/15 transition',
            }),
        }

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip().lower()
        if not username:
            raise ValidationError('Vui lòng nhập tên đăng nhập.')
        if User.objects.filter(username=username).exists():
            raise ValidationError(f'Tên đăng nhập "{username}" đã tồn tại. Vui lòng chọn tên khác.')
        return username

    def clean(self):
        cleaned_data = super().clean()
        pwd = cleaned_data.get('password')
        cpwd = cleaned_data.get('password_confirm')
        if pwd:
            if len(pwd) < 6:
                self.add_error('password', 'Mật khẩu phải có ít nhất 6 ký tự.')
            if cpwd and pwd != cpwd:
                self.add_error('password_confirm', 'Mật khẩu xác nhận không khớp. Vui lòng kiểm tra lại.')
        return cleaned_data

    def save(self, commit=True):
        """Tạo người dùng với mật khẩu băm chuẩn PBKDF2/SHA256 (Chương 07)"""
        user = super().save(commit=False)
        fullname = self.cleaned_data.get('fullname', '').strip()
        parts = fullname.split(' ', 1)
        user.first_name = parts[0] if len(parts) > 0 else user.username
        user.last_name = parts[1] if len(parts) > 1 else ''
        user.set_password(self.cleaned_data['password'])
        user.is_staff = False  # Học viên mặc định (Role-based access control)
        if commit:
            user.save()
        return user


class UserLoginForm(forms.Form):
    """
    Form xác thực đăng nhập người dùng (Chương 04 & Chương 07)
    """
    username = forms.CharField(
        label='Tên đăng nhập',
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full pl-10 pr-3.5 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-800 focus:outline-none focus:border-[#134c81] focus:ring-2 focus:ring-[#134c81]/15 transition',
        })
    )
    password = forms.CharField(
        label='Mật khẩu',
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'w-full pl-10 pr-10 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-800 focus:outline-none focus:border-[#134c81] focus:ring-2 focus:ring-[#134c81]/15 transition',
        })
    )
