from django import forms
from .models import Document, DocumentCategory


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(d, initial) for d in data]
        return [single_file_clean(data, initial)]


class DocumentCreateForm(forms.ModelForm):
    file = MultipleFileField(
        label="Tệp văn bản đính kèm",
        required=True,
        widget=MultipleFileInput(attrs={
            'id': 'doc-file-input',
            'accept': '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx',
            'multiple': True,
            'style': 'display: none;',
        })
    )

    class Meta:
        model = Document
        fields = ['title', 'category', 'description', 'file']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'doc-form-input',
                'id': 'doc-title',
                'placeholder': 'Nhập tên tiêu đề đầy đủ của tài liệu...',
            }),
            'category': forms.Select(attrs={
                'class': 'doc-form-select',
                'id': 'doc-cat',
            }),
            'description': forms.Textarea(attrs={
                'class': 'doc-form-textarea',
                'id': 'doc-desc',
                'placeholder': 'Tóm tắt mục đích áp dụng và các điểm chính trong tài liệu này...',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tự động tạo 6 danh mục mặc định nếu bảng DocumentCategory đang trống
        if not DocumentCategory.objects.exists():
            default_cats = [
                ('workflow', 'Quy trình làm việc', 'grid'),
                ('training', 'Đào tạo & Giảng dạy', 'graduation-cap'),
                ('hr', 'Nhân sự & Hành chính', 'users'),
                ('student-care', 'Chăm sóc học viên', 'message'),
                ('marketing', 'Marketing & Tuyển sinh', 'megaphone'),
                ('tech', 'Công nghệ & Hệ thống', 'monitor'),
            ]
            for order, (code, name, icon) in enumerate(default_cats, start=1):
                DocumentCategory.objects.get_or_create(
                    code=code,
                    defaults={
                        'name': name,
                        'description': f'Tài liệu thuộc danh mục {name}',
                        'icon_name': icon,
                        'display_order': order,
                    }
                )
        self.fields['category'].queryset = DocumentCategory.objects.all()
        self.fields['category'].empty_label = "-- Chọn danh mục --"

    def clean_file(self):
        files = self.cleaned_data.get('file')
        if not files:
            raise forms.ValidationError("Vui lòng đính kèm ít nhất một tập tin tài liệu.")

        max_files = 5
        max_size = 20 * 1024 * 1024  # 20 MB

        if len(files) > max_files:
            raise forms.ValidationError(
                f"Số lượng tập tin đính kèm tối đa là {max_files} (bạn đang chọn {len(files)} tập tin)."
            )

        for f in files:
            if f.size > max_size:
                size_mb = f.size / (1024 * 1024)
                raise forms.ValidationError(
                    f"Tập tin '{f.name}' ({size_mb:.2f} MB) vượt quá giới hạn tối đa 20 MB."
                )
        return files