/**
 * ScotsMate - Survey Published Script
 * Quản lý Pop-up danh sách đối tượng khảo sát và trạng thái nộp / chưa nộp.
 */

document.addEventListener('DOMContentLoaded', function () {
  const modal = document.getElementById('modal-survey-targets');
  if (!modal) return;

  const modalSubtitle = document.getElementById('modal-target-subtitle');
  const searchInput = document.getElementById('modal-target-search');
  const modalBody = document.getElementById('modal-target-body');
  const btnRemind = document.getElementById('btn-remind-participants');
  const closeButtons = modal.querySelectorAll('[data-close-modal]');

  // Đảm bảo modal luôn ẩn khi mới vào trang
  modal.style.display = 'none';
  modal.classList.remove('active');

  function openModal() {
    modal.style.display = 'flex';
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
    if (searchInput) {
      searchInput.value = '';
      setTimeout(() => searchInput.focus(), 100);
    }
  }

  function closeModal() {
    modal.classList.remove('active');
    modal.style.display = 'none';
    document.body.style.overflow = '';
  }

  closeButtons.forEach(btn => {
    btn.addEventListener('click', closeModal);
  });

  modal.addEventListener('click', function (e) {
    if (e.target === modal) {
      closeModal();
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && modal.classList.contains('active')) {
      closeModal();
    }
  });

  // Xử lý khi nhấn nút "Xem danh sách" ở mỗi hàng khảo sát
  document.querySelectorAll('.btn-open-target-modal').forEach(btn => {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      const surveyId = this.getAttribute('data-survey-id');
      const surveyName = this.getAttribute('data-survey-name') || '';
      const isAnonymous = this.getAttribute('data-is-anonymous') === '1';

      if (modalSubtitle) {
        modalSubtitle.textContent = 'Khảo sát: ' + surveyName;
      }

      // Đọc dữ liệu JSON của bài khảo sát tương ứng
      const dataScript = document.getElementById('participants-data-' + surveyId);
      let participants = [];
      if (dataScript) {
        try {
          participants = JSON.parse(dataScript.textContent);
        } catch (err) {
          participants = [];
        }
      }

      // Xóa nội dung cũ và render danh sách mới
      modalBody.innerHTML = '';

      if (!participants || participants.length === 0) {
        const emptyDiv = document.createElement('div');
        emptyDiv.className = 'survey-modal-empty';
        emptyDiv.style.display = 'block';
        emptyDiv.textContent = 'Chưa có đối tượng nào được gán quyền tham gia khảo sát này.';
        modalBody.appendChild(emptyDiv);
      } else {
        participants.forEach(p => {
          const row = document.createElement('div');
          row.className = 'survey-user-row';
          row.setAttribute('data-search', `${p.full_name} ${p.email} ${p.department_name}`);

          let statusHtml = '';
          // Nếu không ẩn danh thì hiển thị trạng thái Đã nộp / Chưa nộp
          if (!isAnonymous) {
            if (p.has_submitted) {
              statusHtml = `<span class="doc-badge doc-badge-approved" style="font-size: 12px; padding: 4px 10px; margin-left: 12px; flex-shrink: 0;">Đã nộp</span>`;
            } else {
              statusHtml = `<span class="doc-badge doc-badge-draft" style="font-size: 12px; padding: 4px 10px; margin-left: 12px; flex-shrink: 0; color: #e11d48; background: #fff1f2; border: 1px solid #ffe4e6;">Chưa nộp</span>`;
            }
          }

          row.innerHTML = `
            <div class="survey-user-avatar">${p.initials || 'NV'}</div>
            <div class="survey-user-info">
              <div class="survey-user-name">${p.full_name}</div>
              <div class="survey-user-dep">${p.department_name}</div>
            </div>
            <div class="survey-user-email">${p.email}</div>
            ${statusHtml}
          `;

          modalBody.appendChild(row);
        });

        // Thẻ thông báo khi tìm kiếm không có kết quả
        const notFoundDiv = document.createElement('div');
        notFoundDiv.className = 'survey-modal-empty modal-search-not-found';
        notFoundDiv.style.display = 'none';
        notFoundDiv.textContent = 'Không tìm thấy đối tượng nào phù hợp với từ khóa.';
        modalBody.appendChild(notFoundDiv);
      }

      openModal();
    });
  });

  // Tìm kiếm theo thời gian thực trong Modal
  if (searchInput) {
    searchInput.addEventListener('input', function () {
      const term = this.value.trim().toLowerCase();
      const rows = modalBody.querySelectorAll('.survey-user-row');
      const notFoundDiv = modalBody.querySelector('.modal-search-not-found');
      let matchCount = 0;

      rows.forEach(row => {
        const searchData = (row.getAttribute('data-search') || '').toLowerCase();
        if (!term || searchData.includes(term)) {
          row.style.display = 'flex';
          matchCount++;
        } else {
          row.style.display = 'none';
        }
      });

      if (notFoundDiv) {
        notFoundDiv.style.display = (rows.length > 0 && matchCount === 0) ? 'block' : 'none';
      }
    });
  }

  // Nút nhắc nhở điền khảo sát
  if (btnRemind) {
    btnRemind.addEventListener('click', function () {
      window.alert('Tính năng gửi thông báo nhắc nhở đến người chưa nộp sẽ sớm được hoàn thiện.');
    });
  }
});
