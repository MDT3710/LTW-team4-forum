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

#form tải tl lên
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

#form tạo danh mục
class DocumentCategoryForm(forms.ModelForm):
    class Meta:
        model = DocumentCategory
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'doc-form-input',
                'id': 'cat-name',
                'placeholder': 'Nhập tên danh mục',
                'required': True,
            }),
            'description': forms.Textarea(attrs={
                'class': 'doc-form-textarea',
                'id': 'cat-desc',
                'rows': 5,
                'placeholder': 'Nhập mô tả về nội dung và mục đích của danh mục...',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cho phép phần mô tả có thể bỏ trống (không có dấu * đỏ trên giao diện)
        self.fields['description'].required = False

# form chỉnh sửa tài liệu
class DocumentEditForm(forms.ModelForm):
    file = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'id': 'edit-file',
            'style': 'position: absolute; top:0; left:0; width:100%; height:100%; opacity:0; cursor:pointer;',
            'onchange': 'updateFileName(this)',
        })
    )

    class Meta:
        model = Document
        fields = ['title', 'category', 'file']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'doc-form-input',
                'id': 'edit-title',
                'required': True,
            }),
            'category': forms.Select(attrs={
                'class': 'doc-form-select',
                'id': 'edit-cat',
                'required': True,
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = DocumentCategory.objects.all()
        self.fields['category'].empty_label = None