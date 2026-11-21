from datetime import timedelta
from django import forms
from django.utils import timezone
from .models import Event


class EventForm(forms.ModelForm):
    """Form chuẩn hóa tạo và chỉnh sửa sự kiện nội bộ."""

    class Meta:
        model = Event
        fields = [
            'title',
            'category',
            'description',
            'agenda',
            'date_start',
            'date_end',
            'location',
            'branch',
            'department',
            'max_participants',
            'status',
        ]

    def __init__(self, *args, is_edit=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_edit = is_edit
        self.fields['agenda'].required = False
        self.fields['branch'].required = False
        self.fields['department'].required = False
        self.fields['status'].required = False

    def clean_title(self):
        title = (self.cleaned_data.get('title') or '').strip()
        if not title:
            raise forms.ValidationError('Vui lòng nhập tên sự kiện.')
        return title

    def clean_location(self):
        location = (self.cleaned_data.get('location') or '').strip()
        if not location:
            raise forms.ValidationError('Vui lòng nhập địa điểm tổ chức.')
        return location

    def clean_description(self):
        description = (self.cleaned_data.get('description') or '').strip()
        if not description:
            raise forms.ValidationError('Vui lòng nhập mô tả sự kiện.')
        return description

    def clean_max_participants(self):
        val = self.cleaned_data.get('max_participants')
        if val is None or val < 1 or val > 1000:
            raise forms.ValidationError('Số lượng người tham gia tối đa phải từ 1 đến 1000.')
        if self.is_edit and self.instance and self.instance.pk:
            current_reg = self.instance.total_registered
            if val < current_reg:
                raise forms.ValidationError(
                    f'Số lượng tối đa ({val}) không được nhỏ hơn số nhân sự đã đăng ký ({current_reg}).'
                )
        return val

    def clean(self):
        cleaned = super().clean()
        date_start = cleaned.get('date_start')
        date_end = cleaned.get('date_end')

        if date_start and date_end and date_end <= date_start:
            self.add_error('date_end', 'Thời gian kết thúc phải diễn ra sau thời gian bắt đầu.')

        if not self.is_edit and date_start:
            if date_start < timezone.now() - timedelta(minutes=1):
                self.add_error('date_start', 'Thời gian bắt đầu sự kiện mới không được nằm trong quá khứ.')

        if not self.is_edit:
            cleaned['status'] = Event.STATUS_UPCOMING
        elif not cleaned.get('status'):
            cleaned['status'] = self.instance.status if self.instance else Event.STATUS_UPCOMING

        return cleaned
