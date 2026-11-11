from django import forms
from .models import *


class Create(forms.ModelForm):
    # Field chọn nhiều Chi nhánh
    branches = forms.ModelMultipleChoiceField(
        queryset=Branch.objects.all(),  # Thay 'Branch' bằng tên model Chi nhánh thực tế của bạn
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'doc-form-input doc-select-multiple',
            'data-placeholder': 'Chọn chi nhánh...',
        })
    )
    # Field chọn nhiều Phòng ban
    departments = forms.ModelMultipleChoiceField(
        queryset=Department.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'doc-form-input doc-select-multiple',
            'data-placeholder': 'Chọn phòng ban...',
        })
    )
    # field nhận bộ câu hỏi
    questions_data = forms.CharField(
        widget=forms.HiddenInput(attrs={'required': False}),
        required=False
    )
    class Meta:
        model = Survey
        fields = ['name','description','response_limit','response_deadline','anonymous']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'doc-form-input',
                'placeholder': 'VD: Khảo sát mức độ hài lòng về môi trường làm việc...',
                'required': True,
                'autocomplete': 'off',  # tắt gợi ý
                'maxlength': '100',
            }),
            'description': forms.Textarea(attrs={
                'class':'doc-form-textarea',
                'placeholder':'Mô tả mục đích của khảo sát này...',
                'autocomplete': 'off',
            }),
            'response_deadline': forms.DateTimeInput(attrs={
                'class': 'doc-form-input',
                'type': 'datetime-local',
                'required': False,
            }),
            'response_limit': forms.NumberInput(attrs={
                'class': 'doc-form-input',
                'type': 'number',
                'min': '1',
                'required': False,
            }),
            'anonymous': forms.CheckboxInput(attrs={
                'class':'checkbox',
                'required': False,
            })
        }

    def clean_response_limit(self):
        limit = self.cleaned_data.get('response_limit')

        # Nếu người dùng nhập giá trị và giá trị đó <= 0
        if limit is not None and limit <= 0:
            raise forms.ValidationError("Giới hạn lượt trả lời phải lớn hơn 0.")

        return limit