from django import forms
from home.models import Department
from .models import Document, DocumentCategory

ALLOWED_DOC_EXTENSIONS = ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx')
MAX_DOC_FILE_BYTES = 20 * 1024 * 1024  # 20 MB


def _validate_uploaded_doc_file(f):
    """Kiểm tra định dạng và dung lượng tối đa 20 MB cho tập tin tài liệu."""
    name_lower = (f.name or '').lower()
    if not any(name_lower.endswith(ext) for ext in ALLOWED_DOC_EXTENSIONS):
        raise forms.ValidationError(
            f"Tập tin '{f.name}' không đúng định dạng hỗ trợ ({', '.join(ALLOWED_DOC_EXTENSIONS)})."
        )
    if f.size > MAX_DOC_FILE_BYTES:
        size_mb = f.size / (1024 * 1024)
        raise forms.ValidationError(
            f"Tập tin '{f.name}' ({size_mb:.2f} MB) vượt quá giới hạn tối đa 20 MB."
        )


def _clean_description_max_300(raw):
    desc = (raw or '').strip()
    if len(desc) > 300:
        raise forms.ValidationError(f"Mô tả tóm tắt tối đa 300 ký tự (hiện tại {len(desc)} ký tự).")
    return desc


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


# Form tải tài liệu lên
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
    departments = forms.ModelMultipleChoiceField(
        queryset=Department.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(),
        label="Chọn phòng ban được phép truy cập"
    )

    class Meta:
        model = Document
        fields = ['title', 'category', 'access_scope', 'description', 'file']
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
            'access_scope': forms.Select(attrs={
                'class': 'doc-form-select',
                'id': 'doc-scope',
            }),
            'description': forms.Textarea(attrs={
                'class': 'doc-form-textarea',
                'id': 'doc-desc',
                'maxlength': '300',
                'rows': 3,
                'placeholder': 'Tóm tắt mục đích áp dụng và các điểm chính (tối đa 300 ký tự)...',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = DocumentCategory.objects.all()
        self.fields['category'].empty_label = "-- Chọn danh mục --"
        self.fields['access_scope'].required = False

    def clean_description(self):
        return _clean_description_max_300(self.cleaned_data.get('description'))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('access_scope') == 'DEPARTMENT' and not cleaned.get('departments'):
            self.add_error('departments', 'Vui lòng chọn ít nhất một phòng ban khi giới hạn phạm vi truy cập.')
        return cleaned

    def clean_file(self):
        files = self.cleaned_data.get('file')
        if not files:
            raise forms.ValidationError("Vui lòng đính kèm ít nhất một tập tin tài liệu.")
        if len(files) > 5:
            raise forms.ValidationError(
                f"Số lượng tập tin đính kèm tối đa là 5 (bạn đang chọn {len(files)} tập tin)."
            )
        for f in files:
            _validate_uploaded_doc_file(f)
        return files


# Form tạo danh mục
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
                'rows': 4,
                'maxlength': '300',
                'placeholder': 'Nhập mô tả về nội dung và mục đích của danh mục (tối đa 300 ký tự)...',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].required = False

    def clean_description(self):
        return _clean_description_max_300(self.cleaned_data.get('description'))


# Form chỉnh sửa tài liệu
class DocumentEditForm(forms.ModelForm):
    file = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'id': 'edit-file',
            'accept': '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx',
            'style': 'position: absolute; top:0; left:0; width:100%; height:100%; opacity:0; cursor:pointer;',
            'onchange': 'updateFileName(this)',
        })
    )
    departments = forms.ModelMultipleChoiceField(
        queryset=Department.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(),
        label="Chọn phòng ban được phép truy cập"
    )

    class Meta:
        model = Document
        fields = ['title', 'category', 'description', 'access_scope', 'file']
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
            'description': forms.Textarea(attrs={
                'class': 'doc-form-textarea',
                'id': 'edit-desc',
                'rows': 3,
                'maxlength': '300',
                'placeholder': 'Tóm tắt nội dung tài liệu (tối đa 300 ký tự)...',
            }),
            'access_scope': forms.Select(attrs={
                'class': 'doc-form-select',
                'id': 'edit-scope',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = DocumentCategory.objects.all()
        self.fields['category'].empty_label = None
        self.fields['description'].required = False
        self.fields['access_scope'].required = False
        if self.instance and self.instance.pk:
            self.fields['departments'].initial = Department.objects.filter(
                accessible_documents__document=self.instance
            )

    def clean_file(self):
        uploaded = self.files.get('file')
        if uploaded:
            _validate_uploaded_doc_file(uploaded)
        return self.cleaned_data.get('file')

    def clean_description(self):
        return _clean_description_max_300(self.cleaned_data.get('description'))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('access_scope') == 'DEPARTMENT' and not cleaned.get('departments'):
            self.add_error('departments', 'Vui lòng chọn ít nhất một phòng ban khi giới hạn phạm vi truy cập.')
        return cleaned