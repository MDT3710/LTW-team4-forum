/**
 * survey_taker.js
 * Quản lý tương tác, cập nhật tiến độ và cảnh báo lỗi tại chỗ (Inline Validation)
 * cho người dùng khi tham gia làm bài khảo sát (SurveyTake).
 */

document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('survey-take-form');
  if (!form) return;

  // Nếu đang ở chế độ xem lại (View mode), không kích hoạt các bộ lắng nghe sự kiện làm bài
  const isViewMode = form.dataset.isViewMode === '1';
  if (isViewMode) return;

  const cards = document.querySelectorAll('.survey-question-card');
  const progressText = document.getElementById('progress-text');
  const progressPercentLabel = document.getElementById('progress-percent-label');
  const progressFillBar = document.getElementById('progress-fill-bar');
  const totalQuestions = cards.length;

  /**
   * Hiển thị thông báo lỗi tại chỗ dưới câu hỏi
   * @param {string|number} qid - ID câu hỏi (SurveyDetail id)
   * @param {string} message - Nội dung cảnh báo
   */
  function showQuestionError(qid, message) {
    const errBox = document.getElementById('error-' + qid);
    if (errBox) {
      const textElem = errBox.querySelector('.error-text');
      if (textElem) textElem.textContent = message;
      errBox.style.display = 'flex';
    }
  }

  /**
   * Ẩn thông báo lỗi tại chỗ
   * @param {string|number} qid - ID câu hỏi
   */
  function hideQuestionError(qid) {
    const errBox = document.getElementById('error-' + qid);
    if (errBox) {
      errBox.style.display = 'none';
    }
  }

  /**
   * Kiểm tra xem câu hỏi đã có phản hồi hợp lệ hay chưa
   * @param {HTMLElement} card - Khung câu hỏi
   * @returns {boolean}
   */
  function isCardAnswered(card) {
    const type = card.dataset.type;
    if (type === 'mc') {
      return card.querySelectorAll('input:checked').length > 0;
    } else if (type === 'essay') {
      const textarea = card.querySelector('textarea');
      return Boolean(textarea && textarea.value.trim().length > 0);
    }
    return false;
  }

  /**
   * Cập nhật thanh tiến độ hoàn thành theo thời gian thực
   */
  function updateProgress() {
    if (totalQuestions === 0) return;
    let answered = 0;
    cards.forEach((card) => {
      if (isCardAnswered(card)) answered++;
    });

    const percent = Math.round((answered / totalQuestions) * 100);

    if (progressText) {
      progressText.textContent = `Tiến độ hoàn thành: ${answered} / ${totalQuestions} câu hỏi`;
    }
    if (progressPercentLabel) {
      progressPercentLabel.textContent = `${percent}%`;
    }
    if (progressFillBar) {
      progressFillBar.style.width = `${percent}%`;
    }
  }

  // Gắn sự kiện lắng nghe tương tác cho từng câu hỏi
  cards.forEach((card) => {
    const qid = card.dataset.qid;
    const type = card.dataset.type;
    const maxChoice = parseInt(card.dataset.maxChoice, 10) || 1;
    const maxChar = parseInt(card.dataset.maxChar, 10) || 0;

    if (type === 'mc') {
      // 1. Trắc nghiệm đơn (Radio)
      const radios = card.querySelectorAll('input[type="radio"]');
      radios.forEach((radio) => {
        radio.addEventListener('change', function () {
          hideQuestionError(qid);
          updateProgress();
        });
      });

      // 2. Trắc nghiệm nhiều lựa chọn (Checkbox)
      const checkboxes = card.querySelectorAll('input[type="checkbox"]');
      checkboxes.forEach((cb) => {
        cb.addEventListener('change', function () {
          const checkedCount = card.querySelectorAll('input[type="checkbox"]:checked').length;
          if (maxChoice > 1 && checkedCount > maxChoice) {
            this.checked = false;
            showQuestionError(qid, `Bạn chỉ được chọn tối đa ${maxChoice} phương án.`);
            setTimeout(() => {
              const currentChecked = card.querySelectorAll('input[type="checkbox"]:checked').length;
              if (currentChecked <= maxChoice) {
                hideQuestionError(qid);
              }
            }, 3000);
          } else {
            hideQuestionError(qid);
          }
          updateProgress();
        });
      });
    } else if (type === 'essay') {
      // 3. Tự luận (Textarea)
      const textarea = card.querySelector('textarea');
      const countSpan = document.getElementById('char-count-' + qid);

      if (textarea) {
        textarea.addEventListener('input', function () {
          const len = this.value.length;
          if (countSpan) {
            countSpan.textContent = len;
          }

          if (maxChar > 0 && len > maxChar) {
            showQuestionError(qid, `Nội dung vượt quá giới hạn ${maxChar} ký tự.`);
          } else if (this.value.trim().length > 0) {
            hideQuestionError(qid);
          }
          updateProgress();
        });
      }
    }
  });

  // 4. Validate toàn bộ câu hỏi khi bấm nút "Gửi bài khảo sát"
  const btnSubmit = document.getElementById('btn-submit-survey');
  if (btnSubmit) {
    btnSubmit.addEventListener('click', function (e) {
      let firstInvalidCard = null;
      let hasError = false;

      cards.forEach((card) => {
        const qid = card.dataset.qid;
        const isRequired = card.dataset.required === '1';
        const type = card.dataset.type;
        const maxChoice = parseInt(card.dataset.maxChoice, 10) || 1;
        const maxChar = parseInt(card.dataset.maxChar, 10) || 0;

        let cardError = null;

        if (type === 'mc') {
          const checkedCount = card.querySelectorAll('input:checked').length;
          if (isRequired && checkedCount === 0) {
            cardError = 'Vui lòng chọn câu trả lời cho câu hỏi bắt buộc này.';
          } else if (maxChoice > 1 && checkedCount > maxChoice) {
            cardError = `Bạn chỉ được chọn tối đa ${maxChoice} phương án.`;
          }
        } else if (type === 'essay') {
          const textarea = card.querySelector('textarea');
          const textVal = textarea ? textarea.value.trim() : '';
          if (isRequired && textVal.length === 0) {
            cardError = 'Vui lòng nhập nội dung cho câu hỏi bắt buộc này.';
          } else if (maxChar > 0 && textVal.length > maxChar) {
            cardError = `Nội dung không được vượt quá ${maxChar} ký tự.`;
          }
        }

        if (cardError) {
          hasError = true;
          showQuestionError(qid, cardError);
          if (!firstInvalidCard) {
            firstInvalidCard = card;
          }
        } else {
          hideQuestionError(qid);
        }
      });

      // Nếu có lỗi, chặn submit và cuộn mượt đến câu hỏi lỗi đầu tiên
      if (hasError && firstInvalidCard) {
        e.preventDefault();
        firstInvalidCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
        firstInvalidCard.style.outline = '2px solid #e11d48';
        firstInvalidCard.style.borderRadius = '8px';
        setTimeout(() => {
          firstInvalidCard.style.outline = 'none';
        }, 2500);
      }
    });
  }
});
