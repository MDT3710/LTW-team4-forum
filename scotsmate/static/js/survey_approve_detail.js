/**
 * ScotsMate - Survey Approval Detail Script
 * Quản lý tương tác Pop-up danh sách người tham gia / người quản lý và tìm kiếm thời gian thực.
 */

document.addEventListener('DOMContentLoaded', function () {
  // Modal Triggers
  const btnOpenParticipants = document.getElementById('btn-open-participants');
  const btnOpenManagers = document.getElementById('btn-open-managers');
  const modalParticipants = document.getElementById('modal-participants');
  const modalManagers = document.getElementById('modal-managers');
  const closeButtons = document.querySelectorAll('[data-close-modal]');
  const overlays = document.querySelectorAll('.survey-modal-overlay');

  // Đảm bảo tất cả modal luôn ẩn khi mới vào trang
  overlays.forEach(overlay => {
    overlay.style.display = 'none';
    overlay.classList.remove('active');
  });

  function openModal(modal) {
    if (!modal) return;
    modal.style.display = 'flex';
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
    const input = modal.querySelector('.survey-modal-search-input');
    if (input) {
      input.value = '';
      input.dispatchEvent(new Event('input'));
      setTimeout(() => input.focus(), 100);
    }
  }

  function closeModal(modal) {
    if (!modal) return;
    modal.classList.remove('active');
    modal.style.display = 'none';
    // Nếu không còn modal nào active thì khôi phục scroll
    if (!document.querySelector('.survey-modal-overlay.active')) {
      document.body.style.overflow = '';
    }
  }

  if (btnOpenParticipants && modalParticipants) {
    btnOpenParticipants.addEventListener('click', function (e) {
      e.preventDefault();
      openModal(modalParticipants);
    });
  }

  if (btnOpenManagers && modalManagers) {
    btnOpenManagers.addEventListener('click', function (e) {
      e.preventDefault();
      openModal(modalManagers);
    });
  }

  closeButtons.forEach(btn => {
    btn.addEventListener('click', function () {
      const modal = this.closest('.survey-modal-overlay');
      closeModal(modal);
    });
  });

  overlays.forEach(overlay => {
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) {
        closeModal(overlay);
      }
    });
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      const activeModal = document.querySelector('.survey-modal-overlay.active');
      if (activeModal) {
        closeModal(activeModal);
      }
    }
  });

  // Tìm kiếm thời gian thực trong Modal
  const searchInputs = document.querySelectorAll('.survey-modal-search-input');
  searchInputs.forEach(input => {
    input.addEventListener('input', function () {
      const modal = this.closest('.survey-modal-card');
      if (!modal) return;
      const term = this.value.trim().toLowerCase();
      const rows = modal.querySelectorAll('.survey-user-row');
      const emptyMsg = modal.querySelector('.survey-modal-empty');
      let visibleCount = 0;

      rows.forEach(row => {
        const searchData = (row.getAttribute('data-search') || '').toLowerCase();
        if (!term || searchData.includes(term)) {
          row.style.display = 'flex';
          visibleCount++;
        } else {
          row.style.display = 'none';
        }
      });

      if (emptyMsg) {
        emptyMsg.style.display = visibleCount === 0 ? 'block' : 'none';
      }
    });
  });

  // Xác nhận khi từ chối và xóa khảo sát
  const btnReject = document.getElementById('btn-reject-survey');
  if (btnReject) {
    btnReject.addEventListener('click', function (e) {
      const confirmed = window.confirm(
        'Bạn có chắc chắn muốn TỪ CHỐI và XÓA vĩnh viễn bài khảo sát này không?\nThao tác này không thể hoàn tác!'
      );
      if (!confirmed) {
        e.preventDefault();
      }
    });
  }
});
